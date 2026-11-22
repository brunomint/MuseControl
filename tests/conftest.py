import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pytest
from flask import Flask


@pytest.fixture
def banco_teste(tmp_path, monkeypatch):
    """Banco SQLite novo em pasta temporária (nunca mexe em dados/)."""
    import banco
    monkeypatch.setattr(banco, "ARQUIVO", str(tmp_path / "dados" / "musecontrol.db"))
    monkeypatch.setattr(banco, "JSON_ANTIGO", str(tmp_path / "dados" / "variaveis.json"))
    banco._iniciados.clear()
    return tmp_path


@pytest.fixture
def c(banco_teste):
    import variaveis, projetos
    app = Flask(__name__)
    app.register_blueprint(variaveis.bp)
    app.register_blueprint(projetos.bp)
    return app.test_client()
