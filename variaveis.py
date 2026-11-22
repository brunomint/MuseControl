"""Variáveis (ideia do LilyPond): trechos com nome, guardados para reusar.

Uma variável é só a lista de toques (pulsos e notas) de um trecho, do mesmo
jeito que o celular grava. Como o ritmo vem da ORDEM dos toques, o trecho pode
ser colado em qualquer ponto sem mudar nada.

Ficam num arquivo JSON no computador, para valer em todos os aparelhos.
"""

import json
import os
import re
import threading
import time

from flask import Blueprint, jsonify, request

from pulsacao import PulseError, analyze

bp = Blueprint("variaveis", __name__)

ARQUIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "variaveis.json")
NOME_OK = re.compile(r"^[\w \-]{1,40}$")  # letras (com acento), números, espaço, - e _
MAX_EVENTOS = 5000
_lock = threading.Lock()


class VariavelError(ValueError):
    pass


def _ler():
    try:
        with open(ARQUIVO, encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, list) else []
    except (OSError, ValueError):
        return []


def _gravar(lista):
    os.makedirs(os.path.dirname(ARQUIVO), exist_ok=True)
    tmp = ARQUIVO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ARQUIVO)  # troca de uma vez: nunca fica um arquivo pela metade


def _nome(valor):
    nome = " ".join(str(valor or "").split())
    if not NOME_OK.match(nome):
        raise VariavelError("Nome inválido: use até 40 letras, números, espaço, - ou _")
    return nome


def _normalizar(eventos):
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


def _resumo(v):
    return {"nome": v["nome"], "eventos": v["eventos"],
            "pulsos": sum(1 for e in v["eventos"] if e["type"] == "pulse")}


@bp.route("/pulso/variaveis")
def listar():
    return jsonify(ok=True, variaveis=[_resumo(v) for v in _ler()])


@bp.route("/pulso/variaveis", methods=["POST"])
def guardar():
    data = request.get_json(force=True) or {}
    try:
        nome = _nome(data.get("nome"))
        eventos = _normalizar(data.get("eventos"))
    except (VariavelError, KeyError, TypeError, ValueError) as e:
        return jsonify(ok=False, erro=str(e)), 400
    with _lock:
        lista = _ler()
        existente = next((v for v in lista if v["nome"].lower() == nome.lower()), None)
        if existente and not data.get("substituir"):
            return jsonify(ok=False, erro=f'Já existe "{existente["nome"]}"', existe=True), 409
        nova = {"nome": nome, "eventos": eventos, "criada": time.strftime("%Y-%m-%d %H:%M")}
        if existente:  # substituir/editar: continua no mesmo lugar da lista
            nova["criada"] = existente.get("criada", nova["criada"])
            lista[lista.index(existente)] = nova
        else:
            lista.append(nova)
        _gravar(lista)
    return jsonify(ok=True, variavel=_resumo(nova))


@bp.route("/pulso/variaveis/<path:nome>/renomear", methods=["POST"])
def renomear(nome):
    data = request.get_json(force=True) or {}
    try:
        novo = _nome(data.get("novo"))
    except VariavelError as e:
        return jsonify(ok=False, erro=str(e)), 400
    with _lock:
        lista = _ler()
        alvo = next((v for v in lista if v["nome"] == nome), None)
        if alvo is None:
            return jsonify(ok=False, erro="Variável não encontrada"), 404
        if any(v is not alvo and v["nome"].lower() == novo.lower() for v in lista):
            return jsonify(ok=False, erro=f'Já existe "{novo}"'), 409
        alvo["nome"] = novo
        _gravar(lista)
    return jsonify(ok=True)


@bp.route("/pulso/variaveis/<path:nome>/duplicar", methods=["POST"])
def duplicar(nome):
    with _lock:
        lista = _ler()
        alvo = next((v for v in lista if v["nome"] == nome), None)
        if alvo is None:
            return jsonify(ok=False, erro="Variável não encontrada"), 404
        usados = {v["nome"].lower() for v in lista}
        n = 2
        while True:  # "baixo Dó 2", "baixo Dó 3"... (cortando o nome se passar de 40)
            sufixo = f" {n}"
            novo = alvo["nome"][:40 - len(sufixo)].rstrip() + sufixo
            if novo.lower() not in usados:
                break
            n += 1
        copia = {"nome": novo, "eventos": [dict(e) for e in alvo["eventos"]],
                 "criada": time.strftime("%Y-%m-%d %H:%M")}
        lista.insert(lista.index(alvo) + 1, copia)  # logo depois da original
        _gravar(lista)
    return jsonify(ok=True, variavel=_resumo(copia))


@bp.route("/pulso/variaveis/<path:nome>", methods=["DELETE"])
def apagar(nome):
    with _lock:
        lista = _ler()
        nova = [v for v in lista if v["nome"] != nome]
        if len(nova) == len(lista):
            return jsonify(ok=False, erro="Variável não encontrada"), 404
        _gravar(nova)
    return jsonify(ok=True)
