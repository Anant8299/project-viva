"""Load source files from a public GitHub repo, an uploaded ZIP, or a local folder."""
from __future__ import annotations

import base64
import io
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

SOURCE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".php", ".rb", ".kt"}
SKIP_DIRS = {
    "node_modules", ".git", "venv", ".venv", "env", "dist", "build", "__pycache__",
    "migrations", "vendor", ".next", "coverage", "site-packages", ".idea", ".vscode",
}
SKIP_FILE_PATTERNS = [r"\.min\.js$", r"\.d\.ts$", r"(^|/)setup\.py$", r"(^|/)manage\.py$",
                      r"(^|/)conftest\.py$", r"config\.(js|ts)$"]
MIN_BYTES = 150
MAX_BYTES = 60_000
MAX_FILES = 40
API = "https://api.github.com"


class RepoError(Exception):
    """Raised with a message that is safe to show in the UI."""


@dataclass
class RepoFile:
    path: str
    content: str

    @property
    def lines(self) -> list[str]:
        return self.content.splitlines()


def parse_github_url(url: str) -> tuple[str, str, str | None]:
    url = url.strip().removesuffix("/")
    m = re.match(r"^(?:https?://)?(?:www\.)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/tree/([^/]+).*)?$", url)
    if not m:
        raise RepoError("That doesn't look like a GitHub repo URL (expected github.com/owner/repo).")
    return m.group(1), m.group(2), m.group(3)


def is_candidate(path: str, size: int | None = None) -> bool:
    parts = path.split("/")
    if any(p in SKIP_DIRS for p in parts[:-1]):
        return False
    if Path(path).suffix.lower() not in SOURCE_EXTS:
        return False
    if any(re.search(p, path) for p in SKIP_FILE_PATTERNS):
        return False
    if size is not None and not (MIN_BYTES <= size <= MAX_BYTES):
        return False
    return True


def _path_priority(path: str) -> int:
    """Lower is better. Tests are kept but pushed down; core-looking files go first."""
    p = path.lower()
    score = p.count("/")
    if "test" in p:
        score += 5
    if re.search(r"(service|api|view|model|route|controller|handler|core|engine|util|store|auth)", p):
        score -= 2
    return score


def load_from_github(url: str, token: str | None = None, session: requests.Session | None = None) -> list[RepoFile]:
    owner, repo, ref = parse_github_url(url)
    s = session or requests.Session()
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def get(path, **params):
        r = s.get(f"{API}{path}", headers=headers, params=params, timeout=20)
        if r.status_code == 404:
            raise RepoError("Repo not found. Check the URL and make sure the repo is public.")
        if r.status_code == 403:
            raise RepoError("GitHub rate limit hit. Add a GitHub token in the sidebar or upload the repo as a ZIP.")
        if r.status_code >= 400:
            raise RepoError(f"GitHub returned HTTP {r.status_code}.")
        return r.json()

    if not ref:
        ref = get(f"/repos/{owner}/{repo}")["default_branch"]
    tree = get(f"/repos/{owner}/{repo}/git/trees/{ref}", recursive="1")
    blobs = [t for t in tree.get("tree", []) if t.get("type") == "blob" and is_candidate(t["path"], t.get("size"))]
    blobs.sort(key=lambda t: (_path_priority(t["path"]), t["path"]))
    files = []
    for blob in blobs[:MAX_FILES]:
        data = get(f"/repos/{owner}/{repo}/contents/{blob['path']}", ref=ref)
        try:
            text = base64.b64decode(data["content"]).decode("utf-8")
        except (KeyError, UnicodeDecodeError, ValueError):
            continue
        files.append(RepoFile(blob["path"], text))
    if not files:
        raise RepoError("No source files found that this tool can read.")
    return files


def load_from_zip(data: bytes) -> list[RepoFile]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise RepoError("The upload is not a valid ZIP file.") from exc
    names = [n for n in zf.namelist() if not n.endswith("/")]
    # GitHub "Download ZIP" wraps everything in one top-level folder; strip it.
    tops = {n.split("/", 1)[0] for n in names}
    strip = len(tops) == 1 and all("/" in n for n in names)
    files = []
    for name in names:
        rel = name.split("/", 1)[1] if strip else name
        info = zf.getinfo(name)
        if not is_candidate(rel, info.file_size):
            continue
        try:
            files.append(RepoFile(rel, zf.read(name).decode("utf-8")))
        except UnicodeDecodeError:
            continue
    files.sort(key=lambda f: (_path_priority(f.path), f.path))
    if not files:
        raise RepoError("No source files found in the ZIP.")
    return files[:MAX_FILES]


def load_from_dir(root: str | os.PathLike) -> list[RepoFile]:
    root = Path(root)
    files = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if is_candidate(rel, p.stat().st_size):
            files.append(RepoFile(rel, p.read_text(encoding="utf-8", errors="replace")))
    files.sort(key=lambda f: (_path_priority(f.path), f.path))
    return files[:MAX_FILES]
