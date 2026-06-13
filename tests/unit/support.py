from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_SRC = REPO_ROOT / "cli" / "src"
if str(CLI_SRC) not in sys.path:
    sys.path.insert(0, str(CLI_SRC))


def echo_argv(message: str = "ok") -> list[str]:
    """Return a cross-platform argv that prints *message* to stdout."""
    if sys.platform == "win32":
        return [sys.executable, "-c", f"print({message!r})"]
    return ["/bin/echo", message]
