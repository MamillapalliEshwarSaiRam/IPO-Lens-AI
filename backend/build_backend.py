from __future__ import annotations

import base64
import hashlib
import tarfile
import zipfile
from pathlib import Path

NAME = "ipo-lens-ai-backend"
VERSION = "0.1.0"
DIST_NAME = NAME.replace("-", "_")
DIST_INFO = f"{DIST_NAME}-{VERSION}.dist-info"
WHEEL_FILENAME = f"{DIST_NAME}-{VERSION}-py3-none-any.whl"
ROOT = Path(__file__).resolve().parent
RUNTIME_REQUIRES = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.2.0",
    "sqlalchemy[asyncio]>=2.0.30",
    "aiosqlite>=0.20.0",
    "httpx>=0.27.0",
    "langgraph>=0.2.0",
    "python-dotenv>=1.0.1",
    "apscheduler>=3.10.4",
]
DEV_REQUIRES = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "ruff>=0.5.0",
]


def _metadata_text() -> str:
    lines = [
        "Metadata-Version: 2.1\n"
        f"Name: {NAME}\n"
        f"Version: {VERSION}\n"
        "Summary: Verifiable IPO intelligence backend with multi-agent orchestration\n",
    ]
    for requirement in RUNTIME_REQUIRES:
        lines.append(f"Requires-Dist: {requirement}\n")
    lines.append("Provides-Extra: dev\n")
    for requirement in DEV_REQUIRES:
        lines.append(f'Requires-Dist: {requirement}; extra == "dev"\n')
    return "".join(lines)


def _wheel_text() -> str:
    return (
        "Wheel-Version: 1.0\n"
        "Generator: ipo-lens-ai custom backend\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    )


def _record_line(path: str, data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{path},sha256={digest},{len(data)}"


def _metadata_directory(metadata_directory: str) -> Path:
    dist_info = Path(metadata_directory) / DIST_INFO
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "METADATA").write_text(_metadata_text(), encoding="utf-8")
    (dist_info / "WHEEL").write_text(_wheel_text(), encoding="utf-8")
    (dist_info / "top_level.txt").write_text("app\n", encoding="utf-8")
    return dist_info


def get_requires_for_build_wheel(config_settings=None):
    return []


def get_requires_for_build_editable(config_settings=None):
    return []


def get_requires_for_build_sdist(config_settings=None):
    return []


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    return _metadata_directory(metadata_directory).name


def prepare_metadata_for_build_editable(metadata_directory, config_settings=None):
    return _metadata_directory(metadata_directory).name


def _build_wheel(wheel_directory: str) -> str:
    wheel_dir = Path(wheel_directory)
    wheel_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = wheel_dir / WHEEL_FILENAME
    source_path = f"{ROOT.as_posix()}\n".encode("utf-8")
    pth_name = f"{DIST_NAME}.pth"
    metadata = _metadata_text().encode("utf-8")
    wheel_text = _wheel_text().encode("utf-8")
    top_level = b"app\n"
    record_rows = [
        _record_line(pth_name, source_path),
        _record_line(f"{DIST_INFO}/METADATA", metadata),
        _record_line(f"{DIST_INFO}/WHEEL", wheel_text),
        _record_line(f"{DIST_INFO}/top_level.txt", top_level),
        f"{DIST_INFO}/RECORD,,",
    ]

    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(pth_name, source_path)
        zf.writestr(f"{DIST_INFO}/METADATA", metadata)
        zf.writestr(f"{DIST_INFO}/WHEEL", wheel_text)
        zf.writestr(f"{DIST_INFO}/top_level.txt", top_level)
        zf.writestr(f"{DIST_INFO}/RECORD", "\n".join(record_rows) + "\n")

    return wheel_path.name


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    return _build_wheel(wheel_directory)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    return _build_wheel(wheel_directory)


def build_sdist(sdist_directory, config_settings=None):
    sdist_dir = Path(sdist_directory)
    sdist_dir.mkdir(parents=True, exist_ok=True)
    sdist_path = sdist_dir / f"{DIST_NAME}-{VERSION}.tar.gz"
    with tarfile.open(sdist_path, "w:gz") as tar:
        for relative in ["build_backend.py", "pyproject.toml", "app", "tests", "migrations"]:
            candidate = ROOT / relative
            if not candidate.exists():
                continue
            tar.add(candidate, arcname=f"{DIST_NAME}-{VERSION}/{relative}")
    return sdist_path.name
