"""Configuration loading and defaults for Familiar."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "familiar" / "config.toml"

SETTLE_DELAY = 0.5
POLL_INTERVAL = 1.0


@dataclass
class FamiliarConfig:
    name: str = "Familiar"
    vault_path: Path = Path("~/Obsidian/Familiar")
    vault_root: Path = Path("~/Obsidian")
    timeout: int = 300
    allowed_paths: list[str] = None

    def __post_init__(self):
        self.vault_path = Path(self.vault_path).expanduser().resolve()
        self.vault_root = Path(self.vault_root).expanduser().resolve()
        if self.allowed_paths is None:
            self.allowed_paths = []
        self.allowed_paths = [
            str(Path(p).expanduser().resolve()) for p in self.allowed_paths
        ]


def load_config() -> dict:
    """Read config.toml and return raw dict. Returns empty dict if missing."""
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def resolve_config(cli_args) -> FamiliarConfig:
    """Merge defaults < config.toml < CLI args into a FamiliarConfig."""
    file_cfg = load_config()

    name = file_cfg.get("name", "Familiar")
    vault_path = file_cfg.get("vault_path", "~/Obsidian/Familiar")
    vault_root = file_cfg.get("vault_root", "~/Obsidian")
    timeout = file_cfg.get("timeout", 300)
    allowed_paths = file_cfg.get("allowed_paths", [])

    if getattr(cli_args, "name", None) is not None:
        name = cli_args.name
    if getattr(cli_args, "vault_path", None) is not None:
        vault_path = str(cli_args.vault_path)
    if getattr(cli_args, "vault_root", None) is not None:
        vault_root = str(cli_args.vault_root)
    if getattr(cli_args, "timeout", None) is not None:
        timeout = cli_args.timeout

    return FamiliarConfig(
        name=name,
        vault_path=Path(vault_path),
        vault_root=Path(vault_root),
        timeout=timeout,
        allowed_paths=allowed_paths,
    )
