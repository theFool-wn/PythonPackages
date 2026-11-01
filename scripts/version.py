#!/usr/bin/env python3
"""Synchronize one package's version from its version.json without importing it."""


from __future__ import annotations

import argparse
import json
import re

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("wecom-messager", "buaa-network-autologin")
SEMVER = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")


def update_marker(path: Path, pattern: str, replacement: str) -> bytes | None:
    try:
        original = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise SystemExit(f"Cannot read {path.relative_to(ROOT)}: {type(exc).__name__}") from None
    updated, count = re.subn(pattern, replacement, original, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"Expected one version marker in {path.relative_to(ROOT)}, found {count}")
    # Keep each file's existing CRLF/LF line endings and UTF-8 BOM, if present.
    return updated.encode("utf-8") if updated != original else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", choices=PACKAGES, required=True, help="only this package")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail if any version marker differs")
    mode.add_argument("--write", action="store_true", help="update this package's version markers")
    args = parser.parse_args()

    package_root = ROOT / args.package
    try:
        release = json.loads((package_root / "version.json").read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read {args.package}/version.json: {type(exc).__name__}") from None
    if not isinstance(release, dict) or not isinstance(release.get("version"), str) or not SEMVER.fullmatch(release["version"]):
        raise SystemExit(f"{args.package}/version.json needs a version like 0.2.0")
    version = release["version"]
    changed: list[str] = []

    markers = [
        (package_root / "pyproject.toml", r'^(version[ \t]*=[ \t]*")[^"\r\n]+(")', rf'\g<1>{version}\g<2>'),
        (package_root / "README.md", r'(https://img\.shields\.io/badge/version-)[0-9]+\.[0-9]+\.[0-9]+(-[^)\s]+)', rf'\g<1>{version}\g<2>'),
    ]
    sources = sorted((package_root / "src").rglob("*.py"))
    if not sources:
        raise SystemExit(f"No Python sources found in {args.package}/src")
    for path in sources:
        markers.append((path, r'^(# @[ \t]*Release Version:[ \t]*)[^\r\n]*(?=\r?$)', rf'\g<1>{version}'))

    pending: list[tuple[Path, bytes]] = []
    for path, pattern, replacement in markers:
        updated = update_marker(path, pattern, replacement)
        if updated is not None:
            relative = str(path.relative_to(ROOT))
            changed.append(relative)
            pending.append((path, updated))
    if changed and args.check:
        raise SystemExit(
            "Version drift: " + ", ".join(changed) +
            f". Run python scripts/version.py --package {args.package} --write"
        )
    if args.write:
        for path, updated in pending:
            path.write_bytes(updated)
    summary = "updated " + ", ".join(changed) if changed else "consistent"
    print(f"{args.package} {version}: {summary}")


if __name__ == "__main__":
    main()
