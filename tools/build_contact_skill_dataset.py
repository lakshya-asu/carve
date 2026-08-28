"""Build Route E behavior-cloning rows from complete Isaac Scene 2 cycles."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PHASE_LABELS = {
    "close": "short matched-velocity force-limited closure",
    "stabilize": "contact-confirmed dynamic hold",
    "reorientation": "reorientation for cutter presentation",
    "release": "release on stationary cutter-entry tray",
}


def _duration(sequence: list[dict], text: str, default: float) -> float:
    for item in sequence:
        if text in item["label"]:
            return float(item["duration_s"])
    return default


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    metrics_paths: list[Path] = []
    for root in args.root:
        metrics_paths.extend(Path(root).resolve().rglob("scene2_integrated_metrics.json"))
    payloads = []
    for path in sorted(set(metrics_paths)):
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if (
            payload.get("passed")
            and payload.get("delivery", {}).get("delivered")
            and payload.get("initial_pose", {}).get("yaw_rad") is not None
            and payload.get("grasp", {}).get("commanded_product_width_m") is not None
            and len(payload.get("grasp", {}).get("peak_contact_force_n", ())) == 2
            and payload.get("sequence")
            and payload.get("artifacts", {}).get("rgb")
            and payload.get("artifacts", {}).get("depth_npy")
        ):
            payloads.append((path, payload))
    seeds = sorted({int(payload["seed"]) for _, payload in payloads})
    if len(seeds) < 5:
        raise RuntimeError("Route E requires at least five complete seeded simulator cycles")
    held_out_count = max(1, len(seeds) // 5)
    held_out = set(seeds[-held_out_count:])
    rows = []
    for path, payload in payloads:
        forces = [float(value) for value in payload["grasp"]["peak_contact_force_n"]]
        force_imbalance = abs(forces[0] - forces[1]) / max(sum(forces), 1e-9)
        features = {
            "solution_b": float(payload["solution"] == "b"),
            "abs_yaw_rad": abs(float(payload["initial_pose"]["yaw_rad"])),
            "product_width_m": float(payload["grasp"]["commanded_product_width_m"]),
            "contact_force_imbalance": force_imbalance,
            "slip_flag": float(payload["slip_detected"]),
        }
        targets = {
            "close": _duration(payload["sequence"], PHASE_LABELS["close"], 0.35),
            "stabilize": _duration(payload["sequence"], PHASE_LABELS["stabilize"], 0.45),
            "slip_correction": 0.001 if payload["slip_detected"] else 0.0,
            "reorientation": 1.0,
            "release": _duration(payload["sequence"], PHASE_LABELS["release"], 0.65),
        }
        for phase, target in targets.items():
            rows.append(
                {
                    "phase": phase,
                    "seed": int(payload["seed"]),
                    "split": "held_out" if int(payload["seed"]) in held_out else "fit",
                    "features": features,
                    "target": target,
                    "source_metrics": str(path),
                    "source_metrics_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "complete_scene2": True,
                }
            )
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "row_count": len(rows),
        "cycle_count": len(payloads),
        "fit_seeds": sorted(set(seeds) - held_out),
        "held_out_seeds": sorted(held_out),
        "source": "complete Isaac Sim Scene 2 rendered RGBD, articulation, PhysX contact, PLC, and delivery evidence",
        "output": str(output),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
