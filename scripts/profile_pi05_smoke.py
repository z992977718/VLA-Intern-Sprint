#!/usr/bin/env python3
"""Run the official LeRobot trainer while recording per-step CUDA metrics.

This is a remote-only wrapper. It does not modify LeRobot and forwards all CLI
arguments unchanged to ``lerobot.scripts.lerobot_train.main``.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import torch

from lerobot.scripts import lerobot_train


RESULT_DIR = Path(os.environ.get("PI05_SMOKE_RESULT_DIR", "results/training/pi05_smoke_test"))
STEPS_JSONL = RESULT_DIR / "torch_step_metrics.jsonl"
SUMMARY_JSON = RESULT_DIR / "torch_memory_timing_summary.json"

records: list[dict[str, Any]] = []
run_started = time.perf_counter()
oom = False
error: str | None = None


def _gib(value: int) -> float:
    return value / 1024**3


def _append_jsonl(record: dict[str, Any]) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    with STEPS_JSONL.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


original_update_policy = lerobot_train.update_policy
original_tracker_step = lerobot_train.MetricsTracker.step


def profiled_update_policy(*args: Any, **kwargs: Any):
    """Wrap one real forward/backward/optimizer update."""
    global oom, error

    started = time.perf_counter()
    try:
        result = original_update_policy(*args, **kwargs)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        tracker = result[0]
        loss = float(tracker.metrics["loss"].val)
        record = {
            "step": len(records) + 1,
            "loss": loss,
            "loss_is_finite": math.isfinite(loss),
            "profiled_update_s": time.perf_counter() - started,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else 0,
            "peak_reserved_bytes": torch.cuda.max_memory_reserved() if torch.cuda.is_available() else 0,
            "current_allocated_bytes": torch.cuda.memory_allocated() if torch.cuda.is_available() else 0,
            "current_reserved_bytes": torch.cuda.memory_reserved() if torch.cuda.is_available() else 0,
        }
        records.append(record)
        return result
    except torch.OutOfMemoryError as exc:
        oom = True
        error = f"{type(exc).__name__}: {exc}"
        _append_jsonl(
            {
                "step": len(records) + 1,
                "oom": True,
                "error": error,
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            }
        )
        raise


def profiled_tracker_step(tracker: Any) -> None:
    """Capture the trainer's complete step timing before its meters reset."""
    if records:
        record = records[-1]
        if not record.get("written"):
            for name in ("dataloading_s", "preprocessing_s", "update_s", "step_s", "gpu_mem_gb"):
                if name in tracker.metrics:
                    record[name] = float(tracker.metrics[name].val)
            persisted = {key: value for key, value in record.items() if key != "written"}
            _append_jsonl(persisted)
            record["written"] = True
    original_tracker_step(tracker)


lerobot_train.update_policy = profiled_update_policy
lerobot_train.MetricsTracker.step = profiled_tracker_step


def write_summary(exit_code: int) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    clean_records = [{key: value for key, value in item.items() if key != "written"} for item in records]
    step_times = [float(item["step_s"]) for item in clean_records if "step_s" in item]
    update_times = [float(item["profiled_update_s"]) for item in clean_records]
    losses = [float(item["loss"]) for item in clean_records if "loss" in item]
    allocated = [int(item["peak_allocated_bytes"]) for item in clean_records]
    reserved = [int(item["peak_reserved_bytes"]) for item in clean_records]
    fallback_allocated = torch.cuda.max_memory_allocated() if torch.cuda.is_available() else 0
    fallback_reserved = torch.cuda.max_memory_reserved() if torch.cuda.is_available() else 0
    peak_allocated = max(allocated, default=fallback_allocated)
    peak_reserved = max(reserved, default=fallback_reserved)

    summary = {
        "exit_code": exit_code,
        "oom": oom,
        "error": error,
        "completed_steps": len(clean_records),
        "requested_argv": sys.argv[1:],
        "total_runtime_s": time.perf_counter() - run_started,
        "mean_step_s": statistics.fmean(step_times) if step_times else None,
        "median_step_s": statistics.median(step_times) if step_times else None,
        "mean_profiled_update_s": statistics.fmean(update_times) if update_times else None,
        "peak_allocated_bytes": peak_allocated,
        "peak_allocated_gib": _gib(peak_allocated),
        "peak_reserved_bytes": peak_reserved,
        "peak_reserved_gib": _gib(peak_reserved),
        "first_loss": losses[0] if losses else None,
        "final_loss": losses[-1] if losses else None,
        "final_loss_is_finite": math.isfinite(losses[-1]) if losses else False,
        "all_losses_finite": all(math.isfinite(value) for value in losses),
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "bf16_supported": torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "total_vram_bytes": torch.cuda.get_device_properties(0).total_memory if torch.cuda.is_available() else 0,
        "total_vram_gib": _gib(torch.cuda.get_device_properties(0).total_memory)
        if torch.cuda.is_available()
        else 0,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    global error, oom

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    if STEPS_JSONL.exists():
        raise FileExistsError(f"Refusing to overwrite existing metrics: {STEPS_JSONL}")

    exit_code = 0
    try:
        lerobot_train.main()
    except BaseException as exc:  # Preserve trainer failure while still emitting the summary.
        exit_code = 1
        if isinstance(exc, torch.OutOfMemoryError):
            oom = True
        if error is None:
            error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    finally:
        write_summary(exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
