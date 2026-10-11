"""Smoke test: run the Script Filter against a fixture cache and check its output.

Uses fictional repositories only, and never calls the real gh. Run with the same
interpreter Alfred uses:
  /usr/bin/python3 tests/smoke.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "repo_jump.py"
sys.path.insert(0, str(ROOT))
import repo_jump  # noqa: E402

# What `gh api user/repos --jq ...` emits: one JSON object per line, in API order.
# Push times are chosen so that push order disagrees with match order.
GH_LINES = [
    {"id": 3, "nameWithOwner": "acme/docs", "description": "Documentation site",
     "url": "https://github.com/acme/docs", "isArchived": False, "isPrivate": False,
     "pushedAt": "2026-01-01T00:00:00Z"},
    {"id": 1, "nameWithOwner": "acme/app-config", "description": "Shared config",
     "url": "https://github.com/acme/app-config", "isArchived": False, "isPrivate": True,
     "pushedAt": "2026-02-01T00:00:00Z"},
    {"id": 4, "nameWithOwner": "acme/old-thing", "description": None,
     "url": "https://github.com/acme/old-thing", "isArchived": True, "isPrivate": False,
     "pushedAt": "2026-04-01T00:00:00Z"},
    {"id": 2, "nameWithOwner": "acme/my-app", "description": "The main app",
     "url": "https://github.com/acme/my-app", "isArchived": False, "isPrivate": False,
     "pushedAt": "2026-03-01T00:00:00Z"},
]


def build_cache():
    """Run the real fetch_repos() on canned gh output."""
    real_gh = repo_jump.gh
    repo_jump.gh = lambda *args: "\n".join(json.dumps(r) for r in GH_LINES)
    try:
        repos = repo_jump.fetch_repos()
    finally:
        repo_jump.gh = real_gh
    data = {"fetched_at": time.time(), "repos": repos}
    assert repo_jump.valid_cache(data), "fixture is not a valid cache; fix the test data first"
    return data


def fake_gh_dir(root):
    """A directory holding a gh that always fails, put first on PATH so a refresh
    started by mistake can never reach the real gh and the user's account."""
    bin_dir = Path(root, "fake-bin")
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\necho 'smoke test: real gh must not be called' >&2\nexit 1\n")
    gh.chmod(0o755)
    return bin_dir


def run(query, cache_dir):
    env = {k: v for k, v in os.environ.items() if k not in ("INCLUDE_ARCHIVED", "CACHE_TTL_HOURS")}
    env["alfred_workflow_cache"] = str(cache_dir)
    env["PATH"] = f"{Path(cache_dir, 'fake-bin')}:{env.get('PATH', '/usr/bin:/bin')}"
    out = subprocess.run([sys.executable, str(SCRIPT), "filter", query],
                         capture_output=True, text=True, env=env, check=True)
    result = json.loads(out.stdout)
    assert "rerun" not in result, f"script tried to refresh during the test: {result}"
    return result["items"]


def main():
    data = build_cache()
    order = [r["nameWithOwner"] for r in data["repos"]]
    assert order == ["acme/old-thing", "acme/my-app", "acme/app-config", "acme/docs"], order  # push desc
    assert data["repos"][1]["uid"] == "github.com:2", data["repos"][1]

    with tempfile.TemporaryDirectory() as d:
        Path(d, "repos.json").write_text(json.dumps(data))
        fake_gh_dir(d)

        items = run("app", d)
        titles = [i["title"] for i in items]
        # app-config (prefix) beats my-app (substring) although my-app was pushed later.
        assert titles[:2] == ["acme/app-config", "acme/my-app"], titles
        assert titles[-1].startswith("Search GitHub"), titles
        first = items[0]
        assert first["uid"] == "github.com:1", first
        assert first["arg"] == "https://github.com/acme/app-config", first
        assert first["subtitle"].startswith("🔒"), first
        assert first["mods"]["cmd"]["arg"].endswith("/pulls"), first
        assert first["mods"]["alt"]["arg"].endswith("/issues"), first
        assert first["mods"]["ctrl"]["arg"].endswith("/actions"), first
        assert first["mods"]["shift"]["arg"] == "git@github.com:acme/app-config.git", first
        assert "uid" not in items[-1], items[-1]

        empty = [i["title"] for i in run("", d)]
        assert empty == ["acme/my-app", "acme/app-config", "acme/docs"], empty  # archived hidden

        assert run("documentation", d)[0]["title"] == "acme/docs"  # description match
        assert run("acme/my", d)[0]["title"] == "acme/my-app"  # owner/name query
    print("smoke test passed")


if __name__ == "__main__":
    main()
