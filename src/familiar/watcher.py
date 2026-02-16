"""File watcher: polling for new jobs."""

import signal
import sys
import time

from .config import POLL_INTERVAL, SETTLE_DELAY, FamiliarConfig
from .dispatcher import log, process_file


def watch(cfg: FamiliarConfig) -> None:
    """Watch Jobs/ for new .md files using polling."""
    jobs = cfg.vault_path / "Jobs"
    log(cfg.name, f"Watching {jobs} (interval={POLL_INTERVAL}s)")

    def cleanup(sig, frame):
        log(cfg.name, "Shutting down")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    seen: set[str] = set()
    while True:
        current = {f.name for f in jobs.glob("*.md")}
        new = current - seen
        for name in sorted(new):
            time.sleep(SETTLE_DELAY)
            f = jobs / name
            if f.exists():
                process_file(f, cfg)
        seen = {f.name for f in jobs.glob("*.md")}
        time.sleep(POLL_INTERVAL)
