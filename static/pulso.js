// Modo Pulsação: grava a ORDEM dos toques (pulso, nota apertada, nota solta)
// e manda para o servidor. Toda a regra musical fica em pulsacao.py.
(function () {
    'use strict';

    const NOMES = ['Dó', 'Dó♯', 'Ré', 'Ré♯', 'Mi', 'Fá', 'Fá♯', 'Sol', 'Sol♯', 'Lá', 'Lá♯', 'Si'];
    const LETRA = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 }; // teclado do computador
    const BRANCAS = [0, 2, 4, 5, 7, 9, 11];
    const MIDI_MIN = 21, MIDI_MAX = 108;
    const TECLA_MIN_PX = 40; // largura mínima confortável de uma tecla branca
    const CURTO = { semibreve: 'semib.', minima: 'mín.', seminima: 'semín.', colcheia: 'colch.', semicolcheia: 'semic.', fusa: 'fusa', semifusa: 'semif.' };
    const TECLA_PULSO = { 1: 32, 2: 16, 3: 8, 4: 4 }; // mesma ordem das faixas na tela
    const HEAD_MS = 120; // igual ao servidor: nota "junto com o pulso"
    const CHAVE = 'musecontrol-pulso-v3';
    const IMG = 'static/notas_musicais/';

    const $ = (id) => document.getElementById(id);
    const el = {
        status: $('status'), previa: $('previa'), compNum: $('compNum'), compDen: $('compDen'), delay: $('delay'),
        teclas: $('teclas'), totalTeclas: $('totalTeclas'),
        ajustes: $('ajustes'), enviar: $('btnEnviar'), som: $('som'),
        piano: $('piano'), faixaVisivel: $('faixaVisivel'),
        modo: $('modo'), armadura: $('armadura'), badge: $('modoBadge'), modoInfo: $('modoInfo'),
    };
    const faixas = Array.from(document.querySelectorAll('.faixa'));

    // ---- estado --------------------------------------------------------
    let events = [];      // {type:'pulse'|'down'|'up', ...}
    let nextId = 1;
    let lastValue = 16;   // faixa usada por último (fica maior)
    let sent = false;
    let inicio = 60;      // primeira tecla (branca) visível do piano; 60 = Dó central
    const pressed = {};   // ponteiro/tecla -> {id, btn}

    function load() {
        try {
            const s = JSON.parse(localStorage.getItem(CHAVE) || 'null');
            if (s && Array.isArray(s.events)) {
                events = s.events;
                nextId = s.nextId || 1;
                lastValue = s.lastValue || 16;
                sent = !!s.sent;
                if (s.comp) { el.compNum.value = s.comp.num; el.compDen.value = s.comp.den; }
                else if (s.bpb) { el.compNum.value = s.bpb; el.compDen.value = 4; } // versão antiga
                if (s.delay) el.delay.value = s.delay;
                if (s.som) el.som.value = s.som;
                if (s.modo) el.modo.value = s.modo;
                if (s.armadura !== undefined) el.armadura.value = s.armadura;
                if (s.inicio && BRANCAS.includes(s.inicio % 12)) inicio = s.inicio;
                else if (s.baseOct) inicio = (s.baseOct + 1) * 12; // versão antiga guardava a oitava
            }
        } catch (e) { /* sem armazenamento: começa vazio */ }
        // tempos antigos são de outra sessão da página: recomeça a contagem depois deles
        const ultimo = events.reduce((m, e) => Math.max(m, e.t), 0);
        offset = ultimo > 0 ? ultimo + 10000 : 0;
        events.forEach((e) => { if (e.type === 'down' && !events.some((u) => u.type === 'up' && u.id === e.id)) events.push({ type: 'up', id: e.id, t: ultimo + 1 }); });
    }
    let offset = 0;

    function save() {
        try {
            localStorage.setItem(CHAVE, JSON.stringify({
                events, nextId, lastValue, sent, comp: compasso(), delay: el.delay.value,
                som: el.som.value, inicio, modo: el.modo.value, armadura: el.armadura.value,
            }));
        } catch (e) { /* ignora */ }
    }

    function compasso() { return { num: Number(el.compNum.value), den: Number(el.compDen.value) }; }
    function tamanhoCompasso() { const c = compasso(); return c.num * 64 / c.den; } // em 64 avos

    function payload() {
        return {
            events, compasso: compasso(), delay: Number(el.delay.value),
            modo: el.modo.value, armadura: Number(el.armadura.value),
        };
    }

    function stamp(ev) {
        return offset + (ev && ev.timeStamp ? ev.timeStamp : performance.now());
    }

    // ---- gravação -------------------------------------------------------
    // trecho enviado no modo teclado que ainda pode ser corrigido de oitava
    let correcao = null; // {elementos, primeira}
    function escondeCorrecao() {
        correcao = null;
        $('corrigir').classList.add('hidden');
    }

    function freshIfSent() {
        escondeCorrecao();
        if (!sent) return;
        events = [];
        sent = false;
    }

    // no app Android a vibração vem da ponte nativa (a WebView não vibra sozinha)
    function vibra(ms) {
        try {
            if (window.AndroidMC) window.AndroidMC.vibrar(ms);
            else if (navigator.vibrate) navigator.vibrate(ms);
        } catch (e) { /* sem vibração */ }
    }

    function pulse(t, value) {
        freshIfSent();
        events.push({ type: 'pulse', value: value, t: t });
        vibra(12);
        changed();
    }

    function noteDown(t, midi) {
        freshIfSent();
        const id = nextId++;
        events.push({ type: 'down', id: id, midi: midi, t: t });
        changed();
        return id;
    }

    function noteUp(t, id) {
        if (events.some((e) => e.type === 'down' && e.id === id)) {
            events.push({ type: 'up', id: id, t: t });
            save();
        }
    }

    function undo() {
        // tira o último pulso e tudo que foi tocado a partir dele
        let idx = -1;
        events.forEach((e, i) => { if (e.type === 'pulse') idx = i; });
        if (idx < 0) { clearAll(); return; }
        const grupo = events[idx].g;
        if (grupo) { // o último pulso veio de uma variável inserida: tira ela inteira
            events = events.filter((e) => e.g !== grupo);
            sent = false;
            changed();
            return;
        }
        const corte = events[idx].t - HEAD_MS;
        const fora = new Set(events.filter((e) => e.type === 'down' && e.t >= corte).map((e) => e.id));
        events = events.filter((e, i) => i !== idx &&
            !(e.type === 'down' && fora.has(e.id)) && !(e.type === 'up' && fora.has(e.id)));
        sent = false;
        changed();
    }

    function clearAll() {
        escondeCorrecao();
        events = [];
        sent = false;
        changed();
    }

    // ---- desenho --------------------------------------------------------
    function pulseCount() { return events.filter((e) => e.type === 'pulse').length; }

    const ouvintes = []; // projetos.js: salva o rascunho no computador
    function changed() {
        save();
        ouvintes.forEach((fn) => { try { fn(); } catch (e) { /* ignora */ } });
        const n = pulseCount();
        statusBase = sent ? 'Enviado. O próximo toque começa outro trecho'
            : n ? n + ' pulso(s)'
            : events.length ? 'Toque a faixa do PULSO junto com a nota'
            : 'Toque uma faixa do PULSO junto com a 1ª nota';
        mostraStatus();
        analyze();
    }

    function setLastValue(v) {
        if (v === lastValue) return;
        lastValue = v;
        faixas.forEach((f) => f.classList.toggle('atual', Number(f.dataset.value) === v));
        save();
    }

    let analyzing = null;
    let again = false;
    let analise = 0; // número da última análise pedida: resposta mais velha é ignorada
    function analyze() {
        const numero = ++analise;
        if (!pulseCount()) { draw([]); el.teclas.textContent = ''; el.totalTeclas.textContent = '0'; return; }
        if (analyzing) { again = true; return; }
        analyzing = fetch('/pulso/analisar', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload()),
        }).then((r) => r.json()).then((d) => {
            if (numero !== analise) return; // o conteúdo mudou enquanto esta análise ia e voltava
            if (!d.ok) { show(d.erro || 'Erro'); return; }
            draw(d.itens);
            el.teclas.textContent = d.aviso ? '⚠ ' + d.aviso : d.teclas;
            el.totalTeclas.textContent = d.total;
            if (d.modo) mostraModo(d.modo);
        }).catch(() => show('Sem conexão com o computador'))
            .finally(() => { analyzing = null; if (again) { again = false; analyze(); } });
    }

    function nomeMidi(m) { return NOMES[m % 12] + (Math.floor(m / 12) - 1); }
    function nomeNota(n) { return nomeMidi(n.midi); }

    function div(cls) { const d = document.createElement('div'); d.className = cls; return d; }

    function figura(it, pc, i, isLast) {
        const f = div('fig' + (it.kind === 'rest' ? ' resto' : '') + (isLast ? ' novo' : ''));
        const box = div('img');
        const img = document.createElement('img');
        img.src = IMG + (it.kind === 'rest' ? 'pausa' : pc.figure) + '.png';
        img.alt = pc.figure;
        box.appendChild(img);
        if (pc.dot) {
            const d = document.createElement('img');
            d.src = IMG + 'pontuada.png'; d.className = 'ponto'; d.alt = 'ponto';
            box.appendChild(d);
        }
        f.appendChild(box);
        const nm = div('nome');
        if (it.kind === 'rest') nm.textContent = 'p. ' + (CURTO[pc.figure] || pc.figure);
        else nm.textContent = (i === 0 && !it.tied) ? it.notes.map(nomeNota).join('+') : '';
        f.appendChild(nm);
        if (it.sustain && i === 0) {
            const v = div('voz2');
            v.textContent = '+ ' + it.sustain.map(nomeNota).join('+') + ' segue';
            f.appendChild(v);
        }
        return f;
    }

    function draw(items) {
        const p = el.previa;
        p.innerHTML = '';
        if (!items.length) {
            p.innerHTML = '<span class="vazio">A partitura aparece aqui conforme você escreve.</span>';
            return;
        }
        const bar = tamanhoCompasso();
        let grupo = null;
        items.forEach((it, idx) => {
            const tp = it.tuplet;
            let alvo = p;
            if (tp) {
                if (tp.first) {
                    grupo = div('quialtera');
                    const num = div('num'); num.textContent = tp.n;
                    grupo.appendChild(num);
                    grupo.appendChild(div('grupo'));
                    if (it.start > 0 && Math.abs(it.start % bar) < 1e-6) p.appendChild(div('barra'));
                    p.appendChild(grupo);
                }
                alvo = grupo.lastChild;
            }
            let pos = it.start;
            it.pieces.forEach((pc, i) => {
                if (!tp && pos > 0 && Math.abs(pos % bar) < 1e-6) p.appendChild(div('barra'));
                if ((i > 0 || it.tied) && it.kind !== 'rest') {
                    const l = div('liga'); l.textContent = '‿'; alvo.appendChild(l);
                }
                alvo.appendChild(figura(it, pc, i, idx === items.length - 1));
                pos += pc.units;
            });
        });
        p.scrollLeft = p.scrollWidth;
    }

    // ---- modo de envio (MIDI ou teclado) -----------------------------------
    let midiDetectado = null;
    function mostraModo(modo) {
        el.badge.textContent = modo === 'midi' ? 'MIDI ✓' : 'Teclado';
        el.badge.className = 'badge modo-' + modo;
        const auto = el.modo.value === 'auto';
        let info;
        if (modo === 'midi') {
            info = 'As notas vão por MIDI: oitava sempre exata.';
        } else {
            info = 'As notas vão por letras: o MuseScore acerta a oitava pela nota anterior, mas a 1ª nota de cada envio pode sair uma oitava fora (corrija com Ctrl+↑/↓). Escolha a armadura certa abaixo.';
            if (auto) info += ' Para oitava exata, no MuseScore abra Editar → Preferências → Áudio e MIDI e escolha Entrada MIDI = "Midi Through".';
        }
        if (auto && midiDetectado === null) info += ' (Não consigo detectar o MIDI neste computador; escolha MIDI manualmente se já estiver ligado.)';
        el.modoInfo.textContent = info;
        el.armadura.closest('label').classList.toggle('hidden', modo === 'midi');
    }
    function verificaModo() {
        fetch('/pulso/status').then((r) => r.json()).then((d) => {
            midiDetectado = d.musescore_midi;
            const modo = el.modo.value !== 'auto' ? el.modo.value : (midiDetectado ? 'midi' : 'teclado');
            mostraModo(modo);
        }).catch(() => { /* sem conexão: o aviso aparece em outro lugar */ });
    }

    // ---- sinal de conexão -------------------------------------------------
    // mede o tempo de resposta do servidor a cada 3 s (média das 3 últimas)
    const tempos = [];
    let ultimoPing = null;
    function barras(ms) {
        if (ms === null) return 0;
        if (ms < 80) return 4;
        if (ms < 200) return 3;
        if (ms < 500) return 2;
        return 1;
    }
    function mostraSinal() {
        const media = tempos.length ? tempos.reduce((a, b) => a + b, 0) / tempos.length : null;
        const b = ultimoPing === null ? 0 : barras(media);
        const sinal = $('sinal');
        sinal.dataset.barras = b;
        sinal.title = b ? 'Conectado: ' + Math.round(media) + ' ms' : 'Sem conexão com o computador';
    }
    function ping() {
        const ctl = new AbortController();
        const limite = setTimeout(() => ctl.abort(), 2500);
        const t0 = performance.now();
        fetch('/pulso/ping', { cache: 'no-store', signal: ctl.signal })
            .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
            .then(() => {
                ultimoPing = performance.now() - t0;
                tempos.push(ultimoPing);
                if (tempos.length > 3) tempos.shift();
            })
            .catch(() => { ultimoPing = null; tempos.length = 0; })
            .finally(() => { clearTimeout(limite); mostraSinal(); });
    }

    // mensagens aparecem no topo, no lugar do status, por 3,5 s: assim não
    // cobrem as notas nem o teclado
    let statusBase = '';
    let aviso = null;
    let avisoTimer = null;
    function mostraStatus() {
        el.status.textContent = aviso || statusBase;
        el.status.title = aviso || '';
        el.status.classList.toggle('com-aviso', !!aviso);
    }
    function show(msg) {
        aviso = msg;
        mostraStatus();
        clearTimeout(avisoTimer);
        avisoTimer = setTimeout(() => { aviso = null; mostraStatus(); }, 3500);
    }

    // ---- envio ------------------------------------------------------------
    function send() {
        if (!pulseCount()) { show('Nada escrito ainda'); return; }
        verificaModo();
        const d = Number(el.delay.value);
        el.enviar.disabled = true;
        show(d ? 'Clique no MuseScore! Digitando em ' + d + ' s…' : 'Digitando no MuseScore…');
        fetch('/pulso/enviar', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload()),
        }).then((r) => r.json()).then((res) => {
            if (!res.ok) { show(res.erro || 'Erro ao enviar'); return; }
            sent = true;
            changed();
            show('Pronto: ' + res.total + ' teclas enviadas');
            if (res.modo === 'teclado') {
                correcao = { elementos: res.elementos, primeira: true };
                $('corrigir').classList.remove('hidden');
            } else {
                escondeCorrecao();
            }
        }).catch(() => show('Sem conexão com o computador'))
            .finally(() => { el.enviar.disabled = false; });
    }

    function corrigeOitava(direcao) {
        if (!correcao) return;
        fetch('/pulso/oitava', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ direcao, elementos: correcao.elementos, primeira: correcao.primeira }),
        }).then((r) => r.json()).then((res) => {
            if (!res.ok) { show(res.erro || 'Erro'); return; }
            correcao.primeira = false; // o trecho fica selecionado no MuseScore
            show('Trecho movido ' + (direcao > 0 ? 'uma oitava acima' : 'uma oitava abaixo') +
                '. Para continuar escrevendo, clique depois do trecho no MuseScore e aperte N.');
        }).catch(() => show('Sem conexão com o computador'));
    }
    $('trechoMais').addEventListener('click', () => corrigeOitava(1));
    $('trechoMenos').addEventListener('click', () => corrigeOitava(-1));

    // ---- entradas: toque --------------------------------------------------
    function noMenu(node) { node.addEventListener('contextmenu', (ev) => ev.preventDefault()); }

    faixas.forEach((f) => {
        noMenu(f);
        const v = Number(f.dataset.value);
        f.addEventListener('pointerdown', (ev) => {
            ev.preventDefault();
            pulse(stamp(ev), v);
            f.classList.add('batida');
        });
        const solta = () => {
            f.classList.remove('batida');
            setLastValue(v); // muda o tamanho só depois de soltar o dedo
        };
        f.addEventListener('pointerup', solta);
        f.addEventListener('pointercancel', solta);
    });

    // ---- piano --------------------------------------------------------------
    let audio = null;
    const vozes = {};
    function somLiga(id, midi) {
        if (el.som.value !== '1') return;
        try {
            audio = audio || new (window.AudioContext || window.webkitAudioContext)();
            const osc = audio.createOscillator();
            const g = audio.createGain();
            osc.type = 'triangle';
            osc.frequency.value = 440 * Math.pow(2, (midi - 69) / 12);
            g.gain.setValueAtTime(0, audio.currentTime);
            g.gain.linearRampToValueAtTime(0.25, audio.currentTime + 0.01);
            g.gain.exponentialRampToValueAtTime(0.05, audio.currentTime + 1.2);
            osc.connect(g).connect(audio.destination);
            osc.start();
            vozes[id] = { osc, g };
        } catch (e) { /* sem áudio */ }
    }
    function somDesliga(id) {
        const v = vozes[id];
        if (!v) return;
        delete vozes[id];
        try {
            v.g.gain.cancelScheduledValues(audio.currentTime);
            v.g.gain.setValueAtTime(v.g.gain.value, audio.currentTime);
            v.g.gain.linearRampToValueAtTime(0, audio.currentTime + 0.08);
            v.osc.stop(audio.currentTime + 0.1);
        } catch (e) { /* ignora */ }
    }

    function aperta(t, midi, chave, btn) {
        const id = noteDown(t, midi);
        pressed[chave] = { id, midi, btn };
        somLiga(id, midi);
        marca(midi);
    }
    function solta(t, chave) {
        const info = pressed[chave];
        if (!info) return;
        delete pressed[chave];
        noteUp(t, info.id);
        somDesliga(info.id);
        marca(info.midi);
    }
    function marca(midi) {
        const on = Object.values(pressed).some((x) => x.midi === midi);
        const k = el.piano.querySelector('[data-midi="' + midi + '"]');
        if (k) k.classList.toggle('tocando', on);
    }

    // teclado do PC: cada letra toca a 1ª tecla com aquele nome a partir do
    // começo do piano visível (as 7 primeiras teclas brancas)
    function midiDaLetra(letra) {
        return inicio + ((LETRA[letra] - (inicio % 12) + 12) % 12);
    }
    function atalhoDe(m) {
        const letra = (n) => Object.keys(LETRA).find((l) => LETRA[l] === n % 12);
        if (BRANCAS.includes(m % 12)) {
            return m >= inicio && m <= inicio + 11 ? letra(m).toUpperCase() : null;
        }
        return m - 1 >= inicio && m - 1 <= inicio + 11 ? '⇧' + letra(m - 1).toUpperCase() : null;
    }

    function montaPiano() {
        const largura = el.piano.clientWidth || 300;
        const minimo = window.innerWidth >= 900 ? 50 : TECLA_MIN_PX; // tela larga: teclas mais largas
        const nBrancas = Math.max(7, Math.min(52, Math.floor(largura / minimo)));
        const brancas = [];
        for (let m = inicio; brancas.length < nBrancas && m <= MIDI_MAX; m++) {
            if (BRANCAS.includes(m % 12)) brancas.push(m);
        }
        el.piano.innerHTML = '';
        brancas.forEach((m) => {
            const b = document.createElement('button');
            b.className = 'tecla branca' + (m % 12 === 0 ? ' do' : '') + (m === 60 ? ' central' : '');
            if (m === 60) b.title = 'Dó central';
            b.dataset.midi = m;
            b.textContent = m % 12 === 0 ? nomeMidi(m) : NOMES[m % 12];
            const atalho = atalhoDe(m);
            if (atalho) b.insertAdjacentHTML('afterbegin', '<kbd class="atalho">' + atalho + '</kbd>');
            el.piano.appendChild(b);
        });
        // pretas: entre a branca i e a i+1, quando existirem
        const passo = 100 / brancas.length;
        brancas.forEach((m, i) => {
            const preta = m + 1;
            if (BRANCAS.includes(preta % 12) || i === brancas.length - 1 || preta > MIDI_MAX) return;
            const b = document.createElement('button');
            b.className = 'tecla preta';
            b.dataset.midi = preta;
            b.setAttribute('aria-label', nomeMidi(preta));
            const atalhoP = atalhoDe(preta);
            if (atalhoP) b.innerHTML = '<kbd class="atalho">' + atalhoP + '</kbd>';
            b.style.left = 'calc(' + ((i + 1) * passo) + '% - ' + (passo * 0.3) + '%)';
            b.style.width = (passo * 0.6) + '%';
            el.piano.appendChild(b);
        });
        el.faixaVisivel.textContent = nomeMidi(brancas[0]) + ' – ' + nomeMidi(brancas[brancas.length - 1]);
        Object.values(pressed).forEach((x) => marca(x.midi));
    }

    const INICIO_MAX = 96; // Dó7: sempre sobra piano visível
    function mudaInicio(novo) {
        novo = Math.max(MIDI_MIN, Math.min(INICIO_MAX, novo));
        if (novo === inicio) return;
        inicio = novo;
        save();
        montaPiano();
    }
    function mudaOitava(d) { mudaInicio(inicio + 12 * d); }
    // anda uma tecla branca para baixo/cima
    function mudaNota(d) {
        let m = inicio + d;
        while (!BRANCAS.includes(((m % 12) + 12) % 12)) m += d;
        mudaInicio(m);
    }

    el.piano.addEventListener('pointerdown', (ev) => {
        const k = ev.target.closest('.tecla');
        if (!k) return;
        ev.preventDefault();
        try { el.piano.setPointerCapture(ev.pointerId); } catch (e) { /* ignora */ }
        aperta(stamp(ev), Number(k.dataset.midi), 'p' + ev.pointerId, k);
    });
    ['pointerup', 'pointercancel'].forEach((tipo) => el.piano.addEventListener(tipo, (ev) => solta(stamp(ev), 'p' + ev.pointerId)));
    noMenu(el.piano);
    $('oitavaMenos').addEventListener('click', () => mudaOitava(-1));
    $('oitavaMais').addEventListener('click', () => mudaOitava(1));
    $('notaMenos').addEventListener('click', () => mudaNota(-1));
    $('notaMais').addEventListener('click', () => mudaNota(1));
    let redim = null;
    window.addEventListener('resize', () => { clearTimeout(redim); redim = setTimeout(montaPiano, 150); });

    $('btnDesfazer').addEventListener('click', undo);
    $('btnLimpar').addEventListener('click', clearAll);
    el.enviar.addEventListener('click', send);
    // janelas 🛠 e ⚙: abrem por cima, fecham no ✕, tocando fora ou com Esc
    function abreJanela(id) {
        const j = $(id);
        const jaAberta = !j.classList.contains('hidden');
        fechaJanelas();
        if (jaAberta) return;
        j.classList.remove('hidden');
        $('fundoJanela').classList.remove('hidden');
        if (id === 'ajustes') verificaModo();
    }
    function fechaJanelas() {
        document.querySelectorAll('.janela').forEach((j) => j.classList.add('hidden'));
        $('fundoJanela').classList.add('hidden');
    }
    function janelaAberta() { return !$('fundoJanela').classList.contains('hidden'); }
    $('btnAjustes').addEventListener('click', () => abreJanela('ajustes'));
    $('btnFerramentas').addEventListener('click', () => abreJanela('ferramentas'));
    $('fundoJanela').addEventListener('click', fechaJanelas);
    document.querySelectorAll('.janela .fechar').forEach((b) => b.addEventListener('click', fechaJanelas));
    document.querySelectorAll('[data-cmd]').forEach((b) => b.addEventListener('click', () => {
        fetch('/pulso/comando/' + b.dataset.cmd, { method: 'POST' })
            .then((r) => r.json()).then((d) => { if (!d.ok) show(d.erro || 'Erro'); })
            .catch(() => show('Sem conexão com o computador'));
    }));
    let desligarConfirma = 0;
    $('btnDesligar').addEventListener('click', () => {
        // sem confirm(): pede um 2º toque em até 3 s
        if (Date.now() - desligarConfirma > 3000) {
            desligarConfirma = Date.now();
            show('Toque de novo para desligar o MuseControl');
            return;
        }
        fetch('/shutdown', { method: 'POST' }).catch(() => {}).finally(() => {
            document.body.innerHTML = '<div style="margin:60px auto;text-align:center;color:#fff"><h2>MuseControl desligado.</h2><p>Pode fechar esta aba.</p></div>';
        });
    });
    el.badge.addEventListener('click', () => { if ($('ajustes').classList.contains('hidden')) abreJanela('ajustes'); });
    [el.compNum, el.compDen, el.delay, el.som, el.armadura].forEach((s) => s.addEventListener('change', changed));
    // compasso e armadura são do projeto: avisa projetos.js
    [el.compNum, el.compDen, el.armadura].forEach((s) => s.addEventListener('change', () =>
        window.dispatchEvent(new CustomEvent('musecontrol:ajustes'))));
    el.modo.addEventListener('change', () => { changed(); verificaModo(); });

    // ---- entradas: teclado do computador ------------------------------------
    document.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape' && janelaAberta()) { fechaJanelas(); return; }
        if (janelaAberta()) return; // com janela aberta o teclado não escreve notas
        if ((ev.ctrlKey || ev.metaKey) && !ev.shiftKey && ev.key.toLowerCase() === 'z') {
            ev.preventDefault();
            undo(); // Ctrl+Z = desfazer o último pulso (como o Backspace)
            return;
        }
        if (ev.repeat || ev.ctrlKey || ev.altKey || ev.metaKey) return;
        if (ev.target.tagName === 'SELECT') return;
        const k = ev.key.toLowerCase();
        const t = stamp(ev);
        if (TECLA_PULSO[k]) { pulse(t, TECLA_PULSO[k]); setLastValue(TECLA_PULSO[k]); }
        else if (k === ' ') { ev.preventDefault(); pulse(t, lastValue); }
        else if (k in LETRA) {
            // Shift + letra = sustenido (Shift+C = Dó♯)
            const midi = midiDaLetra(k) + (ev.shiftKey ? 1 : 0);
            if (!pressed['k' + k]) aperta(t, midi, 'k' + k, null);
        }
        else if (k === 'arrowleft') { ev.preventDefault(); if (ev.shiftKey) mudaNota(-1); else mudaOitava(-1); }
        else if (k === 'arrowright') { ev.preventDefault(); if (ev.shiftKey) mudaNota(1); else mudaOitava(1); }
        else if (k === 'backspace') { ev.preventDefault(); undo(); }
        else if (k === 'enter') { ev.preventDefault(); send(); }
    });
    document.addEventListener('keyup', (ev) => {
        const k = ev.key.toLowerCase();
        if (pressed['k' + k]) solta(stamp(ev), 'k' + k);
    });

    $('sinal').addEventListener('click', () => show($('sinal').title));

    // tema (aplicado cedo por tema.js; aqui só a escolha em ⚙)
    if (window.MuseControlTema) {
        $('tema').value = window.MuseControlTema.atual();
        $('tema').addEventListener('change', () => window.MuseControlTema.muda($('tema').value));
    }

    // ---- usado por variaveis.js -------------------------------------------
    // insere um trecho guardado depois de tudo que já foi escrito.
    // opcoes: transpor (semitons), vezes (repetições), semGrupo (não junta no desfazer)
    function insereEventos(lista, opcoes) {
        opcoes = opcoes || {};
        const transpor = opcoes.transpor || 0;
        const vezes = Math.max(1, Math.min(16, opcoes.vezes || 1));
        const foraDoPiano = lista.some((e) => e.type === 'down' &&
            (e.midi + transpor < MIDI_MIN || e.midi + transpor > MIDI_MAX));
        if (foraDoPiano) return false;
        freshIfSent();
        const ultimo = events.reduce((m, e) => Math.max(m, e.t), 0);
        const duracao = lista.reduce((m, e) => Math.max(m, e.t), 0);
        let inicio = Math.max(ultimo, stamp()) + 500;
        const grupo = opcoes.semGrupo ? null : 'v' + Date.now();
        for (let r = 0; r < vezes; r++) {
            const ids = {};
            lista.forEach((e) => {
                const novo = { type: e.type, t: inicio + e.t };
                if (grupo) novo.g = grupo; // tudo que entrou junto sai junto no desfazer
                if (e.type === 'pulse') novo.value = e.value;
                else {
                    if (!(e.id in ids)) ids[e.id] = nextId++;
                    novo.id = ids[e.id];
                    if (e.type === 'down') novo.midi = e.midi + transpor;
                }
                events.push(novo);
            });
            inicio += duracao + 500;
        }
        // o próximo toque de verdade tem que vir DEPOIS do trecho inserido
        const fim = events.reduce((m, e) => Math.max(m, e.t), 0);
        if (stamp() < fim + 500) offset += fim + 500 - stamp();
        changed();
        return true;
    }

    // troca tudo o que está escrito (usado para editar uma variável e depois
    // voltar ao que estava antes). Devolve o conteúdo antigo.
    function trocaEventos(lista) {
        const antigo = events;
        escondeCorrecao();
        events = lista.map((e) => Object.assign({}, e));
        sent = false;
        const fim = events.reduce((m, e) => Math.max(m, e.t), 0);
        if (stamp() < fim + 500) offset += fim + 500 - stamp();
        changed();
        return antigo;
    }

    // botão Voltar do app Android: fecha a janela aberta (true = tratado)
    window.MuseControlVoltar = function () {
        if (!janelaAberta()) return false;
        fechaJanelas();
        return true;
    };
    if (window.AndroidMC) {
        $('btnTrocarPc').classList.remove('hidden');
        $('btnTrocarPc').addEventListener('click', () => window.AndroidMC.trocarServidor());
    }

    window.MuseControl = {
        eventos: () => events.map((e) => Object.assign({}, e)),
        insereEventos,
        trocaEventos,
        aoMudar: (fn) => ouvintes.push(fn),
        compasso,
        armadura: () => Number(el.armadura.value),
        defineAjustes(comp, arm) { // vindo do projeto (não dispara 'musecontrol:ajustes')
            if (comp) { el.compNum.value = comp.num; el.compDen.value = comp.den; }
            if (arm !== undefined && arm !== null) el.armadura.value = arm;
            changed();
        },
        nomeMidi,
        mostra: show,
        abreJanela,
        fechaJanelas,
    };
    load();
    montaPiano();
    ping();
    setInterval(ping, 3000);
    verificaModo();
    setInterval(verificaModo, 15000); // o MIDI pode ser ligado com a página aberta
    faixas.forEach((f) => f.classList.toggle('atual', Number(f.dataset.value) === lastValue));
    changed();
})();
