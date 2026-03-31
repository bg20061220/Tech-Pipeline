import subprocess
import sys
from pathlib import Path


def main():
    app = Path(__file__).parent / "app.py"
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app)],
        cwd=str(app.parent),
        check=False,
    )
