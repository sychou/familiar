"""CLI entry point: familiar run, familiar init."""

import argparse
import shutil
import sys
from pathlib import Path

from .config import CONFIG_PATH, FamiliarConfig, load_config, resolve_config
from .dispatcher import drain_jobs, ensure_dirs, log
from .watcher import watch

BANNER = r"""
            ('-.     _   .-')                                 ('-.     _  .-')
           ( OO ).-.( '.( OO )_                              ( OO ).-.( \( -O )
   ,------./ . --. / ,--.   ,--.) ,-.-')  ,--.      ,-.-')   / . --. / ,------.
('-| _.---'| \-.  \  |   `.'   |  |  |OO) |  |.-')  |  |OO)  | \-.  \  |   /`. '
(OO|(_\  .-'-'  |  | |         |  |  |  \ |  | OO ) |  |  \.-'-'  |  | |  /  | |
/  |  '--.\| |_.'  | |  |'.'|  |  |  |(_/ |  |`-' | |  |(_/ \| |_.'  | |  |_.' |
\_)|  .--' |  .-.  | |  |   |  | ,|  |_.'(|  '---.',|  |_.'  |  .-.  | |  .  '.'
  \|  |_)  |  | |  | |  |   |  |(_|  |    |      |(_|  |     |  | |  | |  |\  \
   `--'    `--' `--' `--'   `--'  `--'    `------'  `--'     `--' `--' `--' '--'
"""


def cmd_run(args) -> None:
    """Start the watcher."""
    if not CONFIG_PATH.exists():
        print("No config file found. Run 'familiar init' to get started.")
        sys.exit(1)

    cfg = resolve_config(args)
    ensure_dirs(cfg.vault_path)
    log(cfg.name, f"Started — vault: {cfg.vault_path}")

    # Drain existing jobs
    drain_jobs(cfg)

    # Start watcher
    watch(cfg)


def _prompt(label: str, default: str) -> str:
    """Prompt the user for a value, showing the default."""
    raw = input(f"  {label} [{default}]: ").strip()
    return raw if raw else default


def _run_setup(defaults: dict) -> None:
    """Interactive setup wizard. defaults dict provides initial values for prompts."""
    d_vault_root = defaults.get("vault_root", "~/Obsidian")
    d_name = defaults.get("name", "Familiar")
    d_timeout = str(defaults.get("timeout", 300))
    d_allowed = defaults.get("allowed_paths", [])

    # 1. Vault root — ask first and confirm it exists
    vault_root = _prompt(
        "Vault — your Obsidian vault directory",
        d_vault_root,
    )
    resolved_root = Path(vault_root).expanduser().resolve()
    if not resolved_root.exists():
        create = input(f"\n  {resolved_root} doesn't exist. Create it? [Y/n]: ").strip().lower()
        if create in ("", "y", "yes"):
            resolved_root.mkdir(parents=True, exist_ok=True)
            print(f"  Created {resolved_root}\n")
        else:
            print("  Skipped — you'll need to create it before running.\n")
    else:
        print(f"  Found {resolved_root}\n")

    # 2. Name — needed to derive the default working directory
    name = _prompt(
        "Name — your familiar's name, used in logs and the system prompt",
        d_name,
    )

    # 3. Working directory — defaults to vault_root/name (or previous vault_path)
    d_vault_path = defaults.get("vault_path", f"{vault_root}/{name}")
    vault_path = _prompt(
        "Working directory — where Jobs/, Done/, etc. live",
        d_vault_path,
    )
    resolved_vault = Path(vault_path).expanduser().resolve()
    if not resolved_vault.exists():
        create = input(f"\n  {resolved_vault} doesn't exist. Create it? [Y/n]: ").strip().lower()
        if create in ("", "y", "yes"):
            resolved_vault.mkdir(parents=True, exist_ok=True)
            print(f"  Created {resolved_vault}\n")
        else:
            print("  Skipped — you'll need to create it before running.\n")

    # 4. Timeout
    timeout = _prompt(
        "Timeout — max seconds to wait for Claude to respond",
        d_timeout,
    )

    # 5. Allowed paths
    if d_allowed:
        print(f"\n  Current allowed paths: {', '.join(d_allowed)}")
    print(
        "\n  Allowed paths — additional directories your familiar can access.\n"
        "  The vault is always included. Enter one per line, blank to finish."
    )
    allowed_paths: list[str] = []
    while True:
        path = input("  Path (blank to finish): ").strip()
        if not path:
            break
        allowed_paths.append(path)
    # Keep previous paths if none were entered and there were defaults
    if not allowed_paths and d_allowed:
        keep = input("  Keep existing allowed paths? [Y/n]: ").strip().lower()
        if keep in ("", "y", "yes"):
            allowed_paths = d_allowed

    # Validate timeout
    try:
        timeout_int = int(timeout)
    except ValueError:
        print(f"\n  '{timeout}' isn't a number, using 300.")
        timeout_int = 300

    # Write config
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config_lines = [
        f'name = "{name}"',
        f'vault_root = "{vault_root}"',
        f'vault_path = "{vault_path}"',
        f"timeout = {timeout_int}",
    ]
    if allowed_paths:
        paths_toml = ", ".join(f'"{p}"' for p in allowed_paths)
        config_lines.append(f"allowed_paths = [{paths_toml}]")
    CONFIG_PATH.write_text("\n".join(config_lines) + "\n")
    print(f"\n  Wrote {CONFIG_PATH}")

    # Create vault subdirs (Jobs/, Done/, etc.)
    cfg = FamiliarConfig(
        name=name, vault_path=Path(vault_path), vault_root=Path(vault_root),
        timeout=timeout_int, allowed_paths=allowed_paths,
    )
    ensure_dirs(cfg.vault_path)
    print(f"  Created vault directories in {cfg.vault_path}")

    # Check deps
    _check_deps()

    print(f"\nYou're all set. Run 'familiar run' to start {name}.")


def cmd_init(args) -> None:
    """Walk the user through creating config and vault directories."""
    print(BANNER)

    if CONFIG_PATH.exists():
        print(f"  Config found: {CONFIG_PATH}\n")
        choice = input("  [R]econfigure with current values as defaults, [D]elete and start fresh? [R/d]: ").strip().lower()
        if choice in ("d", "delete"):
            CONFIG_PATH.unlink()
            print("  Deleted.\n")
            _run_setup({})
        else:
            existing = load_config()
            print()
            _run_setup(existing)
    else:
        print("Let's set up your familiar.\n")
        _run_setup({})


def _check_deps() -> None:
    print()
    if shutil.which("claude"):
        print("  claude CLI found")
    else:
        print("  claude CLI not found")
        print("  Install: npm install -g @anthropic-ai/claude-code")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="familiar",
        description="Familiar: file-based task runner for Obsidian",
    )
    subparsers = parser.add_subparsers(dest="command")

    # familiar run
    run_parser = subparsers.add_parser("run", help="Start the watcher")
    run_parser.add_argument("--name", default=None, help="Name of your familiar")
    run_parser.add_argument(
        "--vault-path", type=Path, default=None, help="Path to Familiar directory"
    )
    run_parser.add_argument(
        "--timeout", type=int, default=None, help="Claude CLI timeout in seconds"
    )

    # familiar init
    subparsers.add_parser("init", help="Create config file and vault directories")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "init":
        cmd_init(args)
    else:
        parser.print_help()
        sys.exit(0)
