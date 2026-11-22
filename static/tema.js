// Aplica o tema (escuro / claro / automático) antes da página aparecer,
// para não piscar escuro -> claro. A escolha fica em ⚙ → Tema.
(function () {
    'use strict';
    var tema = 'escuro';
    try { tema = localStorage.getItem('musecontrol-tema') || 'escuro'; } catch (e) { /* sem armazenamento */ }
    document.documentElement.setAttribute('data-tema', tema);
    window.MuseControlTema = {
        atual: function () { return document.documentElement.getAttribute('data-tema'); },
        muda: function (novo) {
            document.documentElement.setAttribute('data-tema', novo);
            try { localStorage.setItem('musecontrol-tema', novo); } catch (e) { /* ignora */ }
        },
    };
})();
