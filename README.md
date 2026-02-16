# Familiar

A file-based task runner for Obsidian. Drop a markdown file into a folder, get Claude's output appended back into it, review in Obsidian, add feedback, drop it back in for another round.

The idea is simple: your Obsidian vault becomes a lightweight job queue. No web UI, no database, no API keys to manage. Just files.

## How it works

1. Save a `.md` file into `Jobs/`
2. Familiar picks it up, sends the content to Claude
3. Claude's output gets appended in an Obsidian callout block
4. File moves to `Done/` for review
5. Add feedback, drop it back into `Jobs/`, repeat

Each iteration builds on the last. Claude sees the full history, your reviewer notes, everything.

## Install

```bash
uv pip install -e .
```

## Setup

```bash
familiar init
```

This creates `~/.config/familiar/config.toml` and the vault directory structure. Edit the config to set your familiar's name, vault path, and other options.

## Usage

```bash
familiar run
```

Options:

- `--name NAME` — Override your familiar's name
- `--vault-path PATH` — Override Familiar directory
- `--timeout SECONDS` — Claude CLI timeout (default: 300)

## Config

`~/.config/familiar/config.toml`:

```toml
# Name of your familiar (appears in logs and system prompt)
name = "Familiar"

# Obsidian vault directory
vault_root = "~/Obsidian"

# Working directory where Jobs/, Done/, etc. live
vault_path = "~/Obsidian/Familiar"

# Max seconds for Claude to respond
timeout = 300

# Additional directories the familiar can access (optional)
# allowed_paths = ["~/src/myproject", "~/Documents/research"]
```

CLI args override config file values.

## File format

Input files are plain markdown. Frontmatter is optional on first run, Familiar manages it after that:

```markdown
---
iteration: 2
status: done
last_run: 2025-02-16T14:30:00
---
Research competitors to Guidewire ClaimCenter...

> [!quote] Puck — Report 1 at 2025-02-16 14:00
> [Claude's first output in a callout block]

Go deeper on Duck Creek's AI capabilities.

> [!quote] Puck — Report 2 at 2025-02-16 14:30
> [Claude's second output incorporating feedback]
```

The human writes plain text. The familiar's responses are wrapped in Obsidian callout blocks, making it easy to tell who said what.

## System prompt

Drop a `system-prompt.md` in the Familiar root directory and its contents get prepended to every task. Good for persistent context like "You are helping with insurance industry research" or project-specific instructions.

## Directory structure

```
~/Obsidian/Familiar/
├── Jobs/              # Drop task files here
├── Processing/        # In-flight
├── Done/              # Completed, ready for review
├── Failed/            # Errors (details written into file)
└── system-prompt.md   # Optional persistent context
```

## Dependencies

- Python 3.11+ (stdlib only)
- [Claude Code CLI](https://github.com/anthropics/claude-code) (`npm install -g @anthropic-ai/claude-code`)

## Security

Familiar runs Claude with `--dangerously-skip-permissions`, which grants full tool access with no interactive prompts. This is required because Familiar runs unattended — there's no human at the keyboard to approve each action.

What this means in practice: Claude can read and write files, execute shell commands, and make network requests without asking for confirmation.

There are two precautions in place, but neither is enforced at the OS level:

- **Prompt-based path boundaries.** The system prompt instructs Claude to only access files within `vault_root` and any directories listed in `allowed_paths`. Claude generally follows these instructions, but this is a soft boundary — there is no sandbox or filesystem restriction preventing access outside these paths.
- **Working directory.** Claude's process starts with `cwd` set to your vault root, so relative paths resolve there. But absolute paths to anywhere on the system will still work.

If you're concerned about blast radius, run Familiar under a user account with limited filesystem permissions, or in a container.

## Error handling

All errors get written directly into the file and moved to `Failed/`. No silent failures. You'll see exactly what went wrong when you open the file in Obsidian.
