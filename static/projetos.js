// Projetos: um por música. Guarda no computador (projetos.py) o compasso, a
// armadura, as variáveis e o rascunho (o que está escrito e não foi enviado).
// O rascunho salva sozinho pouco depois de cada mudança.
(function () {
    'use strict';

    const app = window.MuseControl;
    const $ = (id) => document.getElementById(id);
    const CHAVE = 'musecontrol-projeto';
    const ESPERA_MS = 800;

    let projetos = [];
    let atual = null;        // id do projeto aberto
    let versao = 0;          // versão do rascunho que esta página conhece
    let ultimoSalvo = '[]';  // rascunho como está no computador
    let pausado = false;     // editando uma variável: não salva o rascunho
    let abrindo = false;     // trocando de projeto: não salva nada no meio da troca
    let timer = null;
    let salvando = false;
    let deNovo = false;

    function pedido(url, opcoes) {
        return fetch(url, opcoes).then((r) => r.json().then((d) => Object.assign({ status: r.status }, d)));
    }
    function json(metodo, corpo) {
        return { method: metodo, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo || {}) };
    }
    function lembra(id) { try { localStorage.setItem(CHAVE, String(id)); } catch (e) { /* ignora */ } }
    function lembrado() { try { return Number(localStorage.getItem(CHAVE)) || null; } catch (e) { return null; } }
    function editando() { try { return !!localStorage.getItem('musecontrol-edicao'); } catch (e) { return false; } }

    function estado(txt, erro) {
        $('salvoStatus').textContent = txt;
        $('salvoStatus').classList.toggle('erro', !!erro);
    }
    function projetoAtual() { return projetos.find((p) => p.id === atual) || null; }
    function mostraNome() {
        const p = projetoAtual();
        $('nomeProjeto').textContent = p ? p.nome : '…';
    }

    // ---- salvar o rascunho --------------------------------------------------
    function conteudo() { return JSON.stringify(app.eventos()); }

    function agendar() {
        if (pausado || abrindo || atual === null) return;
        if (conteudo() === ultimoSalvo) return;
        estado('…');
        clearTimeout(timer);
        timer = setTimeout(salvar, ESPERA_MS);
    }

    function salvar(sair) {
        clearTimeout(timer);
        if (pausado || abrindo || atual === null) return Promise.resolve();
        const texto = conteudo();
        if (texto === ultimoSalvo) { estado('✓ salvo'); return Promise.resolve(); }
        if (salvando) { deNovo = true; return Promise.resolve(); }
        salvando = true;
        estado('salvando…');
        const id = atual;
        const opcoes = json('PUT', { eventos: JSON.parse(texto), versao });
        if (sair) opcoes.keepalive = true; // fechando a página: termina de enviar mesmo assim
        return pedido('/pulso/projetos/' + id + '/rascunho', opcoes).then((d) => {
            if (id !== atual) return;
            if (d.ok) {
                versao = d.versao;
                ultimoSalvo = texto;
                estado('✓ salvo');
            } else if (d.conflito) {
                // outro aparelho salvou antes: fica com o mais novo e avisa
                versao = d.versao;
                ultimoSalvo = JSON.stringify(d.eventos);
                app.trocaEventos(d.eventos);
                app.mostra('Este projeto foi mudado em outro aparelho. Carreguei a versão mais nova.');
                estado('✓ salvo');
            } else {
                estado('⚠ não salvo', true);
            }
        }).catch(() => estado('⚠ sem conexão: não salvo', true))
            .finally(() => { salvando = false; if (deNovo) { deNovo = false; agendar(); } });
    }

    // ---- abrir / trocar de projeto -----------------------------------------
    function abre(id, inicial) {
        if (editando() && !inicial) { app.mostra('Termine de editar a variável antes de trocar de projeto'); return Promise.resolve(); }
        const antes = atual !== null && !inicial ? salvar() : Promise.resolve();
        return antes.then(() => { abrindo = true; return pedido('/pulso/projetos/' + id + '/rascunho'); }).then((d) => {
            if (!d.ok) throw new Error(d.erro);
            atual = id;
            lembra(id);
            const p = projetoAtual();
            if (p) app.defineAjustes(p.compasso, p.armadura);
            versao = d.versao;
            ultimoSalvo = JSON.stringify(d.eventos);
            mostraNome();
            pausado = editando(); // editando variável: o que está na tela é a variável
            let levarLocal = false;
            if (!pausado) {
                levarLocal = inicial && d.versao === 0 && app.eventos().length > 0;
                if (!levarLocal) app.trocaEventos(d.eventos);
            }
            abrindo = false;
            estado('✓ salvo');
            if (levarLocal) agendar(); // 1ª vez com projetos: leva o que já estava escrito para o computador
            window.dispatchEvent(new CustomEvent('musecontrol:projeto', { detail: { id } }));
        }).finally(() => { abrindo = false; });
    }

    function carregaLista() {
        return pedido('/pulso/projetos').then((d) => { projetos = d.projetos || []; desenhaLista(); mostraNome(); });
    }

    // outro aparelho pode ter mexido: ao voltar para esta tela, confere
    function conferir() {
        if (atual === null || pausado || salvando || conteudo() !== ultimoSalvo) return;
        pedido('/pulso/projetos/' + atual + '/rascunho').then((d) => {
            if (d.ok && d.versao !== versao) {
                versao = d.versao;
                ultimoSalvo = JSON.stringify(d.eventos);
                app.trocaEventos(d.eventos);
                app.mostra('Atualizado com o que foi escrito em outro aparelho');
            }
        }).catch(() => { /* sem conexão */ });
        carregaLista();
    }

    // ---- janela de projetos ------------------------------------------------------
    function desenhaLista() {
        const box = $('listaProjetos');
        box.innerHTML = '';
        projetos.forEach((p) => {
            const linha = document.createElement('div');
            linha.className = 'linha' + (p.id === atual ? ' atual' : '');
            const nome = document.createElement('span');
            nome.className = 'nome';
            nome.textContent = p.nome + ' ';
            const info = document.createElement('small');
            info.textContent = p.compasso.num + '/' + p.compasso.den + ' · ' + p.variaveis +
                (p.variaveis === 1 ? ' variável' : ' variáveis');
            nome.appendChild(info);
            if (p.id === atual) {
                const tag = document.createElement('span');
                tag.className = 'atual-tag';
                tag.textContent = ' · aberto';
                nome.appendChild(tag);
            }
            const botoes = document.createElement('div');
            botoes.className = 'acoes-var';
            const botao = (texto, fn, classe) => {
                const b = document.createElement('button');
                b.textContent = texto;
                if (classe) b.className = classe;
                b.addEventListener('click', () => fn(b));
                botoes.appendChild(b);
            };
            if (p.id !== atual) botao('Abrir', () => abre(p.id).then(() => { app.fechaJanelas(); app.mostra('Projeto "' + p.nome + '" aberto'); }), 'principal');
            botao('Renomear', () => renomeia(linha, p));
            botao('Exportar', () => { window.location.href = '/pulso/projetos/' + p.id + '/exportar'; });
            botao('Apagar', (b) => apaga(b, p), 'apagar');
            linha.append(nome, botoes);
            box.appendChild(linha);
        });
    }

    function renomeia(linha, p) {
        linha.innerHTML = '';
        const campo = document.createElement('input');
        campo.type = 'text';
        campo.maxLength = 40;
        campo.value = p.nome;
        const ok = document.createElement('button');
        ok.className = 'principal';
        ok.textContent = 'OK';
        const cancela = document.createElement('button');
        cancela.textContent = 'Cancelar';
        const salva = () => {
            const novo = campo.value.trim();
            if (!novo || novo === p.nome) { desenhaLista(); return; }
            pedido('/pulso/projetos/' + p.id + '/renomear', json('POST', { novo }))
                .then((d) => { if (!d.ok) app.mostra(d.erro); carregaLista(); });
        };
        ok.addEventListener('click', salva);
        cancela.addEventListener('click', desenhaLista);
        campo.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); salva(); } });
        linha.append(campo, ok, cancela);
        campo.focus();
        campo.select();
    }

    function apaga(b, p) {
        if (!b.classList.contains('confirmar')) { // pede um 2º toque
            b.classList.add('confirmar');
            b.textContent = 'Apagar tudo?';
            setTimeout(() => { b.classList.remove('confirmar'); b.textContent = 'Apagar'; }, 3000);
            return;
        }
        pedido('/pulso/projetos/' + p.id, { method: 'DELETE' }).then((d) => {
            if (!d.ok) { app.mostra(d.erro); return; }
            projetos = d.projetos;
            app.mostra('Projeto "' + p.nome + '" apagado');
            if (p.id === atual) {
                atual = null;
                abre(projetos[0].id, true).then(desenhaLista);
            } else {
                desenhaLista();
            }
        });
    }

    $('criarProjeto').addEventListener('click', () => {
        const nome = $('nomeNovoProjeto').value.trim();
        if (!nome) { $('nomeNovoProjeto').focus(); return; }
        // novo projeto começa com o compasso e a armadura atuais
        pedido('/pulso/projetos', json('POST', { nome, compasso: app.compasso(), armadura: app.armadura() }))
            .then((d) => {
                if (!d.ok) { app.mostra(d.erro); return; }
                $('nomeNovoProjeto').value = '';
                return carregaLista().then(() => abre(d.projeto.id)).then(() => {
                    app.fechaJanelas();
                    app.mostra('Projeto "' + d.projeto.nome + '" criado');
                });
            });
    });
    $('nomeNovoProjeto').addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); $('criarProjeto').click(); } });

    $('arquivoImportar').addEventListener('change', (ev) => {
        const arquivo = ev.target.files[0];
        ev.target.value = '';
        if (!arquivo) return;
        arquivo.text().then((texto) => {
            let dados;
            try { dados = JSON.parse(texto); } catch (e) { app.mostra('Arquivo inválido'); return; }
            return pedido('/pulso/projetos/importar', json('POST', dados)).then((d) => {
                if (!d.ok) { app.mostra(d.erro); return; }
                return carregaLista().then(() => abre(d.projeto.id)).then(() => {
                    app.fechaJanelas();
                    app.mostra('Projeto "' + d.projeto.nome + '" importado');
                });
            });
        }).catch(() => app.mostra('Não consegui importar'));
    });

    $('abaProjeto').addEventListener('click', () => {
        app.abreJanela('janelaProjetos');
        carregaLista();
    });

    // compasso / armadura mudados em ⚙: são do projeto
    window.addEventListener('musecontrol:ajustes', () => {
        if (atual === null) return;
        pedido('/pulso/projetos/' + atual, json('PATCH', { compasso: app.compasso(), armadura: app.armadura() }))
            .then((d) => { if (d.ok) { projetos = projetos.map((p) => (p.id === atual ? d.projeto : p)); } });
    });

    app.aoMudar(agendar);
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') salvar(true);
        else conferir();
    });
    window.addEventListener('pagehide', () => salvar(true));

    // usado por variaveis.js
    window.MuseControlProjeto = {
        atual: () => atual,
        pausa(sim) { pausado = sim; if (!sim) agendar(); },
    };

    carregaLista().then(() => {
        const id = projetos.some((p) => p.id === lembrado()) ? lembrado() : projetos[0].id;
        return abre(id, true);
    }).catch(() => estado('⚠ sem conexão', true));
})();
