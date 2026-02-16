# Familiar

File-based task runner for Obsidian. Watches a folder for markdown files, processes each as a task through `claude --print`, appends output back into the file, moves to Done/.

## Project Structure

```
dispatcher.py    # Main CLI: watches Jobs/, dispatches to Claude, manages lifecycle
setup.sh         # Creates directories, checks dependencies
```

## Runtime Directories

Default path: `~/Obsidian/System/Familiar/`

- `Jobs/` — Drop .md files here to trigger processing
- `Processing/` — In-flight (prevents double-processing)
- `Done/` — Completed tasks for review
- `Failed/` — Error cases (error written into file)
- `system-prompt.md` — Optional context prepended to every task

## Running

```bash
python3 dispatcher.py [--vault-path PATH] [--poll] [--timeout SECONDS]
```

## Dependencies

- Python 3.10+ (stdlib only, no pip packages)
- Claude Code CLI (`claude --print`)
- fswatch (optional, falls back to polling)

## Key Design Decisions

- Atomic move to Processing/ prevents double-processing
- All errors written into the file itself so they're visible in Obsidian
- Frontmatter is auto-managed (iteration, status, last_run)
- Filename collisions in Done/ resolved with `-1`, `-2` suffixes
- 0.5s settle delay after fswatch event to let file finish writing
