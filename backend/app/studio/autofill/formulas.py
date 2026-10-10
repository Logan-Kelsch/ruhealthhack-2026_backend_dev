"""Published clinical formulas used to compute derived values. Pure functions."""
from __future__ import annotations


def egfr_ckd_epi_2021(creatinine_mg_dl: float, age: int, female: bool) -> float:
    """CKD-EPI 2021 creatinine equation, race-free (Inker et al., NEJM 2021)."""
    kappa = 0.7 if female else 0.9
    alpha = -0.241 if female else -0.302
    ratio = creatinine_mg_dl / kappa
    value = 142 * min(ratio, 1.0) ** alpha * max(ratio, 1.0) ** -1.200 * 0.9938**age
    return value * 1.012 if female else value


def creatinine_for_egfr(target_egfr: float, age: int, female: bool, lo: float = 0.2, hi: float = 15.0) -> float:
    """Inverse of the CKD-EPI 2021 equation by bisection (eGFR falls as creatinine rises)."""
    for _ in range(80):
        mid = (lo + hi) / 2
        if egfr_ckd_epi_2021(mid, age, female) > target_egfr:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def anion_gap(na: float, cl: float, hco3: float) -> float:
    return na - (cl + hco3)


def estimated_average_glucose(a1c_percent: float) -> float:
    """ADAG study: eAG (mg/dL) = 28.7 x A1C - 46.7 (Nathan et al., Diabetes Care 2008)."""
    return 28.7 * a1c_percent - 46.7


def friedewald_total_cholesterol(ldl: float, hdl: float, tg: float) -> float:
    """Total cholesterol consistent with the Friedewald relation LDL = TC - HDL - TG/5."""
    return ldl + hdl + tg / 5


def bmi(weight_lb: float, height_in: float) -> float:
    return 703 * weight_lb / height_in**2
