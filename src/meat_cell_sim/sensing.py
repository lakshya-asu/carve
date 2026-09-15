"""Turn the running cell into timestamped sensor records.

This is the ingestion layer. Everything downstream reads its world through
`Observation`, and nothing downstream may read the simulator directly. That rule
is what makes the perception numbers mean anything: an estimator that can reach
into `MjData` will quietly be right for the wrong reason, and the mistake only
shows up on hardware.

Ground truth is available in simulation and is genuinely useful, so it is
returned too, as a separate `GroundTruth` record. Keeping the two apart in the
type system is the whole point. A function that takes an `Observation` cannot
cheat; a function that takes both is a scorer, and is named like one.

Exposure
--------
A camera integrates light over a window, it does not sample an instant. Two
consequences that matter at this cell's tolerances:

* The pose an image describes is the one at the **middle** of the exposure, not
  at the start and not at the moment the array arrives. At 300 mm/s a 5 ms
  exposure spans 1.5 mm of belt travel, which is most of a 2 mm bound.
* The piece smears over that 1.5 mm. `exposure_s` renders the window as several
  sub-frames and averages them, which reproduces the smear rather than assuming
  it away. Set it to zero for an instantaneous render when speed matters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import mujoco
import numpy as np

from meat_cell_sim.arms import UR5E_SPEC, ArmSpec
from meat_cell_sim.cameras import intrinsics_from_model
from meat_cell_sim.contracts import Frame, Observation, Pose2D, wrap_axis_angle
from meat_cell_sim.frames import CameraPose, Intrinsics
from meat_cell_sim.product import PRODUCT_BODY, TROTTER_BODY, product_geom_ids

logger = logging.getLogger(__name__)

# Sub-frames used to render one exposure window. Three samples reproduce the
# first and second moments of a uniform-motion smear exactly, which is all the
# centroid and the axis estimators are sensitive to.
EXPOSURE_SUBFRAMES = 3


@dataclass(frozen=True)
class CameraSpec:
    """One camera as the cell operates it, not as the XML declares it.

    Attributes:
        name: Camera name in the model.
        width_px: Rendered width.
        height_px: Rendered height.
        exposure_s: Integration window. 0 renders one instant with no smear.
        latency_s: Exposure midpoint to the pose being available to the planner.
            Not used by the renderer; it is what the tracker must extrapolate
            over, and it belongs with the camera that causes it.
    """

    name: str
    width_px: int = 1280
    height_px: int = 960
    exposure_s: float = 0.005
    latency_s: float = 0.020

    def __post_init__(self) -> None:
        if self.exposure_s < 0 or self.latency_s < 0:
            raise ValueError("exposure and latency must be non-negative")
        if self.width_px <= 0 or self.height_px <= 0:
            raise ValueError(f"image size must be positive, got {self.width_px}x{self.height_px}")


@dataclass(frozen=True)
class CameraFrameData:
    """One captured frame and the geometry needed to interpret it.

    Attributes:
        stamp_s: Simulation time at the middle of the exposure.
        rgb: (H, W, 3) uint8.
        depth_m: (H, W) float32, distance along the optical axis in metres.
        intrinsics: Pinhole model matching this render.
        camera: Where the camera was during the exposure, world frame.
    """

    stamp_s: float
    rgb: np.ndarray
    depth_m: np.ndarray
    intrinsics: Intrinsics
    camera: CameraPose


@dataclass(frozen=True)
class GroundTruth:
    """What the simulator knows and a real cell would not.

    Never an input to an estimator. Scorers take this alongside an `Observation`
    and are the only things allowed to.

    Attributes:
        stamp_s: Simulation time this describes.
        piece_pose: True planar pose of the product, world frame.
        piece_velocity_mps: True linear velocity of the product, (3,) world.
        piece_top_z_m: True height of the product's upper surface, world z.
        piece_mask: (H, W) bool, exact silhouette of the product, or None.
        mask_touches_border: Whether the silhouette runs off the image edge. A
            clipped mask still produces a confident centroid, and that centroid
            is wrong by centimetres.
        centre_of_mass_m: (3,) world, the product's centre of mass over all its
            bodies (a leg's ham and trotter), or None when not computed.
    """

    stamp_s: float
    piece_pose: Pose2D
    piece_velocity_mps: np.ndarray
    piece_top_z_m: float
    piece_mask: np.ndarray | None = None
    mask_touches_border: bool = False
    centre_of_mass_m: np.ndarray | None = None


def _mask_touches_border(mask: np.ndarray) -> bool:
    return bool(mask[0, :].any() or mask[-1, :].any() or mask[:, 0].any() or mask[:, -1].any())


class Sensors:
    """Renderers and sensor readout for one cell, reused across an episode.

    Building a `mujoco.Renderer` allocates a GL context, which costs far more
    than a render does. One instance per camera per episode, closed at the end.
    Use as a context manager.
    """

    def __init__(self, model: mujoco.MjModel, specs: dict[str, CameraSpec], arm: ArmSpec = UR5E_SPEC) -> None:
        """Validate every camera against the model before an episode starts."""
        self._model = model
        self._specs = dict(specs)
        self._rgb: dict[str, mujoco.Renderer] = {}
        self._depth: dict[str, mujoco.Renderer] = {}
        self._seg: dict[str, mujoco.Renderer] = {}
        for label, spec in self._specs.items():
            if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, spec.name) < 0:
                raise ValueError(f"no camera named {spec.name!r} in the model (spec {label!r})")
            if spec.width_px > model.vis.global_.offwidth or spec.height_px > model.vis.global_.offheight:
                raise ValueError(
                    f"camera {spec.name!r} wants {spec.width_px}x{spec.height_px} but the model's offscreen "
                    f"buffer is {model.vis.global_.offwidth}x{model.vis.global_.offheight}; "
                    "raise <visual><global offwidth= offheight=> in cell.xml"
                )
        # The product is one geom when it is a slab and three when it is a leg,
        # so nothing may assume a single id. The silhouette is the union.
        self._piece_geoms = product_geom_ids(model)
        self._arm_qpos_index = np.array(
            [model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)] for name in arm.joint_names]
        )
        self._piece_qadr = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
        self._piece_dadr = model.jnt_dofadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "slab_free")]
        # A leg's trotter is its own welded body, so the centre of mass spans both.
        body_ids = (mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name) for name in (PRODUCT_BODY, TROTTER_BODY))
        self._piece_bodies = np.array([body for body in body_ids if body >= 0])
        self._sensor_adr = {
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SENSOR, i): int(model.sensor_adr[i])
            for i in range(model.nsensor)
        }

    def __enter__(self) -> Sensors:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Release every GL context. Safe to call twice."""
        for pool in (self._rgb, self._depth, self._seg):
            for renderer in pool.values():
                renderer.close()
            pool.clear()

    def _renderer(self, pool: dict[str, mujoco.Renderer], name: str, mode: str) -> mujoco.Renderer:
        if name not in pool:
            spec = self._specs[name]
            renderer = mujoco.Renderer(self._model, spec.height_px, spec.width_px)
            if mode == "depth":
                renderer.enable_depth_rendering()
            elif mode == "segmentation":
                renderer.enable_segmentation_rendering()
            pool[name] = renderer
        return pool[name]

    def intrinsics(self, name: str) -> Intrinsics:
        """Pinhole model for a camera.

        A camera declared with a resolution and focal lengths (a datasheet camera
        from `cameras.py`) uses those, and may have non-square pixels. Any other
        camera is derived from its vertical field of view with square pixels.
        """
        spec = self._specs[name]
        cam_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_CAMERA, spec.name)
        declared = intrinsics_from_model(self._model, cam_id)
        if declared is not None:
            if (declared.width_px, declared.height_px) != (spec.width_px, spec.height_px):
                raise ValueError(
                    f"camera {spec.name!r} is declared {declared.width_px}x{declared.height_px}; "
                    f"render it at that size, not {spec.width_px}x{spec.height_px}"
                )
            return declared
        return Intrinsics.from_fovy(float(self._model.cam_fovy[cam_id]), spec.width_px, spec.height_px)

    def camera_pose(self, data: mujoco.MjData, name: str) -> CameraPose:
        """Where a camera is right now, in the world frame."""
        cam_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_CAMERA, self._specs[name].name)
        return CameraPose(position_m=data.cam_xpos[cam_id].copy(), rotation=data.cam_xmat[cam_id].reshape(3, 3).copy())

    def capture(self, data: mujoco.MjData, name: str) -> CameraFrameData:
        """Render one frame over the exposure window. See `_capture_at_midpoint`."""
        return self._capture_at_midpoint(data, name)[0]

    def _capture_at_midpoint(self, data: mujoco.MjData, name: str) -> tuple[CameraFrameData, np.ndarray]:
        """Render one frame and read every other sensor at the same instant.

        The simulator is advanced across the exposure and then restored, so the
        caller's state is untouched. The returned stamp is the exposure
        midpoint, which for uniform motion is the instant the smeared image
        actually describes.

        The encoder and joint values are sampled at that same midpoint rather
        than at the start of the exposure. Half an exposure of skew between the
        image and the encoder is 0.75 mm of belt travel at 300 mm/s, and it
        would show up downstream as a bias that grows with belt speed, which is
        indistinguishable from a calibration error until someone changes the
        line speed.

        Returns:
            The frame, and the sensor vector as it stood at the exposure midpoint.
        """
        spec = self._specs[name]
        if spec.exposure_s <= 0.0:
            return self._render_now(data, name, float(data.time)), self._sensordata_now(data)

        saved = np.empty(mujoco.mj_stateSize(self._model, mujoco.mjtState.mjSTATE_FULLPHYSICS))
        mujoco.mj_getState(self._model, data, saved, mujoco.mjtState.mjSTATE_FULLPHYSICS)
        # The simulator cannot resolve time finer than one timestep, so the
        # exposure is rounded to a whole number of them and the stamp reports
        # the window that was actually rendered. Stamping the requested
        # midpoint instead leaves up to half a timestep of error in the one
        # number the whole chain is anchored to: at 2 ms steps that is 1 ms,
        # which is the entire sensing gate.
        steps_per_subframe = max(1, round(spec.exposure_s / (EXPOSURE_SUBFRAMES - 1) / self._model.opt.timestep))
        rendered_exposure = steps_per_subframe * (EXPOSURE_SUBFRAMES - 1) * self._model.opt.timestep
        if abs(rendered_exposure - spec.exposure_s) > 1e-12:
            logger.debug(
                "camera %s exposure %.4f s rendered as %.4f s to land on whole timesteps",
                name,
                spec.exposure_s,
                rendered_exposure,
            )
        midpoint = float(data.time) + rendered_exposure / 2.0
        midpoint_index = EXPOSURE_SUBFRAMES // 2
        rgb_sum = np.zeros((spec.height_px, spec.width_px, 3), dtype=np.float64)
        # Averaging depth across a smear is not physical: a real depth sensor
        # returns one surface per pixel, not a blend of the surfaces that passed
        # through it. Depth comes from the midpoint sub-frame alone.
        depth = np.zeros((spec.height_px, spec.width_px), dtype=np.float32)
        camera = self.camera_pose(data, name)
        sensordata = self._sensordata_now(data)
        for i in range(EXPOSURE_SUBFRAMES):
            if i > 0:
                self._advance(data, steps_per_subframe)
            sub = self._render_now(data, name, midpoint)
            rgb_sum += sub.rgb
            if i == midpoint_index:
                depth = sub.depth_m
                camera = sub.camera
                sensordata = self._sensordata_now(data)
        mujoco.mj_setState(self._model, data, saved, mujoco.mjtState.mjSTATE_FULLPHYSICS)
        mujoco.mj_forward(self._model, data)
        frame = CameraFrameData(
            stamp_s=midpoint,
            rgb=np.rint(rgb_sum / EXPOSURE_SUBFRAMES).astype(np.uint8),
            depth_m=depth,
            intrinsics=self.intrinsics(name),
            camera=camera,
        )
        return frame, sensordata

    def _sensordata_now(self, data: mujoco.MjData) -> np.ndarray:
        """Sensor vector for the state `data` is actually in.

        `mj_step` leaves `sensordata` describing the state at the **start** of
        the step it just took, because sensors are evaluated in the forward pass
        before integration. Reading it straight after stepping therefore returns
        values one timestep old. On this cell that is 0.6 mm of belt travel at
        300 mm/s, it grows with line speed, and it presents as a calibration
        error rather than as a timing fault. `mj_forward` recomputes the derived
        quantities from the current qpos and qvel without integrating, so it is
        safe to call here and costs one forward per capture.
        """
        mujoco.mj_forward(self._model, data)
        return np.asarray(data.sensordata.copy())

    def _advance(self, data: mujoco.MjData, steps: int) -> None:
        for _ in range(steps):
            mujoco.mj_step(self._model, data)

    def _render_now(self, data: mujoco.MjData, name: str, stamp_s: float) -> CameraFrameData:
        camera_name = self._specs[name].name
        rgb_r = self._renderer(self._rgb, name, "rgb")
        rgb_r.update_scene(data, camera=camera_name)
        rgb = rgb_r.render().copy()
        depth_r = self._renderer(self._depth, name, "depth")
        depth_r.update_scene(data, camera=camera_name)
        depth = depth_r.render().copy()
        return CameraFrameData(
            stamp_s=stamp_s,
            rgb=rgb,
            depth_m=depth,
            intrinsics=self.intrinsics(name),
            camera=self.camera_pose(data, name),
        )

    def observe(
        self, data: mujoco.MjData, camera: str | None = None, belt_travel_offset_m: float = 0.0
    ) -> tuple[Observation, CameraFrameData | None]:
        """Read every sensor the real cell would have.

        Args:
            data: Simulator state.
            camera: Camera to render, or None to read the non-visual sensors only.
            belt_travel_offset_m: Distance the belt has been rewound by, which
                `Cell` banks so the belt can be endless. The joint sensor only
                holds travel since the last rewind, so the encoder reading is
                the sum. Zero if the caller is not rewinding the belt.

        Returns:
            The observation, and the frame it was built from if a camera was
            given. The frame is returned separately because it carries the
            geometry a perception module needs and the `Observation` contract
            deliberately does not.
        """
        frame: CameraFrameData | None = None
        sensordata = self._sensordata_now(data)
        if camera is not None:
            frame, sensordata = self._capture_at_midpoint(data, camera)
        obs = Observation(
            stamp_s=frame.stamp_s if frame is not None else float(data.time),
            belt_travel_m=belt_travel_offset_m + float(sensordata[self._sensor_adr["belt_encoder"]]),
            belt_speed_mps=float(sensordata[self._sensor_adr["belt_speed"]]),
            joint_pos_rad=data.qpos[self._arm_qpos_index].copy(),
            gripper_width_m=2.0 * float(sensordata[self._sensor_adr["g_grip_pos"]]),
            rgb=frame.rgb if frame is not None else None,
            depth_m=frame.depth_m if frame is not None else None,
        )
        return obs, frame

    def _piece_top_z(self, data: mujoco.MjData) -> float:
        """Height of the highest point on the product, whatever shape it is.

        Taken from each geom's own bounding box rotated into the world, rather
        than from one size component, because the leg's parts are an ellipsoid
        and two capsules whose size fields mean different things.
        """
        tops = []
        for geom in self._piece_geoms:
            extents = self._model.geom_aabb[geom][3:]
            rotation = data.geom_xmat[geom].reshape(3, 3)
            tops.append(float(data.geom_xpos[geom][2] + np.abs(rotation[2]) @ extents))
        return max(tops)

    def ground_truth(self, data: mujoco.MjData, camera: str | None = None, stamp_s: float | None = None) -> GroundTruth:
        """Oracle state of the product, and its exact silhouette if a camera is named."""
        quat = data.qpos[self._piece_qadr + 3 : self._piece_qadr + 7]
        # Yaw about world z from the quaternion, folded to an undirected axis
        # because the product has no head or tail.
        yaw = np.arctan2(
            2.0 * (quat[0] * quat[3] + quat[1] * quat[2]),
            1.0 - 2.0 * (quat[2] ** 2 + quat[3] ** 2),
        )
        mask = None
        border = False
        if camera is not None:
            seg_r = self._renderer(self._seg, camera, "segmentation")
            seg_r.update_scene(data, camera=self._specs[camera].name)
            mask = np.isin(seg_r.render()[:, :, 0], self._piece_geoms)
            border = _mask_touches_border(mask)
        pos = data.qpos[self._piece_qadr : self._piece_qadr + 3]
        return GroundTruth(
            stamp_s=float(data.time) if stamp_s is None else stamp_s,
            piece_pose=Pose2D(
                x_m=float(pos[0]),
                y_m=float(pos[1]),
                yaw_rad=wrap_axis_angle(float(yaw)),
                frame=Frame.WORLD,
                stamp_s=float(data.time) if stamp_s is None else stamp_s,
            ),
            piece_velocity_mps=data.qvel[self._piece_dadr : self._piece_dadr + 3].copy(),
            piece_top_z_m=self._piece_top_z(data),
            piece_mask=mask,
            mask_touches_border=border,
            centre_of_mass_m=self._centre_of_mass(data),
        )

    def _centre_of_mass(self, data: mujoco.MjData) -> np.ndarray:
        """Mass-weighted mean of the product bodies' centres of mass, (3,) world."""
        masses = self._model.body_mass[self._piece_bodies]
        return np.asarray(data.xipos[self._piece_bodies].T @ masses / masses.sum())
