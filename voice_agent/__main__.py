from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from .daemon.app import VoiceDaemon, settings_from_environment


def main() -> None:
    defaults = settings_from_environment()
    parser = argparse.ArgumentParser(description="Run the persistent Pi voice daemon")
    parser.add_argument("--socket", type=Path, default=defaults.socket_path)
    parser.add_argument("--state", type=Path, default=defaults.state_path)
    parser.add_argument("--pi-session-dir", type=Path, default=defaults.pi_session_dir)
    parser.add_argument("--pi-command", nargs="+", default=list(defaults.pi_command))
    args = parser.parse_args()
    settings = replace(
        defaults,
        socket_path=args.socket,
        state_path=args.state,
        pi_session_dir=args.pi_session_dir,
        pi_command=tuple(args.pi_command),
    )
    daemon = VoiceDaemon(settings)
    try:
        daemon.serve_forever()
    except KeyboardInterrupt:
        daemon.close()


if __name__ == "__main__":
    main()
