# gh-notifications

A terminal UI for GitHub notifications, built with [Textual](https://textual.textualize.io/) and powered by the `gh` CLI.

## Prerequisites

- [gh](https://cli.github.com/) installed and authenticated (`gh auth login`)
- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Install

Latest release:

```bash
uv tool install gh-notifications --from git+https://github.com/denrou/gh-notifications.git@v0.2.0
```

Or the tip of `main`:

```bash
uv tool install gh-notifications --from git+https://github.com/denrou/gh-notifications.git
```

Upgrade with `uv tool upgrade gh-notifications`, or re-run the install command with a newer tag.

To use it as a `gh` subcommand, add an alias:

```bash
gh alias set notifications --shell 'gh-notifications'
```

Then run it with:

```bash
gh notifications
```

### From source

```bash
git clone https://github.com/denrou/gh-notifications.git
cd gh-notifications
uv run gh-notifications
```

## Columns

For pull request notifications, the list shows the state of the pull request itself, fetched in one batched GraphQL request after the notifications load:

| Column     | Values                                                        |
|------------|---------------------------------------------------------------|
| `State`    | `open`, `draft`, `merged`, `closed` (subject type otherwise)  |
| `Review`   | `approved`, `changes`, `pending`, plus `CI!` when checks fail |
| `Activity` | `review`, `comment` or `review+comment` newer than your last read of the thread |

The detail view (`Enter`) adds the latest reviewer and verdict, the latest commenter, and the CI state.

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

## Releasing

Bump `version` in `pyproject.toml`, commit, then push a matching tag:

```bash
git tag -a v0.2.0 -m "v0.2.0" && git push origin main v0.2.0
```

The [Release workflow](.github/workflows/release.yml) checks that the tag matches the version, lints, builds the sdist and wheel, and publishes them as a GitHub Release with generated notes.

## License

MIT
