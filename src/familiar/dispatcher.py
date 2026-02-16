"""Core processing: frontmatter, file lifecycle, Claude invocation."""

import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from .config import FamiliarConfig


def log(name: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{name}] {msg}", flush=True)


class Spinner:
    """Animated spinner with elapsed time for long-running operations."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message
        self._stop = threading.Event()
        self._thread = None

    def _spin(self):
        start = time.monotonic()
        i = 0
        while not self._stop.is_set():
            elapsed = int(time.monotonic() - start)
            m, s = divmod(elapsed, 60)
            frame = self.FRAMES[i % len(self.FRAMES)]
            ts = datetime.now().strftime("%H:%M:%S")
            line = f"\r[{ts}] [{self.name}] {frame} {self.message} ({m}:{s:02d})"
            sys.stdout.write(line)
            sys.stdout.flush()
            i += 1
            self._stop.wait(0.1)
        # Clear the spinner line
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()

    def __enter__(self):
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._stop.set()
        self._thread.join()


def ensure_dirs(base: Path) -> None:
    for dirname in ("Jobs", "Processing", "Done", "Failed"):
        (base / dirname).mkdir(parents=True, exist_ok=True)


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
    body = content[end + 3 :].lstrip("\n")
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


def _run_block(name: str, iteration: int, content: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    # Indent every line of content for the callout block
    indented = "\n".join(f"> {line}" if line else ">" for line in content.splitlines())
    return f"\n\n> [!quote] {name} — Report {iteration} at {ts}\n{indented}\n"


def build_prompt(cfg: FamiliarConfig, meta: dict, body: str) -> str:
    parts = []
    system_prompt = cfg.vault_path / "system-prompt.md"
    if system_prompt.exists():
        parts.append(system_prompt.read_text().strip())

    # Build path boundary instructions
    all_paths = [str(cfg.vault_path)] + cfg.allowed_paths
    path_list = "\n".join(f"- {p}" for p in all_paths)

    parts.append(
        f"You are {cfg.name}. "
        "Execute the following task. Write your full output in well-structured markdown.\n\n"
        "Your previous responses appear in Obsidian callout blocks (lines starting with `>`). "
        "The human's messages are plain text outside callouts. "
        "Do NOT wrap your own response in a callout — that will be done for you.\n\n"
        "IMPORTANT: You may only access files within these directories:\n"
        f"{path_list}\n"
        "Do not read, write, or execute anything outside these paths."
    )

    iteration = meta.get("iteration", 1)
    if iteration > 1:
        parts.append(
            f"This is iteration {iteration}. There may be previous output and "
            "reviewer notes below. Pay attention to feedback and build on prior work."
        )

    parts.append(body)
    return "\n\n".join(parts)


def process_file(filepath: Path, cfg: FamiliarConfig) -> None:
    name = filepath.name
    processing = cfg.vault_path / "Processing" / name
    done_dir = cfg.vault_path / "Done"
    failed_dir = cfg.vault_path / "Failed"

    # Atomic move to Processing
    try:
        shutil.move(str(filepath), str(processing))
    except FileNotFoundError:
        log(cfg.name, f"Skipped {name} (already picked up)")
        return

    log(cfg.name, f"Processing: {name}")

    content = processing.read_text()
    meta, body = parse_frontmatter(content)

    # Increment iteration
    iteration = meta.get("iteration", 0) + 1
    meta["iteration"] = iteration
    meta["status"] = "processing"
    meta["last_run"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Write in-progress marker so it's visible in Obsidian
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    processing_marker = f"\n\n> [!info] {cfg.name} — Working on report {iteration}...\n> Started at {ts}\n"
    processing.write_text(serialize_frontmatter(meta, body + processing_marker))

    # Build prompt
    prompt = build_prompt(cfg, meta, body)

    # Call Claude CLI
    try:
        with Spinner(cfg.name, f"Working on {name}"):
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions", prompt],
                capture_output=True,
                text=True,
                timeout=cfg.timeout,
                cwd=str(cfg.vault_root),
            )
    except FileNotFoundError:
        error_msg = (
            "Error: Claude CLI not found. "
            "Install with: npm install -g @anthropic-ai/claude-code"
        )
        log(cfg.name, f"Failed: {name} — claude CLI not found")
        meta["status"] = "failed"
        meta["last_run"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        run_block = _run_block(cfg.name, iteration, error_msg)
        processing.write_text(serialize_frontmatter(meta, body + run_block))
        dest = unique_dest(failed_dir / name)
        shutil.move(str(processing), str(dest))
        return
    except subprocess.TimeoutExpired:
        error_msg = f"Error: Claude CLI timed out after {cfg.timeout} seconds."
        log(cfg.name, f"Failed: {name} — timeout")
        meta["status"] = "failed"
        meta["last_run"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        run_block = _run_block(cfg.name, iteration, error_msg)
        processing.write_text(serialize_frontmatter(meta, body + run_block))
        dest = unique_dest(failed_dir / name)
        shutil.move(str(processing), str(dest))
        return

    if result.returncode != 0:
        error_msg = f"Error: Claude CLI exited with code {result.returncode}.\n\n```\n{result.stderr.strip()}\n```"
        log(cfg.name, f"Failed: {name} — exit code {result.returncode}")
        meta["status"] = "failed"
        meta["last_run"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        run_block = _run_block(cfg.name, iteration, error_msg)
        processing.write_text(serialize_frontmatter(meta, body + run_block))
        dest = unique_dest(failed_dir / name)
        shutil.move(str(processing), str(dest))
        return

    # Success
    output = result.stdout.strip()
    meta["status"] = "done"
    meta["last_run"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    run_block = _run_block(cfg.name, iteration, output)
    processing.write_text(serialize_frontmatter(meta, body + run_block))
    dest = unique_dest(done_dir / name)
    shutil.move(str(processing), str(dest))
    log(cfg.name, f"Done: {name} → {dest.name}")


def drain_jobs(cfg: FamiliarConfig) -> None:
    """Process any .md files already sitting in Jobs/."""
    jobs = cfg.vault_path / "Jobs"
    for f in sorted(jobs.glob("*.md")):
        process_file(f, cfg)
