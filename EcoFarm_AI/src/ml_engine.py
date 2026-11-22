"""
EcoFarm Circular — Pure-Python Supervised ML Engine (Zero-External-Dependency Fallback)
======================================================================================

Implements transparent, mathematically faithful regression algorithms in pure
Python 3.11 standard library so all Phase 5 training, chronological validation,
test evaluation, and model serialization execute deterministically even in
environments without compiled NumPy/scikit-learn wheels:

  1. StandardScaler (fit strictly on training split; transform val/test)
  2. LinearRegression (closed-form OLS with tiny ridge guard 1e-8 via Gauss-Jordan)
  3. DecisionTreeRegressor (variance-reduction CART using pre-binned quantile splits)
  4. RandomForestRegressor (bagged ensemble with random feature subspacing)
  5. GradientBoostingRegressor (stagewise MSE residual boosting with shrinkage)
  6. Evaluation utilities: MAE, RMSE, R², residual quantiles, and permutation importance.

Note: `notebooks/03_solar_prediction.ipynb` and `notebooks/04_thermal_demand_prediction.ipynb`
also document the equivalent scikit-learn pipelines for local Jupyter environments.
"""

from __future__ import annotations

import bisect
import math
import pickle
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def quantile(sorted_vals: Sequence[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = min(len(sorted_vals) - 1, lo + 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def regression_metrics(y_true: Sequence[float], y_pred: Sequence[float]) -> Dict[str, float]:
    """Compute MAE, RMSE, R^2, Mean Bias Error, and Max Abs Error."""
    n = len(y_true)
    if n == 0:
        return {"n": 0, "mae": 0.0, "rmse": 0.0, "r2": 0.0, "bias": 0.0, "max_abs_err": 0.0}
    abs_sum = 0.0
    sq_sum = 0.0
    err_sum = 0.0
    max_abs = 0.0
    y_bar = sum(y_true) / n
    ss_tot = 0.0
    for yt, yp in zip(y_true, y_pred):
        err = yp - yt
        aerr = abs(err)
        abs_sum += aerr
        sq_sum += err * err
        err_sum += err
        if aerr > max_abs:
            max_abs = aerr
        diff = yt - y_bar
        ss_tot += diff * diff
    mae = abs_sum / n
    rmse = math.sqrt(sq_sum / n)
    r2 = 1.0 - (sq_sum / ss_tot) if ss_tot > 1e-12 else 0.0
    return {
        "n": float(n),
        "mae": round(mae, 5),
        "rmse": round(rmse, 5),
        "r2": round(r2, 5),
        "bias": round(err_sum / n, 5),
        "max_abs_err": round(max_abs, 5),
    }


def residual_summary(y_true: Sequence[float], y_pred: Sequence[float]) -> Dict[str, Any]:
    """Compute signed residual distribution (y_true - y_pred) and histogram bins."""
    res = [yt - yp for yt, yp in zip(y_true, y_pred)]
    if not res:
        return {"count": 0}
    s = sorted(res)
    n = len(s)
    mu = sum(s) / n
    var = sum((r - mu) ** 2 for r in s) / n
    p05 = quantile(s, 0.05)
    p25 = quantile(s, 0.25)
    p50 = quantile(s, 0.50)
    p75 = quantile(s, 0.75)
    p95 = quantile(s, 0.95)
    lo, hi = s[0], s[-1]
    bins = 24
    span = max(hi - lo, 1e-6)
    step = span / bins
    counts = [0] * bins
    for r in s:
        idx = min(bins - 1, max(0, int((r - lo) / step)))
        counts[idx] += 1
    hist = [
        {
            "bin_start": round(lo + i * step, 4),
            "bin_end": round(lo + (i + 1) * step, 4),
            "bin_center": round(lo + (i + 0.5) * step, 4),
            "count": counts[i],
        }
        for i in range(bins)
    ]
    return {
        "count": n,
        "mean": round(mu, 5),
        "std": round(math.sqrt(var), 5),
        "min": round(lo, 5),
        "p05": round(p05, 5),
        "p25": round(p25, 5),
        "median": round(p50, 5),
        "p75": round(p75, 5),
        "p95": round(p95, 5),
        "max": round(hi, 5),
        "histogram": hist,
    }


class StandardScaler:
    """Zero-mean, unit-variance feature scaler fit ONLY on training data."""

    def __init__(self) -> None:
        self.means: List[float] = []
        self.stds: List[float] = []

    def fit(self, X: Sequence[Sequence[float]]) -> "StandardScaler":
        n = len(X)
        p = len(X[0])
        self.means = [0.0] * p
        self.stds = [1.0] * p
        for row in X:
            for j in range(p):
                self.means[j] += row[j]
        for j in range(p):
            self.means[j] /= n
        var = [0.0] * p
        for row in X:
            for j in range(p):
                d = row[j] - self.means[j]
                var[j] += d * d
        for j in range(p):
            s = math.sqrt(var[j] / n)
            self.stds[j] = s if s > 1e-12 else 1.0
        return self

    def transform(self, X: Sequence[Sequence[float]]) -> List[List[float]]:
        means = self.means
        stds = self.stds
        p = len(means)
        return [[(row[j] - means[j]) / stds[j] for j in range(p)] for row in X]

    def fit_transform(self, X: Sequence[Sequence[float]]) -> List[List[float]]:
        return self.fit(X).transform(X)


class LinearRegression:
    """Ordinary Least Squares linear regression with optional scaling and tiny L2 guard."""

    def __init__(self, l2_reg: float = 1e-8, scale_features: bool = True) -> None:
        self.l2_reg = l2_reg
        self.scale_features = scale_features
        self.scaler: Optional[StandardScaler] = StandardScaler() if scale_features else None
        self.weights: List[float] = []
        self.bias: float = 0.0

    def fit(self, X: Sequence[Sequence[float]], y: Sequence[float]) -> "LinearRegression":
        Xs = self.scaler.fit_transform(X) if self.scaler is not None else [list(r) for r in X]
        n = len(Xs)
        p = len(Xs[0])
        m = p + 1  # Last column is intercept 1.0
        xtx = [[0.0] * m for _ in range(m)]
        xty = [0.0] * m

        for i in range(n):
            row = Xs[i]
            yi = y[i]
            for j in range(p):
                rj = row[j]
                xty[j] += rj * yi
                xtx[j][p] += rj
                xtx[p][j] += rj
                for k in range(j, p):
                    xtx[j][k] += rj * row[k]
            xty[p] += yi
            xtx[p][p] += 1.0

        for j in range(p):
            for k in range(j):
                xtx[j][k] = xtx[k][j]
            xtx[j][j] += self.l2_reg

        # Gauss-Jordan elimination with partial pivoting
        aug = [xtx[i][:] + [xty[i]] for i in range(m)]
        for col in range(m):
            pivot_row = max(range(col, m), key=lambda r: abs(aug[r][col]))
            aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
            piv = aug[col][col]
            if abs(piv) < 1e-12:
                piv = 1e-12
            inv_piv = 1.0 / piv
            for k in range(col, m + 1):
                aug[col][k] *= inv_piv
            for r in range(m):
                if r != col and aug[r][col] != 0.0:
                    factor = aug[r][col]
                    for k in range(col, m + 1):
                        aug[r][k] -= factor * aug[col][k]

        self.weights = [aug[j][m] for j in range(p)]
        self.bias = aug[p][m]
        return self

    def predict(self, X: Sequence[Sequence[float]]) -> List[float]:
        Xs = self.scaler.transform(X) if self.scaler is not None else X
        w = self.weights
        b = self.bias
        p = len(w)
        return [b + sum(row[j] * w[j] for j in range(p)) for row in Xs]


@dataclass
class _TreeNode:
    is_leaf: bool
    value: float
    feature_idx: int = -1
    threshold: float = 0.0
    left: Optional["_TreeNode"] = None
    right: Optional["_TreeNode"] = None


def _build_bin_spec(
    X: Sequence[Sequence[float]], max_bins: int = 64, subsample: int = 4096, seed: int = 42
) -> Tuple[List[List[float]], List[List[int]]]:
    """Build quantile split thresholds per feature and integer-bin the training matrix."""
    n = len(X)
    p = len(X[0])
    rng = random.Random(seed)
    sample_idx = rng.sample(range(n), min(n, subsample))
    thresholds_per_feat: List[List[float]] = []

    for j in range(p):
        vals = sorted({X[i][j] for i in sample_idx})
        if len(vals) <= 1:
            thresholds_per_feat.append([])
        elif len(vals) <= max_bins:
            mids = [0.5 * (vals[k] + vals[k + 1]) for k in range(len(vals) - 1)]
            thresholds_per_feat.append(mids)
        else:
            th: List[float] = []
            for b in range(1, max_bins):
                pos = int((b / max_bins) * (len(vals) - 1))
                mid = 0.5 * (vals[pos] + vals[min(len(vals) - 1, pos + 1)])
                if not th or mid > th[-1] + 1e-12:
                    th.append(mid)
            thresholds_per_feat.append(th)

    binned: List[List[int]] = [[0] * p for _ in range(n)]
    for j in range(p):
        th = thresholds_per_feat[j]
        if not th:
            continue
        for i in range(n):
            binned[i][j] = bisect.bisect_right(th, X[i][j])
    return thresholds_per_feat, binned


class DecisionTreeRegressor:
    """Fast histogram-threshold CART regressor minimizing squared error."""

    def __init__(
        self,
        max_depth: int = 10,
        min_samples_split: int = 12,
        min_samples_leaf: int = 5,
        max_bins: int = 64,
        max_features: Optional[int] = None,
        random_state: int = 42,
    ) -> None:
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.max_bins = max_bins
        self.max_features = max_features
        self.random_state = random_state
        self.root: Optional[_TreeNode] = None
        self.n_features: int = 0

    def fit(
        self,
        X: Sequence[Sequence[float]],
        y: Sequence[float],
        precomputed_bins: Optional[Tuple[List[List[float]], List[List[int]]]] = None,
        sample_indices: Optional[List[int]] = None,
    ) -> "DecisionTreeRegressor":
        self.n_features = len(X[0])
        if precomputed_bins is None:
            thresholds, binned = _build_bin_spec(X, max_bins=self.max_bins, seed=self.random_state)
        else:
            thresholds, binned = precomputed_bins

        idx = list(range(len(X))) if sample_indices is None else sample_indices
        rng = random.Random(self.random_state)
        self.root = self._grow(binned, thresholds, y, idx, depth=0, rng=rng)
        return self

    def _grow(
        self,
        binned: List[List[int]],
        thresholds: List[List[float]],
        y: Sequence[float],
        indices: List[int],
        depth: int,
        rng: random.Random,
    ) -> _TreeNode:
        n = len(indices)
        sum_y = 0.0
        sum_y2 = 0.0
        for i in indices:
            yi = y[i]
            sum_y += yi
            sum_y2 += yi * yi
        node_mean = sum_y / n
        total_sse = max(0.0, sum_y2 - (sum_y * sum_y) / n)

        if depth >= self.max_depth or n < self.min_samples_split or total_sse <= 1e-10:
            return _TreeNode(is_leaf=True, value=node_mean)

        feat_candidates = list(range(self.n_features))
        if self.max_features is not None and self.max_features < self.n_features:
            feat_candidates = rng.sample(feat_candidates, self.max_features)

        best_gain = 1e-10
        best_feat = -1
        best_bin_cut = -1
        best_thresh = 0.0

        for j in feat_candidates:
            th = thresholds[j]
            if not th:
                continue
            nbins = len(th) + 1
            cnt = [0] * nbins
            sy = [0.0] * nbins
            for i in indices:
                b = binned[i][j]
                cnt[b] += 1
                sy[b] += y[i]

            left_cnt = 0
            left_sy = 0.0
            for b in range(nbins - 1):
                left_cnt += cnt[b]
                left_sy += sy[b]
                right_cnt = n - left_cnt
                if left_cnt < self.min_samples_leaf or right_cnt < self.min_samples_leaf:
                    continue
                right_sy = sum_y - left_sy
                # Maximizing (left_sy^2 / left_cnt + right_sy^2 / right_cnt - sum_y^2 / n)
                gain = (left_sy * left_sy) / left_cnt + (right_sy * right_sy) / right_cnt - (sum_y * sum_y) / n
                if gain > best_gain:
                    best_gain = gain
                    best_feat = j
                    best_bin_cut = b
                    best_thresh = th[b]

        if best_feat == -1:
            return _TreeNode(is_leaf=True, value=node_mean)

        left_idx: List[int] = []
        right_idx: List[int] = []
        for i in indices:
            if binned[i][best_feat] <= best_bin_cut:
                left_idx.append(i)
            else:
                right_idx.append(i)

        return _TreeNode(
            is_leaf=False,
            value=node_mean,
            feature_idx=best_feat,
            threshold=best_thresh,
            left=self._grow(binned, thresholds, y, left_idx, depth + 1, rng),
            right=self._grow(binned, thresholds, y, right_idx, depth + 1, rng),
        )

    def _predict_row(self, row: Sequence[float]) -> float:
        node = self.root
        while node is not None and not node.is_leaf:
            if row[node.feature_idx] <= node.threshold:
                node = node.left
            else:
                node = node.right
        return node.value if node is not None else 0.0

    def predict(self, X: Sequence[Sequence[float]]) -> List[float]:
        return [self._predict_row(row) for row in X]


class RandomForestRegressor:
    """Bagged ensemble of variance-reducing decision trees."""

    def __init__(
        self,
        n_estimators: int = 20,
        max_depth: int = 11,
        min_samples_split: int = 10,
        min_samples_leaf: int = 4,
        max_features_ratio: float = 0.7,
        subsample_ratio: float = 0.85,
        max_bins: int = 64,
        random_state: int = 42,
    ) -> None:
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.max_features_ratio = max_features_ratio
        self.subsample_ratio = subsample_ratio
        self.max_bins = max_bins
        self.random_state = random_state
        self.trees: List[DecisionTreeRegressor] = []

    def fit(self, X: Sequence[Sequence[float]], y: Sequence[float]) -> "RandomForestRegressor":
        n = len(X)
        p = len(X[0])
        max_feat = max(2, int(round(p * self.max_features_ratio)))
        precomputed = _build_bin_spec(X, max_bins=self.max_bins, seed=self.random_state)
        rng = random.Random(self.random_state)
        bag_size = max(10, int(round(n * self.subsample_ratio)))
        self.trees = []

        for t in range(self.n_estimators):
            sample_idx = [rng.randrange(n) for _ in range(bag_size)]
            tree = DecisionTreeRegressor(
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split,
                min_samples_leaf=self.min_samples_leaf,
                max_bins=self.max_bins,
                max_features=max_feat,
                random_state=self.random_state + t * 17,
            )
            tree.fit(X, y, precomputed_bins=precomputed, sample_indices=sample_idx)
            self.trees.append(tree)
        return self

    def predict(self, X: Sequence[Sequence[float]]) -> List[float]:
        n = len(X)
        preds = [0.0] * n
        inv_k = 1.0 / len(self.trees)
        for tree in self.trees:
            for i in range(n):
                preds[i] += tree._predict_row(X[i])
        return [v * inv_k for v in preds]


class GradientBoostingRegressor:
    """Stagewise gradient-boosted regression trees minimizing L2 loss."""

    def __init__(
        self,
        n_estimators: int = 50,
        learning_rate: float = 0.12,
        max_depth: int = 4,
        min_samples_split: int = 12,
        min_samples_leaf: int = 5,
        subsample: float = 0.85,
        max_bins: int = 64,
        random_state: int = 42,
    ) -> None:
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.subsample = subsample
        self.max_bins = max_bins
        self.random_state = random_state
        self.init_pred: float = 0.0
        self.trees: List[DecisionTreeRegressor] = []

    def fit(self, X: Sequence[Sequence[float]], y: Sequence[float]) -> "GradientBoostingRegressor":
        n = len(X)
        self.init_pred = sum(y) / n
        preds = [self.init_pred] * n
        precomputed = _build_bin_spec(X, max_bins=self.max_bins, seed=self.random_state)
        rng = random.Random(self.random_state)
        sub_n = max(10, int(round(n * self.subsample)))
        self.trees = []

        for m in range(self.n_estimators):
            residuals = [y[i] - preds[i] for i in range(n)]
            sample_idx = rng.sample(range(n), sub_n) if sub_n < n else list(range(n))
            tree = DecisionTreeRegressor(
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split,
                min_samples_leaf=self.min_samples_leaf,
                max_bins=self.max_bins,
                max_features=None,
                random_state=self.random_state + m * 31,
            )
            tree.fit(X, residuals, precomputed_bins=precomputed, sample_indices=sample_idx)
            lr = self.learning_rate
            for i in range(n):
                preds[i] += lr * tree._predict_row(X[i])
            self.trees.append(tree)
        return self

    def predict(self, X: Sequence[Sequence[float]]) -> List[float]:
        n = len(X)
        preds = [self.init_pred] * n
        lr = self.learning_rate
        for tree in self.trees:
            for i in range(n):
                preds[i] += lr * tree._predict_row(X[i])
        return preds


def permutation_importance(
    model: Any,
    X: Sequence[Sequence[float]],
    y: Sequence[float],
    feature_names: Sequence[str],
    n_repeats: int = 5,
    seed: int = 42,
    clip_min: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Compute model-agnostic permutation importance measured as MAE increase (kW)
    and R^2 drop when each feature column is randomly permuted.
    """
    n = len(X)
    base_pred = model.predict(X)
    if clip_min is not None:
        base_pred = [max(clip_min, p) for p in base_pred]
    base_metrics = regression_metrics(y, base_pred)
    base_mae = base_metrics["mae"]
    base_r2 = base_metrics["r2"]

    rng = random.Random(seed)
    X_work = [list(row) for row in X]
    results: List[Dict[str, Any]] = []

    for j, fname in enumerate(feature_names):
        orig_col = [X_work[i][j] for i in range(n)]
        mae_deltas: List[float] = []
        r2_drops: List[float] = []
        for _ in range(n_repeats):
            shuffled = orig_col[:]
            rng.shuffle(shuffled)
            for i in range(n):
                X_work[i][j] = shuffled[i]
            perm_pred = model.predict(X_work)
            if clip_min is not None:
                perm_pred = [max(clip_min, p) for p in perm_pred]
            m = regression_metrics(y, perm_pred)
            mae_deltas.append(m["mae"] - base_mae)
            r2_drops.append(base_r2 - m["r2"])
        # Restore original column before moving to next feature
        for i in range(n):
            X_work[i][j] = orig_col[i]

        mean_mae_inc = sum(mae_deltas) / n_repeats
        std_mae_inc = math.sqrt(sum((d - mean_mae_inc) ** 2 for d in mae_deltas) / n_repeats)
        mean_r2_drop = sum(r2_drops) / n_repeats
        results.append(
            {
                "feature": fname,
                "mae_increase": round(mean_mae_inc, 5),
                "mae_increase_std": round(std_mae_inc, 5),
                "r2_drop": round(mean_r2_drop, 5),
            }
        )

    total_inc = sum(max(0.0, r["mae_increase"]) for r in results) or 1e-9
    for r in results:
        r["relative_pct"] = round(100.0 * max(0.0, r["mae_increase"]) / total_inc, 2)

    results.sort(key=lambda r: r["mae_increase"], reverse=True)
    return results


def save_model_artifact(artifact: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(artifact, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_model_artifact(path: Path) -> Any:
    with open(path, "rb") as f:
        return pickle.load(f)
