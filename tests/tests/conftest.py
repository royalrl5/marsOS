import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["MARSOS_DRY_RUN"] = "1"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("MARSOS_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()


def pytest_sessionfinish(session, exitstatus):
    try:
        from marsos.ui import workers
        workers.wait_idle(3)
    except Exception:
        pass
