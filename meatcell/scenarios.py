from __future__ import annotations

import random
from typing import Any

from .models import Scenario


def generate_scenarios(config: dict[str, Any], episodes: int, seed: int) -> list[Scenario]:
    rng = random.Random(seed)
    conveyor = config["conveyor"]
    perception = config["perception"]
    gripper = config["gripper"]
    scenario_cfg = config["scenario"]
    cutting = config["cutting"]
    result: list[Scenario] = []

    for episode in range(episodes):
        speed = max(
            0.1,
            rng.gauss(
                conveyor["nominal_speed_mps"],
                conveyor["nominal_speed_mps"] * conveyor["speed_sigma_fraction"],
            ),
        )
        encoder_speed = max(
            0.1,
            rng.gauss(speed, speed * conveyor["encoder_sigma_fraction"]),
        )
        ready = rng.random() < cutting["readiness_probability"]
        result.append(
            Scenario(
                episode=episode,
                detected=rng.random() < perception["detection_probability"],
                belt_speed_mps=speed,
                encoder_speed_mps=encoder_speed,
                latency_s=max(0.0, rng.gauss(perception["latency_mean_s"], perception["latency_sigma_s"])),
                timestamp_error_s=rng.gauss(0.0, perception["timestamp_sigma_s"]),
                observation_position_error_m=rng.gauss(0.0, perception["position_sigma_m"]),
                observation_angle_error_deg=rng.gauss(0.0, perception["angle_sigma_deg"]),
                yaw_rate_deg_s=rng.gauss(0.0, scenario_cfg["yaw_rate_sigma_deg_s"]),
                mass_kg=rng.uniform(scenario_cfg["mass_min_kg"], scenario_cfg["mass_max_kg"]),
                friction=max(0.02, rng.gauss(gripper["friction_mean"], gripper["friction_sigma"])),
                calibration_position_error_m=rng.gauss(0.0, scenario_cfg["calibration_sigma_m"]),
                calibration_angle_error_deg=rng.gauss(0.0, scenario_cfg["calibration_sigma_deg"]),
                actuation_position_error_m=rng.gauss(0.0, scenario_cfg["actuation_position_sigma_m"]),
                actuation_angle_error_deg=rng.gauss(0.0, scenario_cfg["actuation_angle_sigma_deg"]),
                slip_position_error_m=rng.gauss(0.0, gripper["slip_position_sigma_m"]),
                slip_angle_error_deg=rng.gauss(0.0, gripper["slip_angle_sigma_deg"]),
                cutter_ready=ready,
                cutter_block_s=0.0 if ready else rng.uniform(0.05, 0.65),
                z_cut_position=rng.gauss(0.0, 1.0),
                z_cut_angle=rng.gauss(0.0, 1.0),
                z_cut_timing=rng.gauss(0.0, 1.0),
                z_cut_speed=rng.gauss(0.0, 1.0),
            )
        )
    return result
