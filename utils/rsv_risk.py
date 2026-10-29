"""
rsv_risk.py
-------------
Rule-based RSV (Respiratory Syncytial Virus) risk screening add-on.

Unlike Allergy_Risk / SideEffect_Risk (which use trained RandomForest
models), this module is a transparent, rule-based scoring system built
on the same lab fields the app already extracts/collects for every
patient: Age, CRP, ALT, AST. No new report fields or models are
required, so it works for CSV Upload, Manual Entry, and Medical
Report Upload alike.

DISCLAIMER: This is an illustrative, synthetic-data educational demo.
The scoring thresholds below are reasonable rule-of-thumb approximations
(age vulnerability + inflammatory/liver-enzyme elevation), NOT a
validated clinical scoring system. This must never be used for real
RSV diagnosis or treatment decisions.
"""

from typing import Dict, Any

from utils.validation import get_reference_range

# Recommendation text per RSV risk level (exact wording as required)
RSV_RECOMMENDATIONS = {
    "High": "Consult Doctor",
    "Medium": "Precaution",
    "Low": "Low",
}

RSV_RISK_COLORS = {"Low": "#2ecc71", "Medium": "#f39c12", "High": "#e74c3c"}

# Precaution steps shown for Medium RSV risk patients — practical steps to
# take before proceeding with vaccination under observation. Only shown for
# "Medium"; High routes to a doctor, Low needs no special precautions.
RSV_PRECAUTIONS = [
    "Ensure the patient is symptom-free (no fever, cough, or wheeze) for at least 48 hours before vaccination.",
    "Recheck temperature on the day of vaccination — do not vaccinate if fever is present.",
    "Keep the patient well-hydrated and rested in the days leading up to the appointment.",
    "Inform the vaccinating doctor about the recent RSV-related lab findings (CRP/ALT/AST).",
    "Vaccinate only under medical observation, with monitoring for at least 30 minutes after the dose.",
    "Watch for any allergic or adverse reaction after vaccination and seek care immediately if one occurs.",
]


def _age_points(age: float) -> int:
    """RSV severity risk is highest in infants/young children and in
    older adults; scores 0-2."""
    try:
        age = float(age)
        if age < 2 or age > 65:
            return 2
        if age <= 5 or age >= 60:
            return 1
        return 0
    except (TypeError, ValueError):
        return 0


def _lab_points(parameter: str, value, age, sex) -> int:
    """Scores a lab value 0-2 against the age/sex-specific reference range
    from utils/validation.py (single source of truth):
        within range            -> 0
        above upper limit       -> 1
        above 2 x upper limit   -> 2
    """
    try:
        value = float(value)
        low, high = get_reference_range(parameter, float(age), sex)
        if value > 2 * high:
            return 2
        if value > high:
            return 1
        return 0
    except (TypeError, ValueError, KeyError, ZeroDivisionError):
        return 0


def assess_rsv_risk(patient: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes a rule-based RSV risk level for a patient using Age,
    CRP, ALT, and AST (fields already available on every patient
    record in this app).

    Args:
        patient: dict with keys Age, Gender, CRP, ALT, AST (missing keys
                 default to 0, which contributes no risk points).

    Returns:
        {
            "risk_level": "Low" | "Medium" | "High",
            "recommendation": "Low" | "Precaution" | "Consult Doctor",
            "score": int,           # 0-8
            "max_score": 8,
            "breakdown": {"Age": 0-2, "CRP": 0-2, "ALT": 0-2, "AST": 0-2},
        }
    """
    try:
        age = patient.get("Age", 0) or 0
        crp = patient.get("CRP", 0) or 0
        alt = patient.get("ALT", 0) or 0
        ast = patient.get("AST", 0) or 0

        sex = patient.get("Gender", "Male")
        breakdown = {
            "Age": _age_points(age),
            "CRP": _lab_points("CRP", crp, age, sex),
            "ALT": _lab_points("ALT", alt, age, sex),
            "AST": _lab_points("AST", ast, age, sex),
        }
        score = sum(breakdown.values())

        if score >= 6:
            risk_level = "High"
        elif score >= 3:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        recommendation = RSV_RECOMMENDATIONS.get(risk_level, "Consult Doctor")
        precautions = RSV_PRECAUTIONS if risk_level == "Medium" else []

        return {
            "risk_level": risk_level,
            "recommendation": recommendation,
            "score": score,
            "max_score": 8,
            "breakdown": breakdown,
            "precautions": precautions,
        }
    except Exception as e:
        raise RuntimeError(f"Error assessing RSV risk: {e}")
