#!/usr/bin/env python3
"""Generate README SVG figures from frozen evaluation/training artifacts."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "figures"
PROGRESSION = ROOT / "results" / "evaluation" / "pi05_checkpoint_progression" / "checkpoint_comparison.csv"
TRAIN_STEPS = ROOT / "results" / "training" / "pi05_expert_first_stage_2k" / "torch_step_metrics.jsonl"
HELDOUT = ROOT / "results" / "evaluation" / "generalization" / "heldout_initial_states" / "summary.json"

WIDTH = 960
HEIGHT = 540
BG = "#ffffff"
FG = "#172033"
MUTED = "#5f6b7a"
GRID = "#d8dee8"
BLUE = "#2563eb"
GREEN = "#159a63"
ORANGE = "#e07a1f"
RED = "#c2413b"


def load_progression() -> list[dict[str, str]]:
    with PROGRESSION.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if [row["checkpoint"] for row in rows] != ["pretrained", "checkpoint_001000", "checkpoint_002000"]:
        raise ValueError("Unexpected checkpoint progression rows")
    return rows


def svg_document(title: str, description: str, body: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">{escape(description)}</desc>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>
  <style>
    text {{ font-family: "Microsoft YaHei", "Noto Sans CJK SC", Inter, "Segoe UI", Arial, sans-serif; fill: {FG}; }}
    .title {{ font-size: 28px; font-weight: 600; }}
    .subtitle {{ font-size: 15px; fill: {MUTED}; }}
    .axis {{ font-size: 13px; fill: {MUTED}; }}
    .value {{ font-size: 16px; font-weight: 600; }}
    .label {{ font-size: 15px; }}
  </style>
{body}
</svg>
'''


def write(name: str, title: str, description: str, body: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(svg_document(title, description, body), encoding="utf-8")


def bar_chart(
    name: str,
    title: str,
    subtitle: str,
    values: list[float],
    labels: list[str],
    annotations: list[str],
    y_max: float,
    y_ticks: list[float],
    unit: str,
    description: str,
) -> None:
    left, right, top, bottom = 105, 55, 105, 100
    plot_w, plot_h = WIDTH - left - right, HEIGHT - top - bottom
    slot = plot_w / len(values)
    bar_w = min(150, slot * 0.55)
    parts = [
        f'  <text x="{left}" y="48" class="title">{escape(title)}</text>',
        f'  <text x="{left}" y="75" class="subtitle">{escape(subtitle)}</text>',
    ]
    for tick in y_ticks:
        y = top + plot_h - (tick / y_max) * plot_h
        parts.append(f'  <line x1="{left}" y1="{y:.1f}" x2="{WIDTH-right}" y2="{y:.1f}" stroke="{GRID}"/>')
        parts.append(f'  <text x="{left-14}" y="{y+5:.1f}" text-anchor="end" class="axis">{tick:g}{escape(unit)}</text>')
    colors = [MUTED, ORANGE, BLUE]
    for idx, (value, label, annotation) in enumerate(zip(values, labels, annotations, strict=True)):
        x = left + slot * idx + (slot - bar_w) / 2
        h = (value / y_max) * plot_h
        y = top + plot_h - h
        parts.append(f'  <rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="5" fill="{colors[idx]}"/>')
        value_text = f"{value:.1f}{unit}" if value % 1 else f"{int(value)}{unit}"
        parts.append(f'  <text x="{x+bar_w/2:.1f}" y="{y-12:.1f}" text-anchor="middle" class="value">{escape(value_text)}</text>')
        parts.append(f'  <text x="{x+bar_w/2:.1f}" y="{top+plot_h+32:.1f}" text-anchor="middle" class="label">{escape(label)}</text>')
        parts.append(f'  <text x="{x+bar_w/2:.1f}" y="{top+plot_h+57:.1f}" text-anchor="middle" class="axis">{escape(annotation)}</text>')
    write(name, title, description, "\n".join(parts))


def make_success_and_length(rows: list[dict[str, str]]) -> None:
    labels = ["Pretrained", "Checkpoint 1k", "Checkpoint 2k"]
    episodes = [int(row["episodes"]) for row in rows]
    annotations = [f"{int(row['success_count'])}/{n} 个 Episode" for row, n in zip(rows, episodes, strict=True)]
    bar_chart(
        "checkpoint-success-rate.svg",
        "Checkpoint 与成功率",
        "重点任务；2k 使用 30 个 Episode，Pretrained 和 1k 各使用 10 个",
        [float(row["success_rate_pct"]) for row in rows],
        labels,
        annotations,
        100,
        [0, 25, 50, 75, 100],
        "%",
        "成功率：Pretrained 0/10，Checkpoint 1k 9/10，Checkpoint 2k 28/30。",
    )
    bar_chart(
        "checkpoint-mean-episode-length.svg",
        "Checkpoint 与平均 Episode 长度",
        "数值越低表示完成越快；失败 Episode 会达到 520-step horizon",
        [float(row["mean_episode_length"]) for row in rows],
        labels,
        [f"n={n}" for n in episodes],
        560,
        [0, 140, 280, 420, 560],
        "",
        "平均 Episode 长度：Pretrained 520，Checkpoint 1k 290，Checkpoint 2k 291.13 control steps。",
    )


def make_loss_curve() -> None:
    rows = [json.loads(line) for line in TRAIN_STEPS.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 2000 or [row["step"] for row in rows] != list(range(1, 2001)):
        raise ValueError("Training metrics must contain exact steps 1-2000")
    losses = [float(row["loss"]) for row in rows]
    if not all(math.isfinite(value) and value > 0 for value in losses):
        raise ValueError("Loss curve requires positive finite raw values")

    left, right, top, bottom = 105, 55, 105, 90
    plot_w, plot_h = WIDTH - left - right, HEIGHT - top - bottom
    log_min, log_max = math.log10(0.004), math.log10(10.0)

    def x(step: int) -> float:
        return left + (step - 1) / 1999 * plot_w

    def y(loss: float) -> float:
        return top + plot_h - (math.log10(loss) - log_min) / (log_max - log_min) * plot_h

    path = " ".join(("M" if i == 0 else "L") + f"{x(row['step']):.2f},{y(float(row['loss'])):.2f}" for i, row in enumerate(rows))
    parts = [
        f'  <text x="{left}" y="48" class="title">训练 Loss 曲线</text>',
        f'  <text x="{left}" y="75" class="subtitle">全部 2,000 个原始逐步 Loss；对数 Y 轴；未平滑</text>',
    ]
    for tick in [0.01, 0.1, 1, 10]:
        ty = y(tick)
        parts.append(f'  <line x1="{left}" y1="{ty:.1f}" x2="{WIDTH-right}" y2="{ty:.1f}" stroke="{GRID}"/>')
        parts.append(f'  <text x="{left-14}" y="{ty+5:.1f}" text-anchor="end" class="axis">{tick:g}</text>')
    for step in [1, 500, 1000, 1500, 2000]:
        tx = x(step)
        parts.append(f'  <line x1="{tx:.1f}" y1="{top}" x2="{tx:.1f}" y2="{top+plot_h}" stroke="{GRID}"/>')
        parts.append(f'  <text x="{tx:.1f}" y="{top+plot_h+30}" text-anchor="middle" class="axis">{step}</text>')
    parts.append(f'  <path d="{path}" fill="none" stroke="{BLUE}" stroke-width="1.15" stroke-linejoin="round" opacity="0.88"/>')
    for step, label in [(1000, "1k: 0.1992"), (2000, "2k: 0.2040")]:
        value = losses[step - 1]
        tx, ty = x(step), y(value)
        parts.append(f'  <circle cx="{tx:.1f}" cy="{ty:.1f}" r="5" fill="{ORANGE}" stroke="{BG}" stroke-width="2"/>')
        anchor = "end" if step == 2000 else "start"
        dx = -10 if step == 2000 else 10
        parts.append(f'  <text x="{tx+dx:.1f}" y="{ty-12:.1f}" text-anchor="{anchor}" class="value">{label}</text>')
    parts.append(f'  <text x="{left+plot_w/2:.1f}" y="{HEIGHT-24}" text-anchor="middle" class="axis">Optimizer Step</text>')
    parts.append(f'  <text x="28" y="{top+plot_h/2:.1f}" transform="rotate(-90 28 {top+plot_h/2:.1f})" text-anchor="middle" class="axis">Flow-matching Loss（对数）</text>')
    write(
        "training-loss-curve.svg",
        "训练 Loss 曲线",
        "在对数 y 轴上展示全部 2,000 个 optimizer step 的原始正 loss，并标出 checkpoint step 1,000 和 2,000。",
        "\n".join(parts),
    )


def make_latency(rows: list[dict[str, str]]) -> None:
    left, right, top, bottom = 105, 55, 115, 100
    plot_w, plot_h = WIDTH - left - right, HEIGHT - top - bottom
    labels = ["Pretrained", "Checkpoint 1k", "Checkpoint 2k"]
    mean_values = [float(row["mean_model_inference_ms"]) for row in rows]
    p95_values = [float(row["p95_model_inference_ms"]) for row in rows]
    y_max = 250
    slot = plot_w / 3
    bar_w = 62
    parts = [
        f'  <text x="{left}" y="48" class="title">推理延迟对比</text>',
        f'  <text x="{left}" y="75" class="subtitle">CUDA 同步的 predict_action_chunk 调用；2k 为 30-Episode Run</text>',
        f'  <rect x="{left}" y="91" width="14" height="14" fill="{BLUE}"/><text x="{left+22}" y="103" class="axis">平均值</text>',
        f'  <rect x="{left+88}" y="91" width="14" height="14" fill="{ORANGE}"/><text x="{left+110}" y="103" class="axis">p95</text>',
    ]
    for tick in [0, 50, 100, 150, 200, 250]:
        ty = top + plot_h - tick / y_max * plot_h
        parts.append(f'  <line x1="{left}" y1="{ty:.1f}" x2="{WIDTH-right}" y2="{ty:.1f}" stroke="{GRID}"/>')
        parts.append(f'  <text x="{left-14}" y="{ty+5:.1f}" text-anchor="end" class="axis">{tick} ms</text>')
    for idx, label in enumerate(labels):
        center = left + slot * idx + slot / 2
        for offset, value, color in [(-bar_w, mean_values[idx], BLUE), (0, p95_values[idx], ORANGE)]:
            h = value / y_max * plot_h
            bx, by = center + offset, top + plot_h - h
            parts.append(f'  <rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w-6}" height="{h:.1f}" rx="4" fill="{color}"/>')
            parts.append(f'  <text x="{bx+(bar_w-6)/2:.1f}" y="{by-9:.1f}" text-anchor="middle" class="axis">{value:.1f}</text>')
        parts.append(f'  <text x="{center-3:.1f}" y="{top+plot_h+34:.1f}" text-anchor="middle" class="label">{label}</text>')
    write(
        "inference-latency-comparison.svg",
        "推理延迟对比",
        "Pretrained、Checkpoint 1k 和 Checkpoint 2k 的 Pi0.5 action-chunk 平均与 p95 推理延迟。",
        "\n".join(parts),
    )


def make_fixed_state_summary() -> None:
    summary = json.loads(HELDOUT.read_text(encoding="utf-8"))
    if summary["success_count"] != 18 or summary["init_state_ids"] != list(range(30, 50)):
        raise ValueError("Unexpected additional fixed-state summary")
    success, failure, total = 46, 4, 50
    left, right, top = 105, 55, 135
    plot_w = WIDTH - left - right
    bar_h = 92
    success_w = plot_w * success / total
    failure_w = plot_w - success_w
    parts = [
        f'  <text x="{left}" y="48" class="title">Checkpoint 2k：完整固定初态评测</text>',
        f'  <text x="{left}" y="78" class="subtitle">仅重点任务：状态 0-29 为 28/30，此前未评测状态 30-49 为 18/20</text>',
        f'  <rect x="{left}" y="{top}" width="{success_w:.1f}" height="{bar_h}" rx="7" fill="{GREEN}"/>',
        f'  <rect x="{left+success_w:.1f}" y="{top}" width="{failure_w:.1f}" height="{bar_h}" rx="7" fill="{RED}"/>',
        f'  <text x="{left+success_w/2:.1f}" y="{top+55}" text-anchor="middle" style="font-size:26px;font-weight:600;fill:#ffffff">46 次成功</text>',
        f'  <text x="{left+success_w+failure_w/2:.1f}" y="{top+55}" text-anchor="middle" style="font-size:18px;font-weight:600;fill:#ffffff">4</text>',
        f'  <text x="{left}" y="{top+bar_h+48}" class="value">46/50 = 92.0%</text>',
        f'  <text x="{left}" y="{top+bar_h+78}" class="subtitle">同一任务的全部存储固定初态；不是完整 LIBERO Benchmark</text>',
        f'  <text x="{left}" y="{top+bar_h+122}" class="label">失败：Init-State ID 14、18、41、49</text>',
        f'  <text x="{left}" y="{top+bar_h+151}" class="subtitle">四个已审查失败均出现错误物体选择行为。</text>',
    ]
    write(
        "fixed-state-summary.svg",
        "Checkpoint 2k 完整固定初态评测",
        "Checkpoint 2k 在重点任务的 50 个存储固定初态中成功 46 次、失败 4 次。",
        "\n".join(parts),
    )


def main() -> int:
    rows = load_progression()
    make_success_and_length(rows)
    make_loss_curve()
    make_latency(rows)
    make_fixed_state_summary()
    for path in sorted(OUT.glob("*.svg")):
        print(path.relative_to(ROOT), path.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
