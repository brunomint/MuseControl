"""Variáveis (ideia do LilyPond): trechos com nome, guardados para reusar.

Uma variável é só a lista de toques (pulsos e notas) de um trecho, do mesmo
jeito que o celular grava. Como o ritmo vem da ORDEM dos toques, o trecho pode
ser colado em qualquer ponto sem mudar nada.

Cada variável pertence a um projeto ou à biblioteca geral (projeto_id = 0),
que aparece em todos os projetos. Ficam no banco (banco.py).
"""

import json
import re
import threading

from flask import Blueprint, jsonify, request

import banco
from pulsacao import PulseError, analyze

bp = Blueprint("variaveis", __name__)

NOME_OK = re.compile(r"^[\w \-]{1,40}$")  # letras (com acento), números, espaço, - e _
MAX_EVENTOS = 5000
_lock = threading.Lock()


class VariavelError(ValueError):
    pass


def nome_valido(valor):
    nome = " ".join(str(valor or "").split())
    if not NOME_OK.match(nome):
        raise VariavelError("Nome inválido: use até 40 letras, números, espaço, - ou _")
    return nome


def normalizar(eventos):
    """Confere o trecho e deixa o 1º toque no tempo 0 e ids a partir de 1."""
    if not isinstance(eventos, list) or not eventos:
        raise VariavelError("Nada escrito para guardar")
    if len(eventos) > MAX_EVENTOS:
        raise VariavelError("Trecho grande demais")
    tipos = {"pulse", "down", "up"}
    limpos, ids = [], {}
    for ev in eventos:
        if not isinstance(ev, dict) or ev.get("type") not in tipos:
            raise VariavelError("Trecho inválido")
        novo = {"type": ev["type"], "t": float(ev["t"])}
        if ev["type"] == "pulse":
            novo["value"] = int(ev["value"])
        else:
            novo["id"] = ids.setdefault(ev["id"], len(ids) + 1)
            if ev["type"] == "down":
                novo["midi"] = int(ev["midi"])
        limpos.append(novo)
    downs = {e["id"] for e in limpos if e["type"] == "down"}
    limpos = [e for e in limpos if e["type"] != "up" or e["id"] in downs]
    if not any(e["type"] == "pulse" for e in limpos):
        raise VariavelError("O trecho precisa ter pelo menos um pulso")
    # nota que ainda estava segurada: solta logo depois do último toque
    fim = max(e["t"] for e in limpos)
    soltas = {e["id"] for e in limpos if e["type"] == "up"}
    for i in sorted(downs - soltas):
        limpos.append({"type": "up", "id": i, "t": fim + 1})
    inicio = min(e["t"] for e in limpos)
    for e in limpos:
        e["t"] = round(e["t"] - inicio, 1)
    limpos.sort(key=lambda e: e["t"])
    try:
        analyze({"events": limpos})  # tem que ser um trecho que o app entende
    except (PulseError, KeyError, TypeError, ValueError) as e:
        raise VariavelError(f"Trecho inválido: {e}")
    return limpos


def resumo(linha):
    eventos = json.loads(linha["eventos"])
    return {"id": linha["id"], "nome": linha["nome"], "eventos": eventos,
            "geral": linha["projeto_id"] == banco.GERAL,
            "pulsos": sum(1 for e in eventos if e["type"] == "pulse")}


def projeto_id(con, valor):
    """projeto_id a usar: 0 (geral) ou o id de um projeto que existe."""
    if valor in (None, "", 0, "0"):
        return banco.GERAL
    pid = int(valor)
    if not con.execute("SELECT 1 FROM projetos WHERE id = ?", (pid,)).fetchone():
        raise VariavelError("Projeto não encontrado")
    return pid


def _variavel(con, vid):
    return con.execute("SELECT * FROM variaveis WHERE id = ?", (vid,)).fetchone()


def _erro(e, codigo=400):
    return jsonify(ok=False, erro=str(e)), codigo


@bp.route("/pulso/variaveis")
def listar():
    """Variáveis do projeto (?projeto=ID) primeiro, depois as gerais."""
    with banco.sessao() as con:
        try:
            pid = projeto_id(con, request.args.get("projeto"))
        except (VariavelError, ValueError):
            pid = banco.GERAL
        linhas = con.execute(
            "SELECT * FROM variaveis WHERE projeto_id IN (?, ?) "
            "ORDER BY projeto_id = 0, ordem", (pid, banco.GERAL)).fetchall()
        return jsonify(ok=True, variaveis=[resumo(l) for l in linhas])


@bp.route("/pulso/variaveis", methods=["POST"])
def guardar():
    data = request.get_json(force=True) or {}
    try:
        nome = nome_valido(data.get("nome"))
        eventos = normalizar(data.get("eventos"))
    except (VariavelError, KeyError, TypeError, ValueError) as e:
        return _erro(e)
    with _lock, banco.sessao() as con:
        try:
            pid = projeto_id(con, data.get("projeto"))
        except (VariavelError, ValueError) as e:
            return _erro(e, 404)
        existente = con.execute("SELECT * FROM variaveis WHERE projeto_id = ? AND nome = ?",
                                (pid, nome)).fetchone()
        if existente and not data.get("substituir"):
            return jsonify(ok=False, erro=f'Já existe "{existente["nome"]}"', existe=True), 409
        if existente:  # substituir: continua no mesmo lugar da lista
            con.execute("UPDATE variaveis SET nome = ?, eventos = ? WHERE id = ?",
                        (nome, json.dumps(eventos), existente["id"]))
            vid = existente["id"]
        else:
            ordem = con.execute("SELECT COALESCE(MAX(ordem), 0) + 1 FROM variaveis WHERE projeto_id = ?",
                                (pid,)).fetchone()[0]
            vid = con.execute(
                "INSERT INTO variaveis (projeto_id, nome, eventos, ordem, criada) VALUES (?, ?, ?, ?, ?)",
                (pid, nome, json.dumps(eventos), ordem, banco.agora())).lastrowid
        return jsonify(ok=True, variavel=resumo(_variavel(con, vid)))


@bp.route("/pulso/variaveis/<int:vid>/salvar", methods=["POST"])
def salvar(vid):
    """Troca o conteúdo (usado ao terminar de editar)."""
    data = request.get_json(force=True) or {}
    try:
        eventos = normalizar(data.get("eventos"))
    except (VariavelError, KeyError, TypeError, ValueError) as e:
        return _erro(e)
    with _lock, banco.sessao() as con:
        if not _variavel(con, vid):
            return _erro("Variável não encontrada", 404)
        con.execute("UPDATE variaveis SET eventos = ? WHERE id = ?", (json.dumps(eventos), vid))
        return jsonify(ok=True, variavel=resumo(_variavel(con, vid)))


@bp.route("/pulso/variaveis/<int:vid>/renomear", methods=["POST"])
def renomear(vid):
    data = request.get_json(force=True) or {}
    try:
        novo = nome_valido(data.get("novo"))
    except VariavelError as e:
        return _erro(e)
    with _lock, banco.sessao() as con:
        alvo = _variavel(con, vid)
        if not alvo:
            return _erro("Variável não encontrada", 404)
        if con.execute("SELECT 1 FROM variaveis WHERE projeto_id = ? AND nome = ? AND id != ?",
                       (alvo["projeto_id"], novo, vid)).fetchone():
            return _erro(f'Já existe "{novo}"', 409)
        con.execute("UPDATE variaveis SET nome = ? WHERE id = ?", (novo, vid))
    return jsonify(ok=True)


@bp.route("/pulso/variaveis/<int:vid>/duplicar", methods=["POST"])
def duplicar(vid):
    with _lock, banco.sessao() as con:
        alvo = _variavel(con, vid)
        if not alvo:
            return _erro("Variável não encontrada", 404)
        novo = banco.nome_livre(con, "variaveis", alvo["nome"], alvo["projeto_id"])
        # logo depois da original: no meio entre ela e a próxima
        prox = con.execute("SELECT MIN(ordem) FROM variaveis WHERE projeto_id = ? AND ordem > ?",
                           (alvo["projeto_id"], alvo["ordem"])).fetchone()[0]
        ordem = (alvo["ordem"] + prox) / 2 if prox is not None else alvo["ordem"] + 1
        nid = con.execute(
            "INSERT INTO variaveis (projeto_id, nome, eventos, ordem, criada) VALUES (?, ?, ?, ?, ?)",
            (alvo["projeto_id"], novo, alvo["eventos"], ordem, banco.agora())).lastrowid
        return jsonify(ok=True, variavel=resumo(_variavel(con, nid)))


@bp.route("/pulso/variaveis/<int:vid>", methods=["DELETE"])
def apagar(vid):
    with _lock, banco.sessao() as con:
        if not con.execute("DELETE FROM variaveis WHERE id = ?", (vid,)).rowcount:
            return _erro("Variável não encontrada", 404)
    return jsonify(ok=True)
