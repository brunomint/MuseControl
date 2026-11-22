from test_pulsacao import play


def eventos(script):
    return play(script)["events"]


def test_sempre_existe_um_projeto(c):
    lista = c.get("/pulso/projetos").json["projetos"]
    assert [p["nome"] for p in lista] == ["Primeiro projeto"]
    assert lista[0]["compasso"] == {"num": 4, "den": 4} and lista[0]["armadura"] == 0


def test_criar_ajustar_renomear(c):
    r = c.post("/pulso/projetos", json={"nome": "Valsa", "compasso": {"num": 3, "den": 4}, "armadura": -1})
    p = r.json["projeto"]
    assert p["compasso"] == {"num": 3, "den": 4} and p["armadura"] == -1
    assert c.post("/pulso/projetos", json={"nome": "valsa"}).status_code == 409
    assert c.patch(f"/pulso/projetos/{p['id']}", json={"compasso": {"num": 6, "den": 8}}).json["projeto"]["compasso"] == {"num": 6, "den": 8}
    assert c.patch(f"/pulso/projetos/{p['id']}", json={"armadura": 9}).status_code == 400
    assert c.patch(f"/pulso/projetos/{p['id']}", json={"compasso": {"num": 4, "den": 3}}).status_code == 400
    assert c.post(f"/pulso/projetos/{p['id']}/renomear", json={"novo": "Primeiro projeto"}).status_code == 409
    assert c.post(f"/pulso/projetos/{p['id']}/renomear", json={"novo": "Lição 5 - Valsa"}).status_code == 200
    assert "Lição 5 - Valsa" in [x["nome"] for x in c.get("/pulso/projetos").json["projetos"]]


def test_rascunho_com_versao(c):
    pid = c.get("/pulso/projetos").json["projetos"][0]["id"]
    assert c.get(f"/pulso/projetos/{pid}/rascunho").json == {"ok": True, "eventos": [], "versao": 0}
    evs = eventos("q:c n:d")
    r = c.put(f"/pulso/projetos/{pid}/rascunho", json={"eventos": evs, "versao": 0})
    assert r.json == {"ok": True, "versao": 1}
    # outro aparelho ainda acha que está na versão 0: conflito, recebe o conteúdo novo
    r = c.put(f"/pulso/projetos/{pid}/rascunho", json={"eventos": [], "versao": 0})
    assert r.status_code == 409 and r.json["conflito"] and r.json["versao"] == 1 and r.json["eventos"] == evs
    assert c.put(f"/pulso/projetos/{pid}/rascunho", json={"eventos": [], "versao": 1}).json["versao"] == 2
    assert c.put(f"/pulso/projetos/{pid}/rascunho", json={"eventos": [{"type": "x"}], "versao": 2}).status_code == 400


def test_apagar_leva_junto_variaveis_e_rascunho(c):
    pid = c.post("/pulso/projetos", json={"nome": "Apagar"}).json["projeto"]["id"]
    c.post("/pulso/variaveis", json={"nome": "do projeto", "eventos": eventos("q:c"), "projeto": pid})
    c.post("/pulso/variaveis", json={"nome": "geral", "eventos": eventos("q:c")})
    c.put(f"/pulso/projetos/{pid}/rascunho", json={"eventos": eventos("q:c"), "versao": 0})
    restantes = c.delete(f"/pulso/projetos/{pid}").json["projetos"]
    assert [p["nome"] for p in restantes] == ["Primeiro projeto"]
    assert [v["nome"] for v in c.get("/pulso/variaveis").json["variaveis"]] == ["geral"]
    assert c.get(f"/pulso/projetos/{pid}/rascunho").status_code == 404


def test_apagar_o_ultimo_cria_outro(c):
    pid = c.get("/pulso/projetos").json["projetos"][0]["id"]
    restantes = c.delete(f"/pulso/projetos/{pid}").json["projetos"]
    assert len(restantes) == 1 and restantes[0]["id"] != pid


def test_exportar_e_importar(c):
    pid = c.post("/pulso/projetos", json={"nome": "Valsa", "compasso": {"num": 3, "den": 4}, "armadura": 2}).json["projeto"]["id"]
    c.post("/pulso/variaveis", json={"nome": "baixo", "eventos": eventos("q:c q:g q:g"), "projeto": pid})
    c.put(f"/pulso/projetos/{pid}/rascunho", json={"eventos": eventos("q:e"), "versao": 0})
    r = c.get(f"/pulso/projetos/{pid}/exportar")
    assert "attachment" in r.headers["Content-Disposition"]
    dados = r.json
    assert dados["formato"] == "musecontrol-projeto" and dados["compasso"] == {"num": 3, "den": 4}
    novo = c.post("/pulso/projetos/importar", json=dados).json["projeto"]
    assert novo["nome"] == "Valsa 2" and novo["armadura"] == 2 and novo["variaveis"] == 1
    assert c.get(f"/pulso/projetos/{novo['id']}/rascunho").json["eventos"] == dados["rascunho"]
    assert c.post("/pulso/projetos/importar", json={"formato": "outro"}).status_code == 400
