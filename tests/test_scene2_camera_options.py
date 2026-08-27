from isaac_sim.render_scene2_camera_options import CAMERA_OPTIONS


def test_camera_options_are_distinct_and_documented() -> None:
    assert set(CAMERA_OPTIONS) == {
        "cell_story_clear",
        "operator_three_quarter",
        "process_side",
        "robot_task_close",
    }
    eyes = {tuple(option["eye"]) for option in CAMERA_OPTIONS.values()}
    targets = {tuple(option["target"]) for option in CAMERA_OPTIONS.values()}
    assert len(eyes) == len(CAMERA_OPTIONS)
    assert len(targets) == len(CAMERA_OPTIONS)
    for option in CAMERA_OPTIONS.values():
        assert len(option["eye"]) == 3
        assert len(option["target"]) == 3
        assert 15.0 <= option["focal_length_mm"] <= 35.0
        assert option["purpose"].endswith(".")
