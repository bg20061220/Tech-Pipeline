import os
import subprocess
import sys
from pathlib import Path


def main():
    app = Path(__file__).parent / "app.py"

    env = os.environ.copy()
    env.setdefault("STREAMLIT_THEME_PRIMARY_COLOR", "#1A5FAD")
    env.setdefault("STREAMLIT_THEME_BACKGROUND_COLOR", "#FFFFFF")
    env.setdefault("STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR", "#F0F4FA")
    env.setdefault("STREAMLIT_THEME_TEXT_COLOR", "#1A1A2E")
    env.setdefault("STREAMLIT_THEME_FONT", "sans serif")

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app)],
        env=env,
        check=False,
    )
