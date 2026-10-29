"""
pages/csv_upload.py
----------------------
Lets the user upload a CSV file of patient records, runs the Digital
Twin ML pipeline (allergy + side-effect risk prediction) on every row,
and stores the results in st.session_state so the Dashboard page can
display them.

Expected CSV columns (case-sensitive):
    PatientName, Age, Gender, ALT, AST, Creatinine, CRP,
    PEG_Allergy, ImmuneScore, GeneticRisk
(Missing optional columns are defaulted sensibly.)
"""

import streamlit as st
import pandas as pd
from utils.digital_twin import create_digital_twin
from utils.validation import validate_patient_values, format_issue
from app_pages.dashboard import render_batch_summary


REQUIRED_COLUMNS = ["Age", "Gender", "ALT", "AST", "Creatinine", "CRP"]


def render_csv_upload():
    """Renders the CSV Upload page."""
    try:
        st.title("Upload Patient CSV")
        st.info(
            "Upload a CSV file containing one or more patient records. "
            "Required columns: " + ", ".join(REQUIRED_COLUMNS) +
            ". Optional columns: PatientName, PEG_Allergy, ImmuneScore, GeneticRisk."
        )

        uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

        if uploaded_file is not None:
            try:
                # Detect a NEW upload (different file than last time) and
                # clear this page's previous batch result, so switching to
                # a different CSV doesn't keep showing the old file's
                # summary until the button is clicked again.
                current_file_id = getattr(uploaded_file, "file_id", None) or (
                    f"{uploaded_file.name}:{uploaded_file.size}"
                )
                if st.session_state.get("csv_upload_file_id") != current_file_id:
                    st.session_state["csv_upload_file_id"] = current_file_id
                    st.session_state["csv_upload_batch_twins"] = None

                df = pd.read_csv(uploaded_file)
                st.success(f"File loaded successfully with {len(df)} rows.")
                st.dataframe(df.head(20), use_container_width=True)

                missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
                if missing_cols:
                    st.error(f"Missing required columns: {missing_cols}")
                    return

                if st.button("Run Digital Twin Analysis on All Rows", type="primary"):
                    with st.spinner("Running ML predictions for all patients..."):
                        twins = []
                        errors = 0
                        row_errors = []
                        row_flags = []
                        for idx, row in df.iterrows():
                            try:
                                patient = row.to_dict()
                                patient.setdefault("PatientName", f"Patient_{idx + 1}")
                                result = validate_patient_values(
                                    age=patient.get("Age"), sex=patient.get("Gender"),
                                    alt=patient.get("ALT"), ast=patient.get("AST"),
                                    creatinine=patient.get("Creatinine"), crp=patient.get("CRP"),
                                )
                                if not result["valid"]:
                                    errors += 1
                                    row_errors.append({"CSV row": idx + 2, "Patient": patient.get("PatientName", f"Patient_{idx + 1}"),
                                                       "Issues": "; ".join(format_issue(f) for f in result["failures"])})
                                    continue
                                if result["warnings"]:
                                    row_flags.append({"CSV row": idx + 2, "Patient": patient.get("PatientName", f"Patient_{idx + 1}"),
                                                      "Month": patient.get("Month", ""),
                                                      "Abnormal values": "; ".join(format_issue(w) for w in result["warnings"])})
                                twin = create_digital_twin(patient)
                                twins.append(twin)
                            except Exception as exc:
                                errors += 1
                                row_errors.append({"CSV row": idx + 2, "Patient": row.get("PatientName", f"Patient_{idx + 1}"), "Issues": str(exc)})
                                continue

                        # Shared keys (also read by the Dashboard page)
                        st.session_state["batch_twins"] = twins
                        if twins:
                            st.session_state["current_twin"] = twins[0]
                            st.session_state["current_patient"] = twins[0]["patient_details"]
                        # Separate, page-scoped key so THIS page's own inline
                        # summary below only reflects a batch actually run
                        # during the current visit, and doesn't keep showing
                        # a stale result from a previous visit to this page
                        # before the button is clicked again.
                        st.session_state["csv_upload_batch_twins"] = twins

                    st.success(
                        f"Analysis complete: {len(twins)} patients processed successfully"
                        + (f", {errors} rows need correction or failed." if errors else ".")
                    )
                    if row_errors:
                        st.warning("Some rows were not predicted because values were missing, non-numeric, or outside the technical input limits.")
                        st.dataframe(pd.DataFrame(row_errors), use_container_width=True)
                    if row_flags:
                        st.info(f"{len(row_flags)} rows contain values outside the age/gender reference range. They were still predicted; the abnormal values are listed below.")
                        st.dataframe(pd.DataFrame(row_flags), use_container_width=True)
                    if not twins:
                        st.warning("No patients were processed successfully.")

                # Rendered from session_state (not the local "twins" variable
                # above) so the batch summary persists across reruns caused
                # by interacting with it - e.g. the drill-down patient
                # selector or the "Download Batch Summary" button - instead
                # of disappearing the moment the button's one-shot click
                # value goes back to False.
                if st.session_state.get("csv_upload_batch_twins"):
                    st.markdown("---")
                    render_batch_summary(st.session_state["csv_upload_batch_twins"], key_prefix="csv_upload_batch")

            except Exception as e:
                st.error(f"Error reading/processing CSV file: {e}")
        else:
            # No file currently selected — don't show a stale batch result
            # from an earlier upload.
            st.session_state["csv_upload_file_id"] = None
            st.session_state["csv_upload_batch_twins"] = None

            st.markdown("##### Sample CSV format")
            sample_df = pd.DataFrame([{
                "PatientName": "Rahul Verma", "Age": 45, "Gender": "Male",
                "ALT": 47, "AST": 42, "Creatinine": 1.06, "CRP": 19.5,
                "PEG_Allergy": 1, "ImmuneScore": 55, "GeneticRisk": 65,
            }])
            st.dataframe(sample_df, use_container_width=True)

    except Exception as e:
        st.error(f"Error rendering CSV Upload page: {e}")