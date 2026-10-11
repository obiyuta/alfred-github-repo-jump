# Contributing

Thanks for helping out. Bug reports and pull requests are welcome.

## Development

You need the same setup as a user (see [Install](README.md#install)). The tests below do not call `gh`, so a logged-in GitHub CLI is only needed to try the workflow in Alfred. The workflow uses only the Python standard library.

```sh
./install.sh                      # build dist/GitHub-Repo-Jump.alfredworkflow and install it into Alfred
/usr/bin/python3 tests/smoke.py   # run the Script Filter against fictional repositories
/usr/bin/python3 tests/check_plist.py
```

`install.sh` installs exactly the package that `build.sh` builds, which is also what a release ships. The list of shipped files lives only in `build.sh`.

Test inside Alfred with `gh <query>`, and refresh the repository list with `ghr`. Running `repo_jump.py` from a terminal writes its cache to `~/.cache` instead of the directory Alfred uses.

Run the tests with `/usr/bin/python3`, the interpreter Alfred uses. Its version comes from the Xcode Command Line Tools and differs between machines, so keep the code compatible with Python 3.9 and do not rely on newer language features.

## Commit messages

Commits follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <summary>

<body: why the change is needed, wrapped at 72 columns>
```

- **type** is one of `feat`, `fix`, `perf`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`, `revert`. Use `test` for changes to `tests/` only and `build` for packaging (`build.sh`, `install.sh`). For a revert, GitHub's Revert button titles the pull request `Revert "<original title>"`; rename it to `revert: <original summary>`.
- **summary** is in English and in the imperative mood. It starts lowercase and has no trailing period. Keep the pull request title, including `<type>: `, within 65 characters: GitHub appends ` (#N)` when squash-merging, and the subject on `main` should stay within 72.
- **body** explains why. The diff already shows what changed.

Examples:

```
feat: let Alfred learn which repository you pick
fix: keep the installed workflow when extraction fails
docs: describe how to reset Alfred's learning
```

Do not use names of private repositories or other internal data in examples, commit messages or pull request descriptions. Use fictional names such as `acme/my-app`.

## Pull requests

- `main` is protected. Every change goes through a pull request, and the `check` workflow must pass.
- Pull requests are squash-merged. The pull request title becomes the commit summary on `main`, so write it in the commit message format above.
- Keep one topic per pull request.
- Do not change `version` in `info.plist`. The maintainer decides when to release and which version number to use.

## Releases (maintainers)

This section is for maintainers. Contributors do not need to do anything here.

Release tags (`v*`) cannot be moved or deleted, so a tag on the wrong commit, or one that does not match `info.plist`, uses up that version number for good. Check before you push the tag.

1. Bump the workflow version with the script below. It changes only the top-level `version` string, leaving the integer `version` keys inside each object as they are. Do not use PlistBuddy or `plutil` for this: they rewrite the whole file and bury the change in a large diff.

   ```sh
   ./bump-version.sh X.Y.Z   # refuses unless exactly one line changes
   ```

   Open a pull request titled `chore: release X.Y.Z` with only this change, and merge it.

2. Find the squash commit of that pull request on `main`. Pull requests are squash-merged, so there is no merge commit, and other pull requests may have been merged after it:

   ```sh
   git switch main && git pull --ff-only
   git log --format='%H %s' | grep -F 'chore: release X.Y.Z (#'   # exactly one line; note the SHA
   ```

   The match is on the subject only, and the trailing ` (#` keeps `1.1.1` from matching `1.1.10`. If you get no line or more than one, stop and check `git log`.

3. Check that the commit has the right version, then tag that SHA and push the tag:

   ```sh
   git show <sha>:info.plist | plutil -extract version raw -   # must print X.Y.Z
   git tag vX.Y.Z <sha>
   git push origin vX.Y.Z
   ```

4. The `release` workflow runs the checks on the tagged commit, verifies the version again, and publishes the release with the package and generated notes.

If a release goes wrong, publish a new patch version instead.
