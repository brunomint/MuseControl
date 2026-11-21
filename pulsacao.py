"""Modo Pulsação do MuseControl.

O pulso é uma referência de CONTAGEM, não de tempo: a velocidade e a
regularidade dos toques não importam, só a ordem.

Regras (combinadas com o Bruno em 21/11/2026):
- O PULSO é um botão dividido em faixas: mínima, semínima, colcheia,
  semicolcheia. A faixa tocada é o valor daquele pulso.
- A 1ª nota do pulso é tocada JUNTO com ele. Notas tocadas sozinhas depois
  dividem o pulso em partes iguais: 1 = o valor do pulso, 2 = metades,
  3 = tercina, 4 = quartos, 5 = quintina... (N notas = N partes).
- PULSO sem nota nova:
    * com a nota anterior ainda SEGURADA -> prolonga a nota (ligadura);
    * sem nada segurado                   -> PAUSA do valor do pulso.
- Notas tocadas juntas = acorde.
- Nota segurada enquanto outra muda num novo pulso = DUAS VOZES (aparece na
  prévia, mas o envio ainda não é feito; decidir depois: teclas x MusicXML).

Formato recebido do celular (t em ms; só serve para saber o que foi junto):
    {"events": [
        {"type": "pulse", "value": 16, "t": ...},      # valor em 64 avos
        {"type": "down", "id": 7, "midi": 60, "t": ...},   # 60 = Dó central (C4)
        {"type": "up", "id": 7, "t": ...}
     ],
     "beatsPerBar": 4}

Envio ao MuseScore: a ALTURA vai por MIDI (porta "Midi Through", que o
MuseScore escuta em Preferências → Áudio e MIDI → Entrada MIDI) e o resto
(duração, ligadura, pausa, quiáltera) vai por teclas.

Durações internas em 64 avos: semibreve 64, mínima 32, semínima 16,
colcheia 8, semicolcheia 4, fusa 2, semifusa 1.
"""

import re
import threading
import time
from fractions import Fraction

from flask import Blueprint, jsonify, render_template, request

bp = Blueprint("pulso", __name__)

HEAD_MS = 120        # nota a até 120 ms do pulso = tocada "junto com o pulso"
CHORD_MS = 80        # notas a até 80 ms uma da outra = acorde
HELD_AFTER_MS = 60   # para prolongar, a nota precisa continuar segurada depois do pulso

PULSE_VALUES = (32, 16, 8, 4)
QUARTER = 16

# valor (64 avos) -> (tecla de duração no MuseScore, nome da figura)
FIGURES = {
    64: ("7", "semibreve"),
    32: ("6", "minima"),
    16: ("5", "seminima"),
    8: ("4", "colcheia"),
    4: ("3", "semicolcheia"),
    2: ("2", "fusa"),
    1: ("1", "semifusa"),
}
# (duração total, figura base, pontuada) — do maior para o menor
PIECES = [
    (96, 64, True), (64, 64, False), (48, 32, True), (32, 32, False),
    (24, 16, True), (16, 16, False), (12, 8, True), (8, 8, False),
    (6, 4, True), (4, 4, False), (3, 2, True), (2, 2, False), (1, 1, False),
]
NOTE_NAMES = ["Dó", "Dó♯", "Ré", "Ré♯", "Mi", "Fá", "Fá♯", "Sol", "Sol♯", "Lá", "Lá♯", "Si"]
MIDI_MIN, MIDI_MAX = 21, 108  # extensão do piano
MIDI_PORT = "Midi Through"
MAX_TUPLET_KEY = 9  # o MuseScore tem atalho Ctrl+2 ... Ctrl+9


class PulseError(ValueError):
    pass


# ---------------------------------------------------------------------------
# 1. Toques -> pulsos com suas partes
# ---------------------------------------------------------------------------

def _note(ev):
    return {"midi": int(ev["midi"])}


def note_name(midi):
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def _parse(data):
    pulses, downs, ups = [], [], {}
    for ev in data.get("events", []):
        typ = ev.get("type")
        t = float(ev["t"])
        if typ == "pulse":
            value = int(ev.get("value", QUARTER))
            if value not in PULSE_VALUES:
                raise PulseError("valor de pulso inválido")
            pulses.append({"t": t, "value": value})
        elif typ == "down":
            if MIDI_MIN <= int(ev.get("midi", 0)) <= MIDI_MAX:
                downs.append({"id": ev["id"], "t": t, "note": _note(ev)})
        elif typ == "up":
            ups[ev["id"]] = t
    for d in downs:
        d["up"] = ups.get(d["id"])
    pulses.sort(key=lambda p: p["t"])
    downs.sort(key=lambda d: d["t"])
    return pulses, downs


def _chords(downs):
    groups = []
    for d in downs:
        if groups and d["t"] - groups[-1][0]["t"] <= CHORD_MS:
            groups[-1].append(d)
        else:
            groups.append([d])
    return groups


def _held(d, t):
    """A nota d estava segurada no momento t (e continuou depois dele)?"""
    return d["t"] < t - HEAD_MS and (d["up"] is None or d["up"] > t + HELD_AFTER_MS)


def _pulse_slots(pulses, downs):
    """Para cada pulso, a lista de partes: nota/acorde, ligadura ou pausa."""
    heads = [[] for _ in pulses]
    subs = [[] for _ in pulses]
    for d in downs:
        near = [(abs(d["t"] - p["t"]), i) for i, p in enumerate(pulses)
                if abs(d["t"] - p["t"]) <= HEAD_MS]
        if near:
            heads[min(near)[1]].append(d)
            continue
        owner = None
        for i, p in enumerate(pulses):
            if p["t"] < d["t"]:
                owner = i
        if owner is not None:  # nota antes do 1º pulso é ignorada
            subs[owner].append(d)

    result = []
    last_attack = set()  # ids das notas do último ataque
    for i, p in enumerate(pulses):
        slots = []
        head = heads[i]
        ids_head = {d["id"] for d in head}
        if head:
            slot = {"kind": "note", "notes": [d["note"] for d in head]}
            # nota de antes que continua segurada durante todo este pulso: 2ª voz
            # (no último pulso: até a última nota tocada nele)
            if i + 1 < len(pulses):
                end = pulses[i + 1]["t"] - HEAD_MS
            else:
                end = max(d["t"] for d in head + subs[i]) + HELD_AFTER_MS
            sustain = [d for d in downs if d["id"] not in ids_head and _held(d, p["t"])
                       and (d["up"] is None or d["up"] >= end)]
            if sustain:
                slot["sustain"] = [d["note"] for d in sustain]
            slots.append(slot)
            last_attack = ids_head
        else:
            cont = [d for d in downs if d["id"] in last_attack and _held(d, p["t"])]
            if cont:
                slots.append({"kind": "tie", "notes": [d["note"] for d in cont]})
            else:
                slots.append({"kind": "rest", "notes": []})
                last_attack = set()
        for chord in _chords(subs[i]):
            slots.append({"kind": "note", "notes": [d["note"] for d in chord]})
            last_attack = {d["id"] for d in chord}
        result.append((p["value"], slots))
    return result


# ---------------------------------------------------------------------------
# 2. Partes -> figuras
# ---------------------------------------------------------------------------

def _split(units, start, bar):
    """Divide uma duração (64 avos) em figuras, quebrando nas barras."""
    pieces = []
    pos = Fraction(start)
    while units > 0:
        room = bar - (pos % bar)
        chunk = min(units, room) if room == int(room) else units
        chunk = int(chunk)
        while chunk > 0:
            size = next(p for p in PIECES if p[0] <= chunk)
            pieces.append(size)
            chunk -= size[0]
            units -= size[0]
            pos += size[0]
    return pieces


def _piece(units, base, dot):
    key, name = FIGURES[base]
    return {"units": units, "key": key, "dot": dot, "figure": name}


def analyze(data):
    """Recebe a gravação e devolve a lista de itens com suas figuras."""
    bpb = int(data.get("beatsPerBar", 4))
    bar = bpb * QUARTER if bpb > 0 else 10 ** 9
    pulses, downs = _parse(data)

    items = []
    pos = Fraction(0)
    for index, (value, slots) in enumerate(_pulse_slots(pulses, downs)):
        n = len(slots)
        if n & (n - 1) == 0:  # 1, 2, 4, 8...: divisão normal
            each, tuplet = Fraction(value, n), None
            if each < 1:
                raise PulseError("Divisão pequena demais para este pulso")
            each = int(each)
        else:  # 3, 5, 6, 7...: quiáltera
            normal = 1 << (n.bit_length() - 1)
            each = Fraction(value, normal)
            if each < 1:
                raise PulseError("Divisão pequena demais para este pulso")
            each = int(each)
            tuplet = {"n": n, "normal": normal, "value": value, "pulse": index}
        real = Fraction(value, n)  # quanto cada parte ocupa de fato

        for k, s in enumerate(slots):
            prev = items[-1] if items else None
            mergeable = (tuplet is None and prev is not None and prev["tuplet"] is None
                         and "sustain" not in s and "sustain" not in prev)
            if mergeable and s["kind"] == "tie" and prev["kind"] == "note":
                prev["units"] += each
                pos += real
                continue
            if mergeable and s["kind"] == "rest" and prev["kind"] == "rest":
                prev["units"] += each
                pos += real
                continue
            item = {
                "kind": "rest" if s["kind"] == "rest" else "note",
                "tied": s["kind"] == "tie",
                "notes": s["notes"],
                "units": each,
                "start": pos,
                "pulse": index,
                "tuplet": dict(tuplet, first=k == 0, last=k == n - 1) if tuplet else None,
            }
            if "sustain" in s:
                item["sustain"] = s["sustain"]
            items.append(item)
            pos += real

    for it in items:
        if it["tuplet"]:
            it["pieces"] = [_piece(it["units"], it["units"], False)]
        else:
            it["pieces"] = [_piece(u, b, d) for (u, b, d) in _split(it["units"], it["start"], bar)]
        it["start"] = float(it["start"])
    return items


# ---------------------------------------------------------------------------
# 3. Figuras -> teclas do MuseScore
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 3a. Modo teclado: alturas por letras (para quem não ligou o MIDI)
# ---------------------------------------------------------------------------
# O MuseScore coloca a letra digitada na oitava mais próxima da nota anterior
# (até uma 4ª para cima ou para baixo) e usa a armadura da partitura. Então
# calculamos quantos Ctrl+↑/↓ e ↑/↓ (semitom) são necessários.

LETTERS = "cdefgab"
NATURAL = [0, 2, 4, 5, 7, 9, 11]
SHARP_ORDER = "fcgdaeb"  # ordem dos sustenidos (bemóis: ao contrário)


def _key_alteration(letter, keysig):
    """Alteração (-1, 0, 1) que a armadura dá a uma letra. keysig: +n ♯ / -n ♭"""
    if keysig > 0 and letter in SHARP_ORDER[:keysig]:
        return 1
    if keysig < 0 and letter in SHARP_ORDER[::-1][:-keysig]:
        return -1
    return 0


def _spell(midi, keysig):
    """(índice da letra, alteração, passo diatônico absoluto) para a nota."""
    pc = midi % 12
    options = []
    for li, nat in enumerate(NATURAL):
        for alt in (-1, 0, 1):
            if (nat + alt) % 12 == pc:
                options.append((li, alt))
    letter_of = lambda o: LETTERS[o[0]]
    # 1º a grafia da armadura, depois a natural, depois ♯ (ou ♭ em tom de bemóis)
    options.sort(key=lambda o: (
        o[1] != _key_alteration(letter_of(o), keysig),
        o[1] != 0,
        o[1] != (1 if keysig >= 0 else -1),
    ))
    li, alt = options[0]
    natural_midi = midi - alt
    octave = natural_midi // 12 - 1
    return li, alt, octave * 7 + li


def _letter_keys(midi, keysig, ref_step, in_chord):
    """Teclas para uma nota digitada por letra. Devolve (teclas, passo)."""
    li, alt, step = _spell(midi, keysig)
    letter = LETTERS[li]
    if in_chord:  # Shift+letra entra acima da nota anterior do acorde
        placed = ref_step + next(d for d in range(1, 8) if (ref_step + d) % 7 == li)
        keys = [["shift", letter]]
    else:  # letra entra a no máximo uma 4ª da nota anterior
        placed = ref_step + next(d for d in (0, 1, -1, 2, -2, 3, -3) if (ref_step + d) % 7 == li)
        keys = [[letter]]
    semis = alt - _key_alteration(letter, keysig)
    keys += [["up"]] * max(0, semis) + [["down"]] * max(0, -semis)
    octaves = (step - placed) // 7
    keys += [["ctrl", "up"]] * max(0, octaves) + [["ctrl", "down"]] * max(0, -octaves)
    return keys, step


# ---------------------------------------------------------------------------
# 3b. Figuras -> ações para o MuseScore
# ---------------------------------------------------------------------------

def to_keys(items, mode="midi", keysig=0):
    """Lista de ações: teclas (['5'], ['ctrl', '3']...) ou notas MIDI
    (['midi', 60, 64] = tocar 60 e 64 juntas).
    mode="teclado": as alturas também vão por teclas (letras)."""
    keys = []
    current = None  # duração selecionada no MuseScore
    ref_step = None  # modo teclado: última nota que o MuseScore recebeu

    for it in items:
        if "sustain" in it:
            raise PulseError("Há duas vozes: o envio delas ainda não foi feito")
        tp = it["tuplet"]
        if tp and tp["first"]:
            if tp["n"] > MAX_TUPLET_KEY:
                raise PulseError(f"O MuseScore só cria quiálteras de até {MAX_TUPLET_KEY} pelo atalho")
            keys.append([FIGURES[tp["value"]][0]])
            keys.append(["ctrl", str(tp["n"])])
            current = None
        for i, p in enumerate(it["pieces"]):
            if not tp:
                dur = (p["key"], p["dot"])
                if dur != current:
                    keys.append([p["key"]])
                    if p["dot"]:
                        keys.append(["."])
                    current = dur
            if it["kind"] == "rest":
                keys.append(["0"])
            elif i == 0 and not it["tied"]:
                notes = sorted(n["midi"] for n in it["notes"])
                if mode == "teclado":
                    for j, m in enumerate(notes):
                        if ref_step is None:  # 1ª nota: sem referência, vai como está
                            ref_step = _spell(m, keysig)[2]
                        k, ref_step = _letter_keys(m, keysig, ref_step, j > 0)
                        keys.extend(k)
                else:
                    keys.append(["midi"] + notes)
            else:
                keys.append(["t"])  # nota ligada, mesma altura
        if tp and tp["last"]:
            current = None
    return keys


def keys_text(keys):
    return " ".join("+".join(note_name(m) for m in k[1:]) if k[0] == "midi" else "+".join(k)
                    for k in keys)


# ---------------------------------------------------------------------------
# 4. Rotas
# ---------------------------------------------------------------------------

_send_lock = threading.Lock()


_midi_out = None
SEQ_CLIENTS = "/proc/asound/seq/clients"


def musescore_listening():
    """O MuseScore está ouvindo a porta Midi Through? True/False, ou None se
    não dá para saber neste sistema (só sabemos ver isso no Linux)."""
    try:
        with open(SEQ_CLIENTS) as f:
            text = f.read()
    except OSError:
        return None
    names, through_targets, current = {}, [], None
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r'Client\s+(\d+)\s*:\s*"([^"]*)"', line)
        if m:
            current = int(m.group(1))
            names[current] = m.group(2)
        elif line.startswith("Connecting To:") and MIDI_PORT in names.get(current, ""):
            through_targets += [int(x.split(":")[0]) for x in line.split(":", 1)[1].split(",")]
    return any("MuseScore" in names.get(c, "") for c in through_targets)


def _mode(data):
    """'midi' ou 'teclado', conforme o ajuste e a detecção automática."""
    wanted = data.get("modo", "auto")
    if wanted in ("midi", "teclado"):
        return wanted
    return "midi" if musescore_listening() else "teclado"


def _open_midi():
    """Abre (uma vez) a saída MIDI para a porta que o MuseScore escuta."""
    global _midi_out
    if _midi_out is not None:
        return _midi_out
    try:
        import rtmidi  # importado aqui para os testes rodarem sem MIDI
    except ImportError:
        raise PulseError('Falta instalar o python-rtmidi (pip install python-rtmidi) '
                         'ou escolha o envio "Teclado" nos ajustes')
    out = rtmidi.MidiOut(name="MuseControl")
    ports = out.get_ports()
    idx = next((i for i, name in enumerate(ports) if MIDI_PORT in name), None)
    if idx is None:
        out.delete()
        raise PulseError(f'Porta MIDI "{MIDI_PORT}" não encontrada no computador')
    out.open_port(idx, "MuseControl")
    _midi_out = out
    return out


def _type_keys(keys, interval):
    import pyautogui  # importado aqui para os testes rodarem sem tela
    midi = _open_midi() if any(k[0] == "midi" for k in keys) else None
    for k in keys:
        if k[0] == "midi":
            notes = k[1:]
            for n in notes:  # todas juntas = acorde
                midi.send_message([0x90, n, 90])
            time.sleep(0.05)
            for n in notes:
                midi.send_message([0x80, n, 0])
        elif len(k) == 1:
            pyautogui.press(k[0])
        else:
            pyautogui.hotkey(*k)
        time.sleep(interval)


@bp.route("/pulso")
def pagina():
    return render_template("pulso.html")


@bp.route("/pulso/status")
def status():
    return jsonify(musescore_midi=musescore_listening())


@bp.route("/pulso/analisar", methods=["POST"])
def analisar():
    data = request.get_json(force=True) or {}
    try:
        items = analyze(data)
    except (PulseError, KeyError, TypeError, ValueError) as e:
        return jsonify(ok=False, erro=str(e)), 400
    mode = _mode(data)
    try:
        keys = to_keys(items, mode, int(data.get("armadura", 0)))
        return jsonify(ok=True, itens=items, teclas=keys_text(keys), total=len(keys), modo=mode)
    except PulseError as e:
        return jsonify(ok=True, itens=items, teclas="", total=0, aviso=str(e), modo=mode)


@bp.route("/pulso/enviar", methods=["POST"])
def enviar():
    data = request.get_json(force=True) or {}
    mode = _mode(data)
    try:
        items = analyze(data)
        keys = to_keys(items, mode, int(data.get("armadura", 0)))
    except (PulseError, KeyError, TypeError, ValueError) as e:
        return jsonify(ok=False, erro=str(e)), 400
    if not keys:
        return jsonify(ok=False, erro="Nada para enviar"), 400
    if not _send_lock.acquire(blocking=False):
        return jsonify(ok=False, erro="Já estou enviando, aguarde"), 409
    try:
        delay = max(0.0, min(10.0, float(data.get("delay", 0))))
        interval = max(0.02, min(0.5, float(data.get("interval", 0.08))))
        if any(k[0] == "midi" for k in keys):
            _open_midi()  # confere a porta antes de digitar qualquer coisa
        time.sleep(delay)
        _type_keys(keys, interval)
    except PulseError as e:
        return jsonify(ok=False, erro=str(e)), 400
    finally:
        _send_lock.release()
    # cada figura enviada vira um elemento (nota, acorde ou pausa) no MuseScore
    return jsonify(ok=True, total=len(keys), teclas=keys_text(keys), modo=mode,
                   elementos=sum(len(it["pieces"]) for it in items))


def octave_fix_keys(direction, elements, first):
    """Teclas para mover uma oitava o trecho que acabou de ser enviado.

    Na 1ª vez: Esc sai do modo de inserção (fica selecionada a última nota),
    Shift+← estende a seleção até o começo do trecho, Ctrl+↑/↓ move tudo.
    Nas vezes seguintes o trecho já está selecionado: só Ctrl+↑/↓."""
    arrow = "up" if direction > 0 else "down"
    keys = []
    if first:
        keys.append(["escape"])
        keys += [["shift", "left"]] * max(0, elements - 1)
    keys.append(["ctrl", arrow])
    return keys


# Ferramentas do MuseScore (só esta lista é aceita)
COMMANDS = {
    "esquerda": ["left"],
    "direita": ["right"],
    "cima": ["up"],
    "baixo": ["down"],
    "desfazer": ["ctrl", "z"],
    "refazer": ["ctrl", "shift", "z"],
    "apagar": ["backspace"],
    "tocar": ["space"],
    "insercao": ["n"],
    "sair": ["escape"],
}


@bp.route("/pulso/comando/<nome>", methods=["POST"])
def comando(nome):
    keys = COMMANDS.get(nome)
    if keys is None:
        return jsonify(ok=False, erro="comando desconhecido"), 404
    if not _send_lock.acquire(blocking=False):
        return jsonify(ok=False, erro="Já estou enviando, aguarde"), 409
    try:
        _type_keys([keys], 0.02)
    finally:
        _send_lock.release()
    return jsonify(ok=True, teclas=keys_text([keys]))


@bp.route("/pulso/oitava", methods=["POST"])
def oitava():
    data = request.get_json(force=True) or {}
    try:
        direction = 1 if int(data.get("direcao", 1)) > 0 else -1
        elements = max(1, min(500, int(data.get("elementos", 1))))
    except (TypeError, ValueError):
        return jsonify(ok=False, erro="dados inválidos"), 400
    keys = octave_fix_keys(direction, elements, bool(data.get("primeira", True)))
    if not _send_lock.acquire(blocking=False):
        return jsonify(ok=False, erro="Já estou enviando, aguarde"), 409
    try:
        _type_keys(keys, 0.05)
    finally:
        _send_lock.release()
    return jsonify(ok=True, teclas=keys_text(keys))
