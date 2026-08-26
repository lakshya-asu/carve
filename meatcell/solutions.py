"""Solution A and B task state machines operating on shared contracts."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .contracts import Contract, CutterMode, CutterState, SimTime, TerminalPath, Transform
from .grasp import GraspModel, SlipEstimate
from .supervisor import CellState, CellSupervisor


@dataclass(frozen=True)
class PLCState(Contract):
    timestamp: SimTime
    conveyor_speed_mps: float
    recipe_id: str
    cutter: CutterState
    fault_active: bool
    emergency_stop_active: bool
    result_acknowledged: bool

    def __post_init__(self) -> None:
        if self.conveyor_speed_mps < 0.0 or not math.isfinite(self.conveyor_speed_mps):
            raise ValueError("PLC conveyor speed must be finite and nonnegative")
        if not self.recipe_id.strip():
            raise ValueError("PLC recipe_id must not be blank")


@dataclass(frozen=True)
class DeliveryTolerance:
    position_m: float
    angle_rad: float
    timing_s: float
    speed_mps: float

    def __post_init__(self) -> None:
        if any(not math.isfinite(item) or item <= 0.0 for item in (self.position_m, self.angle_rad, self.timing_s, self.speed_mps)):
            raise ValueError("Delivery tolerances must be finite and positive")


@dataclass(frozen=True)
class DeliveryMeasurement(Contract):
    position_error_m: float
    angle_error_rad: float
    timing_error_s: float
    speed_error_mps: float

    def __post_init__(self) -> None:
        for name in ("position_error_m", "angle_error_rad", "timing_error_s", "speed_error_mps"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")


@dataclass(frozen=True)
class DeliveryAssessment(Contract):
    measurement: DeliveryMeasurement
    position_ok: bool
    angle_ok: bool
    timing_ok: bool
    speed_ok: bool

    @property
    def success(self) -> bool:
        return self.position_ok and self.angle_ok and self.timing_ok and self.speed_ok


def assess_delivery(measurement: DeliveryMeasurement, tolerance: DeliveryTolerance) -> DeliveryAssessment:
    return DeliveryAssessment(
        measurement,
        measurement.position_error_m <= tolerance.position_m,
        measurement.angle_error_rad <= tolerance.angle_rad,
        measurement.timing_error_s <= tolerance.timing_s,
        measurement.speed_error_mps <= tolerance.speed_mps,
    )


class _SolutionBase:
    def __init__(self, supervisor: CellSupervisor, delivery_tolerance: DeliveryTolerance) -> None:
        self.supervisor = supervisor
        self.delivery_tolerance = delivery_tolerance
        self._permissive_sequence: int | None = None

    def _check_plc_safety(self, plc: PLCState) -> bool:
        if plc.emergency_stop_active:
            self.supervisor.safe_stop(plc.timestamp, "plc_emergency_stop")
            return False
        if plc.fault_active or plc.cutter.mode is CutterMode.FAULT:
            self.supervisor.safe_stop(plc.timestamp, "plc_machine_fault")
            return False
        return True

    def _accept_permissive(self, plc: PLCState) -> bool:
        if not self._check_plc_safety(plc):
            return False
        cutter = plc.cutter
        if cutter.mode is not CutterMode.READY or cutter.recipe_id != plc.recipe_id:
            return False
        self._permissive_sequence = cutter.permissive_sequence
        return True

    def _verify_permissive(self, plc: PLCState) -> bool:
        return (
            self._permissive_sequence is not None
            and plc.cutter.mode is CutterMode.READY
            and plc.cutter.permissive_sequence == self._permissive_sequence
            and plc.cutter.recipe_id == plc.recipe_id
            and not plc.emergency_stop_active
            and not plc.fault_active
        )

    def verify_delivery(
        self,
        timestamp: SimTime,
        measurement: DeliveryMeasurement,
        *,
        auto_complete_retract: bool = True,
    ) -> DeliveryAssessment:
        assessment = assess_delivery(measurement, self.delivery_tolerance)
        self.supervisor.transition(
            CellState.VERIFY_DELIVERY,
            timestamp,
            "delivery_measured",
            {
                "position_ok": assessment.position_ok,
                "angle_ok": assessment.angle_ok,
                "timing_ok": assessment.timing_ok,
                "speed_ok": assessment.speed_ok,
            },
        )
        if not assessment.success:
            failed = next(
                name
                for name, ok in (
                    ("position", assessment.position_ok),
                    ("angle", assessment.angle_ok),
                    ("timing", assessment.timing_ok),
                    ("speed", assessment.speed_ok),
                )
                if not ok
            )
            self.supervisor.recover(SimTime(timestamp.nanoseconds + 1), f"delivery_{failed}_out_of_tolerance")
            return assessment
        self.supervisor.transition(CellState.RETRACT, SimTime(timestamp.nanoseconds + 1), "delivery_verified")
        if auto_complete_retract:
            self.supervisor.return_to_idle(SimTime(timestamp.nanoseconds + 2), "retract_complete")
        return assessment


class SolutionAController(_SolutionBase):
    def __init__(self, supervisor: CellSupervisor, delivery_tolerance: DeliveryTolerance, max_hold_s: float = 0.25) -> None:
        super().__init__(supervisor, delivery_tolerance)
        if max_hold_s <= 0.0:
            raise ValueError("max_hold_s must be positive")
        self.max_hold_s = max_hold_s

    def begin_direct_transfer(self, timestamp: SimTime, plc: PLCState, predicted_ready_delay_s: float = 0.0) -> bool:
        if self.supervisor.state is not CellState.VERIFY_GRASP:
            raise RuntimeError("Direct transfer requires verified grasp state")
        if predicted_ready_delay_s > self.max_hold_s or not self._accept_permissive(plc):
            self.supervisor.reject(timestamp, "cutter_unavailable_before_commit")
            return False
        self.supervisor.transition(CellState.TRANSFER_DIRECT, timestamp, "grasp_verified")
        return True

    def complete_direct_transfer(self, timestamp: SimTime) -> None:
        self.supervisor.transition(
            CellState.WAIT_CUTTER_PERMISSIVE,
            timestamp,
            "direct_transfer_complete",
        )

    def align_and_feed(self, timestamp: SimTime, plc: PLCState) -> bool:
        if not self._verify_permissive(plc):
            self.supervisor.safe_stop(timestamp, "cutter_permissive_sequence_mismatch")
            return False
        self.supervisor.transition(CellState.ALIGN_DIRECT, timestamp, "cut_target_frame_aligned")
        self.supervisor.transition(CellState.FEED_DIRECT, SimTime(timestamp.nanoseconds + 1), "direct_feed_started")
        return True


@dataclass
class BufferRuntime:
    capacity: int
    max_hold_s: float
    occupied_product_id: str | None = None
    occupied_since: SimTime | None = None
    sanitation_ready: bool = True

    def __post_init__(self) -> None:
        if self.capacity < 1 or self.max_hold_s <= 0.0:
            raise ValueError("Buffer capacity and maximum hold must be positive")


class SolutionBController(_SolutionBase):
    def __init__(
        self,
        supervisor: CellSupervisor,
        delivery_tolerance: DeliveryTolerance,
        buffer: BufferRuntime,
        grasp_model: GraspModel,
    ) -> None:
        super().__init__(supervisor, delivery_tolerance)
        self.buffer = buffer
        self.grasp_model = grasp_model
        self.corrected_pose: Transform | None = None

    def begin_buffer_transfer(self, product_id: str, timestamp: SimTime) -> bool:
        if self.supervisor.state is not CellState.VERIFY_GRASP:
            raise RuntimeError("Buffer transfer requires verified grasp state")
        if not self.buffer.sanitation_ready:
            self.supervisor.reject(timestamp, "buffer_sanitation_unavailable")
            return False
        if self.buffer.occupied_product_id is not None:
            self.supervisor.reject(timestamp, "buffer_occupied")
            return False
        self.supervisor.transition(CellState.TRANSFER_BUFFER, timestamp, "grasp_verified")
        return True

    def release_to_buffer(self, product_id: str, timestamp: SimTime) -> None:
        if self.supervisor.state is not CellState.TRANSFER_BUFFER:
            raise RuntimeError("Buffer release requires transfer state")
        self.buffer.occupied_product_id = product_id
        self.buffer.occupied_since = timestamp
        self.supervisor.transition(CellState.RELEASE_BUFFER, timestamp, "buffer_pose_reached")

    def begin_settle(self, timestamp: SimTime) -> None:
        self.supervisor.transition(CellState.SETTLE, timestamp, "product_released")

    def transfer_to_buffer(self, product_id: str, timestamp: SimTime) -> bool:
        if not self.begin_buffer_transfer(product_id, timestamp):
            return False
        self.release_to_buffer(product_id, SimTime(timestamp.nanoseconds + 1))
        self.begin_settle(SimTime(timestamp.nanoseconds + 2))
        return True

    def reobserve_and_align(
        self,
        timestamp: SimTime,
        observed_product_pose: Transform,
        slip: SlipEstimate,
    ) -> bool:
        if self.buffer.occupied_since is None:
            raise RuntimeError("Buffer is not occupied")
        hold_s = timestamp.seconds - self.buffer.occupied_since.seconds
        if hold_s > self.buffer.max_hold_s:
            self.supervisor.recover(timestamp, "buffer_timeout")
            return False
        self.supervisor.transition(CellState.REOBSERVE_BUFFER, timestamp, "buffer_settled")
        self.corrected_pose = self.grasp_model.corrected_product_pose(observed_product_pose, slip)
        self.supervisor.transition(
            CellState.ALIGN_BUFFER,
            SimTime(timestamp.nanoseconds + 1),
            "buffer_slip_corrected" if slip.detected else "buffer_pose_confirmed",
        )
        return True

    def wait_and_feed(self, timestamp: SimTime, plc: PLCState) -> bool:
        if self.buffer.occupied_since is None:
            raise RuntimeError("Buffer is not occupied")
        hold_s = timestamp.seconds - self.buffer.occupied_since.seconds
        if hold_s > self.buffer.max_hold_s:
            self.supervisor.recover(timestamp, "buffer_timeout")
            return False
        self.supervisor.transition(CellState.WAIT_CUTTER_PERMISSIVE, timestamp, "buffer_alignment_complete")
        if not self._accept_permissive(plc):
            self.supervisor.recover(SimTime(timestamp.nanoseconds + 1), "cutter_not_ready_before_buffer_timeout")
            return False
        if not self._verify_permissive(plc):
            self.supervisor.safe_stop(SimTime(timestamp.nanoseconds + 1), "cutter_permissive_sequence_mismatch")
            return False
        self.supervisor.transition(CellState.FEED_BUFFER, SimTime(timestamp.nanoseconds + 1), "servo_feed_started")
        self.buffer.occupied_product_id = None
        self.buffer.occupied_since = None
        return True
