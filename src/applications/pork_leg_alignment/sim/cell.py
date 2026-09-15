"""The running cell: owns the clock, the belt, the saw and the sensors.

Stepping lives here rather than in each script because the belt needs it. A
conveyor is an endless surface that carries product without going anywhere
itself, and MuJoCo has no such primitive. Modelling it as a plank on a slide
joint, which is what this cell did first, gives a belt that physically
translates: it slides out from under the product, the product reaches the end,
and it falls off. Nothing is wrong with the physics; the model is just of a
moving plank rather than of a conveyor.

The fix is to rewind the belt joint to zero after every step while leaving its
velocity alone. Contact friction depends on the relative velocity at the contact
point, not on where the belt has got to, so the product is still dragged exactly
as before, while the belt surface stays put and never runs out. That is what a
conveyor is.

The belt's position is then always near zero, so it can no longer serve as the
encoder. `belt_travel_m` integrates instead, which is what a real incremental
encoder does anyway: it accumulates counts and can be zeroed, and nothing in the
plant knows where the belt "is".

The saw is checked every step for the same reason the belt is rewound every
step: a leg at 0.3 m/s moves 0.6 mm per step, and checking less often would
move where the cut lands.
"""

from __future__ import annotations

import logging

import mujoco
import numpy as np

from applications.pork_leg_alignment.sim.hold_down import HoldDown
from applications.pork_leg_alignment.sim.product import TROTTER_JOINT
from applications.pork_leg_alignment.sim.saw import CutResult, Saw
from applications.pork_leg_alignment.sim.scene import CellConfig, build_model
from applications.pork_leg_alignment.sim.sensing import CameraSpec, GroundTruth, Sensors
from robotics.core.camera_frame import CameraFrameData
from robotics.core.contracts import Observation
from robotics.hardware.arms import ARM_SPECS
from robotics.hardware.grippers import GRIPPER_SPECS, command_opening, measure_geometry, measured_opening_m

logger = logging.getLogger(__name__)

BELT_JOINT = "belt_x"
PRODUCT_JOINT = "slab_free"
BELT_ACTUATOR = "belt_drive"


class Cell:
    """One cell, stepping. Use as a context manager so the renderers are released.

    Attributes:
        model: The compiled model.
        data: Simulator state. Read it, but step through `step` so the belt
            stays a belt and the saw sees every step.
        saw: The trotter saw, when the config has one.
    """

    def __init__(self, config: CellConfig | None = None, cameras: dict[str, CameraSpec] | None = None) -> None:
        """Build the cell and its sensors."""
        self.config = config or CellConfig()
        self.model, self.data = build_model(self.config)
        self.arm = ARM_SPECS[self.config.arm]
        self.sensors = Sensors(self.model, cameras or {}, arm=self.arm)
        self._arm_qpos_index = np.array(
            [
                self.model.jnt_qposadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, name)]
                for name in self.arm.joint_names
            ]
        )
        self._arm_actuators = np.array(
            [mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, name) for name in self.arm.actuator_names]
        )
        self._belt_actuator = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, BELT_ACTUATOR)
        self.gripper = GRIPPER_SPECS[self.config.gripper]
        self.gripper_geometry = measure_geometry(self.model, self.gripper)
        self._belt_qadr = int(
            self.model.jnt_qposadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, BELT_JOINT)]
        )
        self._product_qadr = int(
            self.model.jnt_qposadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, PRODUCT_JOINT)]
        )
        self._product_dadr = int(
            self.model.jnt_dofadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, PRODUCT_JOINT)]
        )
        trotter = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, TROTTER_JOINT)
        self._trotter_qadr = int(self.model.jnt_qposadr[trotter]) if trotter >= 0 else None
        self._trotter_dadr = int(self.model.jnt_dofadr[trotter]) if trotter >= 0 else None
        self.saw = (
            Saw(self.model, self.config.saw, self.config.leg)
            if self.config.saw is not None and self.config.leg is not None
            else None
        )
        self.hold_down = HoldDown(self.model, self.config.hold_down) if self.config.hold_down is not None else None
        self._travel_offset_m = 0.0

    def __enter__(self) -> Cell:
        return self

    def __exit__(self, *exc: object) -> None:
        self.sensors.close()

    @property
    def time_s(self) -> float:
        """Simulation time."""
        return float(self.data.time)

    @property
    def belt_travel_m(self) -> float:
        """Distance the belt surface has carried product, from the encoder.

        The integrated part plus whatever the joint has accumulated since the
        last rewind, so the value is correct even part way through a camera
        exposure, where the sensing layer steps the world itself.
        """
        return self._travel_offset_m + float(self.data.qpos[self._belt_qadr])

    @property
    def belt_speed_mps(self) -> float:
        """Measured belt speed, which is not the commanded one under load."""
        return float(
            self.data.qvel[self.model.jnt_dofadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, BELT_JOINT)]]
        )

    @property
    def cut_result(self) -> CutResult | None:
        """The saw's verdict on the current leg, once it has passed the blade."""
        return self.saw.result if self.saw is not None else None

    def reset(self, belt_speed_mps: float | None = None) -> None:
        """Return the arm to its home pose, zero the encoder, and set the belt running.

        The home pose comes from the arm's spec rather than a keyframe, because
        only the Menagerie UR5e ships with one.
        """
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[self._arm_qpos_index] = self.arm.home_qpos
        self.data.ctrl[self._arm_actuators] = self.arm.home_qpos
        speed = self.config.belt_speed_mps if belt_speed_mps is None else belt_speed_mps
        self.data.ctrl[self._belt_actuator] = speed
        if self.hold_down is not None:
            self.hold_down.start(self.data, speed)
        self._travel_offset_m = 0.0
        mujoco.mj_forward(self.model, self.data)

    def place_product(self, x_m: float, y_m: float, yaw_rad: float, settle_s: float = 0.0) -> None:
        """Put the product on the belt at a known pose, at rest, trotter reattached."""
        pose = [
            x_m,
            y_m,
            0.90 + self.config.product_rest_height_m,
            np.cos(yaw_rad / 2),
            0.0,
            0.0,
            np.sin(yaw_rad / 2),
        ]
        self.data.qpos[self._product_qadr : self._product_qadr + 7] = pose
        self.data.qvel[self._product_dadr : self._product_dadr + 6] = 0.0
        if self._trotter_qadr is not None and self._trotter_dadr is not None:
            self.data.qpos[self._trotter_qadr : self._trotter_qadr + 7] = pose
            self.data.qvel[self._trotter_dadr : self._trotter_dadr + 6] = 0.0
        if self.saw is not None:
            self.saw.rearm(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)
        if settle_s > 0:
            self.step(seconds=settle_s)

    @property
    def arm_qpos(self) -> np.ndarray:
        """Arm joint values now, one per joint: radians, or metres for a SCARA's vertical axis."""
        return np.array(self.data.qpos[self._arm_qpos_index], dtype=float)

    def move_arm(self, target_q: np.ndarray, seconds: float) -> None:
        """Ramp the arm's joint commands to `target_q` over `seconds`, stepping the world.

        A step change in a position servo's command slams the arm, and anything
        it holds moves because of the slam rather than because of the task.
        """
        start = np.asarray(self.data.ctrl[self._arm_actuators], dtype=float).copy()
        steps = max(1, round(seconds / self.model.opt.timestep))
        for step in range(steps):
            blend = (step + 1) / steps
            self.data.ctrl[self._arm_actuators] = start + blend * (np.asarray(target_q) - start)
            self.step()

    def open_gripper(self, opening_m: float) -> None:
        """Command the jaws or fingers to an opening, metres. Does not step the world."""
        command_opening(self.data, self.model, self.gripper_geometry, opening_m)

    def close_gripper(self) -> None:
        """Command fully closed. The gripper's force limit, not its stroke, stops it on a part."""
        command_opening(self.data, self.model, self.gripper_geometry, self.gripper_geometry.rest_gap_m)

    @property
    def gripper_opening_m(self) -> float:
        """Measured opening now, which differs from the command when closed on something."""
        return measured_opening_m(self.data, self.model, self.gripper)

    @property
    def product_x_m(self) -> float:
        """Where the product is along the belt, world frame."""
        return float(self.data.qpos[self._product_qadr])

    def step(self, steps: int = 1, seconds: float | None = None) -> None:
        """Advance the world, keeping the belt endless and the saw watching.

        Args:
            steps: Number of simulator steps.
            seconds: If given, overrides `steps` with the equivalent duration.
        """
        if seconds is not None:
            steps = max(1, round(seconds / self.model.opt.timestep))
        for _ in range(steps):
            mujoco.mj_step(self.model, self.data)
            # Rewind the belt, bank the distance. Doing this every step keeps the
            # rewind smaller than a millimetre, so nothing that touches the belt
            # sees a discontinuity in its surface.
            self._travel_offset_m += float(self.data.qpos[self._belt_qadr])
            self.data.qpos[self._belt_qadr] = 0.0
            if self.hold_down is not None:
                self.hold_down.rewind(self.data)
            if self.saw is not None:
                self.saw.update(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)

    def observe(self, camera: str | None = None) -> tuple[Observation, CameraFrameData | None]:
        """Read the sensors, with the encoder reporting integrated travel."""
        return self.sensors.observe(self.data, camera, belt_travel_offset_m=self._travel_offset_m)

    def ground_truth(self, camera: str | None = None, stamp_s: float | None = None) -> GroundTruth:
        """Oracle state. Scoring only; no estimator may receive this."""
        return self.sensors.ground_truth(self.data, camera, stamp_s=stamp_s)
