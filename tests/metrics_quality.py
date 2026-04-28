"""Quality metrics for multi-objective optimization: GD, IGD, HV, SP.

Handles mixed objectives (cost minimize, balance/efficiency maximize).
Normalizes all objectives to [0,1] before computing metrics.
Pure numpy — no extra dependencies.
"""

import numpy as np


def _negate_maximize(points: np.ndarray) -> np.ndarray:
    """Convert mixed objectives to all-minimization.
    Assumes column order: cost(minimize), balance(maximize), efficiency(maximize).
    """
    pts = points.copy().astype(float)
    pts[:, 1] = -pts[:, 1]  # balance: max → min
    pts[:, 2] = -pts[:, 2]  # efficiency: max → min
    return pts


def _normalize(points: np.ndarray, ideal: np.ndarray, nadir: np.ndarray) -> np.ndarray:
    """Min-max normalize to [0,1] using ideal and nadir points."""
    denom = nadir - ideal
    denom[denom == 0] = 1.0
    return (points - ideal) / denom


def _filter_nondominated(points: np.ndarray) -> np.ndarray:
    """Keep only non-dominated points (all objectives minimization)."""
    points = np.array(points)
    n = len(points)
    keep = np.ones(n, dtype=bool)
    for i in range(n):
        if not keep[i]:
            continue
        for j in range(n):
            if i == j or not keep[j]:
                continue
            if np.all(points[i] <= points[j]) and np.any(points[i] < points[j]):
                keep[j] = False
    return points[keep]


def gd(pareto_front: np.ndarray, reference_front: np.ndarray) -> float:
    """Generational Distance — lower is better."""
    if len(pareto_front) == 0 or len(reference_front) == 0:
        return 0.0
    distances = [min(np.linalg.norm(p - r) for r in reference_front) for p in pareto_front]
    return float(np.mean(distances))


def igd(pareto_front: np.ndarray, reference_front: np.ndarray) -> float:
    """Inverted Generational Distance — lower is better."""
    if len(pareto_front) == 0 or len(reference_front) == 0:
        return 0.0
    distances = [min(np.linalg.norm(r - p) for p in pareto_front) for r in reference_front]
    return float(np.mean(distances))


def spacing(pareto_front: np.ndarray) -> float:
    """Spacing metric — lower is better (uniform distribution)."""
    if len(pareto_front) < 2:
        return 0.0
    distances = []
    for i, p in enumerate(pareto_front):
        nearest = min(np.linalg.norm(p - q) for j, q in enumerate(pareto_front) if j != i)
        distances.append(nearest)
    d_mean = np.mean(distances)
    if len(distances) < 2:
        return 0.0
    sp = np.sqrt(np.sum((np.array(distances) - d_mean) ** 2) / (len(distances) - 1))
    return float(sp)


def hypervolume_3d(points: np.ndarray, ref_point: np.ndarray) -> float:
    """Hypervolume for 3 objectives using recursive slicing.
    Points and ref_point should be in normalized [0,1] minimization space.
    """
    points = np.array(points)
    if len(points) == 0:
        return 0.0
    nondom = _filter_nondominated(points)
    if len(nondom) == 0:
        return 0.0
    # Sort by first objective descending
    sorted_idx = np.argsort(-nondom[:, 0])
    nondom = nondom[sorted_idx]
    return _hv_recursive_3d(nondom, ref_point, 0)


def _hv_recursive_3d(points: np.ndarray, ref: np.ndarray, depth: int) -> float:
    """Recursive hypervolume in 3D."""
    if len(points) == 0:
        return 0.0
    if depth >= 3:
        return 1.0  # base case: remaining volume is 1.0
    idx = np.argsort(-points[:, depth])
    sorted_pts = points[idx]
    vol = 0.0
    prev = ref[depth]
    for i in range(len(sorted_pts)):
        val = sorted_pts[i, depth]
        if val >= ref[depth]:
            continue
        slice_len = prev - val
        if slice_len <= 0:
            prev = val
            continue
        remaining = sorted_pts[:i + 1]
        sub_vol = _hv_recursive_3d(remaining, ref, depth + 1)
        vol += slice_len * sub_vol
        prev = val
    return vol


def compute_quality_metrics(fronts: dict[str, np.ndarray]) -> dict[str, dict]:
    """Compute GD, IGD, HV, SP for each algorithm front.

    Normalizes all objectives to [0,1] for fair comparison.
    Handles mixed: cost(minimize), balance(maximize), efficiency(maximize).

    Args:
        fronts: dict mapping algo_name -> np.ndarray of shape (n, 3)
    Returns:
        dict: algo_name -> {gd, igd, hv, sp}
    """
    if len(fronts) < 2:
        return {}

    # Convert to all-minimization
    minim_pts = {name: _negate_maximize(pts) for name, pts in fronts.items()}
    all_pts = np.vstack(list(minim_pts.values()))

    # Normalize to [0,1]
    ideal = np.min(all_pts, axis=0)
    nadir = np.max(all_pts, axis=0)
    norm_pts = {name: _normalize(pts, ideal, nadir) for name, pts in minim_pts.items()}

    # Reference front (non-dominated in normalized space)
    all_norm = np.vstack(list(norm_pts.values()))
    ref_front = _filter_nondominated(all_norm)

    if len(ref_front) == 0:
        return {name: {"gd": 0, "igd": 0, "hv": 0, "sp": 0} for name in fronts}

    # Reference point = worst across all fronts + 10%
    ref_point = np.ones(3) * 1.1  # in normalized [0,1] space

    results = {}
    for name, front in norm_pts.items():
        if len(front) == 0:
            results[name] = {"gd": 0, "igd": 0, "hv": 0, "sp": 0}
            continue
        results[name] = {
            "gd": round(gd(front, ref_front), 4),
            "igd": round(igd(front, ref_front), 4),
            "hv": round(hypervolume_3d(front, ref_point), 4),
            "sp": round(spacing(front), 4),
        }
    return results
