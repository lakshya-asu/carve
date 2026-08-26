import math

from meatcell.contracts import CutterMode, CutterState, SimTime, TerminalPath, Transform
from meatcell.grasp import GraspModel, GraspModelConfig
from meatcell.solutions import (
    BufferRuntime,
    DeliveryMeasurement,
    DeliveryTolerance,
    PLCState,
    SolutionAController,
    SolutionBController,
)
from meatcell.supervisor import CellState, CellSupervisor


def supervisor_at_verified_grasp() -> CellSupervisor:
    supervisor = CellSupervisor()
    supervisor.start_episode("episode", SimTime(0))
    for index, state in enumerate(
        (CellState.TRACK, CellState.PLAN, CellState.WAIT_COMMIT, CellState.INTERCEPT, CellState.VERIFY_GRASP), start=1
    ):
        supervisor.transition(state, SimTime(index), f"to_{state.value}")
    return supervisor


def plc(at: SimTime, *, mode=CutterMode.READY, sequence=7, recipe="reference-cut", estop=False) -> PLCState:
    return PLCState(
        at,
        2.24,
        recipe,
        CutterState(at, mode, "cut_target_frame", 0.4, 0.0, recipe, sequence),
        False,
        estop,
        False,
    )


def tolerance() -> DeliveryTolerance:
    return DeliveryTolerance(0.01, math.radians(3.0), 0.02, 0.15)


def nominal_measurement() -> DeliveryMeasurement:
    return DeliveryMeasurement(0.003, math.radians(0.7), 0.004, 0.03)


def grasp_model() -> GraspModel:
    return GraspModel(GraspModelConfig(0.04, 0.2, 2, 1.2, 25_000.0, 0.005, 0.02))


def test_solution_a_nominal_episode_and_separate_delivery_results() -> None:
    supervisor = supervisor_at_verified_grasp()
    controller = SolutionAController(supervisor, tolerance())
    assert controller.begin_direct_transfer(SimTime(10), plc(SimTime(10)))
    controller.complete_direct_transfer(SimTime(11))
    assert controller.align_and_feed(SimTime(20), plc(SimTime(20)))
    assessment = controller.verify_delivery(SimTime(30), nominal_measurement())
    assert assessment.position_ok and assessment.angle_ok and assessment.timing_ok and assessment.speed_ok
    assert supervisor.state is CellState.IDLE
    assert supervisor.terminal_path is TerminalPath.SUCCESS


def test_solution_a_rejects_unavailable_cutter_before_exclusion_zone() -> None:
    supervisor = supervisor_at_verified_grasp()
    controller = SolutionAController(supervisor, tolerance(), max_hold_s=0.2)
    assert not controller.begin_direct_transfer(SimTime(10), plc(SimTime(10), mode=CutterMode.BLOCKED), 0.3)
    assert supervisor.state is CellState.REJECT
    assert all(event.state not in {CellState.ALIGN_DIRECT.value, CellState.FEED_DIRECT.value} for event in supervisor.events)


def test_solution_a_checks_matching_permissive_sequence_and_recovers() -> None:
    supervisor = supervisor_at_verified_grasp()
    controller = SolutionAController(supervisor, tolerance())
    assert controller.begin_direct_transfer(SimTime(10), plc(SimTime(10), sequence=3))
    controller.complete_direct_transfer(SimTime(11))
    assert not controller.align_and_feed(SimTime(20), plc(SimTime(20), sequence=4))
    assert supervisor.state is CellState.SAFE_STOP
    supervisor.return_to_idle(SimTime(21), "manual_reset_and_home_verified")
    assert supervisor.known_safe


def test_solution_b_nominal_corrects_logged_slip_and_feeds() -> None:
    supervisor = supervisor_at_verified_grasp()
    grasp = grasp_model()
    controller = SolutionBController(supervisor, tolerance(), BufferRuntime(1, 0.75), grasp)
    assert controller.transfer_to_buffer("product-1", SimTime(10))
    observed = Transform.planar(0.008, 0.0, 0.0, 0.03)
    slip = grasp.estimate_slip(commanded_grasp_from_product=Transform.identity(), observed_grasp_from_product=observed)
    assert controller.reobserve_and_align(SimTime(20), observed, slip)
    assert controller.corrected_pose is not None
    assert abs(controller.corrected_pose.translation.x_m) < 1e-12
    assert controller.wait_and_feed(SimTime(30), plc(SimTime(30), sequence=9))
    assessment = controller.verify_delivery(SimTime(40), nominal_measurement())
    assert assessment.success
    assert supervisor.terminal_path is TerminalPath.SUCCESS


def test_solution_b_buffer_occupancy_and_timeout_are_distinct() -> None:
    occupied_supervisor = supervisor_at_verified_grasp()
    occupied = BufferRuntime(1, 0.75, occupied_product_id="other", occupied_since=SimTime(0))
    controller = SolutionBController(occupied_supervisor, tolerance(), occupied, grasp_model())
    assert not controller.transfer_to_buffer("new", SimTime(10))
    assert occupied_supervisor.events[-1].reason == "buffer_occupied"

    timeout_supervisor = supervisor_at_verified_grasp()
    timeout_controller = SolutionBController(timeout_supervisor, tolerance(), BufferRuntime(1, 0.1), grasp_model())
    assert timeout_controller.transfer_to_buffer("piece", SimTime(10))
    no_slip = grasp_model().estimate_slip(
        commanded_grasp_from_product=Transform.identity(), observed_grasp_from_product=Transform.identity()
    )
    assert not timeout_controller.reobserve_and_align(SimTime.from_seconds(0.2), Transform.identity(), no_slip)
    assert timeout_supervisor.events[-1].reason == "buffer_timeout"


def test_feed_does_not_begin_without_matching_permissive() -> None:
    supervisor = supervisor_at_verified_grasp()
    controller = SolutionBController(supervisor, tolerance(), BufferRuntime(1, 0.75), grasp_model())
    controller.transfer_to_buffer("piece", SimTime(10))
    no_slip = grasp_model().estimate_slip(
        commanded_grasp_from_product=Transform.identity(), observed_grasp_from_product=Transform.identity()
    )
    controller.reobserve_and_align(SimTime(20), Transform.identity(), no_slip)
    assert not controller.wait_and_feed(SimTime(30), plc(SimTime(30), mode=CutterMode.BLOCKED))
    assert all(event.state != CellState.FEED_BUFFER.value for event in supervisor.events)
