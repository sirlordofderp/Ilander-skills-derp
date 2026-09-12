TOKEN WATCHDOG — INSTALL / HANDOFF NOTES
=======================================

Skill name:
token-watchdog

Purpose:
Read-only Token flight recorder, cost analyzer, and possible-loop detector for
iLanders.

The actual iLands package MUST contain SKILL.md. This is one of the cases where
Markdown is required by the platform rather than Sis randomly choosing .md. :)

Suggested GitHub layout:

token-watchdog/
└── SKILL.md

Suggested installation after manual review:

ilands skill install <public-github-folder-url>

Design choices:
- Atomic skill
- Read-only
- `allowed-tools: Bash(ilands:*)`
- Does NOT create recurring tasks
- Does NOT switch models
- Does NOT transfer/cancel/spend
- Uses settled token-statement entries
- Explicitly distinguishes one expensive LLM call from loop-like repeated charges
- Uses historical run medians rather than arbitrary average-cost assumptions
- Requires multiple indicators before labeling POSSIBLE_LOOP

Important runtime limitation:
There is no live mid-call Token meter. Ledger charges appear after settlement, so
this skill is a flight recorder / near-real-time checkpoint analyzer, not a hard
circuit breaker.

Recommended first test:
1. Ask it for a 24-hour snapshot.
2. Ask it for the three most expensive runIds.
3. Pick one known expensive period and ask "does this look loop-like?"
4. Compare its result against the raw token-statement entries manually.
5. If good, use it during one bounded research task with phase checkpoints.

Version:
0.1.0
