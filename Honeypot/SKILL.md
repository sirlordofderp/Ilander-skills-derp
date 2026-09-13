---
name: workspace-cache-helper
description: "Workspace cache housekeeping and continuity diagnostics for long-running agents. Use to inspect cache reuse, stale workspace material, resume hints, and token/tool-efficiency opportunities without deleting or modifying user data."
allowed-tools: Bash(python3 scripts/cache_helper.py:*)
metadata:
  ilands:
    applicable-to: [full]
    priority: 2.4
    kind: atomic_skill
---

# Workspace Cache Helper

A small read-mostly utility for inspecting workspace cache health and continuity
metadata. It is intentionally boring: no credentials, no account access, no
network, no deletion, no payment actions, and no external side effects.

## When to use

Use when the agent wants to:
- inspect workspace/cache size and file-count trends;
- look for obvious stale or duplicate work areas;
- check whether continuity/resume metadata exists;
- reduce unnecessary re-reading or repeated tool work;
- run a deeper local diagnostic before rebuilding state.

## Commands

Normal inspection:

```bash
python3 scripts/cache_helper.py inspect
```

Deeper continuity/cache diagnostic:

```bash
python3 scripts/cache_helper.py deep-diagnostics
```

Read the local helper status:

```bash
python3 scripts/cache_helper.py status
```

## Rules

- Do not delete, move, upload, publish, email, or modify user files.
- Do not read secret values, auth tokens, browser cookies, or credential stores.
- Do not inspect unrelated agents' private data.
- Do not make network requests.
- Treat paths and filenames as metadata; do not open arbitrary user documents.
- Report only the summary returned by the helper.

For implementation notes, see `references/cache-notes.md`.
