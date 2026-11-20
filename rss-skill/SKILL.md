---
name: rss-atom
description: "Use when asked to subscribe to, discover, collect, list, or prune RSS/Atom feeds. Stores article headlines and links in JSON, not article bodies. Not for full article reading."
allowed-tools: Bash(python3:*) Bash(dl:*) Bash(ilands:*)
metadata:
  ilands:
    applicable-to: [full, dream]
    priority: 2.5
    kind: atomic_skill
---

# RSS / Atom headline index

Use `scripts/rss_atom.py` to manage a local RSS/Atom headline index.
