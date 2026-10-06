# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv run gh-notifications     # Run the app
uv run ruff check .         # Lint
uv run ruff format .        # Format
uv add <pkg>                # Add dependency
uv add --dev <pkg>          # Add dev dependency
```

## Architecture

Two-module design inside `gh_notifications/`:

- **`gh.py`** — Stateless wrapper around the `gh` CLI. All GitHub API calls go through `subprocess.run(["gh", "api", ...])`, relying on the user's existing `gh auth` session. Exposes a `Notification` dataclass and functions for fetch/read/unsubscribe/open. Pull request state (`PullRequestInfo`: merged/draft, review decision, latest review and comment, CI) comes from a separate batched GraphQL query in `fetch_pull_request_info()`, run after the notifications are fetched so the table renders first and is enriched afterwards.
- **`app.py`** — Textual TUI. `NotificationsApp` owns all state (`_notifications`, `_filtered`, `_selected`, `_filter_text`). API calls run in background threads via `@work(thread=True)` with UI updates through `call_from_thread()`. Modal screens handle filtering (`FilterInput`) and detail view (`DetailScreen`).

Entry point: `gh_notifications.app:main`.

## Notes

- Browser opening uses macOS `open` command (not cross-platform yet).
- `ruff` rule `E501` (line length) is not enforced.
