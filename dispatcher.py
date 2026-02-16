#!/usr/bin/env python3
"""Familiar: File-based task runner for Obsidian using Claude Code CLI."""

import argparse
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEFAULT_VAULT_PATH = Path.home() / "Obsidian" / "System" / "Familiar"
DEFAULT_TIMEOUT = 300
SETTLE_DELAY = 0.5
POLL_INTERVAL = 1.0


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def ensure_dirs(base: Path) -> None:
    for name in ("Jobs", "Processing", "Done", "Failed"):
        (base / name).mkdir(parents=True, exist_ok=True)


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown. Returns (metadata dict, body)."""
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    raw = content[3:end].strip()
    meta = {}
    for line in raw.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip()
            if val.isdigit():
                val = int(val)
            meta[key.strip()] = val
    body = content[end + 3:].lstrip("\n")
    return meta, body


def serialize_frontmatter(meta: dict, body: str) -> str:
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines) + body


def unique_dest(dest: Path) -> Path:
    """If dest exists, append -1, -2, etc. to the stem."""
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    i = 1
    while True:
        candidate = parent / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def build_prompt(base: Path, meta: dict, body: str) -> str:
    parts = []
    system_prompt = base / "system-prompt.md"
    if system_prompt.exists():
        parts.append(system_prompt.read_text().strip())

    parts.append(
        "Execute the following task. Write your full output in well-structured markdown."
    )

    iteration = meta.get("iteration", 1)
    if iteration > 1:
        parts.append(
            f"This is iteration {iteration}. There may be previous output and "
            "reviewer notes below. Pay attention to feedback and build on prior work."
        )

    parts.append(body)
    return "\n\n".join(parts)


def process_file(filepath: Path, base: Path, timeout: int) -> None:
    name = filepath.name
    processing = base / "Processing" / name
    done_dir = base / "Done"
    failed_dir = base / "Failed"

    # Atomic move to Processing
    try:
        shutil.move(str(filepath), str(processing))
    except FileNotFoundError:
        log(f"Skipped {name} (already picked up)")
        return

    log(f"Processing: {name}")

    content = processing.read_text()
    meta, body = parse_frontmatter(content)

    # Increment iteration
    iteration = meta.get("iteration", 0) + 1
    meta["iteration"] = iteration

    # Build prompt
    prompt = build_prompt(base, meta, body)

    # Call Claude CLI
    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(base),
        )
    except FileNotFoundError:
        error_msg = (
            "Error: Claude CLI not found. "
            "Install with: npm install -g @anthropic-ai/claude-code"
        )
        log(f"Failed: {name} — claude CLI not found")
        meta["status"] = "failed"
        meta["last_run"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        run_block = _run_block(iteration, error_msg)
        processing.write_text(serialize_frontmatter(meta, body + run_block))
        dest = unique_dest(failed_dir / name)
        shutil.move(str(processing), str(dest))
        return
    except subprocess.TimeoutExpired:
        error_msg = f"Error: Claude CLI timed out after {timeout} seconds."
        log(f"Failed: {name} — timeout")
        meta["status"] = "failed"
        meta["last_run"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        run_block = _run_block(iteration, error_msg)
        processing.write_text(serialize_frontmatter(meta, body + run_block))
        dest = unique_dest(failed_dir / name)
        shutil.move(str(processing), str(dest))
        return

    if result.returncode != 0:
        error_msg = f"Error: Claude CLI exited with code {result.returncode}.\n\n```\n{result.stderr.strip()}\n```"
        log(f"Failed: {name} — exit code {result.returncode}")
        meta["status"] = "failed"
        meta["last_run"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        run_block = _run_block(iteration, error_msg)
        processing.write_text(serialize_frontmatter(meta, body + run_block))
        dest = unique_dest(failed_dir / name)
        shutil.move(str(processing), str(dest))
        return

    # Success
    output = result.stdout.strip()
    meta["status"] = "done"
    meta["last_run"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    run_block = _run_block(iteration, output)
    processing.write_text(serialize_frontmatter(meta, body + run_block))
    dest = unique_dest(done_dir / name)
    shutil.move(str(processing), str(dest))
    log(f"Done: {name} → {dest.name}")


def _run_block(iteration: int, content: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"\n---\n\n## Run {iteration}\n*{ts}*\n\n{content}\n"


def drain_jobs(base: Path, timeout: int) -> None:
    """Process any .md files already sitting in Jobs/."""
    jobs = base / "Jobs"
    for f in sorted(jobs.glob("*.md")):
        process_file(f, base, timeout)


def watch_fswatch(base: Path, timeout: int) -> None:
    """Watch Jobs/ using fswatch."""
    jobs = str(base / "Jobs")
    cmd = [
        "fswatch",
        "-0",              # null-delimited
        "--event", "Created",
        "--event", "MovedTo",
        jobs,
    ]
    log(f"Watching {jobs} with fswatch")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

    def cleanup(sig, frame):
        proc.terminate()
        log("Shutting down")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    buf = b""
    while True:
        chunk = proc.stdout.read(1)
        if not chunk:
            break
        if chunk == b"\0":
            path = Path(buf.decode().strip())
            buf = b""
            if path.suffix == ".md" and path.exists():
                time.sleep(SETTLE_DELAY)
                process_file(path, base, timeout)
        else:
            buf += chunk


def watch_poll(base: Path, timeout: int) -> None:
    """Watch Jobs/ using polling fallback."""
    jobs = base / "Jobs"
    log(f"Watching {jobs} with polling (interval={POLL_INTERVAL}s)")

    def cleanup(sig, frame):
        log("Shutting down")
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
                process_file(f, base, timeout)
        seen = {f.name for f in jobs.glob("*.md")}
        time.sleep(POLL_INTERVAL)


def main() -> None:
    parser = argparse.ArgumentParser(description="Familiar: file-based task runner")
    parser.add_argument(
        "--vault-path",
        type=Path,
        default=DEFAULT_VAULT_PATH,
        help=f"Path to Familiar directory (default: {DEFAULT_VAULT_PATH})",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Use polling instead of fswatch",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Claude CLI timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args()

    base = args.vault_path.expanduser().resolve()
    ensure_dirs(base)
    log(f"Familiar started — vault: {base}")

    # Drain existing jobs
    drain_jobs(base, args.timeout)

    # Choose watcher
    use_poll = args.poll
    if not use_poll and shutil.which("fswatch") is None:
        log("fswatch not found, falling back to polling")
        use_poll = True

    if use_poll:
        watch_poll(base, args.timeout)
    else:
        watch_fswatch(base, args.timeout)


if __name__ == "__main__":
    main()
