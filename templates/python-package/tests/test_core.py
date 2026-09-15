import numpy as np
import pytest

from pkgname import ActionChunk, normalize_actions


def test_action_chunk_properties() -> None:
    chunk = ActionChunk(actions=np.zeros((10, 7), dtype=np.float32), dt_s=0.05)
    assert chunk.horizon == 10
    assert chunk.duration_s == pytest.approx(0.5)


def test_action_chunk_rejects_bad_shape() -> None:
    with pytest.raises(ValueError, match="must be"):
        ActionChunk(actions=np.zeros(7, dtype=np.float32), dt_s=0.05)


def test_normalize_roundtrip_stats() -> None:
    rng = np.random.default_rng(0)
    actions = rng.normal(size=(100, 3)).astype(np.float32)
    mean, std = actions.mean(0), actions.std(0)
    out = normalize_actions(actions, mean, std)
    np.testing.assert_allclose(out.mean(0), 0.0, atol=1e-5)
    np.testing.assert_allclose(out.std(0), 1.0, atol=1e-3)


def test_normalize_dim_mismatch() -> None:
    with pytest.raises(ValueError, match="action dim"):
        normalize_actions(
            np.zeros((4, 3), np.float32), np.zeros(2, np.float32), np.ones(2, np.float32)
        )
