from fractions import Fraction

from meatcell.clock import EventPriority, EventScheduler, FixedStepClock
from meatcell.contracts import SimTime


def test_fixed_step_clock_has_no_accumulated_float_drift() -> None:
    clock = FixedStepClock(240)
    clock.step(240 * 60 * 60)
    assert clock.exact_seconds == Fraction(3600, 1)
    assert clock.now == SimTime.from_seconds(3600.0)


def test_same_time_events_have_documented_stable_priority_and_insertion_order() -> None:
    scheduler = EventScheduler()
    at = SimTime.from_seconds(1.0)
    scheduler.schedule("controller-1", at, priority=EventPriority.CONTROLLER)
    scheduler.schedule("camera", at, priority=EventPriority.CAMERA_EXPOSURE)
    scheduler.schedule("controller-2", at, priority=EventPriority.CONTROLLER)
    scheduler.schedule("estop", at, priority=EventPriority.EMERGENCY_STOP)
    assert [item.event_type for item in scheduler.pop_due(at)] == [
        "estop",
        "camera",
        "controller-1",
        "controller-2",
    ]


def test_identical_inputs_produce_identical_order_with_phase_offsets() -> None:
    def run() -> list[tuple[str, int]]:
        scheduler = EventScheduler()
        scheduler.schedule_periodic(
            "camera", frequency_hz=60, count=4, phase=SimTime.from_seconds(0.002), priority=EventPriority.CAMERA_EXPOSURE
        )
        scheduler.schedule_periodic("encoder", frequency_hz=1000, count=60, priority=EventPriority.ENCODER)
        return [(item.event_type, item.timestamp.nanoseconds) for item in scheduler.pop_due(SimTime.from_seconds(0.1))]

    assert run() == run()
    assert ("camera", 2_000_000) in run()


def test_delayed_delivery_retains_exposure_time() -> None:
    scheduler = EventScheduler()
    exposure = SimTime.from_seconds(0.25)
    event_id = scheduler.schedule("camera", exposure, priority=EventPriority.CAMERA_EXPOSURE)
    scheduler.schedule_delivery(event_id, exposure, 0.03, payload="frame-1")
    due = scheduler.pop_due(SimTime.from_seconds(0.28))
    assert [event.event_type for event in due] == ["camera", "perception_delivery"]
    assert due[1].payload["exposure_time_ns"] == exposure.nanoseconds


def test_cancellation_and_reset() -> None:
    scheduler = EventScheduler()
    first = scheduler.schedule("one", SimTime(1))
    scheduler.schedule("two", SimTime(2))
    assert scheduler.cancel(first)
    assert [item.event_type for item in scheduler.pop_due(SimTime(2))] == ["two"]
    scheduler.schedule("three", SimTime(3))
    scheduler.reset()
    assert scheduler.pending_count == 0
    assert scheduler.schedule("fresh", SimTime(0)) == 1


def test_clock_reset() -> None:
    clock = FixedStepClock()
    clock.step(99)
    clock.reset()
    assert clock.step_index == 0
    assert clock.now == SimTime(0)
