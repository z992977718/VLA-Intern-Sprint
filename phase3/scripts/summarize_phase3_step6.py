#!/usr/bin/env python3
"""Summarize only measured Step 6 evidence."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from phase3_step6_common import LANGUAGE, atomic_json


def main() -> int:
    project = Path("/root/autodl-tmp/VLA-Intern-Sprint")
    result = project / "results/phase3_step6"
    episodes = []
    latencies = []
    for index in range(3):
        folder = result / f"episode_{index:02d}"
        complete = json.loads((folder / "episode_complete.json").read_text(encoding="utf-8"))
        cycle_files = sorted(folder.glob("cycle_???.json"))
        cycles = [json.loads(path.read_text(encoding="utf-8")) for path in cycle_files]
        latencies.extend(record["inference_latency_ms"] for record in cycles)
        episodes.append(
            {
                "episode_index": index,
                "initial_state_id": index,
                "completed": complete["completed"],
                "success": complete["success"],
                "termination": complete["termination"],
                "cycles_completed": complete["cycles_completed"],
                "runtime_sec": complete["runtime_sec"],
                "video": f"assets/videos/phase3_step6_ep{index:02d}.mp4",
            }
        )
    policy = json.loads((result / "policy_complete.json").read_text(encoding="utf-8"))
    successes = sum(int(episode["success"]) for episode in episodes)
    pipeline_pass = all(episode["completed"] for episode in episodes) and policy["total_real_inference_calls"] == sum(
        episode["cycles_completed"] for episode in episodes
    )
    summary = {
        "step": "Phase 3 / Step 6",
        "experimental_pipeline_pass": bool(pipeline_pass),
        "task_success_count": successes,
        "episodes": 3,
        "success_rate": successes / 3.0,
        "language": LANGUAGE,
        "checkpoint": "results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model",
        "cross_simulator_claim": "same LIBERO semantic task reconstructed in Isaac Sim; no retraining",
        "prohibited_claims": ["unseen-task", "zero-shot new-task", "open-world generalization", "sim-to-real"],
        "receding_horizon_k": 1,
        "max_cycles": 100,
        "episodes_detail": episodes,
        "inference_latency_ms": {
            "count": len(latencies),
            "mean": statistics.fmean(latencies) if latencies else None,
            "median": statistics.median(latencies) if latencies else None,
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "torch_peak_allocated_bytes": policy["torch_peak_allocated_bytes"],
        "torch_peak_reserved_bytes": policy["torch_peak_reserved_bytes"],
        "oom": policy["oom"] or any(json.loads((result / f"episode_{i:02d}/episode_complete.json").read_text())["oom"] for i in range(3)),
        "manual_intervention": False,
        "training_or_weight_update": False,
    }
    atomic_json(result / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if pipeline_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
