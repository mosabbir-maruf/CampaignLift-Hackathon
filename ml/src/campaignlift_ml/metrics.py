"""Uplift Evaluation Metrics module for CampaignLift.

Mathematical Formulations & Causal Foundations:
------------------------------------------------
1. Radcliffe (2007) Qini Curve:
   Given N customers sorted descending by predicted individual treatment effect (uplift) tau_hat:
       Q(k) = Y_t(k) - Y_c(k) * (N_t / N_c)
   where:
       - k in [0, 1, ..., N] is the number of targeted customers.
       - N_t, N_c are the total counts of treated (T=1) and control (T=0) customers in the cohort.
       - Y_t(k), Y_c(k) are the cumulative factual responders (Y=1) in the top-k for treated and control.
       - At k=0: Q(0) = 0.
       - At k=N: Q(N) = Y_t - Y_c * (N_t / N_c) = N_t * ATE (Average Treatment Effect).

2. Random Targeting Baseline:
   A randomized policy that targets a fraction u = k / N achieves linear cumulative incremental gain:
       Q_random(k) = (k / N) * Q(N)

3. Qini Score (Area Between Qini Curve and Random Baseline):
   Evaluated using trapezoidal integration over normalized population fraction u in [0, 1]:
       Qini = Area(Q) - Area(Q_random) = \\int_0^1 [Q(u) - Q_random(u)] du

4. Cumulative Gain Curve (Uplift Curve):
   Measures the cumulative difference in response rates normalized by arm sizes:
       Gain(k) = (Y_t(k) / N_t) - (Y_c(k) / N_c)
   Note the relation: Q(k) = N_t * Gain(k).

5. Randomized Support Constraint (Responsible Causal Rule):
   If any evaluated slice has fewer than 30 treated customers (N_t < 30) or fewer than 30 control
   customers (N_c < 30), causal effect estimation lacks randomized support. In this case,
   do not report a noisy incremental rate; return 'insufficient randomized support'.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
import pandas as pd


@dataclass
class QiniCurveResult:
    """Detailed output of Qini curve calculation across population cutoffs."""
    n_samples: int
    n_treated: int
    n_control: int
    cutoffs: np.ndarray              # 0 to N
    population_fraction: np.ndarray  # 0.0 to 1.0
    qini_curve: np.ndarray           # Q(k)
    random_curve: np.ndarray         # Q_random(k)
    qini_score: float                # Area(Q) - Area(Q_random)
    normalized_qini_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert scalar summary metrics to serializable dictionary."""
        return {
            "n_samples": self.n_samples,
            "n_treated": self.n_treated,
            "n_control": self.n_control,
            "qini_score": round(self.qini_score, 6),
            "normalized_qini_score": round(self.normalized_qini_score, 6) if self.normalized_qini_score is not None else None,
            "qini_endpoint": round(float(self.qini_curve[-1]), 6),
        }


@dataclass
class CumulativeGainResult:
    """Output of Cumulative Gain (Uplift) curve calculation."""
    n_samples: int
    n_treated: int
    n_control: int
    cutoffs: np.ndarray
    population_fraction: np.ndarray
    gain_curve: np.ndarray           # Gain(k) = Y_t(k)/N_t - Y_c(k)/N_c
    random_curve: np.ndarray         # u * ATE
    ate: float                       # Overall Average Treatment Effect (Y_t/N_t - Y_c/N_c)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_samples": self.n_samples,
            "n_treated": self.n_treated,
            "n_control": self.n_control,
            "ate": round(self.ate, 6),
            "gain_endpoint": round(float(self.gain_curve[-1]), 6),
        }


@dataclass
class SliceIncrementalResponse:
    """Incremental response rate inside a specified audience or slice."""
    has_sufficient_support: bool
    n_treated: int
    n_control: int
    n_total: int
    treated_rate: Optional[float] = None
    control_rate: Optional[float] = None
    incremental_rate: Optional[float] = None  # treated_rate - control_rate
    status: str = "ok"                       # "ok" or "insufficient_randomized_support"
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_sufficient_support": self.has_sufficient_support,
            "n_treated": self.n_treated,
            "n_control": self.n_control,
            "n_total": self.n_total,
            "treated_rate": round(self.treated_rate, 6) if self.treated_rate is not None else None,
            "control_rate": round(self.control_rate, 6) if self.control_rate is not None else None,
            "incremental_rate": round(self.incremental_rate, 6) if self.incremental_rate is not None else None,
            "status": self.status,
            "message": self.message,
        }


def _validate_inputs(
    y_true: Union[np.ndarray, pd.Series],
    uplift_preds: Union[np.ndarray, pd.Series],
    treatment: Union[np.ndarray, pd.Series],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Validate arrays and ensure equal lengths and binary indicator types."""
    y = np.asarray(y_true, dtype=float)
    preds = np.asarray(uplift_preds, dtype=float)
    t = np.asarray(treatment, dtype=int)

    if not (len(y) == len(preds) == len(t)):
        raise ValueError(
            f"Input length mismatch: len(y)={len(y)}, len(preds)={len(preds)}, len(t)={len(t)}"
        )
    if len(y) == 0:
        raise ValueError("Input arrays must not be empty.")

    unique_t = set(np.unique(t))
    if not unique_t.issubset({0, 1}):
        raise ValueError(f"Treatment must be binary 0 or 1, found values: {unique_t}")

    return y, preds, t


def _trapezoid_area(y: np.ndarray, x: np.ndarray) -> float:
    """Compute definite integral using composite trapezoidal rule across all NumPy versions."""
    return float(np.sum(0.5 * (y[:-1] + y[1:]) * (x[1:] - x[:-1])))


def compute_qini_curve(
    y_true: Union[np.ndarray, pd.Series],
    uplift_preds: Union[np.ndarray, pd.Series],
    treatment: Union[np.ndarray, pd.Series],
) -> QiniCurveResult:
    """Compute the Radcliffe Qini curve and Qini score.

    Args:
        y_true: Factual binary outcome (1=transacted, 0=not).
        uplift_preds: Predicted individual treatment effect (tau_hat).
        treatment: Factual binary treatment assignment (1=treated, 0=control).

    Returns:
        QiniCurveResult containing curve arrays, endpoints, and Qini score.
    """
    y, preds, t = _validate_inputs(y_true, uplift_preds, treatment)

    # Sort descending by predicted uplift (using mergesort for stable sorting)
    order = np.argsort(-preds, kind="mergesort")
    y_sorted = y[order]
    t_sorted = t[order]

    n_samples = len(y_sorted)
    n_treated = int(np.sum(t_sorted == 1))
    n_control = int(np.sum(t_sorted == 0))

    if n_treated == 0 or n_control == 0:
        raise ValueError(
            f"Both arms must be present to compute Qini curve. Found n_treated={n_treated}, n_control={n_control}."
        )

    # Cumulative treated and control outcomes
    y_t_cum = np.cumsum(y_sorted * (t_sorted == 1))
    y_c_cum = np.cumsum(y_sorted * (t_sorted == 0))

    # Prepend zero at k=0
    y_t_curve = np.concatenate([[0.0], y_t_cum])
    y_c_curve = np.concatenate([[0.0], y_c_cum])
    cutoffs = np.arange(n_samples + 1)
    pop_fraction = cutoffs / n_samples

    # Q(k) = Y_t(k) - Y_c(k) * (N_t / N_c)
    ratio = n_treated / n_control
    qini_curve = y_t_curve - y_c_curve * ratio

    # Random baseline line: (k / N) * Q(N)
    final_qini = qini_curve[-1]
    random_curve = pop_fraction * final_qini

    # Area under Qini curve via trapezoidal rule over normalized fraction [0, 1]
    area_qini = _trapezoid_area(qini_curve, pop_fraction)
    area_random = _trapezoid_area(random_curve, pop_fraction)
    qini_score = area_qini - area_random

    # Optional normalized Qini score:
    # Compute the theoretical upper bound Qini curve (oracle factual ordering)
    # Sort all treated responders first, then control non-responders, then control responders, then treated non-responders
    try:
        # Optimal factual ranking
        opt_rank_key = np.zeros(n_samples)
        for i in range(n_samples):
            if t[i] == 1 and y[i] == 1:
                opt_rank_key[i] = 4  # Best
            elif t[i] == 0 and y[i] == 0:
                opt_rank_key[i] = 3
            elif t[i] == 0 and y[i] == 1:
                opt_rank_key[i] = 2
            else:
                opt_rank_key[i] = 1  # Worst: T=1, Y=0
        opt_order = np.argsort(-opt_rank_key, kind="mergesort")
        y_opt = y[opt_order]
        t_opt = t[opt_order]
        y_t_opt = np.concatenate([[0.0], np.cumsum(y_opt * (t_opt == 1))])
        y_c_opt = np.concatenate([[0.0], np.cumsum(y_opt * (t_opt == 0))])
        qini_opt = y_t_opt - y_c_opt * ratio
        area_opt = _trapezoid_area(qini_opt, pop_fraction)
        denom = area_opt - area_random
        normalized_qini = float(qini_score / denom) if denom > 1e-9 else 0.0
    except Exception:
        normalized_qini = None

    return QiniCurveResult(
        n_samples=n_samples,
        n_treated=n_treated,
        n_control=n_control,
        cutoffs=cutoffs,
        population_fraction=pop_fraction,
        qini_curve=qini_curve,
        random_curve=random_curve,
        qini_score=qini_score,
        normalized_qini_score=normalized_qini,
    )


def compute_qini_score(
    y_true: Union[np.ndarray, pd.Series],
    uplift_preds: Union[np.ndarray, pd.Series],
    treatment: Union[np.ndarray, pd.Series],
    normalized: bool = False,
) -> float:
    """Convenience helper returning just the Qini coefficient (score)."""
    res = compute_qini_curve(y_true, uplift_preds, treatment)
    if normalized and res.normalized_qini_score is not None:
        return res.normalized_qini_score
    return res.qini_score


def compute_cumulative_gain_curve(
    y_true: Union[np.ndarray, pd.Series],
    uplift_preds: Union[np.ndarray, pd.Series],
    treatment: Union[np.ndarray, pd.Series],
) -> CumulativeGainResult:
    """Compute the Cumulative Gain (Uplift) curve.

    Gain(k) = (Y_t(k) / N_t) - (Y_c(k) / N_c)
    """
    y, preds, t = _validate_inputs(y_true, uplift_preds, treatment)

    order = np.argsort(-preds, kind="mergesort")
    y_sorted = y[order]
    t_sorted = t[order]

    n_samples = len(y_sorted)
    n_treated = int(np.sum(t_sorted == 1))
    n_control = int(np.sum(t_sorted == 0))

    if n_treated == 0 or n_control == 0:
        raise ValueError(
            f"Both arms must be present. Found n_treated={n_treated}, n_control={n_control}."
        )

    y_t_cum = np.cumsum(y_sorted * (t_sorted == 1))
    y_c_cum = np.cumsum(y_sorted * (t_sorted == 0))

    y_t_curve = np.concatenate([[0.0], y_t_cum])
    y_c_curve = np.concatenate([[0.0], y_c_cum])
    cutoffs = np.arange(n_samples + 1)
    pop_fraction = cutoffs / n_samples

    gain_curve = (y_t_curve / n_treated) - (y_c_curve / n_control)
    ate = float(gain_curve[-1])
    random_curve = pop_fraction * ate

    return CumulativeGainResult(
        n_samples=n_samples,
        n_treated=n_treated,
        n_control=n_control,
        cutoffs=cutoffs,
        population_fraction=pop_fraction,
        gain_curve=gain_curve,
        random_curve=random_curve,
        ate=ate,
    )


def compute_incremental_response(
    y_true: Union[np.ndarray, pd.Series],
    treatment: Union[np.ndarray, pd.Series],
    min_support: int = 30,
) -> SliceIncrementalResponse:
    """Compute the factual incremental response rate for an audience with support check.

    Rule: If either arm has fewer than min_support (default: 30) observations,
    returns status='insufficient_randomized_support' and leaves incremental_rate as None.
    """
    y = np.asarray(y_true, dtype=float)
    t = np.asarray(treatment, dtype=int)

    n_total = len(y)
    n_treated = int(np.sum(t == 1))
    n_control = int(np.sum(t == 0))

    if n_treated < min_support or n_control < min_support:
        return SliceIncrementalResponse(
            has_sufficient_support=False,
            n_treated=n_treated,
            n_control=n_control,
            n_total=n_total,
            treated_rate=None,
            control_rate=None,
            incremental_rate=None,
            status="insufficient_randomized_support",
            message=f"insufficient randomized support (treated={n_treated} < {min_support} or control={n_control} < {min_support})",
        )

    treated_outcomes = y[t == 1]
    control_outcomes = y[t == 0]

    treated_rate = float(np.mean(treated_outcomes))
    control_rate = float(np.mean(control_outcomes))
    incremental_rate = treated_rate - control_rate

    return SliceIncrementalResponse(
        has_sufficient_support=True,
        n_treated=n_treated,
        n_control=n_control,
        n_total=n_total,
        treated_rate=treated_rate,
        control_rate=control_rate,
        incremental_rate=incremental_rate,
        status="ok",
        message=None,
    )


def compute_top_decile_incremental_response(
    y_true: Union[np.ndarray, pd.Series],
    uplift_preds: Union[np.ndarray, pd.Series],
    treatment: Union[np.ndarray, pd.Series],
    min_support: int = 30,
) -> SliceIncrementalResponse:
    """Compute incremental response rate within the top 10% highest predicted uplift scores."""
    y, preds, t = _validate_inputs(y_true, uplift_preds, treatment)

    order = np.argsort(-preds, kind="mergesort")
    top_10_count = max(1, int(np.ceil(0.10 * len(y))))
    top_indices = order[:top_10_count]

    return compute_incremental_response(
        y_true=y[top_indices],
        treatment=t[top_indices],
        min_support=min_support,
    )


def compute_treatment_rate(treatment: Union[np.ndarray, pd.Series]) -> float:
    """Calculate the treatment proportion inside a selected cohort: N_treated / N_total."""
    t = np.asarray(treatment, dtype=int)
    if len(t) == 0:
        return 0.0
    return float(np.mean(t == 1))


def evaluate_uplift_predictions(
    y_true: Union[np.ndarray, pd.Series],
    uplift_preds: Union[np.ndarray, pd.Series],
    treatment: Union[np.ndarray, pd.Series],
    candidate_id: str = "U0",
    model_name: str = "uplift_model",
    min_support: int = 30,
) -> Dict[str, Any]:
    """Produce comprehensive non-oracle uplift metrics bundle."""
    qini_res = compute_qini_curve(y_true, uplift_preds, treatment)
    gain_res = compute_cumulative_gain_curve(y_true, uplift_preds, treatment)
    top_decile_res = compute_top_decile_incremental_response(
        y_true, uplift_preds, treatment, min_support=min_support
    )
    overall_inc_res = compute_incremental_response(
        y_true, treatment, min_support=min_support
    )

    return {
        "candidate_id": candidate_id,
        "model_name": model_name,
        "n_eval": qini_res.n_samples,
        "n_treated": qini_res.n_treated,
        "n_control": qini_res.n_control,
        "treatment_rate": round(compute_treatment_rate(treatment), 5),
        "qini_score": round(qini_res.qini_score, 5),
        "normalized_qini_score": round(qini_res.normalized_qini_score, 5) if qini_res.normalized_qini_score is not None else None,
        "ate": round(gain_res.ate, 5),
        "top_decile": top_decile_res.to_dict(),
        "overall_incremental": overall_inc_res.to_dict(),
    }
