"""
report_store.py
---------------
Keeps a permanent copy of every report the app generates inside the
project's ``reports/`` folder, so earlier reports stay available (and
travel with the project zip) instead of existing only in the browser's
Downloads folder.

- save_pdf_report(twin, pdf_bytes)  -> saves a patient PDF (once per
  unique patient result; re-renders / re-downloads do not duplicate it)
- save_batch_summary(csv_bytes)     -> saves a batch summary CSV (same rule)
- save_uploaded_file(name, data)    -> adds an older report the user
  uploads manually (PDF / CSV)
- list_reports() / delete_report()  -> used by the Saved Reports page

All functions fail soft (return None / False) if the folder is read-only,
so a storage problem never breaks the analysis itself.
"""

import hashlib
import os
import re
from datetime import datetime

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
ALLOWED_EXTENSIONS = (".pdf", ".csv")


def _safe(text) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(text or "patient")).strip("_") or "patient"


def _ensure_dir() -> bool:
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        return True
    except OSError:
        return False


def _find_existing(content_id: str):
    try:
        for fname in os.listdir(REPORTS_DIR):
            if fname.endswith(f"_{content_id}.pdf") or fname.endswith(f"_{content_id}.csv"):
                return os.path.join(REPORTS_DIR, fname)
    except OSError:
        pass
    return None


def save_pdf_report(twin: dict, pdf_bytes: bytes):
    """Saves the patient's PDF report; returns the file path (or None)."""
    try:
        if not _ensure_dir():
            return None
        d = twin.get("patient_details", {})
        fingerprint = "|".join(str(d.get(k)) for k in
                               ("PatientName", "Age", "Gender", "ALT", "AST", "Creatinine", "CRP",
                                "PEG_Allergy", "ImmuneScore", "GeneticRisk", "Month"))
        fingerprint += f"|{twin.get('overall_risk_level')}|{twin.get('recommendation')}"
        content_id = hashlib.sha1(fingerprint.encode()).hexdigest()[:8]
        existing = _find_existing(content_id)
        if existing:
            return existing
        risk = _safe(twin.get("overall_risk_level", "NA"))
        fname = f"{_safe(d.get('PatientName'))}_{risk}_{datetime.now():%Y%m%d_%H%M%S}_{content_id}.pdf"
        path = os.path.join(REPORTS_DIR, fname)
        with open(path, "wb") as f:
            f.write(pdf_bytes)
        return path
    except Exception:
        return None


def save_batch_summary(csv_bytes: bytes):
    """Saves a batch summary CSV; returns the file path (or None)."""
    try:
        if not _ensure_dir():
            return None
        content_id = hashlib.sha1(csv_bytes).hexdigest()[:8]
        existing = _find_existing(content_id)
        if existing:
            return existing
        path = os.path.join(REPORTS_DIR, f"batch_summary_{datetime.now():%Y%m%d_%H%M%S}_{content_id}.csv")
        with open(path, "wb") as f:
            f.write(csv_bytes)
        return path
    except Exception:
        return None


def save_uploaded_file(name: str, data: bytes) -> bool:
    """Adds an older report the user uploads manually. Keeps the original
    name (path parts stripped); never overwrites - adds _1, _2... instead."""
    try:
        if not _ensure_dir():
            return False
        base = os.path.basename(str(name)).replace("\\", "_")
        stem, ext = os.path.splitext(base)
        if ext.lower() not in ALLOWED_EXTENSIONS:
            return False
        stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", stem) or "report"
        path, n = os.path.join(REPORTS_DIR, stem + ext.lower()), 1
        while os.path.exists(path):
            path = os.path.join(REPORTS_DIR, f"{stem}_{n}{ext.lower()}")
            n += 1
        with open(path, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False


def list_reports():
    """Returns saved reports, newest first, as dicts."""
    items = []
    try:
        for fname in os.listdir(REPORTS_DIR):
            if fname.lower().endswith(ALLOWED_EXTENSIONS):
                p = os.path.join(REPORTS_DIR, fname)
                st_ = os.stat(p)
                items.append({"name": fname, "path": p, "size_kb": round(st_.st_size / 1024, 1),
                              "modified": datetime.fromtimestamp(st_.st_mtime),
                              "type": "PDF" if fname.lower().endswith(".pdf") else "CSV"})
    except OSError:
        pass
    return sorted(items, key=lambda x: x["modified"], reverse=True)


def delete_report(name: str) -> bool:
    try:
        p = os.path.join(REPORTS_DIR, os.path.basename(name))
        if os.path.isfile(p) and p.lower().endswith(ALLOWED_EXTENSIONS):
            os.remove(p)
            return True
    except OSError:
        pass
    return False
