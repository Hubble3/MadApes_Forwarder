"""
Reset local runtime state for a clean start.

This deletes:
- signals.db (tracking database)
- session.session / session.session-journal (Telethon login session)

Run:
  python reset_local_state.py
"""

from __future__ import annotations

import os
import glob

FILES = ["signals.db"]


def main() -> None:
    # Remove all Telethon session files in this folder (supports SESSION_NAME usage).
    session_files = glob.glob("*.session") + glob.glob("*.session-journal")
    targets = list(dict.fromkeys(FILES + session_files))  # keep order, remove dupes

    removed = []
    missing = []
    for f in targets:
        if os.path.exists(f):
            os.remove(f)
            removed.append(f)
        else:
            missing.append(f)

    print("✅ Reset complete.")
    if removed:
        print("Removed:")
        for f in removed:
            print(f" - {f}")
    if missing:
        print("Already missing:")
        for f in missing:
            print(f" - {f}")


if __name__ == "__main__":
    main()

