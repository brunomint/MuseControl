import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pulsacao as p

VAL = {"m": 32, "q": 16, "e": 8, "s": 4}
STEP = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
LETTER = {v: k for k, v in STEP.items()}


def midi_of(tok):
    """'c' = Dó4 (60), 'f#' = Fá♯4, 'c5' = Dó5, 'bb3' = Si♭3"""
    m = STEP[tok[0]] + 12 * (int(tok[-1]) + 1 if tok[-1].isdigit() else 5)
    return m + tok[1:].count("#") - (tok[1:].rstrip("0123456789").count("b"))


def name_of(m):
    base = LETTER.get(m % 12) or LETTER[(m - 1) % 12] + "#"
    return base + ("" if m // 12 == 5 else str(m // 12 - 1))


def play(script, bpb=4, gap=500):
    """Simula a execução. Passos separados por espaço:
       q:c     pulso de semínima + Dó junto   (m=mínima q=semínima e=colcheia s=semicolcheia)
       q:c+e   pulso + acorde
       q:      pulso sozinho
       n:d     nota sozinha (divide o pulso)
       c*      sufixo * = continua segurando até 'r:c'
       r:c     solta o Dó
    """
    evs, t, nid, held = [], 0, 0, {}

    def press(spec, at):
        nonlocal nid
        for nm in filter(None, spec.split("+")):
            hold = nm.endswith("*")
            nm = nm.rstrip("*")
            nid += 1
            evs.append({"type": "down", "id": nid, "midi": midi_of(nm), "t": at})
            if hold:
                held[nm] = nid
            else:
                evs.append({"type": "up", "id": nid, "t": at + 100})

    for step in script.split():
        kind, _, rest = step.partition(":")
        if kind in VAL:
            evs.append({"type": "pulse", "value": VAL[kind], "t": t})
            press(rest, t + 20)
        elif kind == "n":
            press(rest, t)
        elif kind == "r":
            evs.append({"type": "up", "id": held.pop(rest), "t": t})
            t -= gap - 10  # soltar não gasta um passo
        t += gap
    return {"events": evs, "beatsPerBar": bpb}


def figs(items):
    out = []
    for it in items:
        name = "pausa" if it["kind"] == "rest" else "+".join(name_of(n["midi"]) for n in it["notes"])
        if it["tied"]:
            name = "~" + name
        fig = "~".join(pc["figure"] + ("." if pc["dot"] else "") for pc in it["pieces"])
        if it["tuplet"]:
            fig += "/%d" % it["tuplet"]["n"]
        out.append((name, fig))
    return out


def keys(script, **kw):
    return p.keys_text(p.to_keys(p.analyze(play(script, **kw))))


# --- contagem -------------------------------------------------------------

def test_seminimas():
    assert figs(p.analyze(play("q:c q:d q:e q:f"))) == [(x, "seminima") for x in "cdef"]


def test_colcheias():
    assert figs(p.analyze(play("q:c n:d q:e n:f"))) == [(x, "colcheia") for x in "cdef"]


def test_tercina():
    assert figs(p.analyze(play("q:c n:d n:e"))) == [(x, "colcheia/3") for x in "cde"]


def test_semicolcheias():
    assert figs(p.analyze(play("q:c n:d n:e n:f"))) == [(x, "semicolcheia") for x in "cdef"]


def test_quintina():
    assert figs(p.analyze(play("q:c n:d n:e n:f n:g"))) == [(x, "semicolcheia/5") for x in "cdefg"]


def test_tempo_nao_importa():
    rapido = figs(p.analyze(play("q:c n:d q:e", gap=200)))
    lento = figs(p.analyze(play("q:c n:d q:e", gap=4000)))
    assert rapido == lento == [("c", "colcheia"), ("d", "colcheia"), ("e", "seminima")]


# --- valor do pulso ------------------------------------------------------

def test_colcheia_e_duas_semicolcheias():
    assert figs(p.analyze(play("e:c e:d n:e"))) == [
        ("c", "colcheia"), ("d", "semicolcheia"), ("e", "semicolcheia")]


def test_minima_com_duas_notas():
    assert figs(p.analyze(play("m:c n:d"))) == [("c", "seminima"), ("d", "seminima")]


# --- segurar / soltar ----------------------------------------------------

def test_semibreve_segurando():
    assert figs(p.analyze(play("q:c* q: q: q: r:c"))) == [("c", "semibreve")]


def test_colcheia_pontuada_e_semicolcheia():
    assert figs(p.analyze(play("e:c* s: r:c s:d"))) == [("c", "colcheia."), ("d", "semicolcheia")]


def test_pulso_sem_nota_segurada_e_pausa():
    assert figs(p.analyze(play("q:c q: q:d"))) == [
        ("c", "seminima"), ("pausa", "seminima"), ("d", "seminima")]


def test_pausas_seguidas_se_juntam():
    assert figs(p.analyze(play("q:c q: q:"))) == [("c", "seminima"), ("pausa", "minima")]


def test_contratempo():
    assert figs(p.analyze(play("q: n:c"))) == [("pausa", "colcheia"), ("c", "colcheia")]


def test_ligadura_na_barra():
    assert figs(p.analyze(play("q: q: q:c* q: q: r:c"))) == [
        ("pausa", "minima"), ("c", "minima~seminima")]


def test_sincope_prolongando_nota_da_divisao():
    assert figs(p.analyze(play("q:c n:d* q: n:e r:d"))) == [
        ("c", "colcheia"), ("d", "seminima"), ("e", "colcheia")]


def test_prolongar_depois_de_tercina():
    assert figs(p.analyze(play("q:c n:d n:e* q: r:e"))) == [
        ("c", "colcheia/3"), ("d", "colcheia/3"), ("e", "colcheia/3"), ("~e", "seminima")]


# --- acordes e vozes -----------------------------------------------------

def test_acorde():
    assert figs(p.analyze(play("q:c+e+g q:d+f"))) == [("c+e+g", "seminima"), ("d+f", "seminima")]


def test_duas_vozes():
    items = p.analyze(play("q:c*+e q:f r:c"))
    assert figs(items) == [("c+e", "seminima"), ("f", "seminima")]
    assert [n["midi"] for n in items[1]["sustain"]] == [60]


# --- teclas ---------------------------------------------------------------

def test_teclas_simples():
    assert keys("q:c n:d q:f#") == "4 Dó4 Ré4 5 Fá♯4"


def test_alturas_exatas():
    assert keys("q:c4 q:d5 q:c3") == "5 Dó4 Ré5 Dó3"
    assert p.to_keys(p.analyze(play("q:c4+e4+g4")))[-1] == ["midi", 60, 64, 67]


def test_teclas_tercina():
    assert keys("q:c n:d n:e q:f") == "5 ctrl+3 Dó4 Ré4 Mi4 5 Fá4"


def test_teclas_pontuada_ligadura_pausa():
    assert keys("e:c* s: r:c s:d q:") == "4 . Dó4 3 Ré4 5 0"
    assert keys("q: q: q:c* q: q: r:c") == "6 0 Dó4 5 t"


def test_duas_vozes_nao_envia():
    import pytest
    with pytest.raises(p.PulseError):
        p.to_keys(p.analyze(play("q:c*+e q:f r:c")))


def test_rotas():
    from flask import Flask
    app = Flask(__name__, template_folder="../templates")
    app.register_blueprint(p.bp)
    c = app.test_client()
    r = c.post("/pulso/analisar", json=dict(play("q:c"), modo="midi"))
    assert r.status_code == 200 and r.json["teclas"] == "5 Dó4"
    r = c.post("/pulso/analisar", json=dict(play("q:c"), modo="teclado"))
    assert r.json["teclas"] == "5 c" and r.json["modo"] == "teclado"
    r = c.post("/pulso/analisar", json=play("q:c*+e q:f r:c"))
    assert r.status_code == 200 and "vozes" in r.json["aviso"]
    assert c.post("/pulso/analisar", json={"events": [{"type": "pulse", "value": 3, "t": 0}]}).status_code == 400


def test_legato_nao_vira_duas_vozes():
    # solta o Dó 40 ms depois de tocar o Ré: é só legato, não duas vozes
    data = {"beatsPerBar": 4, "events": [
        {"type": "pulse", "value": 16, "t": 0}, {"type": "down", "id": 1, "midi": 60, "t": 10},
        {"type": "pulse", "value": 16, "t": 500}, {"type": "down", "id": 2, "midi": 62, "t": 510},
        {"type": "up", "id": 1, "t": 550}, {"type": "up", "id": 2, "t": 700},
        {"type": "pulse", "value": 16, "t": 1000}, {"type": "down", "id": 3, "midi": 64, "t": 1010},
        {"type": "up", "id": 3, "t": 1100}]}
    items = p.analyze(data)
    assert figs(items) == [(x, "seminima") for x in "cde"]
    assert not any("sustain" in it for it in items)


def test_envio_mistura_teclas_e_midi_na_ordem(monkeypatch):
    import types
    log = []
    fake_gui = types.SimpleNamespace(press=lambda k: log.append(("tecla", k)),
                                     hotkey=lambda *k: log.append(("tecla", "+".join(k))))
    monkeypatch.setitem(sys.modules, "pyautogui", fake_gui)
    fake_midi = types.SimpleNamespace(send_message=lambda m: log.append(("midi", m[0], m[1])))
    monkeypatch.setattr(p, "_midi_out", fake_midi)
    monkeypatch.setattr(p.time, "sleep", lambda s: None)
    p._type_keys(p.to_keys(p.analyze(play("q:c n:d q:c+e"))), 0.01)
    assert log == [
        ("tecla", "4"), ("midi", 0x90, 60), ("midi", 0x80, 60),
        ("midi", 0x90, 62), ("midi", 0x80, 62),
        ("tecla", "5"), ("midi", 0x90, 60), ("midi", 0x90, 64), ("midi", 0x80, 60), ("midi", 0x80, 64),
    ]


# --- modo teclado (sem MIDI) ------------------------------------------------

def tkeys(script, armadura=0):
    return p.keys_text(p.to_keys(p.analyze(play(script)), "teclado", armadura))


def test_teclado_oitavas_calculadas():
    # Dó4 -> Ré5 (a letra cairia em Ré4: +1 oitava) -> Dó3 (cairia em Dó5: -2)
    assert tkeys("q:c4 q:d5 q:c3") == "5 c d ctrl+up c ctrl+down ctrl+down"


def test_teclado_salto_de_quarta_e_quinta():
    assert tkeys("q:c4 q:f4 q:b4") == "5 c f b"          # 4ª e 4ª aum. acima: sem correção
    assert tkeys("q:c4 q:f4 q:c5") == "5 c f c ctrl+up"  # Fá->Dó acima é 5ª: a letra cai embaixo
    assert tkeys("q:c4 q:g4") == "5 c g ctrl+up"         # 5ª acima: a letra cai em Sol3


def test_teclado_acidentes_e_armadura():
    assert tkeys("q:f#4") == "5 f up"                    # Dó maior
    assert tkeys("q:f#4", armadura=2) == "5 f"           # Ré maior: Fá já é sustenido
    assert tkeys("q:f4", armadura=2) == "5 f down"       # Fá natural em Ré maior
    assert tkeys("q:bb4", armadura=-1) == "5 b"          # Fá maior: Si já é bemol
    assert tkeys("q:a#4", armadura=-1) == "5 b"          # Lá♯ = Si♭ em Fá maior


def test_teclado_acordes():
    assert tkeys("q:c4+e4+g4 q:a4") == "5 c shift+e shift+g a"
    assert tkeys("q:c4+c5") == "5 c shift+c"
    assert tkeys("q:c4+e5") == "5 c shift+e ctrl+up"


def test_teclado_pausa_e_ligadura_nao_mudam_referencia():
    assert tkeys("q:c5 q: q:d5* q: r:d5") == "5 c 0 6 d"  # Ré5 medido a partir do Dó5


def test_deteccao_midi(tmp_path, monkeypatch):
    f = tmp_path / "clients"
    f.write_text("""Client info
  cur  clients : 5
Client  14 : "Midi Through" [Kernel Legacy]
  Port   0 : "Midi Through Port-0" (RWe-) [In/Out]
    Connecting To: 128:0, 131:0
Client 128 : "Chrome (input)" [User Legacy]
Client 131 : "MuseScore" [User Legacy]
  Port   0 : "MuseScore Input Port" (-we-) [Out]
    Connected From: 14:0
""")
    monkeypatch.setattr(p, "SEQ_CLIENTS", str(f))
    assert p.musescore_listening() is True
    f.write_text(f.read_text().replace("131:0", "999:0"))
    assert p.musescore_listening() is False
    monkeypatch.setattr(p, "SEQ_CLIENTS", str(tmp_path / "nao-existe"))
    assert p.musescore_listening() is None


def test_corrigir_oitava_do_trecho():
    assert p.keys_text(p.octave_fix_keys(-1, 3, True)) == "escape shift+left shift+left ctrl+down"
    assert p.keys_text(p.octave_fix_keys(1, 3, False)) == "ctrl+up"


def test_envio_informa_elementos(monkeypatch):
    from flask import Flask
    monkeypatch.setattr(p, "_type_keys", lambda keys, interval: None)
    app = Flask(__name__, template_folder="../templates")
    app.register_blueprint(p.bp)
    # pausa de mínima + Dó + Ré mínima cortada na barra (2 figuras) + pausa = 5
    r = app.test_client().post("/pulso/enviar", json=dict(play("q: q: q:c q:d* q: r:d q:"), modo="teclado"))
    assert r.json["ok"] and r.json["modo"] == "teclado"
    assert r.json["elementos"] == 5


def test_comandos_ferramentas(monkeypatch):
    from flask import Flask
    enviados = []
    monkeypatch.setattr(p, "_type_keys", lambda keys, interval: enviados.append(keys))
    app = Flask(__name__, template_folder="../templates")
    app.register_blueprint(p.bp)
    c = app.test_client()
    assert c.post("/pulso/comando/desfazer").json["teclas"] == "ctrl+z"
    assert c.post("/pulso/comando/alt+f4").status_code == 404  # nada fora da lista
    assert enviados == [[["ctrl", "z"]]]


def test_ping():
    from flask import Flask
    app = Flask(__name__, template_folder="../templates")
    app.register_blueprint(p.bp)
    assert app.test_client().get("/pulso/ping").json == {"ok": True}


# --- compassos ------------------------------------------------------------

def comp(script, num, den):
    data = play(script)
    del data["beatsPerBar"]
    data["compasso"] = {"num": num, "den": den}
    return figs(p.analyze(data))


def test_tamanho_do_compasso():
    assert p.bar_length({"compasso": {"num": 4, "den": 4}}) == 64
    assert p.bar_length({"compasso": {"num": 3, "den": 8}}) == 24
    assert p.bar_length({"compasso": {"num": 2, "den": 2}}) == 64
    assert p.bar_length({"compasso": {"num": 7, "den": 16}}) == 28
    assert p.bar_length({"beatsPerBar": 3}) == 48  # formato antigo continua valendo
    for ruim in ({"num": 0, "den": 4}, {"num": 17, "den": 4}, {"num": 4, "den": 3}):
        import pytest
        with pytest.raises(p.PulseError):
            p.bar_length({"compasso": ruim})


def test_nota_cortada_na_barra_de_3_8():
    # mínima começando no 1º tempo de 3/8: 3 colcheias no compasso + 1 no seguinte
    assert comp("m:c", 3, 8) == [("c", "seminima.~colcheia")]


def test_cinco_por_quatro_nao_corta():
    # 5 tempos cabem no mesmo compasso: nada de barra no meio (em 4/4 seria cortado)
    assert comp("q:c* q: q: q: q: r:c", 5, 4) == [("c", "semibreve~seminima")]
    assert comp("q:c* q: q: q: q: q: r:c", 5, 4) == [("c", "semibreve~seminima~seminima")]


def test_seis_por_oito_com_pulso_de_colcheia():
    assert comp("e:c e:d e:e e:f e:g e:a", 6, 8) == [(x, "colcheia") for x in "cdefga"]
