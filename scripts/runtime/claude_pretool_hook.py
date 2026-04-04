#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_SRC = REPO_ROOT / "cli" / "src"
if str(CLI_SRC) not in sys.path:
    sys.path.insert(0, str(CLI_SRC))

from policy_federation.claude_hooks import main


if __name__ == "__main__":
    main()
