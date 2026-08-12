#!/usr/bin/env python3
"""Create compact acceptance artifacts from a profiled Pi0.5 sanity run."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    result_dir = Path(sys.argv[1])
    summary_path = result_dir / "torch_memory_timing_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    checkpoint = result_dir / "run" / "checkpoints" / "000020"
    checkpoint_ok = checkpoint.is_dir()
    passed = (
        summary["exit_code"] == 0
        and summary["completed_steps"] == 20
        and summary["all_losses_finite"]
        and not summary["oom"]
        and checkpoint_ok
    )

    memory_lines = [
        f"gpu_name={summary['gpu_name']}",
        f"total_vram_gib={summary['total_vram_gib']}",
        f"peak_allocated_gib={summary['peak_allocated_gib']}",
        f"peak_reserved_gib={summary['peak_reserved_gib']}",
        f"oom={summary['oom']}",
    ]
    (result_dir / "memory_stats.txt").write_text("\n".join(memory_lines) + "\n", encoding="utf-8")

    timing_lines = [
        f"completed_steps={summary['completed_steps']}",
        f"total_runtime_s={summary['total_runtime_s']}",
        f"mean_step_s={summary['mean_step_s']}",
        f"median_step_s={summary['median_step_s']}",
        f"mean_profiled_update_s={summary['mean_profiled_update_s']}",
    ]
    (result_dir / "timing.txt").write_text("\n".join(timing_lines) + "\n", encoding="utf-8")

    report = f"""# Pi0.5 sanity training on the new server

- Result: {'PASS' if passed else 'FAIL'}
- GPU: {summary['gpu_name']}
- Total VRAM: {summary['total_vram_gib']:.2f} GiB
- Steps: {summary['completed_steps']} / 20
- Batch size: 1
- Precision: bfloat16 (Accelerate bf16)
- Train expert only: true
- Gradient checkpointing: true
- Freeze vision encoder: true
- Peak allocated VRAM: {summary['peak_allocated_gib']:.2f} GiB
- Peak reserved VRAM: {summary['peak_reserved_gib']:.2f} GiB
- Mean step time: {summary['mean_step_s']} s
- Total runtime: {summary['total_runtime_s']:.2f} s
- Initial loss: {summary['first_loss']}
- Final loss: {summary['final_loss']}
- All losses finite: {summary['all_losses_finite']}
- OOM: {summary['oom']}
- Final checkpoint: {'PASS' if checkpoint_ok else 'FAIL'} (`{checkpoint}`)
"""
    (result_dir / "result_summary.md").write_text(report, encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
