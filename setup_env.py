"""
Survey Pipeline — one-command launcher.

First time:   python setup_env.py   →  creates .venv, installs deps, launches app
Every time:   python setup_env.py   →  launches app using existing .venv
"""

import subprocess
import sys
from pathlib import Path


def main():
    repo = Path(__file__).parent.resolve()
    venv = repo / ".venv"

    # Venv binary paths differ by OS
    if sys.platform == "win32":
        python = venv / "Scripts" / "python.exe"
        pip    = venv / "Scripts" / "pip.exe"
    else:
        python = venv / "bin" / "python"
        pip    = venv / "bin" / "pip"

    # Create venv if it doesn't exist
    if not venv.exists():
        print("[ setup ] Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        print("[ setup ] Installing dependencies (this may take a minute)...")
        subprocess.run([str(pip), "install", "--quiet", "-e", str(repo)], check=True)
        print("[ setup ] Done.\n")
    else:
        # Ensure the package is installed (handles case where venv exists but install was incomplete)
        result = subprocess.run(
            [str(python), "-c", "import streamlit, groq, fpdf, plotly"],
            capture_output=True,
        )
        if result.returncode != 0:
            print("[ setup ] Installing missing dependencies...")
            subprocess.run([str(pip), "install", "--quiet", "-e", str(repo)], check=True)

    print("[ survey-pipeline ] Starting... (press Ctrl+C to stop)\n")
    app = repo / "app.py"
    subprocess.run([str(python), "-m", "streamlit", "run", str(app)])


if __name__ == "__main__":
    main()
