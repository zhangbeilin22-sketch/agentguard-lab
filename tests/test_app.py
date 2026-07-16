from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_starts_without_exception():
    app_path = Path(__file__).resolve().parent.parent / "app.py"

    app = AppTest.from_file(str(app_path)).run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "AgentGuard Lab"

