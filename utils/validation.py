"""
utils/validation.py
-----------------------
Age/sex-aware clinical reference-range validation for the Manual Entry
workflow. This runs BEFORE the prediction model. If Age/Sex are
missing or invalid, or if any lab value is missing, non-numeric,
physically impossible, or outside its age/sex-appropriate reference
range, prediction is blocked and the specific failing field(s) are
returned so the page can display them.

====================================================================
CONFIGURATION - REFERENCE RANGES  (edit this section only)
====================================================================
This project did not already define age/sex-specific reference
ranges anywhere else in the codebase (only rough, adult-oriented,
thresholds in utils/rsv_risk.py now read from this file).

The ranges below are therefore standard, commonly-published clinical
reference intervals (the kind found in general lab-medicine
references), used as sensible out-of-the-box defaults so this feature
works immediately. They are NOT taken from this project's own
dataset/lab, and real reference ranges legitimately vary between labs,
instruments, and populations.

Before relying on this for anything beyond a learning demo, replace
or verify these numbers against your own trusted clinical source
(e.g. your lab's own reference intervals, or a peer-reviewed
pediatric/adult reference table). No other code in this file needs to
change to update the ranges - only the tables below.
====================================================================
"""


# ---- Age bands are per-test (in years): [low, high) - each age matches exactly one.
# 15 days is stored as 15/365.25 years. Ranges below are the project owner's
# supplied lab reference table (replaces the earlier generic defaults).
_D15 = 15 / 365.25
_BIG = 121  # "and older" (technical max age is 120)

# Each entry: (age_min, age_max, (male_min, male_max), (female_min, female_max))
REFERENCE_TABLE = {
    "ALT": [  # U/L
        (0,    1,    (0, 36), (0, 36)),
        (1,    13,   (0, 28), (0, 28)),
        (13,   19,   (0, 27), (0, 25)),
        (19,   _BIG, (0, 50), (0, 35)),
    ],
    "AST": [  # U/L
        (0,    _D15, (0, 175), (0, 175)),
        (_D15, 1,    (0, 77),  (0, 77)),
        (1,    7,    (0, 53),  (0, 53)),
        (7,    12,   (0, 45),  (0, 45)),
        (12,   19,   (0, 44),  (0, 34)),
        (19,   _BIG, (0, 50),  (0, 35)),
    ],
    "Creatinine": [  # mg/dL
        (0,    _D15, (0.40, 1.00), (0.40, 1.00)),
        (_D15, 2,    (0.20, 0.40), (0.20, 0.40)),
        (2,    4,    (0.30, 0.50), (0.30, 0.50)),
        (4,    12,   (0.40, 0.70), (0.40, 0.70)),
        (12,   16,   (0.50, 0.90), (0.50, 0.90)),
        (16,   _BIG, (0.67, 1.17), (0.51, 0.95)),
    ],
    "CRP": [  # mg/L - all ages, upper limit < 5
        (0,    _BIG, (0, 5), (0, 5)),
    ],
}

UNITS = {"ALT": "U/L", "AST": "U/L", "Creatinine": "mg/dL", "CRP": "mg/L"}

# Physically-impossible bounds (reject obvious data-entry errors
# regardless of age/sex - e.g. a negative lab value can never be real).
ABSOLUTE_BOUNDS = {
    "ALT": (0, 5000),
    "AST": (0, 5000),
    "Creatinine": (0, 50),
    "CRP": (0, 1000),
}
# ====================================================================
# END CONFIGURATION
# ====================================================================


def get_reference_range(parameter: str, age: float, sex: str):
    """Returns the (min, max) reference range for a lab parameter, given
    a patient's age (years) and sex ('Male' or 'Female')."""
    is_male = str(sex).strip().lower().startswith("m")
    for amin, amax, male, female in REFERENCE_TABLE[parameter]:
        if amin <= age < amax:
            return male if is_male else female
    return REFERENCE_TABLE[parameter][-1][2 if is_male else 3]


def validate_patient_values(age, sex, alt, ast, creatinine, crp) -> dict:
    """
    Validates Age, Sex, ALT, AST, Creatinine, and CRP before prediction,
    per the required flow:
        1. Check Age and Sex first.
        2. Use them to select the age/sex-appropriate reference range
           for each lab value.
        3. Check every lab value against its applicable range.

    Returns:
        {
            "valid": bool,
            "failures": [
                {
                    "field": "ALT",
                    "value": 70,
                    "unit": "U/L",
                    "expected_range": (5, 35),
                    "reason": "above reference range",
                },
                ...
            ],
            "warnings": [...same shape, for abnormal-but-valid labs...],
        }

    A field FAILS validation (blocks prediction) only if it is missing,
    non-numeric, or outside the technical limits (see ABSOLUTE_BOUNDS).
    A value outside its age/sex reference range is returned under
    "warnings" instead (abnormal lab) and does NOT block prediction -
    otherwise high/moderate-risk patients could never be analysed.
    """
    failures = []   # invalid input: blocks prediction
    warnings = []   # abnormal but valid lab values: flagged, prediction still runs

    # ---- Step 1: Age and Sex must themselves be valid first, since
    # every lab threshold below depends on them. ----
    # Allowed range: 0 <= Age <= 120 (technical input limit).
    age_val = None
    try:
        age_val = float(age)
        if age_val < 0 or age_val > 120:
            failures.append({
                "field": "Age", "value": age, "unit": "years",
                # expected_range left as None here (rather than (1, 120))
                # so the page doesn't append a duplicate "(expected
                # range: ...)" suffix - the exact required message is
                # already in "reason" below.
                "expected_range": None,
                "reason": "Age must be between 0 and 120.",
            })
            age_val = None
    except (TypeError, ValueError):
        failures.append({
            "field": "Age", "value": age, "unit": "years",
            "expected_range": None,
            "reason": "missing or non-numeric",
        })

    sex_str = str(sex).strip() if sex else ""
    if sex_str.lower() not in ("male", "female"):
        failures.append({
            "field": "Sex", "value": sex, "unit": None,
            "expected_range": None,
            "reason": "must be 'Male' or 'Female'",
        })
        sex_str = ""

    # If Age or Sex is itself invalid, there is no reliable threshold to
    # check labs against - stop here rather than guessing a default.
    if age_val is None or not sex_str:
        return {"valid": False, "failures": failures, "warnings": warnings}

    # ---- Step 2 & 3: Look up age/sex-appropriate thresholds and check
    # every lab value against them. ----
    raw_values = {"ALT": alt, "AST": ast, "Creatinine": creatinine, "CRP": crp}

    for field, raw_value in raw_values.items():
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            failures.append({
                "field": field, "value": raw_value, "unit": UNITS[field],
                "expected_range": None,
                "reason": "missing or non-numeric",
            })
            continue

        abs_low, abs_high = ABSOLUTE_BOUNDS[field]
        if value < abs_low or value > abs_high:
            failures.append({
                "field": field, "value": value, "unit": UNITS[field],
                "expected_range": (abs_low, abs_high),
                "reason": "physically impossible value",
            })
            continue

        low, high = get_reference_range(field, age_val, sex_str)
        if value < low or value > high:
            # Out-of-range is a CLINICAL FINDING (abnormal lab), not bad
            # input - so it is reported as a warning and prediction still
            # runs. Only missing / non-numeric / impossible values block.
            warnings.append({
                "field": field, "value": value, "unit": UNITS[field],
                "expected_range": (low, high),
                "reason": "below reference range" if value < low else "above reference range",
            })

    return {"valid": len(failures) == 0, "failures": failures, "warnings": warnings}


def format_issue(item: dict) -> str:
    """One-line text for a failure/warning dict, e.g.
    'ALT: 76 U/L - above reference range (expected 0-50 U/L)'."""
    unit = f" {item['unit']}" if item.get("unit") else ""
    value = item.get("value")
    value_str = "missing" if value in (None, "") else f"{value}{unit}"
    text = f"{item['field']}: {value_str} - {item['reason']}"
    expected = item.get("expected_range")
    if expected:
        text += f" (expected {expected[0]}-{expected[1]}{unit})"
    return text
