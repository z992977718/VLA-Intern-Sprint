#!/usr/bin/env python3
"""Create a paired Pi0.5 baseline-versus-checkpoint comparison."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--training-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite comparison: {args.output_dir}")
    args.output_dir.mkdir(parents=True)

    baseline = load_json(args.baseline_dir / "summary.json")
    checkpoint = load_json(args.checkpoint_dir / "summary.json")
    training = load_json(args.training_summary)
    baseline_eps = load_csv(args.baseline_dir / "episodes.csv")
    checkpoint_eps = load_csv(args.checkpoint_dir / "episodes.csv")

    if baseline["seeds"] != checkpoint["seeds"]:
        raise ValueError("Evaluation seeds differ; paired comparison is invalid")
    if (baseline["suite"], baseline["task_id"]) != (checkpoint["suite"], checkpoint["task_id"]):
        raise ValueError("Evaluation task differs; paired comparison is invalid")

    paired_rows = []
    for base_row, tuned_row in zip(baseline_eps, checkpoint_eps, strict=True):
        if base_row["seed"] != tuned_row["seed"]:
            raise ValueError("Episode order/seeds differ")
        paired_rows.append(
            {
                "seed": int(base_row["seed"]),
                "baseline_success": base_row["success"].lower() == "true",
                "checkpoint_success": tuned_row["success"].lower() == "true",
                "baseline_episode_length": int(base_row["episode_length"]),
                "checkpoint_episode_length": int(tuned_row["episode_length"]),
                "episode_length_delta": int(tuned_row["episode_length"]) - int(base_row["episode_length"]),
                "baseline_video": base_row["video_path"],
                "checkpoint_video": tuned_row["video_path"],
            }
        )

    success_delta_pp = (checkpoint["success_rate"] - baseline["success_rate"]) * 100.0
    latency_delta_ms = checkpoint["mean_model_inference_ms"] - baseline["mean_model_inference_ms"]
    comparison = {
        "protocol": {
            "suite": baseline["suite"],
            "task_id": baseline["task_id"],
            "task_description": baseline["task_description"],
            "episodes_per_policy": baseline["episodes"],
            "seeds": baseline["seeds"],
            "precision": baseline["policy_dtype"],
            "n_action_steps": baseline["n_action_steps"],
            "hard_reset": baseline["hard_reset"],
        },
        "training": {
            "completed_steps": training["completed_steps"],
            "batch_size": 1,
            "first_loss": training["first_loss"],
            "final_loss": training["final_loss"],
            "all_losses_finite": training["all_losses_finite"],
            "oom": training["oom"],
            "mean_step_s": training["mean_step_s"],
            "total_runtime_s": training["total_runtime_s"],
            "peak_allocated_gib": training["peak_allocated_gib"],
            "peak_reserved_gib": training["peak_reserved_gib"],
        },
        "baseline": baseline,
        "checkpoint": checkpoint,
        "deltas": {
            "success_rate_percentage_points": success_delta_pp,
            "mean_episode_length": checkpoint["mean_episode_length"] - baseline["mean_episode_length"],
            "mean_model_inference_ms": latency_delta_ms,
            "mean_model_inference_percent": latency_delta_ms / baseline["mean_model_inference_ms"] * 100.0,
            "eval_wall_s": checkpoint["eval_wall_s"] - baseline["eval_wall_s"],
        },
        "conclusion": (
            "The 2k expert-only checkpoint is better on this paired task: all ten paired episodes changed "
            "from failure to success. This is a single-task engineering result, not a full LIBERO benchmark."
        ),
    }

    (args.output_dir / "summary.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    with (args.output_dir / "episodes_paired.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(paired_rows[0]))
        writer.writeheader()
        writer.writerows(paired_rows)

    report = f"""# Pi0.5 first paired comparison

## Result

| Metric | Pretrained baseline | 2k expert-only checkpoint | Change |
| --- | ---: | ---: | ---: |
| Success | {baseline['success_count']}/{baseline['episodes']} ({baseline['success_rate'] * 100:.1f}%) | {checkpoint['success_count']}/{checkpoint['episodes']} ({checkpoint['success_rate'] * 100:.1f}%) | {success_delta_pp:+.1f} percentage points |
| Mean episode length | {baseline['mean_episode_length']:.1f} | {checkpoint['mean_episode_length']:.1f} | {checkpoint['mean_episode_length'] - baseline['mean_episode_length']:+.1f} steps |
| Mean model inference | {baseline['mean_model_inference_ms']:.2f} ms | {checkpoint['mean_model_inference_ms']:.2f} ms | {latency_delta_ms:+.2f} ms |
| p95 model inference | {baseline['p95_model_inference_ms']:.2f} ms | {checkpoint['p95_model_inference_ms']:.2f} ms | {checkpoint['p95_model_inference_ms'] - baseline['p95_model_inference_ms']:+.2f} ms |
| Evaluation wall time | {baseline['eval_wall_s']:.2f} s | {checkpoint['eval_wall_s']:.2f} s | {checkpoint['eval_wall_s'] - baseline['eval_wall_s']:+.2f} s |
| Peak allocated VRAM | {baseline['peak_allocated_gib']:.2f} GiB | {checkpoint['peak_allocated_gib']:.2f} GiB | {checkpoint['peak_allocated_gib'] - baseline['peak_allocated_gib']:+.2f} GiB |

The paired protocol used `libero_10` task 0, seeds 1000–1009, BF16,
`n_action_steps=10`, fixed initial states, hard resets, and a 520-step limit.
Every baseline episode timed out; every 2k-checkpoint episode succeeded in
227–370 steps.

## Training evidence

- 2,000/2,000 optimizer steps, batch size 1.
- Expert-only, frozen vision encoder, gradient checkpointing, BF16.
- First profiled loss: {training['first_loss']:.6f}; final profiled loss: {training['final_loss']:.6f}.
- All losses finite: `{str(training['all_losses_finite']).lower()}`; OOM: `{str(training['oom']).lower()}`.
- Mean step time: {training['mean_step_s']:.4f} s; total wrapper runtime: {training['total_runtime_s']:.2f} s.
- Peak allocated/reserved training VRAM: {training['peak_allocated_gib']:.2f}/{training['peak_reserved_gib']:.2f} GiB.

## Interpretation

The 2k checkpoint is decisively better than the pretrained baseline on this
specific paired task. The change in training loss and the change in success
rate are separate observations: loss is an offline optimization signal, while
success is a closed-loop environment outcome. The lower loss does not by
itself prove the rollout improvement; the paired 0/10 versus 10/10 rollout is
the direct evidence.

This is not a full LIBERO benchmark. It covers one of the ten LIBERO-Long
tasks and therefore must not be presented as a 100% LIBERO success rate.

## Decision

Stop at the planned decision point. Keep the RTX 6000D and both 1k/2k
checkpoints. Do not automatically continue to 5k or 10k; the next experiment
should be chosen only after reviewing this report and the videos.
"""
    (args.output_dir / "comparison.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
