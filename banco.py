"""Banco de dados do MuseControl (SQLite, um arquivo só: dados/musecontrol.db).

Tabelas:
- projetos:  uma por música (nome, compasso, armadura)
- variaveis: trechos guardados; projeto_id = 0 é a biblioteca geral (vale em
             todos os projetos)
- rascunhos: o que está escrito e ainda não foi enviado, um por projeto, com
             número de versão para dois aparelhos não apagarem o trabalho um
             do outro

Na primeira vez, as variáveis do antigo dados/variaveis.json viram gerais.
"""

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager

import caminhos

PASTA = caminhos.pasta_dados()  # ./dados no código; pasta do usuário no instalado
ARQUIVO = os.path.join(PASTA, "musecontrol.db")
JSON_ANTIGO = os.path.join(PASTA, "variaveis.json")
GERAL = 0  # projeto_id das variáveis gerais

ESQUEMA = """
CREATE TABLE IF NOT EXISTS projetos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    comp_num    INTEGER NOT NULL DEFAULT 4,
    comp_den    INTEGER NOT NULL DEFAULT 4,
    armadura    INTEGER NOT NULL DEFAULT 0,
    criado      TEXT NOT NULL,
    atualizado  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS variaveis (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto_id  INTEGER NOT NULL DEFAULT 0,
    nome        TEXT NOT NULL COLLATE NOCASE,
    eventos     TEXT NOT NULL,
    ordem       REAL NOT NULL,
    criada      TEXT NOT NULL,
    UNIQUE (projeto_id, nome)
);
CREATE TABLE IF NOT EXISTS rascunhos (
    projeto_id  INTEGER PRIMARY KEY,
    eventos     TEXT NOT NULL DEFAULT '[]',
    versao      INTEGER NOT NULL DEFAULT 0,
    atualizado  TEXT NOT NULL
);
"""


def agora():
    return time.strftime("%Y-%m-%d %H:%M:%S")


_iniciados = set()
_init_lock = threading.Lock()


def conectar():
    """Abre o banco (criando as tabelas e migrando na primeira vez)."""
    os.makedirs(os.path.dirname(ARQUIVO), exist_ok=True)
    con = sqlite3.connect(ARQUIVO, timeout=10)
    con.row_factory = sqlite3.Row
    with _init_lock:
        if ARQUIVO not in _iniciados:
            con.execute("PRAGMA journal_mode=WAL")  # celular e PC gravando ao mesmo tempo
            con.executescript(ESQUEMA)
            _migrar_json(con)
            _garantir_projeto(con)
            con.commit()
            _iniciados.add(ARQUIVO)
    return con


@contextmanager
def sessao():
    """with banco.sessao() as con: ...  grava no fim (ou desfaz se der erro) e fecha."""
    con = conectar()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _migrar_json(con):
    """Traz as variáveis do arquivo antigo (uma vez só) como variáveis gerais."""
    if not os.path.exists(JSON_ANTIGO):
        return
    if con.execute("SELECT COUNT(*) FROM variaveis").fetchone()[0]:
        return
    try:
        with open(JSON_ANTIGO, encoding="utf-8") as f:
            antigas = json.load(f)
    except (OSError, ValueError):
        antigas = []
    for i, v in enumerate(antigas if isinstance(antigas, list) else []):
        try:
            con.execute(
                "INSERT OR IGNORE INTO variaveis (projeto_id, nome, eventos, ordem, criada) VALUES (?, ?, ?, ?, ?)",
                (GERAL, v["nome"], json.dumps(v["eventos"]), i + 1, v.get("criada") or agora()))
        except (KeyError, TypeError):
            continue
    con.commit()
    os.replace(JSON_ANTIGO, JSON_ANTIGO + ".migrado")  # guarda o antigo como cópia de segurança


def _garantir_projeto(con):
    """Sempre existe pelo menos um projeto."""
    if not con.execute("SELECT 1 FROM projetos LIMIT 1").fetchone():
        t = agora()
        con.execute("INSERT INTO projetos (nome, criado, atualizado) VALUES (?, ?, ?)",
                    ("Primeiro projeto", t, t))


def nome_livre(con, tabela, nome, projeto_id=None):
    """'baixo' -> 'baixo 2', 'baixo 3'... até achar um nome que não existe."""
    def existe(n):
        if tabela == "projetos":
            return con.execute("SELECT 1 FROM projetos WHERE nome = ?", (n,)).fetchone()
        return con.execute("SELECT 1 FROM variaveis WHERE projeto_id = ? AND nome = ?",
                           (projeto_id, n)).fetchone()
    if not existe(nome):
        return nome
    k = 2
    while True:
        sufixo = f" {k}"
        candidato = nome[:40 - len(sufixo)].rstrip() + sufixo
        if not existe(candidato):
            return candidato
        k += 1
