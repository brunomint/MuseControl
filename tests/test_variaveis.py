import json, os
from test_pulsacao import play


def eventos(script):
    return play(script)["events"]


def nomes(c, projeto=None):
    url = "/pulso/variaveis" + (f"?projeto={projeto}" if projeto else "")
    return [(v["nome"], v["geral"]) for v in c.get(url).json["variaveis"]]


def projeto1(c):
    return c.get("/pulso/projetos").json["projetos"][0]["id"]


def test_guardar_geral_e_normalizar(c):
    evs = eventos("q:c e:g n:e")
    for e in evs:
        e["t"] += 90000
    r = c.post("/pulso/variaveis", json={"nome": "  baixo   Dó ", "eventos": evs})
    v = r.json["variavel"]
    assert r.status_code == 200 and v["nome"] == "baixo Dó" and v["geral"] and v["pulsos"] == 2
    ts = [e["t"] for e in v["eventos"]]
    assert min(ts) == 0 and ts == sorted(ts)


def test_do_projeto_aparecem_antes_das_gerais(c):
    pid = projeto1(c)
    c.post("/pulso/variaveis", json={"nome": "escala", "eventos": eventos("q:c")})
    c.post("/pulso/variaveis", json={"nome": "tema", "eventos": eventos("q:d"), "projeto": pid})
    assert nomes(c, pid) == [("tema", False), ("escala", True)]
    outro = c.post("/pulso/projetos", json={"nome": "Valsa"}).json["projeto"]["id"]
    assert nomes(c, outro) == [("escala", True)]  # a do outro projeto não aparece


def test_mesmo_nome_em_lugares_diferentes(c):
    pid = projeto1(c)
    assert c.post("/pulso/variaveis", json={"nome": "a", "eventos": eventos("q:c")}).status_code == 200
    assert c.post("/pulso/variaveis", json={"nome": "A", "eventos": eventos("q:c"), "projeto": pid}).status_code == 200
    r = c.post("/pulso/variaveis", json={"nome": "A", "eventos": eventos("q:d")})
    assert r.status_code == 409 and r.json["existe"]


def test_substituir_mantem_posicao(c):
    for nome, sc in (("a", "q:c"), ("b", "q:d"), ("c", "q:e")):
        c.post("/pulso/variaveis", json={"nome": nome, "eventos": eventos(sc)})
    r = c.post("/pulso/variaveis", json={"nome": "b", "eventos": eventos("q:f q:g"), "substituir": True})
    assert r.json["variavel"]["pulsos"] == 2
    assert [n for n, _ in nomes(c)] == ["a", "b", "c"]


def test_validacoes(c):
    assert c.post("/pulso/variaveis", json={"nome": "", "eventos": eventos("q:c")}).status_code == 400
    assert c.post("/pulso/variaveis", json={"nome": "x/y", "eventos": eventos("q:c")}).status_code == 400
    assert c.post("/pulso/variaveis", json={"nome": "x", "eventos": []}).status_code == 400
    assert c.post("/pulso/variaveis", json={"nome": "x", "eventos": [{"type": "down", "id": 1, "midi": 60, "t": 0}]}).status_code == 400
    assert c.post("/pulso/variaveis", json={"nome": "x", "eventos": eventos("q:c"), "projeto": 999}).status_code == 404


def test_nota_segurada_ganha_soltura(c):
    evs = [{"type": "pulse", "value": 16, "t": 0}, {"type": "down", "id": 9, "midi": 60, "t": 10}]
    salvos = c.post("/pulso/variaveis", json={"nome": "s", "eventos": evs}).json["variavel"]["eventos"]
    assert any(e["type"] == "up" and e["id"] == 1 for e in salvos)


def test_renomear_duplicar_salvar_apagar(c):
    a = c.post("/pulso/variaveis", json={"nome": "baixo", "eventos": eventos("q:c q:g")}).json["variavel"]["id"]
    c.post("/pulso/variaveis", json={"nome": "fim", "eventos": eventos("q:c")})
    assert c.post(f"/pulso/variaveis/{a}/duplicar").json["variavel"]["nome"] == "baixo 2"
    assert c.post(f"/pulso/variaveis/{a}/duplicar").json["variavel"]["nome"] == "baixo 3"
    assert [n for n, _ in nomes(c)] == ["baixo", "baixo 3", "baixo 2", "fim"]
    assert c.post(f"/pulso/variaveis/{a}/renomear", json={"novo": "fim"}).status_code == 409
    assert c.post(f"/pulso/variaveis/{a}/renomear", json={"novo": "Alberti"}).status_code == 200
    r = c.post(f"/pulso/variaveis/{a}/salvar", json={"eventos": eventos("q:c q:g q:e")})
    assert r.json["variavel"]["pulsos"] == 3 and r.json["variavel"]["nome"] == "Alberti"
    assert c.delete(f"/pulso/variaveis/{a}").status_code == 200
    assert c.delete(f"/pulso/variaveis/{a}").status_code == 404
    assert c.post("/pulso/variaveis/999/duplicar").status_code == 404


def test_migra_o_json_antigo(banco_teste):
    import banco
    os.makedirs(banco_teste / "dados", exist_ok=True)
    antigas = [{"nome": "baixo Dó", "eventos": eventos("q:c q:g"), "criada": "2026-11-22 00:30"},
               {"nome": "escala", "eventos": eventos("q:c n:d")}]
    (banco_teste / "dados" / "variaveis.json").write_text(json.dumps(antigas), encoding="utf-8")
    with banco.sessao() as con:
        linhas = con.execute("SELECT nome, projeto_id FROM variaveis ORDER BY ordem").fetchall()
        projetos = con.execute("SELECT nome FROM projetos").fetchall()
    assert [(l["nome"], l["projeto_id"]) for l in linhas] == [("baixo Dó", 0), ("escala", 0)]
    assert [p["nome"] for p in projetos] == ["Primeiro projeto"]
    assert not (banco_teste / "dados" / "variaveis.json").exists()
    assert (banco_teste / "dados" / "variaveis.json.migrado").exists()  # cópia de segurança
