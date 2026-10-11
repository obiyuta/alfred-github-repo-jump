#!/usr/bin/env python3
"""Alfred Script Filter: jump to a GitHub repository.

Usage:
  repo_jump.py filter <query>   -> Alfred JSON items
  repo_jump.py refresh          -> rebuild the repository cache via `gh`

Repos are fetched with `gh api user/repos` (everything the authenticated user can
access: own, collaborator, org member) and cached in $alfred_workflow_cache/repos.json.
Fetching always happens in a background process; searches only read the cache.

Locking: one flock on refresh.lock. The filter takes it, spawns the refresh child with
the locked fd inherited, and the child releases it on exit. The OS drops the lock if
the child dies, so there is no stale-lock handling. The same file stores the last
refresh error (empty on success), which drives a retry backoff.

Note: Alfred sets $alfred_workflow_cache. Running this script by hand from a terminal
writes to ~/.cache instead, so use the `ghr` keyword to refresh what Alfred reads.
"""
import fcntl
import json
import math
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import NamedTuple, Optional

# Alfred runs with a minimal PATH; append common gh locations without shadowing the user's own.
os.environ["PATH"] = (os.environ.get("PATH") or "/usr/bin:/bin") + ":/opt/homebrew/bin:/usr/local/bin"

CACHE_DIR = Path(os.environ.get("alfred_workflow_cache") or Path.home() / ".cache" / "alfred-github-repo-jump")
CACHE_FILE = CACHE_DIR / "repos.json"
LOCK_FILE = CACHE_DIR / "refresh.lock"
LOCK_FD_ENV = "REPO_JUMP_LOCK_FD"
ERROR_BACKOFF_SEC = 300   # after a failed refresh, do not retry automatically for this long
GH_TIMEOUT_SEC = 120
MIN_TTL_SEC = 60
INCLUDE_ARCHIVED = os.environ.get("INCLUDE_ARCHIVED", "0") == "1"
MAX_ITEMS = 500  # Alfred learns only from results it receives, so do not cut early
ENC = "utf-8"


def ttl_seconds():
    try:
        hours = float(os.environ.get("CACHE_TTL_HOURS", "") or 6)
    except ValueError:
        hours = 6
    seconds = hours * 3600
    if not math.isfinite(seconds):  # also catches overflow of huge values
        seconds = 6 * 3600
    return max(seconds, MIN_TTL_SEC)


class GhError(RuntimeError):
    pass


def gh(*args):
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True, encoding=ENC, timeout=GH_TIMEOUT_SEC)
    except FileNotFoundError:
        raise GhError("gh CLI not found. Install it with `brew install gh`")
    except subprocess.TimeoutExpired:
        raise GhError(f"gh did not respond within {GH_TIMEOUT_SEC}s")
    if out.returncode != 0:
        lines = [l.strip() for l in out.stderr.splitlines() if l.strip()]
        msg = " / ".join(lines) if lines else f"gh exited with {out.returncode}"
        raise GhError(msg[:300])
    return out.stdout


def host_of(url):
    return urllib.parse.urlsplit(url).netloc or "github.com"


def make_uid(repo):
    """Stable key for Alfred's learning, computed once per refresh and stored in the cache.

    The numeric repository id survives renames and transfers (node ids change format
    over time). Both forms are scoped by host because github.com and GHE can collide.
    """
    host = host_of(repo["url"])
    rid = repo.get("id")
    if isinstance(rid, (int, str)) and not isinstance(rid, bool) and str(rid) not in ("", "null"):
        return f"{host}:{rid}"
    return f"{host}:{repo['nameWithOwner']}"


def fetch_repos():
    """All repositories visible to the authenticated user (owner, collaborator, org member)."""
    raw = gh("api", "user/repos", "--paginate", "-X", "GET", "-f", "per_page=100",
             "--jq", '.[] | {id, nameWithOwner: .full_name, description, url: .html_url, '
                     'isArchived: .archived, isPrivate: .private, pushedAt: .pushed_at}')
    repos = {}
    for line in raw.splitlines():
        if line.strip():
            r = json.loads(line)
            r["matchFull"] = r["nameWithOwner"].lower()      # precomputed so score() does
            r["matchDesc"] = (r.get("description") or "").lower()  # no per-keystroke lower()
            r["uid"] = make_uid(r)
            repos[r["nameWithOwner"]] = r
    # ISO-8601 strings sort correctly as text; this order is reused by filter_items.
    return sorted(repos.values(), key=lambda r: r.get("pushedAt") or "", reverse=True)


# --- cache state

def try_lock():
    """Return an fd holding the exclusive refresh lock, or None if another process holds it."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except OSError:
        os.close(fd)
        return None


def record_result(fd, error):
    """Store the refresh outcome in the lock file: the error message, or empty on success."""
    try:
        os.ftruncate(fd, 0)
        if error:
            os.pwrite(fd, error.encode(ENC), 0)
    except OSError:
        pass


def recent_error():
    """Last refresh error message if it happened within the backoff period, else None."""
    try:
        if time.time() - LOCK_FILE.stat().st_mtime < ERROR_BACKOFF_SEC:
            return LOCK_FILE.read_text(encoding=ENC).strip() or None
    except OSError:
        pass
    return None


REPO_STR_KEYS = ("nameWithOwner", "url", "matchFull", "matchDesc")  # "uid" is checked separately


def valid_cache(data):
    if not isinstance(data, dict):
        return False
    repos, fetched_at = data.get("repos"), data.get("fetched_at")
    if not isinstance(repos, list):
        return False
    if not isinstance(fetched_at, (int, float)) or isinstance(fetched_at, bool) or not math.isfinite(fetched_at):
        return False
    return all(isinstance(r, dict) and all(isinstance(r.get(k), str) for k in REPO_STR_KEYS)
               and "/" in r["matchFull"] and isinstance(r.get("uid", ""), str) for r in repos)


def read_cache():
    """Cache dict, or None if missing. A corrupt file is discarded; a read error is left alone."""
    try:
        text = CACHE_FILE.read_text(encoding=ENC)
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError):
        return None
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if not valid_cache(data):  # corrupt or older format: discard and refetch
        CACHE_FILE.unlink(missing_ok=True)
        return None
    return data


def refresh(lock_fd=None):
    """Rebuild the cache. Returns repo count, or None when another refresh holds the lock."""
    fd = lock_fd if lock_fd is not None else try_lock()
    if fd is None:
        return None
    tmp = CACHE_DIR / f"repos.{os.getpid()}.tmp"
    try:
        repos = fetch_repos()
        tmp.write_text(json.dumps({"fetched_at": time.time(), "repos": repos}, ensure_ascii=False), encoding=ENC)
        tmp.replace(CACHE_FILE)
        record_result(fd, None)
        return len(repos)
    except Exception as e:
        record_result(fd, str(e) or type(e).__name__)
        tmp.unlink(missing_ok=True)
        raise
    finally:
        os.close(fd)  # releases the flock


def spawn_refresh(fd):
    """Hand the locked fd to a background refresh process."""
    try:
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "refresh"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, pass_fds=(fd,), env={**os.environ, LOCK_FD_ENV: str(fd)},
        )
    finally:
        os.close(fd)  # the child's inherited fd keeps the lock alive


def ensure_refreshing(error):
    """Start a background refresh unless one is running or we are backing off.

    Returns True if a refresh is in progress after the call.
    """
    fd = try_lock()
    if fd is None:
        return True  # another refresh holds the lock
    if error:
        os.close(fd)
        return False
    spawn_refresh(fd)
    return True


class CacheState(NamedTuple):
    repos: Optional[list]  # None until the first fetch has landed
    refreshing: bool
    error: Optional[str]


def load_state():
    data = read_cache()
    error = recent_error()
    age = time.time() - data["fetched_at"] if data else None
    stale = (age is None or age < 0 or age > ttl_seconds()  # age < 0: clock moved backwards
             or any("uid" not in r for r in data["repos"]))  # v1.0.0 cache: switch uids now
    refreshing = stale and ensure_refreshing(error)
    return CacheState(data["repos"] if data else None, refreshing, error)


# --- matching

def subsequence(q, s):
    i = 0
    for ch in s:
        if i < len(q) and ch == q[i]:
            i += 1
    return i == len(q)


def score(query, repo):
    """Lower is better. None = no match.

    A query containing "/" is matched against "owner/name", otherwise against the name.
    """
    q = query.lower()
    full = repo["matchFull"]
    target = full if "/" in q else full.split("/", 1)[1]
    desc = repo["matchDesc"]
    if q == target:
        return 0
    if target.startswith(q):
        return 1
    if q in target:
        return 2
    if q in full:  # owner match for a name-only query
        return 3
    terms = q.split()
    if len(terms) > 1 and all(t in full or t in desc for t in terms):
        return 4
    if q in desc:
        return 5
    if subsequence(q, target):
        return 6
    return None


def item(repo):
    full = repo["nameWithOwner"]
    url = repo["url"]
    badges = []
    if repo.get("isPrivate"):
        badges.append("🔒")
    if repo.get("isArchived"):
        badges.append("📦")
    desc = repo.get("description") or ""
    subtitle = " ".join(badges + [desc]).strip() or url
    # "uid" lets Alfred learn which result you pick for what you typed (partial input
    # included) and move it up next time. score() orders everything Alfred has not learned.
    return {
        "uid": repo.get("uid") or make_uid(repo),  # make_uid only for a v1.0.0 cache
        "title": full,
        "subtitle": subtitle,
        "arg": url,
        "autocomplete": full,
        "quicklookurl": url,
        "text": {"copy": url, "largetype": full},
        "mods": {
            "cmd": {"arg": f"{url}/pulls", "subtitle": "Open Pull Requests"},
            "alt": {"arg": f"{url}/issues", "subtitle": "Open Issues"},
            "ctrl": {"arg": f"{url}/actions", "subtitle": "Open Actions"},
            "shift": {"arg": f"git@{host_of(url)}:{full}.git", "subtitle": "Copy SSH clone URL"},
        },
    }


def error_item(msg):
    return {"title": "Failed to refresh repository list", "subtitle": f"{msg} (run `ghr` to retry)", "valid": False}


def filter_items(query):
    query = query.strip()
    repos, refreshing, error = load_state()
    if repos is None:
        if refreshing:
            return {"items": [{"title": "Fetching repository list…", "subtitle": "Takes a few seconds the first time", "valid": False}],
                    "rerun": 1}
        # Poll so the retry starts by itself once the backoff period has passed.
        return {"items": [error_item(error or "Could not start the fetch")], "rerun": 5}
    host = host_of(repos[0]["url"]) if repos else "github.com"  # GitHub Enterprise aware
    repos = [r for r in repos if INCLUDE_ARCHIVED or not r.get("isArchived")]
    if query:
        scored = [(s, r) for r in repos if (s := score(query, r)) is not None]
        scored.sort(key=lambda t: t[0])  # stable: ties keep the cache's pushedAt-desc order
        repos = [r for _, r in scored]
    items = [item(r) for r in repos[:MAX_ITEMS]]
    if query:
        items.append({
            "title": f"Search GitHub for “{query}”",
            "subtitle": "Search repositories on GitHub",
            "arg": f"https://{host}/search?type=repositories&q=" + urllib.parse.quote(query),
            "mods": {"shift": {"valid": False, "subtitle": "No clone URL for a search"}},
        })
    if error:
        items.append(error_item(error))  # results are still usable, so keep it out of the way
    result = {"items": items}
    if refreshing:
        result["rerun"] = 2  # pick up the background refresh when it lands
    return result


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "filter"
    if cmd == "refresh":
        if "alfred_workflow_cache" not in os.environ:
            sys.stderr.write(f"warning: not run by Alfred, writing to {CACHE_DIR}\n")
        lock_fd = int(os.environ[LOCK_FD_ENV]) if LOCK_FD_ENV in os.environ else None
        try:
            n = refresh(lock_fd)
        except Exception as e:
            print(f"Refresh failed: {e}")
            return
        print("Another refresh is already running" if n is None else f"Cached {n} repositories")
        return
    query = " ".join(sys.argv[2:])
    try:
        print(json.dumps(filter_items(query), ensure_ascii=False))
    except Exception as e:  # surface errors inside Alfred instead of a silent empty list
        print(json.dumps({"items": [{"title": "Error", "subtitle": f"{type(e).__name__}: {e}", "valid": False}]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
