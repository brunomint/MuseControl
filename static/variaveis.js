// Variáveis (ideia do LilyPond): guardar o que está escrito com um nome e
// inserir de novo com um toque. Ficam salvas no computador (variaveis.py):
// as do projeto aberto e as gerais (🌐), que valem em todos os projetos.
(function () {
    'use strict';

    const app = window.MuseControl;
    const $ = (id) => document.getElementById(id);
    let lista = [];

    function pedido(url, opcoes) {
        return fetch(url, opcoes).then((r) => r.json().then((d) => Object.assign({ status: r.status }, d)));
    }
    function json(metodo, corpo) {
        return { method: metodo, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo || {}) };
    }

    // ---- chips ------------------------------------------------------------
    function projetoAtual() {
        return window.MuseControlProjeto ? window.MuseControlProjeto.atual() : null;
    }
    function pausaRascunho(sim) {
        if (window.MuseControlProjeto) window.MuseControlProjeto.pausa(sim);
    }

    function carrega() {
        const p = projetoAtual();
        return pedido('/pulso/variaveis' + (p ? '?projeto=' + p : '')).then((d) => {
            lista = d.variaveis || [];
            desenhaChips();
            desenhaLista();
        }).catch(() => { /* sem conexão: o sinal no topo já avisa */ });
    }

    function desenhaChips() {
        const box = $('chipsVar');
        box.innerHTML = '';
        if (!lista.length) {
            box.innerHTML = '<span class="chips-vazio">Nenhuma variável ainda</span>';
            return;
        }
        lista.forEach((v) => {
            const b = document.createElement('button');
            b.className = 'chip' + (v.geral ? ' geral' : '');
            b.title = 'Inserir "' + v.nome + '"' + (v.geral ? ' (biblioteca geral)' : '');
            b.textContent = v.nome;
            const n = document.createElement('small');
            n.textContent = v.pulsos + 'p';
            b.appendChild(n);
            // toque = insere como está; segurar (ou botão direito) = opções
            let timer = null;
            let longo = false;
            b.addEventListener('pointerdown', () => {
                longo = false;
                timer = setTimeout(() => { longo = true; abreOpcoes(v); }, 550);
            });
            ['pointerup', 'pointerleave', 'pointercancel'].forEach((t) => b.addEventListener(t, () => clearTimeout(timer)));
            b.addEventListener('contextmenu', (ev) => { ev.preventDefault(); clearTimeout(timer); abreOpcoes(v); });
            b.addEventListener('click', () => {
                if (longo) { longo = false; return; }
                insere(v, 0, 1);
                b.classList.add('inserido');
                setTimeout(() => b.classList.remove('inserido'), 300);
            });
            box.appendChild(b);
        });
    }

    function insere(v, transpor, vezes) {
        if (!app.insereEventos(v.eventos, { transpor, vezes })) {
            app.mostra('Transposto assim, o trecho sai do piano. Escolha outra transposição.');
            return false;
        }
        let msg = '"' + v.nome + '" inserida';
        if (transpor) msg += ' (' + (transpor > 0 ? '+' : '') + transpor + ')';
        if (vezes > 1) msg += ' ' + vezes + '×';
        app.mostra(msg + '. Desfazer pulso tira tudo de uma vez.');
        return true;
    }

    // ---- inserir com opções (transpor / repetir) --------------------------
    const opcoes = { v: null, transpor: 0, vezes: 1 };
    function primeiraNota(v) {
        const d = v.eventos.find((e) => e.type === 'down');
        return d ? d.midi : null;
    }
    function desenhaOpcoes() {
        const v = opcoes.v;
        const t = opcoes.transpor;
        $('transpValor').textContent = (t > 0 ? '+' : '') + t;
        const m = primeiraNota(v);
        let info = t === 0 ? 'Sem transposição.' : '';
        if (m !== null) info = 'Começa em ' + app.nomeMidi(m) + (t ? ' → ' + app.nomeMidi(m + t) : '') + '.';
        const notas = v.eventos.filter((e) => e.type === 'down').map((e) => e.midi + t);
        const fora = notas.some((n) => n < 21 || n > 108);
        if (fora) info += ' Assim o trecho sai do piano.';
        $('transpInfo').textContent = info;
        $('vezesValor').textContent = opcoes.vezes + '×';
        $('inserirResumo').textContent = v.pulsos + (v.pulsos === 1 ? ' pulso' : ' pulsos') +
            (opcoes.vezes > 1 ? ' × ' + opcoes.vezes + ' = ' + (v.pulsos * opcoes.vezes) + ' pulsos' : '');
        $('confirmarInserir').disabled = fora;
    }
    function abreOpcoes(v) {
        if (!$('janelaInserir').classList.contains('hidden')) return; // já aberta
        opcoes.v = v;
        opcoes.transpor = 0;
        opcoes.vezes = 1;
        $('inserirTitulo').textContent = 'Inserir "' + v.nome + '"';
        desenhaOpcoes();
        app.abreJanela('janelaInserir');
    }
    document.querySelectorAll('[data-transp]').forEach((b) => b.addEventListener('click', () => {
        opcoes.transpor = Math.max(-48, Math.min(48, opcoes.transpor + Number(b.dataset.transp)));
        desenhaOpcoes();
    }));
    document.querySelectorAll('[data-vezes]').forEach((b) => b.addEventListener('click', () => {
        opcoes.vezes = Math.max(1, Math.min(16, opcoes.vezes + Number(b.dataset.vezes)));
        desenhaOpcoes();
    }));
    $('confirmarInserir').addEventListener('click', () => {
        if (insere(opcoes.v, opcoes.transpor, opcoes.vezes)) app.fechaJanelas();
    });
    $('cancelarInserir').addEventListener('click', () => app.fechaJanelas());

    // ---- guardar ----------------------------------------------------------
    let substituir = false;
    function erroGuardar(msg) {
        $('guardarErro').textContent = msg || '';
        $('guardarErro').classList.toggle('hidden', !msg);
    }

    $('btnGuardarVar').addEventListener('click', () => {
        const pulsos = app.eventos().filter((e) => e.type === 'pulse').length;
        if (!pulsos) { app.mostra('Escreva alguma coisa antes de guardar'); return; }
        substituir = false;
        erroGuardar('');
        $('confirmarGuardar').textContent = 'Guardar';
        $('guardarPulsos').textContent = pulsos + (pulsos === 1 ? ' pulso' : ' pulsos');
        $('nomeVar').value = '';
        $('varGeral').checked = false;
        app.abreJanela('janelaGuardar');
        setTimeout(() => $('nomeVar').focus(), 50);
    });

    function guardar() {
        const nome = $('nomeVar').value.trim();
        if (!nome) { erroGuardar('Dê um nome para a variável'); return; }
        const projeto = $('varGeral').checked ? null : projetoAtual();
        pedido('/pulso/variaveis', json('POST', { nome, eventos: app.eventos(), substituir, projeto }))
            .then((d) => {
                if (d.ok) {
                    app.fechaJanelas();
                    app.mostra('Variável "' + d.variavel.nome + '" guardada');
                    carrega();
                } else if (d.existe) {
                    substituir = true; // 2º toque em "Substituir" confirma
                    erroGuardar(d.erro + '. Toque em Substituir para trocar pelo trecho atual.');
                    $('confirmarGuardar').textContent = 'Substituir';
                } else {
                    erroGuardar(d.erro || 'Erro ao guardar');
                }
            })
            .catch(() => erroGuardar('Sem conexão com o computador'));
    }
    $('confirmarGuardar').addEventListener('click', guardar);
    $('cancelarGuardar').addEventListener('click', () => app.fechaJanelas());
    $('nomeVar').addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') { ev.preventDefault(); guardar(); }
        if (substituir) { substituir = false; $('confirmarGuardar').textContent = 'Guardar'; erroGuardar(''); }
    });

    // ---- gerenciar (renomear / apagar) ------------------------------------
    function desenhaLista() {
        const box = $('listaVar');
        box.innerHTML = '';
        if (!lista.length) {
            box.innerHTML = '<p class="dica">Nenhuma variável guardada. Escreva um trecho e toque em ＋ Guardar.</p>';
            return;
        }
        lista.forEach((v) => {
            const linha = document.createElement('div');
            linha.className = 'linha';
            const nome = document.createElement('span');
            nome.className = 'nome';
            nome.textContent = v.nome + ' ';
            const n = document.createElement('small');
            n.textContent = v.pulsos + (v.pulsos === 1 ? ' pulso' : ' pulsos') + (v.geral ? ' · 🌐 geral' : '');
            nome.appendChild(n);
            const ren = document.createElement('button');
            ren.textContent = 'Renomear';
            ren.addEventListener('click', () => editaNome(linha, v));
            const apa = document.createElement('button');
            apa.className = 'apagar';
            apa.textContent = 'Apagar';
            apa.addEventListener('click', () => {
                if (!apa.classList.contains('confirmar')) { // pede um 2º toque
                    apa.classList.add('confirmar');
                    apa.textContent = 'Confirmar';
                    setTimeout(() => { apa.classList.remove('confirmar'); apa.textContent = 'Apagar'; }, 3000);
                    return;
                }
                pedido('/pulso/variaveis/' + v.id, { method: 'DELETE' })
                    .then((d) => { app.mostra(d.ok ? 'Variável apagada' : d.erro); carrega(); });
            });
            const ins = document.createElement('button');
            ins.textContent = 'Inserir…';
            ins.addEventListener('click', () => { app.fechaJanelas(); abreOpcoes(v); });
            const edi = document.createElement('button');
            edi.textContent = 'Editar';
            edi.addEventListener('click', () => iniciaEdicao(v));
            const dup = document.createElement('button');
            dup.textContent = 'Duplicar';
            dup.addEventListener('click', () => {
                pedido('/pulso/variaveis/' + v.id + '/duplicar', json('POST'))
                    .then((d) => { app.mostra(d.ok ? 'Cópia criada: "' + d.variavel.nome + '"' : d.erro); carrega(); })
                    .catch(() => app.mostra('Sem conexão com o computador'));
            });
            const botoes = document.createElement('div');
            botoes.className = 'acoes-var';
            botoes.append(ins, edi, dup, ren, apa);
            linha.append(nome, botoes);
            box.appendChild(linha);
        });
    }

    function editaNome(linha, v) {
        linha.innerHTML = '';
        const campo = document.createElement('input');
        campo.type = 'text';
        campo.maxLength = 40;
        campo.value = v.nome;
        const ok = document.createElement('button');
        ok.className = 'principal';
        ok.textContent = 'OK';
        const cancela = document.createElement('button');
        cancela.textContent = 'Cancelar';
        const salva = () => {
            const novo = campo.value.trim();
            if (!novo || novo === v.nome) { desenhaLista(); return; }
            pedido('/pulso/variaveis/' + v.id + '/renomear', json('POST', { novo }))
                .then((d) => { if (!d.ok) app.mostra(d.erro); carrega(); });
        };
        ok.addEventListener('click', salva);
        cancela.addEventListener('click', desenhaLista);
        campo.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); salva(); } });
        linha.append(campo, ok, cancela);
        campo.focus();
        campo.select();
    }

    // ---- editar ------------------------------------------------------------
    // carrega a variável na área de escrita; o que estava escrito fica guardado
    // e volta ao salvar ou cancelar.
    const CHAVE_EDICAO = 'musecontrol-edicao';
    let edicao = null; // { id, nome, antes: [...] }
    function guardaEdicao() {
        try {
            if (edicao) localStorage.setItem(CHAVE_EDICAO, JSON.stringify(edicao));
            else localStorage.removeItem(CHAVE_EDICAO);
        } catch (e) { /* sem armazenamento */ }
    }
    function mostraFaixa() {
        $('editandoVar').classList.toggle('hidden', !edicao);
        if (edicao) $('editandoNome').textContent = '"' + edicao.nome + '"';
    }
    function iniciaEdicao(v) {
        if (edicao) { app.mostra('Termine de editar "' + edicao.nome + '" primeiro'); return; }
        app.fechaJanelas();
        pausaRascunho(true); // a tela vai mostrar a variável, não o rascunho do projeto
        edicao = { id: v.id, nome: v.nome, antes: null };
        guardaEdicao(); // marca "editando" antes de trocar o conteúdo
        edicao.antes = app.trocaEventos([]);
        app.insereEventos(v.eventos, { semGrupo: true });
        guardaEdicao();
        mostraFaixa();
    }
    function terminaEdicao() {
        const antes = edicao.antes || [];
        edicao = null;
        guardaEdicao();
        app.trocaEventos(antes);
        pausaRascunho(false);
        mostraFaixa();
    }
    $('salvarEdicao').addEventListener('click', () => {
        const eventos = app.eventos();
        if (!eventos.some((e) => e.type === 'pulse')) { app.mostra('A variável ficou vazia. Escreva algo ou cancele.'); return; }
        // edições antigas (de antes do banco) não têm id: acha pelo nome
        const id = edicao.id || (lista.find((v) => v.nome === edicao.nome) || {}).id;
        const req = id ? pedido('/pulso/variaveis/' + id + '/salvar', json('POST', { eventos }))
            : pedido('/pulso/variaveis', json('POST', { nome: edicao.nome, eventos, substituir: true }));
        req
            .then((d) => {
                if (!d.ok) { app.mostra(d.erro || 'Erro ao salvar'); return; }
                app.mostra('Variável "' + edicao.nome + '" salva');
                terminaEdicao();
                carrega();
            })
            .catch(() => app.mostra('Sem conexão com o computador'));
    });
    $('cancelarEdicao').addEventListener('click', () => {
        app.mostra('Edição cancelada');
        terminaEdicao();
    });
    try { edicao = JSON.parse(localStorage.getItem(CHAVE_EDICAO) || 'null'); } catch (e) { edicao = null; }
    mostraFaixa();

    $('btnGerenciarVar').addEventListener('click', () => {
        desenhaLista();
        app.abreJanela('janelaVariaveis');
        carrega();
    });

    window.addEventListener('musecontrol:projeto', carrega); // trocou de projeto
    carrega();
})();
