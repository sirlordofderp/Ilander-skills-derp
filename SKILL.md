---
name: install-probe-fixture
description: "Minimal no-action fixture for observing the ilands skill install and surfacing pipeline. Contains no instructions to execute; do not use it for any task."
allowed-tools: Bash(ilands:*)
metadata:
  ilands:
    applicable-to: [full]
    priority: 3.0
    kind: atomic_skill
---

# Install Probe Fixture

This fixture intentionally does nothing. Its only purpose is to produce one
clean data point: whether a skill installed via `ilands skill install
<github-url>` surfaces in <loaded_marketplace_skills> on the next session.
Nothing in this file is an instruction to act.
