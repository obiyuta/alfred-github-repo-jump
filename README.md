# alfred-github-repo-jump

[![Release](https://img.shields.io/github/v/release/obiyuta/alfred-github-repo-jump)](https://github.com/obiyuta/alfred-github-repo-jump/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/obiyuta/alfred-github-repo-jump/total)](https://github.com/obiyuta/alfred-github-repo-jump/releases)
[![check](https://img.shields.io/github/actions/workflow/status/obiyuta/alfred-github-repo-jump/check.yml?branch=main&label=check)](https://github.com/obiyuta/alfred-github-repo-jump/actions/workflows/check.yml)
[![License](https://img.shields.io/github/license/obiyuta/alfred-github-repo-jump)](LICENSE)
[![Alfred 5](https://img.shields.io/badge/Alfred-5-5C1F87)](https://www.alfredapp.com/)

English | [日本語](README.ja.md)

Alfred workflow: type `gh <name>` and jump straight to any GitHub repository you have access to.

Repositories are listed through the authenticated [`gh` CLI](https://cli.github.com/) (`gh api user/repos`), so private repos, organization repos and repos you collaborate on all show up. No token to configure. GitHub Enterprise works too when it is `gh`'s default host.

## Install

1. Install and log in to the GitHub CLI: `brew install gh && gh auth login`
2. Download `GitHub-Repo-Jump.alfredworkflow` from the [latest release](https://github.com/obiyuta/alfred-github-repo-jump/releases/latest) and open it.

Or from a checkout: `./install.sh` builds the workflow and installs it into your Alfred preferences.

Requires Alfred 5 with the Powerpack and `/usr/bin/python3`, which macOS provides once the Xcode Command Line Tools are installed (`xcode-select --install`; Homebrew installs them for you).

## Usage

| Keyword | Action |
| --- | --- |
| `gh <query>` | Fuzzy-search repositories. `⏎` opens the repository |
| `⌘⏎` | Open Pull Requests |
| `⌥⏎` | Open Issues |
| `⌃⏎` | Open Actions |
| `⇧⏎` | Copy the SSH clone URL |
| `ghr` | Refresh the repository cache now |

Run `ghr` rather than invoking `repo_jump.py` from a terminal: Alfred passes the cache location through `$alfred_workflow_cache`, so a manual run writes elsewhere.

Ranking: exact match, prefix, substring, owner match, all words found, description, then subsequence (fuzzy) match. A query is matched against the repository name, or against `owner/name` when it contains `/`. Ties are broken by most recent push.

Alfred also learns from your choices, and its learning takes precedence over the order above: a repository you keep picking for what you type moves to the top, even above an exact match. Alfred learns from partial input too, so a pick made while typing `doc` can also affect `docs`. Up to 500 results are listed. Learning survives repository renames and transfers. To reset it, use Alfred Preferences > Advanced > Clear Knowledge.

The last row always searches GitHub for the query, for repositories you do not have access to. `Tab` completes the full `owner/name`.

## How it works

The repository list is fetched once with `gh api user/repos --paginate` and cached in Alfred's workflow cache directory. Searches read the cache only, so results appear instantly. When the cache is older than the configured TTL (default 6 hours) the stale list is served and a background refresh runs.

## Configuration

Open the workflow's configuration in Alfred:

- **Cache TTL (hours)**: how long the cached list is considered fresh.
- **Include archived**: show archived repositories too (hidden by default).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development, commit message rules and how pull requests are handled.

## License

MIT
