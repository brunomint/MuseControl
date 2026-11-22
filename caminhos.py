"""Onde ficam os arquivos do programa e onde ficam os dados do usuário.

- Rodando do código (desenvolvimento): dados em ./dados, como sempre.
- Programa empacotado (.exe do Windows): os arquivos vêm de dentro do pacote e
  os dados vão para a pasta do usuário (%APPDATA%\\MuseControl), que não some
  ao atualizar ou reinstalar.
- MUSECONTROL_DADOS=/algum/lugar manda em tudo (o instalador do Linux usa).
"""

import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))


def empacotado():
    """True quando roda como .exe (PyInstaller)."""
    return getattr(sys, "frozen", False)


def pasta_recursos():
    """Pasta com templates/ e static/."""
    return getattr(sys, "_MEIPASS", AQUI) if empacotado() else AQUI


def pasta_dados():
    """Pasta do banco (musecontrol.db)."""
    escolhida = os.environ.get("MUSECONTROL_DADOS")
    if escolhida:
        return os.path.abspath(os.path.expanduser(escolhida))
    if not empacotado():
        return os.path.join(AQUI, "dados")
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "MuseControl")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/MuseControl")
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "musecontrol", "dados")
