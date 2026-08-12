#!/usr/bin/env python3
"""Create evenly sampled contact sheets for failed evaluation videos."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def make_sheet(video_path: Path, output_path: Path, samples: int = 20, columns: int = 5) -> None:
    capture = cv2.VideoCapture(str(video_path))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(capture.get(cv2.CAP_PROP_FPS)) or 1.0
    if frame_count <= 0:
        raise RuntimeError(f"No frames found in {video_path}")

    indices = np.linspace(0, frame_count - 1, samples, dtype=int)
    tiles: list[np.ndarray] = []
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f"Could not read frame {index} from {video_path}")
        height, width = frame.shape[:2]
        target_width = 384
        target_height = round(height * target_width / width)
        frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
        cv2.rectangle(frame, (0, 0), (target_width, 28), (0, 0, 0), thickness=-1)
        cv2.putText(
            frame,
            f"frame {index}/{frame_count - 1}  t={index / fps:.2f}s",
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        tiles.append(frame)
    capture.release()

    rows = (len(tiles) + columns - 1) // columns
    blank = np.zeros_like(tiles[0])
    while len(tiles) < rows * columns:
        tiles.append(blank.copy())
    sheet = np.vstack([np.hstack(tiles[row * columns : (row + 1) * columns]) for row in range(rows)])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), sheet):
        raise RuntimeError(f"Could not write {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=20)
    args = parser.parse_args()
    for video_path in args.video:
        output = args.output_dir / f"{video_path.parent.parent.name}_{video_path.stem}_contact_sheet.jpg"
        make_sheet(video_path, output, samples=args.samples)
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
