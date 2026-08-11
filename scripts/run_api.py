from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


ROOT_DIR = Path(__file__).resolve().parents[1]
APP = "rag_luat_gt.api.main:app"
HOST = "127.0.0.1"
PORT = 8010
RELOAD = False


def main() -> None:
    os.chdir(ROOT_DIR)
    sys.path.insert(0, str(ROOT_DIR))
    uvicorn.run(APP, host=HOST, port=PORT, reload=RELOAD)


if __name__ == "__main__":
    main()
