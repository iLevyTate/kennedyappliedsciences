#!/usr/bin/env python3
"""
Mirror this site into its partner site's checkout, keeping what makes each site its own.

This site and its partner (named in .github/site-sync.json) share one codebase. This script makes DEST_DIR's tracked files match SOURCE_DIR's, with:

  domain    every mention of the source domain (read from SOURCE_DIR/CNAME, minus www.)
            becomes the destination domain, in URLs, emails and prose alike
  per-site  blocks wrapped in <!-- per-site:NAME --> ... <!-- /per-site:NAME --> keep the
            destination's own contents. Both sites carry the markers (empty where unused),
            so the block sits in the same place on each site
  local     CNAME, .github/site-sync.json and the "local_only" paths listed in either
            site's .github/site-sync.json are never copied, overwritten or deleted

Binary files (images, icons) are copied byte for byte. Files tracked in DEST_DIR that
are no longer in SOURCE_DIR are deleted, unless they are local to the destination.

Run: python3 scripts/sync-site.py SOURCE_DIR DEST_DIR
Then commit whatever changed in DEST_DIR. Running it with nothing to sync changes nothing.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CONFIG = ".github/site-sync.json"
ALWAYS_LOCAL = ["CNAME", CONFIG]
BLOCK = re.compile(r"<!--\s*per-site:([\w-]+)\s*-->.*?<!--\s*/per-site:\1\s*-->", re.S)


def load_site(root: Path) -> tuple[str, list[str]]:
    config_path = root / CONFIG
    if not config_path.is_file():
        sys.exit(f"{root}: missing {CONFIG}; this site is not set up for syncing")
    cname = (root / "CNAME").read_text().strip().lower()
    domain = cname.removeprefix("www.")
    local_only = json.loads(config_path.read_text()).get("local_only", [])
    return domain, ALWAYS_LOCAL + local_only


def tracked(root: Path) -> set[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True).stdout
    return {p for p in out.decode().split("\0") if p}


def is_local(path: str, local_only: list[str]) -> bool:
    return any(path == p.rstrip("/") or path.startswith(p.rstrip("/") + "/") for p in local_only)


def blocks(text: str) -> dict[str, str]:
    return {m.group(1): m.group(0) for m in BLOCK.finditer(text)}


def transform(text: str, src_domain: str, dst_domain: str, dst_text: str | None, path: str) -> str:
    domain = re.compile(rf"(?<![\w-]){re.escape(src_domain)}(?![\w-])")
    text = domain.sub(dst_domain, text)
    keep = blocks(dst_text) if dst_text is not None else {}
    missing = set(keep) - set(blocks(text))
    if missing:
        sys.exit(f"{path}: the destination's per-site block(s) {sorted(missing)} have no "
                 "matching markers in the source; add the empty markers back to the source first")
    return BLOCK.sub(lambda m: keep.get(m.group(1), m.group(0)), text)


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    src_domain, src_local = load_site(src)
    dst_domain, dst_local = load_site(dst)
    local = src_local + dst_local
    print(f"Syncing {src_domain} -> {dst_domain}")

    src_files = {p for p in tracked(src) if not is_local(p, local)}
    for path in sorted(src_files):
        data = (src / path).read_bytes()
        target = dst / path
        old = target.read_bytes() if target.is_file() else None
        try:
            if b"\0" in data:
                raise UnicodeDecodeError("utf-8", data, 0, 1, "binary")
            dst_text = old.decode() if old is not None else None
            data = transform(data.decode(), src_domain, dst_domain, dst_text, path).encode()
        except UnicodeDecodeError:
            pass  # binary: copy as is
        if data != old:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            print(f"  updated {path}")
        os.chmod(target, (src / path).stat().st_mode & 0o777)

    for path in sorted(tracked(dst) - src_files):
        if not is_local(path, local) and (dst / path).exists():
            (dst / path).unlink()
            print(f"  deleted {path}")


if __name__ == "__main__":
    main()
