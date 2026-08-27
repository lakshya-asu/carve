"""Probe reachable top-down FANUC pickup poses with the project Lula model."""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    from isaacsim import SimulationApp

    app = SimulationApp({"headless": True})
    try:
        import numpy as np

        from isaacsim.robot_motion.motion_generation import LulaKinematicsSolver

        solver = LulaKinematicsSolver(
            str(PROJECT_ROOT / "configs" / "fanuc_m10id12_lula.yaml"),
            str(PROJECT_ROOT / "assets" / "robots" / "fanuc_m10id12" / "fanuc_m10id12.urdf"),
        )
        solver.set_robot_base_pose(
            np.asarray((0.35, -1.25, 0.59), dtype=float),
            np.asarray((2.0**-0.5, 0.0, 0.0, 2.0**-0.5), dtype=float),
        )
        top_down = np.asarray((2.0**-0.5, 0.0, 2.0**-0.5, 0.0), dtype=float)
        warm_start = np.asarray((0.0, 1.2, 0.4, 0.0, -0.77, 0.0), dtype=float)
        targets = []
        probes = (
            ("intercept_start", (-0.55, 0.0, 0.875)),
            ("intercept_mid", (-0.25, 0.0, 0.875)),
            ("intercept_end", (0.05, 0.0, 0.875)),
            ("compliance_high", (0.05, 0.0, 1.10)),
            ("intercept_limit", (0.35, 0.0, 0.875)),
            ("cutter_tray_current", (1.92, 0.0, 0.88)),
            ("cutter_candidate_140", (1.40, 0.0, 0.88)),
            ("cutter_candidate_130", (1.30, 0.0, 0.88)),
            ("cutter_candidate_120", (1.20, 0.0, 0.88)),
            ("buffer", (1.25, -0.55, 0.88)),
            ("reject", (1.25, -0.70, 0.98)),
        )
        for label, center in probes:
            product_center = np.asarray(center, dtype=float)
            flange_position = product_center + np.asarray((0.0, 0.0, 0.35), dtype=float)
            joints, success = solver.compute_inverse_kinematics(
                "ee_link",
                flange_position,
                top_down,
                warm_start=warm_start,
                position_tolerance=0.002,
                orientation_tolerance=0.02,
            )
            entry = {
                "label": label,
                "product_center_m": product_center.tolist(),
                "flange_target_m": flange_position.tolist(),
                "success": bool(success),
                "joint_positions_rad": np.asarray(joints, dtype=float).tolist(),
            }
            if success:
                achieved_position, achieved_rotation = solver.compute_forward_kinematics("ee_link", joints)
                entry["achieved_flange_m"] = np.asarray(achieved_position, dtype=float).tolist()
                entry["position_error_m"] = float(np.linalg.norm(achieved_position - flange_position))
                warm_start = np.asarray(joints, dtype=float)
            targets.append(entry)
        print(json.dumps({"targets": targets}, indent=2))
        required = {"intercept_mid", "intercept_end", "cutter_candidate_130", "buffer", "reject"}
        passed = all(item["success"] for item in targets if item["label"] in required)
        return 0 if passed else 1
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
