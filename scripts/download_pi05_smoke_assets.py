#!/usr/bin/env python3
"""Download the pinned public assets for the remote π0.5 smoke test."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from huggingface_hub import snapshot_download


def download_with_retries(
    *, repo_id: str, repo_type: str, revision: str, local_dir: Path, attempts: int, max_workers: int
) -> dict:
    local_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    started = time.perf_counter()
    for attempt in range(1, attempts + 1):
        try:
            resolved = snapshot_download(
                repo_id=repo_id,
                repo_type=repo_type,
                revision=revision,
                local_dir=local_dir,
                max_workers=max_workers,
            )
            return {
                "ok": True,
                "repo_id": repo_id,
                "repo_type": repo_type,
                "revision": revision,
                "local_dir": str(Path(resolved).resolve()),
                "attempt": attempt,
                "elapsed_s": time.perf_counter() - started,
                "errors": errors,
            }
        except Exception as exc:  # Network accelerator can disconnect; snapshot_download resumes.
            message = f"attempt {attempt}: {type(exc).__name__}: {exc}"
            errors.append(message)
            print(message, flush=True)
            if attempt < attempts:
                time.sleep(min(5 * attempt, 30))
    return {
        "ok": False,
        "repo_id": repo_id,
        "repo_type": repo_type,
        "revision": revision,
        "local_dir": str(local_dir.resolve()),
        "attempt": attempts,
        "elapsed_s": time.perf_counter() - started,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-repo", default="lerobot/pi05_libero_base")
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--dataset-repo", default="lerobot/libero")
    parser.add_argument("--dataset-revision", required=True)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=10)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--summary-path", type=Path, required=True)
    args = parser.parse_args()

    results = {
        "model": download_with_retries(
            repo_id=args.model_repo,
            repo_type="model",
            revision=args.model_revision,
            local_dir=args.model_dir,
            attempts=args.attempts,
            max_workers=args.max_workers,
        )
    }
    if results["model"]["ok"]:
        results["dataset"] = download_with_retries(
            repo_id=args.dataset_repo,
            repo_type="dataset",
            revision=args.dataset_revision,
            local_dir=args.dataset_dir,
            attempts=args.attempts,
            max_workers=args.max_workers,
        )
    else:
        results["dataset"] = {"ok": False, "skipped": "model download failed"}

    args.summary_path.parent.mkdir(parents=True, exist_ok=True)
    args.summary_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2), flush=True)
    return 0 if results["model"]["ok"] and results["dataset"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
