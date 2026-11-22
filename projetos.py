"""Projetos: um por música. Cada projeto guarda o compasso, a armadura, as
suas variáveis e o rascunho (o que está escrito e ainda não foi enviado).

O rascunho tem número de versão: quem salva diz em qual versão estava
baseado. Se outro aparelho salvou antes, a resposta é 409 com o conteúdo
novo, e a página avisa em vez de apagar o trabalho do outro em silêncio.
"""

import json
import threading

from flask import Blueprint, Response, jsonify, request

import banco
from pulsacao import DENOMINADORES
from variaveis import VariavelError, nome_valido, normalizar

bp = Blueprint("projetos", __name__)
_lock = threading.Lock()
MAX_RASCUNHO = 20000
FORMATO = "musecontrol-projeto"


def _erro(e, codigo=400):
    return jsonify(ok=False, erro=str(e)), codigo


def _resumo(con, p):
    nvars = con.execute("SELECT COUNT(*) FROM variaveis WHERE projeto_id = ?", (p["id"],)).fetchone()[0]
    return {"id": p["id"], "nome": p["nome"], "compasso": {"num": p["comp_num"], "den": p["comp_den"]},
            "armadura": p["armadura"], "atualizado": p["atualizado"], "variaveis": nvars}


def _projeto(con, pid):
    return con.execute("SELECT * FROM projetos WHERE id = ?", (pid,)).fetchone()


def _ajustes(data):
    """Confere compasso e armadura vindos da página."""
    campos = {}
    if "compasso" in data:
        num, den = int(data["compasso"]["num"]), int(data["compasso"]["den"])
        if not 1 <= num <= 16 or den not in DENOMINADORES:
            raise VariavelError("Compasso inválido")
        campos["comp_num"], campos["comp_den"] = num, den
    if "armadura" in data:
        arm = int(data["armadura"])
        if not -7 <= arm <= 7:
            raise VariavelError("Armadura inválida")
        campos["armadura"] = arm
    return campos


def _eventos_rascunho(eventos):
    """O rascunho pode estar vazio ou pela metade; só confere o formato."""
    if not isinstance(eventos, list) or len(eventos) > MAX_RASCUNHO:
        raise VariavelError("Rascunho inválido")
    for e in eventos:
        if not isinstance(e, dict) or e.get("type") not in ("pulse", "down", "up"):
            raise VariavelError("Rascunho inválido")
    return eventos


def _criar(con, nome, campos=None):
    t = banco.agora()
    pid = con.execute("INSERT INTO projetos (nome, criado, atualizado) VALUES (?, ?, ?)",
                      (nome, t, t)).lastrowid
    for coluna, valor in (campos or {}).items():
        con.execute(f"UPDATE projetos SET {coluna} = ? WHERE id = ?", (valor, pid))
    return pid


# ---- projetos ---------------------------------------------------------------

@bp.route("/pulso/projetos")
def listar():
    with banco.sessao() as con:
        linhas = con.execute("SELECT * FROM projetos ORDER BY nome COLLATE NOCASE").fetchall()
        return jsonify(ok=True, projetos=[_resumo(con, p) for p in linhas])


@bp.route("/pulso/projetos", methods=["POST"])
def criar():
    data = request.get_json(force=True) or {}
    try:
        nome = nome_valido(data.get("nome"))
        campos = _ajustes(data)
    except (VariavelError, KeyError, TypeError, ValueError) as e:
        return _erro(e)
    with _lock, banco.sessao() as con:
        if con.execute("SELECT 1 FROM projetos WHERE nome = ?", (nome,)).fetchone():
            return _erro(f'Já existe o projeto "{nome}"', 409)
        pid = _criar(con, nome, campos)
        return jsonify(ok=True, projeto=_resumo(con, _projeto(con, pid)))


@bp.route("/pulso/projetos/<int:pid>", methods=["PATCH"])
def ajustar(pid):
    """Muda compasso e/ou armadura do projeto."""
    try:
        campos = _ajustes(request.get_json(force=True) or {})
    except (VariavelError, KeyError, TypeError, ValueError) as e:
        return _erro(e)
    with _lock, banco.sessao() as con:
        if not _projeto(con, pid):
            return _erro("Projeto não encontrado", 404)
        for coluna, valor in campos.items():
            con.execute(f"UPDATE projetos SET {coluna} = ? WHERE id = ?", (valor, pid))
        con.execute("UPDATE projetos SET atualizado = ? WHERE id = ?", (banco.agora(), pid))
        return jsonify(ok=True, projeto=_resumo(con, _projeto(con, pid)))


@bp.route("/pulso/projetos/<int:pid>/renomear", methods=["POST"])
def renomear(pid):
    try:
        novo = nome_valido((request.get_json(force=True) or {}).get("novo"))
    except VariavelError as e:
        return _erro(e)
    with _lock, banco.sessao() as con:
        if not _projeto(con, pid):
            return _erro("Projeto não encontrado", 404)
        if con.execute("SELECT 1 FROM projetos WHERE nome = ? AND id != ?", (novo, pid)).fetchone():
            return _erro(f'Já existe o projeto "{novo}"', 409)
        con.execute("UPDATE projetos SET nome = ?, atualizado = ? WHERE id = ?", (novo, banco.agora(), pid))
    return jsonify(ok=True)


@bp.route("/pulso/projetos/<int:pid>", methods=["DELETE"])
def apagar(pid):
    """Apaga o projeto com as variáveis e o rascunho dele (as gerais ficam)."""
    with _lock, banco.sessao() as con:
        if not _projeto(con, pid):
            return _erro("Projeto não encontrado", 404)
        con.execute("DELETE FROM variaveis WHERE projeto_id = ?", (pid,))
        con.execute("DELETE FROM rascunhos WHERE projeto_id = ?", (pid,))
        con.execute("DELETE FROM projetos WHERE id = ?", (pid,))
        banco._garantir_projeto(con)  # nunca fica sem nenhum projeto
        restantes = con.execute("SELECT * FROM projetos ORDER BY nome COLLATE NOCASE").fetchall()
        return jsonify(ok=True, projetos=[_resumo(con, p) for p in restantes])


# ---- rascunho -----------------------------------------------------------------

@bp.route("/pulso/projetos/<int:pid>/rascunho")
def ler_rascunho(pid):
    with banco.sessao() as con:
        if not _projeto(con, pid):
            return _erro("Projeto não encontrado", 404)
        r = con.execute("SELECT * FROM rascunhos WHERE projeto_id = ?", (pid,)).fetchone()
        return jsonify(ok=True, eventos=json.loads(r["eventos"]) if r else [], versao=r["versao"] if r else 0)


@bp.route("/pulso/projetos/<int:pid>/rascunho", methods=["PUT"])
def salvar_rascunho(pid):
    data = request.get_json(force=True) or {}
    try:
        eventos = _eventos_rascunho(data.get("eventos"))
        base = int(data.get("versao", 0))
    except (VariavelError, TypeError, ValueError) as e:
        return _erro(e)
    with _lock, banco.sessao() as con:
        if not _projeto(con, pid):
            return _erro("Projeto não encontrado", 404)
        r = con.execute("SELECT * FROM rascunhos WHERE projeto_id = ?", (pid,)).fetchone()
        atual = r["versao"] if r else 0
        if base != atual:  # outro aparelho salvou depois que esta página carregou
            return jsonify(ok=False, conflito=True, eventos=json.loads(r["eventos"]) if r else [],
                           versao=atual), 409
        nova = atual + 1
        con.execute(
            "INSERT INTO rascunhos (projeto_id, eventos, versao, atualizado) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(projeto_id) DO UPDATE SET eventos = excluded.eventos, "
            "versao = excluded.versao, atualizado = excluded.atualizado",
            (pid, json.dumps(eventos), nova, banco.agora()))
        con.execute("UPDATE projetos SET atualizado = ? WHERE id = ?", (banco.agora(), pid))
        return jsonify(ok=True, versao=nova)


# ---- exportar / importar ---------------------------------------------------------

@bp.route("/pulso/projetos/<int:pid>/exportar")
def exportar(pid):
    with banco.sessao() as con:
        p = _projeto(con, pid)
        if not p:
            return _erro("Projeto não encontrado", 404)
        vs = con.execute("SELECT nome, eventos FROM variaveis WHERE projeto_id = ? ORDER BY ordem",
                         (pid,)).fetchall()
        r = con.execute("SELECT eventos FROM rascunhos WHERE projeto_id = ?", (pid,)).fetchone()
        dados = {
            "formato": FORMATO, "versao": 1, "nome": p["nome"],
            "compasso": {"num": p["comp_num"], "den": p["comp_den"]}, "armadura": p["armadura"],
            "variaveis": [{"nome": v["nome"], "eventos": json.loads(v["eventos"])} for v in vs],
            "rascunho": json.loads(r["eventos"]) if r else [],
        }
        nome_arquivo = "".join(c if c.isalnum() or c in " -_" else "_" for c in p["nome"]).strip() or "projeto"
    return Response(json.dumps(dados, ensure_ascii=False, indent=1), mimetype="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}.musecontrol.json"'})


@bp.route("/pulso/projetos/importar", methods=["POST"])
def importar():
    dados = request.get_json(force=True) or {}
    try:
        if dados.get("formato") != FORMATO:
            raise VariavelError("Este arquivo não é um projeto do MuseControl")
        nome = nome_valido(dados.get("nome"))
        campos = _ajustes(dados)
        variaveis = [(nome_valido(v["nome"]), normalizar(v["eventos"])) for v in dados.get("variaveis", [])]
        rascunho = _eventos_rascunho(dados.get("rascunho", []))
    except (VariavelError, KeyError, TypeError, ValueError) as e:
        return _erro(e)
    with _lock, banco.sessao() as con:
        pid = _criar(con, banco.nome_livre(con, "projetos", nome), campos)
        for ordem, (vnome, eventos) in enumerate(variaveis, 1):
            con.execute(
                "INSERT INTO variaveis (projeto_id, nome, eventos, ordem, criada) VALUES (?, ?, ?, ?, ?)",
                (pid, banco.nome_livre(con, "variaveis", vnome, pid), json.dumps(eventos), ordem, banco.agora()))
        if rascunho:
            con.execute("INSERT INTO rascunhos (projeto_id, eventos, versao, atualizado) VALUES (?, ?, 1, ?)",
                        (pid, json.dumps(rascunho), banco.agora()))
        return jsonify(ok=True, projeto=_resumo(con, _projeto(con, pid)))
