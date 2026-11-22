import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pytest
from flask import Flask
import variaveis as v
from test_pulsacao import play


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setattr(v, "ARQUIVO", str(tmp_path / "dados" / "variaveis.json"))
    app = Flask(__name__)
    app.register_blueprint(v.bp)
    return app.test_client()


def eventos(script):
    return play(script)["events"]


def test_guardar_listar_e_normalizar(c):
    evs = eventos("q:c e:g n:e")
    for e in evs:
        e["t"] += 90000  # tempos "de verdade" da página
    r = c.post("/pulso/variaveis", json={"nome": "  baixo   Dó ", "eventos": evs})
    assert r.status_code == 200 and r.json["variavel"]["nome"] == "baixo Dó"
    lista = c.get("/pulso/variaveis").json["variaveis"]
    assert [x["nome"] for x in lista] == ["baixo Dó"] and lista[0]["pulsos"] == 2
    ts = [e["t"] for e in lista[0]["eventos"]]
    assert min(ts) == 0 and ts == sorted(ts)


def test_nome_repetido_pede_confirmacao(c):
    c.post("/pulso/variaveis", json={"nome": "a", "eventos": eventos("q:c")})
    r = c.post("/pulso/variaveis", json={"nome": "A", "eventos": eventos("q:d")})
    assert r.status_code == 409 and r.json["existe"]
    r = c.post("/pulso/variaveis", json={"nome": "A", "eventos": eventos("q:d"), "substituir": True})
    assert r.status_code == 200
    lista = c.get("/pulso/variaveis").json["variaveis"]
    assert len(lista) == 1 and lista[0]["nome"] == "A"


def test_validacoes(c):
    assert c.post("/pulso/variaveis", json={"nome": "", "eventos": eventos("q:c")}).status_code == 400
    assert c.post("/pulso/variaveis", json={"nome": "x/y", "eventos": eventos("q:c")}).status_code == 400
    assert c.post("/pulso/variaveis", json={"nome": "x", "eventos": []}).status_code == 400
    assert c.post("/pulso/variaveis", json={"nome": "x", "eventos": [{"type": "down", "id": 1, "midi": 60, "t": 0}]}).status_code == 400


def test_nota_segurada_ganha_soltura(c):
    evs = [{"type": "pulse", "value": 16, "t": 0}, {"type": "down", "id": 9, "midi": 60, "t": 10}]
    r = c.post("/pulso/variaveis", json={"nome": "s", "eventos": evs})
    salvos = r.json["variavel"]["eventos"]
    assert any(e["type"] == "up" and e["id"] == 1 for e in salvos)


def test_renomear_e_apagar(c):
    c.post("/pulso/variaveis", json={"nome": "a", "eventos": eventos("q:c")})
    c.post("/pulso/variaveis", json={"nome": "b", "eventos": eventos("q:d")})
    assert c.post("/pulso/variaveis/a/renomear", json={"novo": "b"}).status_code == 409
    assert c.post("/pulso/variaveis/a/renomear", json={"novo": "escala"}).status_code == 200
    assert c.delete("/pulso/variaveis/b").status_code == 200
    assert c.delete("/pulso/variaveis/b").status_code == 404
    assert [x["nome"] for x in c.get("/pulso/variaveis").json["variaveis"]] == ["escala"]


def test_substituir_mantem_posicao(c):
    for nome, sc in (("a", "q:c"), ("b", "q:d"), ("c", "q:e")):
        c.post("/pulso/variaveis", json={"nome": nome, "eventos": eventos(sc)})
    r = c.post("/pulso/variaveis", json={"nome": "b", "eventos": eventos("q:f q:g"), "substituir": True})
    assert r.json["variavel"]["pulsos"] == 2
    assert [x["nome"] for x in c.get("/pulso/variaveis").json["variaveis"]] == ["a", "b", "c"]


def test_duplicar(c):
    c.post("/pulso/variaveis", json={"nome": "baixo", "eventos": eventos("q:c q:g")})
    c.post("/pulso/variaveis", json={"nome": "fim", "eventos": eventos("q:c")})
    assert c.post("/pulso/variaveis/baixo/duplicar").json["variavel"]["nome"] == "baixo 2"
    assert c.post("/pulso/variaveis/baixo/duplicar").json["variavel"]["nome"] == "baixo 3"
    lista = c.get("/pulso/variaveis").json["variaveis"]
    assert [x["nome"] for x in lista] == ["baixo", "baixo 3", "baixo 2", "fim"]
    assert lista[1]["eventos"] == lista[0]["eventos"]
    assert c.post("/pulso/variaveis/nada/duplicar").status_code == 404
    longo = "x" * 40
    c.post("/pulso/variaveis", json={"nome": longo, "eventos": eventos("q:c")})
    assert c.post(f"/pulso/variaveis/{longo}/duplicar").json["variavel"]["nome"] == "x" * 38 + " 2"
