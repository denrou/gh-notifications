# gh-notifications

A terminal UI for GitHub notifications, built with [Textual](https://textual.textualize.io/) and powered by the `gh` CLI.

## Prerequisites

- [gh](https://cli.github.com/) installed and authenticated (`gh auth login`)
- [uv](https://docs.astral.sh/uv/) for dependency management

## Install

```bash
uv tool install git+https://github.com/denrou/gh-notifications.git
```

Or clone and run locally:

```bash
git clone https://github.com/denrou/gh-notifications.git
cd gh-notifications
uv run gh-notifications
```

## Keybindings

| Key     | Action                  |
|---------|-------------------------|
| `j`/`k` | Navigate down/up       |
| `Enter` | Show notification details |
| `s`     | Select/deselect row     |
| `a`     | Select/deselect all     |
| `/`     | Filter (regex)          |
| `c`     | Clear filter            |
| `r`     | Mark as read            |
| `R`     | Mark all as read        |
| `u`     | Unsubscribe             |
| `o`     | Open in browser         |
| `g`     | Refresh                 |
| `q`     | Quit                    |

## License

MIT
