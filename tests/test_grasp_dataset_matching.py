import pytest

from tools.build_grasp_affordance_dataset import validate_matched_rows


def _rows() -> list[dict[str, object]]:
    rows = []
    for group, split in (("fit-group", "fit"), ("held-group", "held_out")):
        condition = {"seed": 1 if split == "fit" else 2, "belt_speed_mps": 0.16}
        for candidate_index in range(5):
            rows.append(
                {
                    "trial_group_id": group,
                    "candidate_index": candidate_index,
                    "split": split,
                    "trial_condition": condition,
                }
            )
    return rows


def test_complete_matched_candidate_groups_pass() -> None:
    summary = validate_matched_rows(_rows())
    assert summary == {
        "trial_group_count": 2,
        "candidate_indices": [0, 1, 2, 3, 4],
        "rows_per_group": 5,
    }


def test_missing_candidate_fails_closed() -> None:
    rows = _rows()
    rows.pop()
    with pytest.raises(ValueError, match="candidates 0 through 4"):
        validate_matched_rows(rows)


def test_condition_change_within_reset_group_fails_closed() -> None:
    rows = _rows()
    rows[4]["trial_condition"] = {"seed": 1, "belt_speed_mps": 0.20}
    with pytest.raises(ValueError, match="changed conditions"):
        validate_matched_rows(rows)
