"""Create a fixed, auditable S0 through S4 Scene 2 experiment manifest."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from meatcell.experiment_matrix import build_manifest, sha256_file, validate_manifest, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_root")
    parser.add_argument("--flows", nargs="+", default=["a", "b"])
    parser.add_argument("--stacks", nargs="+", default=["S0", "S1", "S2", "S3", "S4"])
    parser.add_argument("--seed", type=int, default=4801)
    parser.add_argument("--perturbation", default="pose_disturbance")
    parser.add_argument("--belt-speed-mps", type=float, default=0.16)
    parser.add_argument("--start-y-m", type=float, default=0.02)
    parser.add_argument("--start-yaw-deg", type=float, default=35.0)
    args = parser.parse_args()

    output_root = Path(args.output_root)
    yolo_model = PROJECT_ROOT / "models" / "yolo26_meat_reference_buffer_v2" / "weights" / "best.pt"
    grasp_model = PROJECT_ROOT / "models" / "grasp_affordance_v2_matched" / "model.json"
    manifest = build_manifest(
        experiment_id=output_root.name,
        flows=args.flows,
        stacks=args.stacks,
        seed=args.seed,
        perturbation=args.perturbation,
        belt_speed_mps=args.belt_speed_mps,
        start_y_m=args.start_y_m,
        start_yaw_deg=args.start_yaw_deg,
        model_hashes={
            "yolo26": sha256_file(yolo_model) if yolo_model.exists() else None,
            "grasp_affordance": sha256_file(grasp_model) if grasp_model.exists() else None,
            "contact_skill": None,
        },
    )
    validate_manifest(manifest)
    write_json(output_root / "experiment_manifest.json", manifest)
    print((output_root / "experiment_manifest.json").resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
