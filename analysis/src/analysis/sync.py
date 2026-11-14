"""Trace sync from the shared server (`GET /api/runs/export`)."""
from __future__ import annotations

import io
import os
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path

from .loader import default_data_dir, find_repo_root


def resolve_api_url(api_url: str | None = None, repo_root: Path | None = None) -> str:
    if api_url:
        return api_url.rstrip("/")
    env = os.environ.get("API_URL", "").strip()
    if env:
        return env.rstrip("/")
    root = repo_root or find_repo_root()
    f = root / "coordination" / "API_URL"
    if f.exists():
        txt = f.read_text(encoding="utf-8").strip()
        if txt:
            return txt.rstrip("/")
    raise RuntimeError("No API URL specified and coordination/API_URL is empty")


def _safe_extract_tar_bytes(payload: bytes, runs_dir: Path) -> int:
    runs_dir.mkdir(parents=True, exist_ok=True)
    base = runs_dir.resolve()
    run_ids: set[str] = set()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            rel = Path(member.name)
            if rel.is_absolute() or ".." in rel.parts or len(rel.parts) < 2:
                raise ValueError(f"Unsafe tar member path: {member.name}")
            target = (base / rel).resolve()
            if base not in target.parents:
                raise ValueError(f"Tar path escapes runs_dir: {member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            fobj = tar.extractfile(member)
            if fobj is None:
                continue
            with fobj:
                target.write_bytes(fobj.read())
            run_ids.add(rel.parts[0])
    return len(run_ids)


def sync_runs(
    api_url: str | None = None,
    data_dir: Path | None = None,
    since: str | None = None,
    timeout_s: float = 60.0,
) -> dict[str, object]:
    """Mirror finished runs from the shared server into `<data_dir>/runs`."""
    base_url = resolve_api_url(api_url)
    target_data = data_dir or default_data_dir()
    runs_dir = target_data / "runs"
    since_file = target_data / ".last_sync"
    if since is None and since_file.exists():
        saved = since_file.read_text(encoding="utf-8").strip()
        if saved:
            since = saved

    endpoint = f"{base_url}/api/runs/export"
    if since:
        endpoint = f"{endpoint}?{urllib.parse.urlencode({'since': since})}"

    req = urllib.request.Request(endpoint, headers={"Accept": "application/gzip"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        payload = resp.read()
        run_count_header = resp.headers.get("X-Run-Count")

    extracted = _safe_extract_tar_bytes(payload, runs_dir)
    from .loader import now_iso

    sync_ts = now_iso()
    target_data.mkdir(parents=True, exist_ok=True)
    since_file.write_text(sync_ts + "\n", encoding="utf-8")
    return {
        "api_url": base_url,
        "runs_dir": str(runs_dir),
        "extracted_runs": extracted,
        "server_run_count": int(run_count_header) if run_count_header and run_count_header.isdigit() else extracted,
        "synced_at": sync_ts,
    }
