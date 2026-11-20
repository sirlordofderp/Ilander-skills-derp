# Omnisiah RSS/Atom skill

An atomic skill for collecting **titles and article URLs** from RSS/Atom feeds. Supports adding/removing subscriptions, autodiscovery, OPML imports/exports, JSON deduplication, review/bookmark actions, and retention pruning. No external Python packages.

## Install

Host the `rss-atom/` folder in a **public GitHub repository**, with `SKILL.md` at the root of the folder and `scripts/rss_atom.py` beneath it. Ask Omnisiah to run:

    ilands skill install https://github.com/YOUR_USERNAME/YOUR_REPOSITORY/tree/main/rss-atom

That command only requests an install; wait until the **next** turn and confirm the loaded skill path exists and contains the script. GitHub-path installation and preservation of nested `scripts/` are not yet tested in the user's sandbox. If the install loses the helper file, report it and do not pretend the skill is functional.

Alternatively, extract the ZIP and upload the files to GitHub using the GitHub website. No GitHub connector is required. Don't put the JSON database in the public GitHub repo; it can contain browsing interests and feed subscriptions.

## Quick start (local)

    python3 scripts/rss_atom.py --db /tmp/feeds.json add https://example.org/feed.xml
    python3 scripts/rss_atom.py --db /tmp/feeds.json fetch
    python3 scripts/rss_atom.py --db /tmp/feeds.json headlines
    python3 scripts/rss_atom.py --db /tmp/feeds.json prune

The DB is ephemeral unless explicitly exported/backed up to recoverable object storage. `README.md` is for human setup; `SKILL.md` is what Omnisiah reads. To run tests from this directory: `python3 -m unittest discover -s tests -v`.
