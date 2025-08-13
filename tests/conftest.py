import os, sys, importlib
from pathlib import Path
import pytest

@pytest.fixture()
def app_module(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEVICE_MASTER_KEY", "test-master-key")

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    app_module = importlib.import_module("app")
    importlib.reload(app_module)
    return app_module

@pytest.fixture()
def client(app_module):
    app = app_module.app
    db = app_module.db
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()
