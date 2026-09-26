"""Build reproducible public source archives for the three native SDKs.

Run from the repository root: python sdk/package_release.py
Only allowlisted source files are packaged; local.properties, caches, build
outputs, logs, and credentials are never copied into release archives.
"""

from __future__ import annotations

import hashlib
import gzip
import io
import json
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VERSION = "3.0.0"
PROJECTS = {
    "android": ("android", "tokenpay-id-android"),
    "swift": ("swift", "tokenpay-id-swift"),
    "jvm-desktop": ("jvm-desktop", "tokenpay-id-jvm-desktop"),
}
ROOT_FILES = {
    "android": {"README.md", "LICENSE", "build.gradle.kts", "settings.gradle.kts", "gradle.properties"},
    "swift": {"README.md", "LICENSE", "Package.swift"},
    "jvm-desktop": {"README.md", "LICENSE", "build.gradle.kts", "settings.gradle.kts", "gradle.properties"},
}
SOURCE_SUFFIXES = {".kt", ".kts", ".java", ".swift", ".xml", ".pro", ".ttf", ".png", ".md", ".properties"}
BLOCKED_PARTS = {"build", ".gradle", ".git", ".idea", ".build", "__pycache__", "node_modules"}
BLOCKED_NAMES = {"local.properties", ".env", ".env.local", "id_rsa", "id_ed25519"}


def source_files(project_id: str, directory: Path) -> list[Path]:
    result = []
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(directory)
        if any(part in BLOCKED_PARTS for part in relative.parts):
            continue
        if path.name in BLOCKED_NAMES:
            continue
        if len(relative.parts) == 1 and path.name not in ROOT_FILES[project_id]:
            continue
        if len(relative.parts) > 1 and path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        result.append(path)
    return sorted(result, key=lambda p: p.relative_to(directory).as_posix())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_archive(project_id: str, subdir: str, stem: str) -> tuple[Path, Path]:
    directory = ROOT / "sdk" / subdir
    destination = ROOT / "frontend" / "sdk" / subdir
    destination.mkdir(parents=True, exist_ok=True)
    files = source_files(project_id, directory)
    if not files or not any(p.suffix == ".png" for p in files):
        raise RuntimeError(f"Missing source or bundled brand assets in {directory}")
    prefix = f"{stem}-{VERSION}"
    tar_path = destination / f"{prefix}.tar.gz"
    zip_path = destination / f"{prefix}.zip"

    with tar_path.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, compresslevel=9, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in files:
                    data = path.read_bytes()
                    info = tarfile.TarInfo(f"{prefix}/{path.relative_to(directory).as_posix()}")
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    archive.addfile(info, io.BytesIO(data))

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(f"{prefix}/{path.relative_to(directory).as_posix()}", (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    for path in (tar_path, zip_path):
        path.with_name(path.name + ".sha256").write_text(f"{sha256(path)}  {path.name}\n", encoding="ascii")
    print(f"{project_id}: {len(files)} source files, {tar_path.stat().st_size} tar bytes")
    return tar_path, zip_path


def main() -> None:
    manifest_path = ROOT / "frontend" / "sdk" / "releases.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = VERSION
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifest["distribution"] = "source-release"
    manifest["notes"] = (
        "3.0.0 — native SDK UI and authentication-flow update. Compact remembered-account card, "
        "clear next-step guidance, QR shortcut and rounded monochrome actions on Android, Swift and JVM. "
        "Windows and Apple automatic themes follow the OS. Cached sessions must match the selected account; "
        "unfinished native passkey screens are no longer offered. Existing API v1 and integrator contracts remain supported."
    )
    by_id = {item["id"]: item for item in manifest["artifacts"]}
    for project_id, (subdir, stem) in PROJECTS.items():
        tar_path, zip_path = write_archive(project_id, subdir, stem)
        item = by_id[project_id]
        item["primary"] = {
            "url": f"https://www.tokenpay.space/sdk/{subdir}/{tar_path.name}",
            "label": "Source (tar.gz)",
            "size": tar_path.stat().st_size,
            "sha256": sha256(tar_path),
        }
        item["secondary"] = [{
            "url": f"https://www.tokenpay.space/sdk/{subdir}/{zip_path.name}",
            "label": "Source (zip)",
            "size": zip_path.stat().st_size,
            "sha256": sha256(zip_path),
        }]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
