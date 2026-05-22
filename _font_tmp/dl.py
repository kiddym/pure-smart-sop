"""Robust chunked/resumable downloader for flaky networks (stdlib only)."""

from __future__ import annotations

import sys
import time
import urllib.request
from pathlib import Path

CHUNK = 1024 * 1024  # 1 MiB per range request


def total_size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return int(resp.headers["Content-Length"])


def download(url: str, dest: str) -> None:
    path = Path(dest)
    total = total_size(url)
    print(f"{dest}: total={total}", flush=True)
    have = path.stat().st_size if path.exists() else 0
    attempts = 0
    while have < total:
        end = min(have + CHUNK, total) - 1
        req = urllib.request.Request(url, headers={"Range": f"bytes={have}-{end}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            with open(path, "ab") as fh:
                fh.write(data)
            have += len(data)
            attempts = 0
            if have % (4 * CHUNK) < CHUNK:
                print(f"{dest}: {have}/{total}", flush=True)
        except Exception as exc:  # noqa: BLE001
            attempts += 1
            print(f"{dest}: chunk fail @{have} ({exc}); retry {attempts}", flush=True)
            time.sleep(2)
            if attempts > 30:
                print(f"{dest}: GIVING UP at {have}/{total}", flush=True)
                return
    print(f"{dest}: DONE {have}/{total}", flush=True)


if __name__ == "__main__":
    download(sys.argv[1], sys.argv[2])
