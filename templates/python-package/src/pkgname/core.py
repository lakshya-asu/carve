"""Core data structures and transforms.

This module is a template. It shows the expected style: typed, documented,
shape-annotated, and free of hidden state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

logger = logging.getLogger(__name__)

FloatArray = npt.NDArray[np.float32]


@dataclass(frozen=True)
class ActionChunk:
    """A fixed-horizon block of robot actions.

    Attributes:
        actions: Array of shape (T, D) float32. T timesteps, D action dims.
        dt_s: Time between consecutive actions, in seconds.
    """

    actions: FloatArray
    dt_s: float

    def __post_init__(self) -> None:
        if self.actions.ndim != 2:
            raise ValueError(f"actions must be (T, D), got shape {self.actions.shape}")
        if self.dt_s <= 0:
            raise ValueError(f"dt_s must be positive, got {self.dt_s}")

    @property
    def horizon(self) -> int:
        """Number of timesteps T."""
        return int(self.actions.shape[0])

    @property
    def duration_s(self) -> float:
        """Total duration covered by the chunk, in seconds."""
        return self.horizon * self.dt_s


def normalize_actions(
    actions: FloatArray, mean: FloatArray, std: FloatArray, eps: float = 1e-6
) -> FloatArray:
    """Standardize actions per dimension.

    Args:
        actions: Shape (..., D) float32.
        mean: Shape (D,) per-dimension mean.
        std: Shape (D,) per-dimension standard deviation.
        eps: Added to std to avoid division by zero.

    Returns:
        Array of the same shape as `actions`, float32.

    Raises:
        ValueError: If the trailing dimension of `actions` does not match `mean`.
    """
    if actions.shape[-1] != mean.shape[0]:
        raise ValueError(f"action dim {actions.shape[-1]} != stats dim {mean.shape[0]}")
    out = (actions - mean) / (std + eps)
    logger.debug("normalized actions with shape %s", out.shape)
    return out.astype(np.float32)
