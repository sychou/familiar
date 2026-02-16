# Familiar

A file-based task runner for Obsidian. Drop a markdown file into a folder, get Claude's output appended back into it, review in Obsidian, add feedback, drop it back in for another round.

The idea is simple: your Obsidian vault becomes a lightweight job queue. No web UI, no database, no API keys to manage. Just files.

## How it works

1. Save a `.md` file into `Jobs/`
2. Familiar picks it up, sends the content to `claude --print`
3. Claude's output gets appended under a `## Run N` heading with a timestamp
4. File moves to `Done/` for review
5. Add feedback, drop it back into `Jobs/`, repeat

Each iteration builds on the last. Claude sees the full history, your reviewer notes, everything.

## Setup

```bash
./setup.sh
```

This creates the directory structure at `~/Obsidian/System/Familiar/` and checks for dependencies.

## Usage

```bash
python3 dispatcher.py
```

Options:

- `--vault-path PATH` — Custom Familiar directory (default: `~/Obsidian/System/Familiar`)
- `--poll` — Use polling instead of fswatch
- `--timeout SECONDS` — Claude CLI timeout (default: 300)

## File format

Input files are plain markdown. Frontmatter is optional on first run, Familiar manages it after that:

```yaml
---
iteration: 2
status: done
last_run: 2025-02-16T14:30:00
---
Research competitors to Guidewire ClaimCenter...

---

## Run 1
*2025-02-16 14:00*

[Claude's first output]

> **Reviewer note:** Go deeper on Duck Creek's AI capabilities.

---

## Run 2
*2025-02-16 14:30*

[Claude's second output incorporating feedback]
```

## System prompt

Drop a `system-prompt.md` in the Familiar root directory and its contents get prepended to every task. Good for persistent context like "You are helping with insurance industry research" or project-specific instructions.

## Directory structure

```
~/Obsidian/System/Familiar/
├── Jobs/              # Drop task files here
├── Processing/        # In-flight
├── Done/              # Completed, ready for review
├── Failed/            # Errors (details written into file)
└── system-prompt.md   # Optional persistent context
```

## Dependencies

- Python 3.10+ (stdlib only)
- [Claude Code CLI](https://github.com/anthropics/claude-code) (`npm install -g @anthropic-ai/claude-code`)
- fswatch (optional, `brew install fswatch`, falls back to polling)

## Error handling

All errors get written directly into the file and moved to `Failed/`. No silent failures. You'll see exactly what went wrong when you open the file in Obsidian.
