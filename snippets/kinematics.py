"""Rotation, transform, kinematics, and conveyor helpers from the kinematics note.

Companion to ``library/topics/kinematics-dynamics-and-rotations.md``. Conventions:
quaternions are scipy order ``xyzw`` unless the name says otherwise, transforms are
4x4 float64 named ``T_a_b`` ("b expressed in a"), angles are radians, lengths meters.

Run ``python snippets/kinematics.py`` or ``pytest snippets/kinematics.py`` for the checks.
"""

from __future__ import annotations

import numpy as np
from scipy.linalg import expm
from scipy.spatial.transform import Rotation as R
from scipy.spatial.transform import Slerp

# --- quaternions ------------------------------------------------------------------


def wxyz_to_xyzw(q: np.ndarray) -> np.ndarray:
    """Reorder scalar-first to scalar-last. Pure reorder, no sign change. (..., 4)."""
    return np.concatenate([q[..., 1:], q[..., :1]], axis=-1)


def xyzw_to_wxyz(q: np.ndarray) -> np.ndarray:
    """Reorder scalar-last to scalar-first. (..., 4)."""
    return np.concatenate([q[..., 3:], q[..., :3]], axis=-1)


def continuous(q_xyzw: np.ndarray) -> np.ndarray:
    """Flip each sample onto the previous sample's hemisphere so a series has no sign jumps.

    Args:
        q_xyzw: (T, 4) unit quaternions in time order.
    """
    out = q_xyzw.copy()
    for t in range(1, len(out)):
        if np.dot(out[t], out[t - 1]) < 0:
            out[t] = -out[t]
    return out


def orientation_error(q_des_xyzw: np.ndarray, q_cur_xyzw: np.ndarray) -> np.ndarray:
    """Rotation vector (rad, base frame) that takes current to desired: log(R_des R_cur^T).

    Sign-blind: passing -q_cur gives the same result. Feed to a P controller as angular velocity.
    """
    return (R.from_quat(q_des_xyzw) * R.from_quat(q_cur_xyzw).inv()).as_rotvec()


# --- transforms ---------------------------------------------------------------------


def make_T(p: np.ndarray, q_xyzw: np.ndarray) -> np.ndarray:
    """Homogeneous transform from position (3,) and quaternion (4,)."""
    T = np.eye(4)
    T[:3, :3] = R.from_quat(q_xyzw).as_matrix()
    T[:3, 3] = p
    return T


def inv_T(T: np.ndarray) -> np.ndarray:
    """Inverse of a rigid transform without a general matrix inverse."""
    out = np.eye(4)
    out[:3, :3] = T[:3, :3].T
    out[:3, 3] = -T[:3, :3].T @ T[:3, 3]
    return out


def relative_pose(T_w_a: np.ndarray, T_w_b: np.ndarray) -> np.ndarray:
    """T_a_b: pose of b expressed in a. Both inputs share the parent frame w."""
    return inv_T(T_w_a) @ T_w_b


def delta_in_tool_frame(T_b_t0: np.ndarray, T_b_t1: np.ndarray) -> np.ndarray:
    """Action moving the tool from t0 to t1, expressed in the tool frame.

    Apply as ``T_b_t1 = T_b_t0 @ delta``. The base-frame delta is
    ``T_b_t1 @ inv_T(T_b_t0)`` and is applied on the left instead.
    """
    return inv_T(T_b_t0) @ T_b_t1


def interp_se3(T0: np.ndarray, T1: np.ndarray, s: float) -> np.ndarray:
    """Straight line in position, SLERP in orientation, s in [0, 1]."""
    rots = R.from_matrix(np.stack([T0[:3, :3], T1[:3, :3]]))
    T = np.eye(4)
    T[:3, :3] = Slerp([0.0, 1.0], rots)(s).as_matrix()
    T[:3, 3] = (1 - s) * T0[:3, 3] + s * T1[:3, 3]
    return T


# --- kinematics (product of exponentials, MR chapter 4 and 5) -------------------------


def se3_hat(screw: np.ndarray) -> np.ndarray:
    """Matrix form of a screw axis (w, v) as a 4x4, MR eq. 3.83."""
    w, v = screw[:3], screw[3:]
    hat = np.zeros((4, 4))
    hat[:3, :3] = [[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]]
    hat[:3, 3] = v
    return hat


def fk_poe(screws: np.ndarray, M: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Forward kinematics T_base_tool = exp([S1] q1) ... exp([Sn] qn) M.

    Args:
        screws: (n, 6) joint screw axes in the base frame at q = 0, rows (w, v).
        M: (4, 4) tool pose at q = 0.
        q: (n,) joint positions.
    """
    T = np.eye(4)
    for S, qi in zip(screws, q, strict=True):
        T = T @ expm(se3_hat(S) * qi)
    return T @ M


def jacobian_fd(screws: np.ndarray, M: np.ndarray, q: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Geometric Jacobian (6, n) by central differences: rows are (v, w) of the tool in the base frame.

    Good enough for checks and for a policy-side manipulability monitor; use pinocchio for control.
    """
    n = len(q)
    J = np.zeros((6, n))
    for i in range(n):
        dq = np.zeros(n)
        dq[i] = eps
        Tp, Tm = fk_poe(screws, M, q + dq), fk_poe(screws, M, q - dq)
        J[:3, i] = (Tp[:3, 3] - Tm[:3, 3]) / (2 * eps)
        dR = Tp[:3, :3] @ Tm[:3, :3].T
        J[3:, i] = R.from_matrix(dR).as_rotvec() / (2 * eps)
    return J


def manipulability(J: np.ndarray) -> float:
    """Yoshikawa measure sqrt(det(J J^T)), zero at a singularity (MR 5.4)."""
    return float(np.sqrt(max(np.linalg.det(J @ J.T), 0.0)))


def dls_step(J: np.ndarray, err: np.ndarray, damping: float) -> np.ndarray:
    """Damped least-squares joint step J^T (J J^T + lambda^2 I)^-1 err (MR 6.2)."""
    JJt = J @ J.T
    return J.T @ np.linalg.solve(JJt + damping**2 * np.eye(JJt.shape[0]), err)


# --- conveyor -----------------------------------------------------------------------


def intercept_time(p_part: np.ndarray, v_belt: np.ndarray, p_tcp: np.ndarray, v_max: float) -> float | None:
    """Earliest t >= 0 at which a TCP moving at most v_max can meet a part on a belt.

    All vectors in the base frame; the part moves as p_part + v_belt t. Solves
    |p_part + v_belt t - p_tcp| = v_max t. Returns None when the part outruns the arm.
    Reach and joint limits at the meeting point are a separate IK check.
    """
    d = p_part - p_tcp
    a = float(v_belt @ v_belt - v_max**2)
    b = float(2.0 * d @ v_belt)
    c = float(d @ d)
    if abs(a) < 1e-12:  # belt speed equals v_max: the quadratic degenerates
        return -c / b if b < 0 else None
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    roots = sorted(((-b - np.sqrt(disc)) / (2 * a), (-b + np.sqrt(disc)) / (2 * a)))
    return next((t for t in roots if t >= 0), None)


# --- checks ----------------------------------------------------------------------------


def test_quaternions() -> None:
    """Order swap round-trips, continuity repair, sign-blind error."""
    q = R.random(5, random_state=1).as_quat()
    assert np.allclose(xyzw_to_wxyz(q), R.from_quat(q).as_quat(scalar_first=True))
    assert np.allclose(wxyz_to_xyzw(xyzw_to_wxyz(q)), q)
    seq = R.from_rotvec(np.outer(np.linspace(0, 2 * np.pi, 50), [0, 0, 1])).as_quat()
    seq[25:] *= -1  # the sign flip a logger produces
    fixed = continuous(seq)
    assert (np.einsum("ij,ij->i", fixed[1:], fixed[:-1]) > 0).all()
    q_cur = R.from_euler("z", 10, degrees=True).as_quat()
    q_des = R.from_euler("z", 40, degrees=True).as_quat()
    assert np.allclose(orientation_error(q_des, q_cur), [0, 0, np.deg2rad(30)])
    assert np.allclose(orientation_error(q_des, -q_cur), [0, 0, np.deg2rad(30)])


def test_transforms() -> None:
    """Inverse, relative pose, tool- and base-frame deltas, midpoint interpolation."""
    rng = np.random.default_rng(0)
    T_w_a = make_T(rng.normal(size=3), R.random(random_state=2).as_quat())
    T_w_b = make_T(rng.normal(size=3), R.random(random_state=3).as_quat())
    assert np.allclose(inv_T(T_w_a) @ T_w_a, np.eye(4))
    assert np.allclose(T_w_a @ relative_pose(T_w_a, T_w_b), T_w_b)
    assert np.allclose(T_w_a @ delta_in_tool_frame(T_w_a, T_w_b), T_w_b)
    assert np.allclose((T_w_b @ inv_T(T_w_a)) @ T_w_a, T_w_b)
    Tm = interp_se3(T_w_a, T_w_b, 0.5)
    assert np.allclose(Tm[:3, 3], 0.5 * (T_w_a[:3, 3] + T_w_b[:3, 3]))
    half = R.from_matrix(T_w_a[:3, :3].T @ Tm[:3, :3]).magnitude()
    full = R.from_matrix(T_w_a[:3, :3].T @ T_w_b[:3, :3]).magnitude()
    assert np.isclose(half, full / 2)


def _planar_2r(l1: float = 1.0, l2: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Two revolute joints about z, links along x (MR example 4.1)."""
    screws = np.array([[0, 0, 1, 0, 0, 0], [0, 0, 1, 0, -l1, 0]], dtype=float)
    M = np.eye(4)
    M[0, 3] = l1 + l2
    return screws, M


def test_kinematics() -> None:
    """PoE FK and finite-difference Jacobian against the closed-form planar 2R; DLS near the singularity."""
    screws, M = _planar_2r()
    q = np.array([0.3, 0.7])
    T = fk_poe(screws, M, q)
    x = np.cos(q[0]) + np.cos(q.sum())
    y = np.sin(q[0]) + np.sin(q.sum())
    assert np.allclose(T[:2, 3], [x, y])
    J = jacobian_fd(screws, M, q)
    J_closed = np.array([[-y, -np.sin(q.sum())], [x, np.cos(q.sum())]])
    assert np.allclose(J[:2], J_closed, atol=1e-6)
    assert np.allclose(J[5], [1, 1], atol=1e-6)  # both joints spin the tool about z
    Jp = J[:2]  # planar task: x, y only
    assert manipulability(Jp) > 0.5
    assert manipulability(jacobian_fd(screws, M, np.array([0.3, 0.0]))[:2]) < 1e-5  # stretched arm
    # near the singularity the pseudo-inverse step explodes; the damped one stays bounded
    J_sing = jacobian_fd(screws, M, np.array([0.3, 1e-4]))[:2]
    err = np.array([0.0, 0.01])
    assert np.linalg.norm(np.linalg.pinv(J_sing) @ err) > 10
    assert np.linalg.norm(dls_step(J_sing, err, damping=0.1)) < 1


def test_intercept() -> None:
    """Receding, approaching, and unreachable parts."""
    origin = np.zeros(3)
    assert np.isclose(intercept_time(np.array([1.0, 0, 0]), np.array([0.5, 0, 0]), origin, 1.0), 2.0)
    assert np.isclose(intercept_time(np.array([1.0, 0, 0]), np.array([-0.5, 0, 0]), origin, 1.0), 2 / 3)
    assert intercept_time(np.array([1.0, 0, 0]), np.array([2.0, 0, 0]), origin, 1.0) is None


if __name__ == "__main__":
    test_quaternions()
    test_transforms()
    test_kinematics()
    test_intercept()
    print("all checks passed")
