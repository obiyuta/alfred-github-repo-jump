"""Check that info.plist is wired correctly.

  /usr/bin/python3 tests/check_plist.py
"""
import plistlib
import re
from pathlib import Path

PLIST = Path(__file__).resolve().parent.parent / "info.plist"
UUID = re.compile(r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}")


def main():
    with PLIST.open("rb") as f:
        d = plistlib.load(f)
    uids = [o["uid"] for o in d["objects"]]
    assert len(uids) == len(set(uids)), "duplicate object uids"
    bad = [u for u in uids if not UUID.fullmatch(u)]
    assert not bad, f"object uids are not uppercase UUIDs: {bad}"

    known = set(uids)
    sources = set(d["connections"])
    targets = {c["destinationuid"] for cs in d["connections"].values() for c in cs}
    layout = set(d.get("uidata", {}))
    for name, refs in (("connection sources", sources), ("connection targets", targets), ("uidata", layout)):
        missing = refs - known
        assert not missing, f"{name} point to missing objects: {missing}"

    assert re.fullmatch(r"\d+\.\d+\.\d+", d["version"]), f"version is not X.Y.Z: {d['version']}"
    print(f"info.plist ok: version {d['version']}, {len(uids)} objects")


if __name__ == "__main__":
    main()
