from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_FILE = "ui/streamlit_app.py"
HOST = "127.0.0.1"
PORT = 8510


def main() -> None:
    os.chdir(ROOT_DIR)
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            APP_FILE,
            "--server.address",
            HOST,
            "--server.port",
            str(PORT),
        ],
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
