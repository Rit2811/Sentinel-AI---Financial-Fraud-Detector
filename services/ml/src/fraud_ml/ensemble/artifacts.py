from __future__ import annotations

import hashlib
from pathlib import Path

import joblib


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(root: Path, excluded=("checksums.sha256",)) -> dict[str, str]:
    checksums = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in excluded
    }
    content = "".join(
        f"{checksum}  {relative_path}\n"
        for relative_path, checksum in checksums.items()
    )
    (root / "checksums.sha256").write_text(content, encoding="utf-8")
    return checksums


def verify_checksums(root: Path) -> dict[str, str]:
    checksum_file = root / "checksums.sha256"
    if not checksum_file.is_file():
        raise ValueError("Bundle checksum file is missing")
    expected = {}
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        checksum, relative_path = line.split("  ", maxsplit=1)
        expected[relative_path] = checksum
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    }
    if actual_paths != set(expected):
        raise ValueError("Bundle file set is incomplete or unexpected")
    for relative_path, checksum in expected.items():
        if sha256_file(root / relative_path) != checksum:
            raise ValueError(f"Bundle checksum mismatch: {relative_path}")
    return expected


def trusted_load(root: Path, relative_path: str):
    resolved_root = root.resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(resolved_root):
        raise ValueError("Artifact path escapes trusted bundle root")
    verify_checksums(root)
    return joblib.load(target)
