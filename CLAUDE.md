# Familiar

File-based task runner for Obsidian. Watches a folder for markdown files, processes each as a task through `claude --print`, appends output back into the file, moves to Done/.

## Project Structure

```
src/familiar/
├── __init__.py      # Version
├── __main__.py      # python -m familiar
├── cli.py           # argparse subcommands: run, init
├── config.py        # TOML config loading, defaults, FamiliarConfig dataclass
├── dispatcher.py    # Core processing (frontmatter, file lifecycle, Claude)
└── watcher.py       # fswatch + polling watchers
```

## Runtime Directories

Default path: `~/Obsidian/System/Familiar/`

- `Jobs/` — Drop .md files here to trigger processing
- `Processing/` — In-flight (prevents double-processing)
- `Done/` — Completed tasks for review
- `Failed/` — Error cases (error written into file)
- `system-prompt.md` — Optional context prepended to every task

## Config

`~/.config/familiar/config.toml` — created by `familiar init`:

- `name` — Familiar's name (appears in logs and system prompt)
- `vault_path` — Path to Obsidian vault directory
- `timeout` — Max seconds for Claude to respond

Precedence: CLI args > config.toml > built-in defaults

## Running

```bash
familiar run [--name NAME] [--vault-path PATH] [--timeout SECONDS]
familiar init
```

## Dependencies

- Python 3.11+ (stdlib only, no pip packages)
- Claude Code CLI (`claude --print`)

## Key Design Decisions

- Atomic move to Processing/ prevents double-processing
- All errors written into the file itself so they're visible in Obsidian
- Frontmatter is auto-managed (iteration, status, last_run)
- Filename collisions in Done/ resolved with `-1`, `-2` suffixes
- Polling watcher with 0.5s settle delay to let files finish writing
