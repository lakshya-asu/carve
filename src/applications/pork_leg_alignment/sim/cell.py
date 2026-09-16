"""The running cell: owns the clock, the belt, the judge (saw or infeed fixture) and the sensors.

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
move where the cut lands. The loin cell's infeed fixture is checked the same
way, for the same reason.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable

import mujoco
import numpy as np

from applications.pork_leg_alignment.sim.hold_down import HOLD_DOWN_PLATE_GEOM, HOLD_DOWN_RAMP_GEOM, HoldDown
from applications.pork_leg_alignment.sim.infeed_fixture import InfeedFixture, InfeedResult
from applications.pork_leg_alignment.sim.product import PRODUCT_BODY, TROTTER_JOINT
from applications.pork_leg_alignment.sim.saw import BELT_GEOM, SAW_POST_GEOM, CutResult, Saw
from applications.pork_leg_alignment.sim.scene import CellConfig, build_model
from applications.pork_leg_alignment.sim.sensing import CameraSpec, GroundTruth, Sensors
from robotics.core.camera_frame import CameraFrameData
from robotics.core.contracts import Observation
from robotics.hardware.arms import ARM_SPECS, SERVO_INTEGRAL_GAIN_PER_S, SERVO_INTEGRAL_LIMIT
from robotics.hardware.grippers import GRIPPER_SPECS, command_opening, measure_geometry, measured_opening_m
from robotics.hardware.ik import solve_ik_rotation, tool_pose

logger = logging.getLogger(__name__)

BELT_JOINT = "belt_x"
PRODUCT_JOINT = "slab_free"
BELT_ACTUATOR = "belt_drive"
RAIL_GEOM = "rail_far"
# How often a Cartesian path is turned into a new joint command. Between
# ticks the joints ramp linearly, the way a servoj-style interface on a real
# controller interpolates between setpoints; 50 Hz is the rate the ROS 2
# executor sends at. Each command is for the pose `TOOL_LEAD_S` beyond the
# ramp's end, a stand-in for a controller's velocity feedforward. Measured
# following a grasp point at 0.3 m/s (2026-09-15): with no lead the UR20 was
# 1.4 mm behind it along the belt and the SR-20iA 1.4 mm ahead, and every
# 10 ms of lead put both about 3 mm further ahead, so the servos' own integral
# action already covers the lag and the lead stays at zero.
TOOL_TICK_S = 0.02
TOOL_LEAD_S = 0.0

ToolPath = Callable[[float], tuple[np.ndarray, np.ndarray]]


def _descends_from(model: mujoco.MjModel, body: int, ancestor: int) -> bool:
    while body > 0:
        body = int(model.body_parentid[body])
        if body == ancestor:
            return True
    return False


class Cell:
    """One cell, stepping. Use as a context manager so the renderers are released.

    Attributes:
        model: The compiled model.
        data: Simulator state. Read it, but step through `step` so the belt
            stays a belt and the saw sees every step.
        saw: The trotter saw, when the config has one.
        infeed_fixture: The loin puller's infeed fixture, when the config has one.
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
        self.infeed_fixture = (
            InfeedFixture(self.model, self.config.infeed_fixture, self.config.loin)
            if self.config.infeed_fixture is not None and self.config.loin is not None
            else None
        )
        self._travel_offset_m = 0.0
        self._arm_target = np.array(self.arm.home_qpos, dtype=float)
        self._arm_previous_target = self._arm_target.copy()
        self._arm_integral = np.zeros(self.arm.dof)
        # Velocity feedforward: a position actuator with damping kv trails a
        # command moving at v by kv v / kp, and MuJoCo sets kv from the joint's
        # inertia (0.03 s on the UR20's shoulder, 0.06 s on the SR-20iA's J1).
        # Commanding that far ahead cancels the trail, as a drive's velocity
        # feedforward does; without it the UR20 arrived 30 to 40 mm short of a
        # horizontal approach and its integrator wound up on the lag (2026-09-15).
        self._servo_lead_s = np.array(
            [-self.model.actuator_biasprm[a][2] / self.model.actuator_gainprm[a][0] for a in self._arm_actuators]
        )
        self._arm_geoms, self._fixture_geoms = self._collision_sets()
        self.arm_collisions = 0
        self.arm_collision_pairs: set[tuple[str, str]] = set()
        self.arm_collision_first_s = math.nan

    def _collision_sets(self) -> tuple[set[int], set[int]]:
        """Geoms of the arm and gripper, and geoms of the cell they must never touch."""
        mount = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "pedestal")
        arm_bodies = {
            body for body in range(self.model.nbody) if body != mount and _descends_from(self.model, body, mount)
        }
        arm_geoms = {geom for geom in range(self.model.ngeom) if int(self.model.geom_bodyid[geom]) in arm_bodies}
        fixtures = set()
        for name in (BELT_GEOM, RAIL_GEOM, HOLD_DOWN_PLATE_GEOM, HOLD_DOWN_RAMP_GEOM, SAW_POST_GEOM):
            geom = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, name)
            if geom >= 0:
                fixtures.add(int(geom))
        return arm_geoms, fixtures

    def _count_arm_collisions(self) -> None:
        for i in range(self.data.ncon):
            contact = self.data.contact[i]
            a, b = int(contact.geom1), int(contact.geom2)
            if b in self._arm_geoms and a in self._fixture_geoms:
                a, b = b, a
            if a in self._arm_geoms and b in self._fixture_geoms:
                if self.arm_collisions == 0:
                    self.arm_collision_first_s = float(self.data.time)
                self.arm_collisions += 1
                self.arm_collision_pairs.add(
                    (
                        mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_GEOM, a) or str(a),
                        mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_GEOM, b) or str(b),
                    )
                )
                return

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

    @property
    def infeed_result(self) -> InfeedResult | None:
        """The infeed fixture's verdict on the current loin, once it has crossed the plane."""
        return self.infeed_fixture.result if self.infeed_fixture is not None else None

    @property
    def release_before_x_m(self) -> float | None:
        """The x no part of the product may reach before the arm has let go.

        The hold-down's lead-in, or the infeed fixture's plane; None when the
        cell has neither.
        """
        if self.hold_down is not None:
            return self.hold_down.config.entry_x_m
        if self.infeed_fixture is not None:
            return self.infeed_fixture.config.x_m
        return None

    def product_centreline_world(self, fractions: np.ndarray) -> np.ndarray:
        """Points on the product's centreline now, world frame, (N, 3), from the simulator's own pose.

        Reads the leg or the loin through the same two methods, so a skill that
        plans on a centreline does not know which product it holds.

        Raises:
            ValueError: If the product is the slab, which has no centreline.
        """
        product = self.config.product
        if product is None:
            raise ValueError("the slab has no centreline")
        body = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, PRODUCT_BODY)
        position = np.asarray(self.data.xpos[body], dtype=float)
        rotation = self.data.xmat[body].reshape(3, 3)
        return position + product.centreline_m(np.asarray(fractions, dtype=float)) @ rotation.T

    def reset(self, belt_speed_mps: float | None = None) -> None:
        """Return the arm to its home pose, zero the encoder, and set the belt running.

        The home pose comes from the arm's spec rather than a keyframe, because
        only the Menagerie UR5e ships with one.
        """
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[self._arm_qpos_index] = self.arm.home_qpos
        self._arm_integral[:] = 0.0
        self._arm_previous_target = np.array(self.arm.home_qpos, dtype=float)
        self.arm_collisions = 0
        self.arm_collision_pairs.clear()
        self.arm_collision_first_s = math.nan
        self.command_arm(np.array(self.arm.home_qpos))
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
        if self.infeed_fixture is not None:
            self.infeed_fixture.rearm()
        mujoco.mj_forward(self.model, self.data)
        if settle_s > 0:
            self.step(seconds=settle_s)

    @property
    def arm_qpos(self) -> np.ndarray:
        """Arm joint values now, one per joint: radians, or metres for a SCARA's vertical axis."""
        return np.array(self.data.qpos[self._arm_qpos_index], dtype=float)

    @property
    def arm_target(self) -> np.ndarray:
        """The joint values the arm is currently commanded to hold."""
        return self._arm_target.copy()

    def command_arm(self, target_q: np.ndarray) -> None:
        """Set the joint values the servos hold from the next step on. Does not step the world.

        The servo's integral correction is added on top at each step, so write
        commands here rather than into `data.ctrl`, where they would be overwritten.
        """
        self._arm_target = np.array(target_q, dtype=float)
        self.data.ctrl[self._arm_actuators] = self._arm_target + self._arm_integral

    def move_arm(self, target_q: np.ndarray, seconds: float) -> None:
        """Ramp the arm's joint commands to `target_q` over `seconds`, stepping the world.

        A step change in a position servo's command slams the arm, and anything
        it holds moves because of the slam rather than because of the task. The
        ramp is an S-curve with zero velocity at both ends: a linear ramp that
        stops dead leaves the servos' integral term wound up on the lag, and
        the UR20's tool overshot a horizontal approach by 12 mm (2026-09-15).
        """
        start = self._arm_target.copy()
        steps = max(1, round(seconds / self.model.opt.timestep))
        for step in range(steps):
            fraction = (step + 1) / steps
            blend = fraction * fraction * (3.0 - 2.0 * fraction)
            self.command_arm(start + blend * (np.asarray(target_q) - start))
            self.step()

    def follow_tool(self, path: ToolPath, seconds: float) -> None:
        """Drive the tool along a Cartesian path for `seconds`, stepping the world.

        `path(t_s)` gives the tool position (3,) and world-from-tool rotation
        (3, 3) wanted at simulation time `t_s`. Every `TOOL_TICK_S` the pose due
        `TOOL_LEAD_S` after the end of the tick is solved for joints, seeded
        from the current command so successive solutions stay on one branch,
        and the joints ramp to it over the tick. A path that reads the belt
        encoder inside `path` tracks the belt.

        Raises:
            UnreachableError: If some pose on the path has no joint solution.
                The world is left where it got to; the caller decides what that
                means for its task.
        """
        end_s = self.time_s + seconds
        while self.time_s < end_s - 1e-9:
            tick_s = min(TOOL_TICK_S, end_s - self.time_s)
            position, rotation = path(self.time_s + tick_s + TOOL_LEAD_S)
            target = solve_ik_rotation(
                self.model, self.data, position, rotation, seed_qpos=self._arm_target, arm=self.arm
            )
            self.move_arm(target, tick_s)

    @property
    def tool_position_m(self) -> np.ndarray:
        """Tool centre point now, world frame, (3,) metres."""
        return tool_pose(self.model, self.data)[0]

    @property
    def tool_rotation(self) -> np.ndarray:
        """World-from-tool rotation now, (3, 3)."""
        return tool_pose(self.model, self.data)[1]

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
        dt = float(self.model.opt.timestep)
        for _ in range(steps):
            # The servo: the command, plus velocity feedforward for the trail
            # the damping would leave, plus an integral term that corrects the
            # standing error, bounded so a joint held against something cannot
            # wind up.
            velocity = (self._arm_target - self._arm_previous_target) / dt
            self._arm_previous_target = self._arm_target.copy()
            error = self._arm_target - self.data.qpos[self._arm_qpos_index]
            self._arm_integral = np.clip(
                self._arm_integral + SERVO_INTEGRAL_GAIN_PER_S * error * dt,
                -SERVO_INTEGRAL_LIMIT,
                SERVO_INTEGRAL_LIMIT,
            )
            self.data.ctrl[self._arm_actuators] = self._arm_target + self._servo_lead_s * velocity + self._arm_integral
            mujoco.mj_step(self.model, self.data)
            self._count_arm_collisions()
            # Rewind the belt, bank the distance. Doing this every step keeps the
            # rewind smaller than a millimetre, so nothing that touches the belt
            # sees a discontinuity in its surface.
            self._travel_offset_m += float(self.data.qpos[self._belt_qadr])
            self.data.qpos[self._belt_qadr] = 0.0
            if self.hold_down is not None:
                self.hold_down.rewind(self.data)
            if self.saw is not None:
                self.saw.update(self.model, self.data)
            if self.infeed_fixture is not None:
                self.infeed_fixture.update(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)

    def observe(self, camera: str | None = None) -> tuple[Observation, CameraFrameData | None]:
        """Read the sensors, with the encoder reporting integrated travel."""
        return self.sensors.observe(self.data, camera, belt_travel_offset_m=self._travel_offset_m)

    def ground_truth(self, camera: str | None = None, stamp_s: float | None = None) -> GroundTruth:
        """Oracle state. Scoring only; no estimator may receive this."""
        return self.sensors.ground_truth(self.data, camera, stamp_s=stamp_s)
