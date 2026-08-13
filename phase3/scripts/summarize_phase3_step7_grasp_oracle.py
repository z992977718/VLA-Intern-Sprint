#!/usr/bin/env python3
"""Summarize the six fixed, non-overwritable Step 7C oracle trials."""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path

def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--result-dir", type=Path, required=True); args=parser.parse_args()
    rows=[]
    for group in ("alphabet", "tomato"):
        for index in range(3):
            folder=args.result_dir/f"{group}_{index:02d}"
            result=json.loads((folder/"result.json").read_text(encoding="utf-8"))
            motion=json.loads((folder/"object_motion.json").read_text(encoding="utf-8")) if (folder/"object_motion.json").is_file() else None
            rows.append({**result, "object_motion": motion})
    failure=Counter(row["failure_category"] for row in rows)
    by_object={group: [row for row in rows if row["object"].startswith("alphabet") == (group=="alphabet")] for group in ("alphabet", "tomato")}
    success_count=sum(bool(row["success"]) for row in rows)
    classification="ROBUST PASS" if success_count>=5 and all(any(row["success"] for row in by_object[group]) for group in by_object) else ("PARTIAL" if success_count else "FAIL")
    summary={"objects": {group: {"success": sum(bool(row["success"]) for row in values), "trials": 3, "rows": values} for group,values in by_object.items()}, "overall": {"success": success_count, "trials": 6, "classification": classification}, "failure_counts": dict(failure), "policy_used": False, "step6_rerun": False, "physics_changed": False}
    dump(args.result_dir/"trial_summary.json", {"trials": rows})
    dump(args.result_dir/"failure_summary.json", {"counts": dict(failure), "trials": [{"trial_id":r["trial_id"],"failure_category":r["failure_category"]} for r in rows]})
    dump(args.result_dir/"grasp_success_summary.json", summary)
    dump(args.result_dir/"run_status.json", {"phase":"Phase 3 / Step 7C", "formal_trials":6, "hard_reset_per_trial":True, "pi05_called":False, "predict_action_chunk_called":False, "training":False, "step6_rerun":False, "object_teleport":False, "kinematic_attach":False, "physics_parameters_changed":False, "classification":classification})
    (args.result_dir/"summary.md").write_text(f"# Phase 3 / Step 7C Scripted Grasp Oracle\n\n- Alphabet soup: {summary['objects']['alphabet']['success']}/3\n- Tomato sauce: {summary['objects']['tomato']['success']}/3\n- Overall: {success_count}/6 ({classification})\n- Pi0.5 / predict_action_chunk / training / Step 6 rerun: not used.\n", encoding="utf-8")
    return 0
if __name__=="__main__": raise SystemExit(main())
