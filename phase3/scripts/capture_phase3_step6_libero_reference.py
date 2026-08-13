#!/usr/bin/env python3
"""Capture source-of-truth LIBERO task metadata and two policy-facing camera frames."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from lerobot.envs.libero import get_task_init_states
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv


TASK_SUITE = "libero_10"
TASK_ID = 0
INSTRUCTION = "put both the alphabet soup and the tomato sauce in the basket"
CAMERAS = ("agentview", "robot0_eye_in_hand")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def names(model: object, kind: str, count: int) -> list[str]:
    method = getattr(model, f"{kind}_id2name")
    return [str(method(index)) for index in range(count)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--init-state-id", type=int, default=0)
    parser.add_argument("--resolution", type=int, default=360)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    output.mkdir(parents=True)

    suite = benchmark.get_benchmark_dict()[TASK_SUITE]()
    task = suite.get_task(TASK_ID)
    if task.language != INSTRUCTION:
        raise RuntimeError(f"Task mismatch: {task.language}")
    bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
    init_states = np.asarray(get_task_init_states(suite, TASK_ID))
    if not 0 <= args.init_state_id < len(init_states):
        raise IndexError(args.init_state_id)

    env = OffScreenRenderEnv(
        bddl_file_name=str(bddl),
        camera_names=list(CAMERAS),
        camera_heights=args.resolution,
        camera_widths=args.resolution,
        control_freq=20,
        hard_reset=True,
    )
    try:
        env.reset()
        raw = env.set_init_state(init_states[args.init_state_id])
        for _ in range(10):
            raw, _, _, _ = env.step([0, 0, 0, 0, 0, 0, -1])

        image_files: dict[str, dict[str, str]] = {}
        for camera in CAMERAS:
            key = f"{camera}_image"
            raw_image = np.asarray(raw[key], dtype=np.uint8)
            raw_path = output / f"libero_{camera}_raw.png"
            policy_path = output / f"libero_{camera}.png"
            Image.fromarray(raw_image).save(raw_path)
            # Current LeRobot LiberoProcessorStep flips both H and W before Pi0.5.
            Image.fromarray(raw_image[::-1, ::-1]).save(policy_path)
            image_files[camera] = {
                "raw": raw_path.name,
                "raw_sha256": sha256(raw_path),
                "policy_facing": policy_path.name,
                "policy_facing_sha256": sha256(policy_path),
                "shape": list(raw_image.shape),
            }

        sim = env.sim
        model = sim.model
        data = sim.data
        body_names = names(model, "body", model.nbody)
        body_poses = {}
        for body_name in body_names:
            if any(token in body_name for token in ("alphabet_soup", "tomato_sauce", "basket")):
                body_id = model.body_name2id(body_name)
                body_poses[body_name] = {
                    "position_xyz_m": np.asarray(data.body_xpos[body_id], dtype=float).tolist(),
                    "quaternion_wxyz": np.asarray(data.body_xquat[body_id], dtype=float).tolist(),
                }

        camera_poses = {}
        for camera in CAMERAS:
            camera_id = model.camera_name2id(camera)
            camera_poses[camera] = {
                "model_parent_body": model.body_id2name(int(model.cam_bodyid[camera_id])),
                "local_position_xyz_m": np.asarray(model.cam_pos[camera_id], dtype=float).tolist(),
                "local_quaternion_wxyz": np.asarray(model.cam_quat[camera_id], dtype=float).tolist(),
                "world_position_xyz_m": np.asarray(data.cam_xpos[camera_id], dtype=float).tolist(),
                "world_rotation_matrix": np.asarray(data.cam_xmat[camera_id], dtype=float).reshape(3, 3).tolist(),
                "fovy_deg": float(model.cam_fovy[camera_id]),
            }

        robot = env.robots[0]
        robot_joint_positions = np.asarray(data.qpos[robot._ref_joint_pos_indexes], dtype=float)
        gripper_positions = np.asarray(raw["robot0_gripper_qpos"], dtype=float)
        robot_root_body = str(robot.robot_model.root_body)
        robot_root_body_id = model.body_name2id(robot_root_body)
        report = {
            "task_suite": TASK_SUITE,
            "suite_task_id": TASK_ID,
            "suite_task_index_zero_based": TASK_ID,
            "language": task.language,
            "task_name": task.name,
            "problem_folder": task.problem_folder,
            "bddl_file": str(bddl),
            "bddl_sha256": sha256(bddl),
            "robot_class": type(robot).__name__,
            "robot_model_class": type(robot.robot_model).__name__,
            "robot_model_name": str(robot.robot_model.name),
            "robot_root_body": robot_root_body,
            "robot_base_position_xyz_m": np.asarray(data.body_xpos[robot_root_body_id], dtype=float).tolist(),
            "robot_base_quaternion_wxyz": np.asarray(data.body_xquat[robot_root_body_id], dtype=float).tolist(),
            "robot_initial_joint_positions_rad": robot_joint_positions.tolist(),
            "gripper_initial_qpos": gripper_positions.tolist(),
            "eef_position_xyz_m": np.asarray(raw["robot0_eef_pos"], dtype=float).tolist(),
            "eef_quaternion_xyzw": np.asarray(raw["robot0_eef_quat"], dtype=float).tolist(),
            "control_frequency_hz": 20,
            "mujoco_timestep_sec": float(model.opt.timestep),
            "phase1_episode_horizon_control_steps": 520,
            "phase1_evaluation_resolution": [args.resolution, args.resolution],
            "camera_poses": camera_poses,
            "body_poses": body_poses,
            "initial_state_id": args.init_state_id,
            "initial_state_count": int(len(init_states)),
            "initial_state_vector_shape": list(init_states.shape),
            "check_success_at_reset": bool(env.check_success()),
            "images": image_files,
            "success_source": {
                "bddl_goal": "And(In(alphabet_soup_1, basket_1_contain_region), In(tomato_sauce_1, basket_1_contain_region))",
                "predicate_in": "container.check_contact(object) and container.check_contain(object)",
            },
        }
        (output / "libero_reference.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (output / "task.bddl").write_text(bddl.read_text(encoding="utf-8"), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
