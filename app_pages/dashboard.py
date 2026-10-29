"""
pages/dashboard.py
---------------------
The main results Dashboard. Displays the Digital Twin card, prediction
percentages, recommendation, risk gauges, and Plotly charts for either
the current single patient (from Manual Entry / Medical Report Upload)
or the full batch (from CSV Upload).
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from utils.report_generator import generate_pdf_report
from utils.report_store import save_pdf_report, save_batch_summary


RISK_COLORS = {"Low": "#2ecc71", "Medium": "#f39c12", "High": "#e74c3c"}


def _risk_gauge(title: str, predicted_class: str, probability: float):
    """Builds a Plotly gauge chart for a single risk prediction."""
    try:
        color = RISK_COLORS.get(predicted_class, "#3498db")
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=probability * 100,
            number={"suffix": "%"},
            title={"text": f"{title}<br><span style='font-size:0.8em;color:{color}'>{predicted_class} Risk</span>"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 33], "color": "#eafaf1"},
                    {"range": [33, 66], "color": "#fef5e7"},
                    {"range": [66, 100], "color": "#fdedec"},
                ],
            },
        ))
        fig.update_layout(height=280, margin=dict(l=20, r=20, t=60, b=20))
        return fig
    except Exception as e:
        st.error(f"Error building gauge chart: {e}")
        return None


def _render_rsv_risk_card(rsv_risk: dict):
    """Renders the RSV (Respiratory Syncytial Virus) risk screening card."""
    try:
        if not rsv_risk:
            return
        risk_level = rsv_risk.get("risk_level", "Low")
        recommendation = rsv_risk.get("recommendation", "Low")
        score = rsv_risk.get("score", 0)
        max_score = rsv_risk.get("max_score", 8)
        color = RISK_COLORS.get(risk_level, "#3498db")

        st.markdown("#### RSV Risk Screening")
        st.markdown(
            f"""
            <div style="border:2px solid {color}; border-radius:12px; padding:16px; background-color:#fafafa;">
                <p style="margin:0;"><b>RSV Risk Level:</b>
                    <span style="color:{color}; font-weight:bold;">{risk_level}</span>
                </p>
                <p style="margin:6px 0 0 0;"><b>Result:</b>
                    <span style="font-weight:bold;">{recommendation}</span>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ---- Precautions (Medium risk only) ----
        precautions = rsv_risk.get("precautions") or []
        if risk_level == "Medium" and precautions:
            st.markdown("**Precautions to take before vaccination:**")
            for step in precautions:
                st.markdown(f"- {step}")

        st.caption(f"Risk score: {score} / {max_score} (based on Age, CRP, ALT, AST)")
        with st.expander("View RSV score breakdown"):
            breakdown = rsv_risk.get("breakdown", {})
            for factor, points in breakdown.items():
                st.write(f"{factor}: {points} / 2 points")
    except Exception as e:
        st.error(f"Error rendering RSV risk card: {e}")


def render_digital_twin_card(twin: dict):
    """Renders the Digital Twin summary card + gauges + charts for one
    patient. Public so other pages (e.g. Medical Report Upload, Manual
    Entry) can render the result inline right after generation, without
    requiring a trip to the Dashboard page."""
    try:
        details = twin["patient_details"]
        allergy = twin["allergy_risk"]
        side_effect = twin["side_effect_risk"]
        overall_risk = twin["overall_risk_level"]
        recommendation = twin["recommendation"]
        rsv_risk = twin.get("rsv_risk")

        # ---- Digital Twin Card ----
        st.markdown("### Digital Twin Profile")
        card_color = RISK_COLORS.get(overall_risk, "#3498db")
        st.markdown(
            f"""
            <div style="border:2px solid {card_color}; border-radius:12px; padding:20px; background-color:#fafafa;">
                <h4 style="margin-top:0;">{details.get('PatientName', 'Unknown')}</h4>
                <p><b>Age:</b> {details.get('Age')} &nbsp;|&nbsp; <b>Gender:</b> {details.get('Gender')}</p>
                <p><b>ALT:</b> {details.get('ALT')} U/L &nbsp;|&nbsp; <b>AST:</b> {details.get('AST')} U/L</p>
                <p><b>Creatinine:</b> {details.get('Creatinine')} mg/dL &nbsp;|&nbsp; <b>CRP:</b> {details.get('CRP')} mg/L</p>
                <p><b>Overall Risk Level:</b> <span style="color:{card_color}; font-weight:bold;">{overall_risk}</span></p>
                <p><b>Recommendation:</b> <span style="font-weight:bold;">{recommendation}</span></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("&nbsp;")

        # ---- Download Report button ----
        patient_name = details.get("PatientName") or "patient"
        safe_name = "".join(c if c.isalnum() else "_" for c in str(patient_name))
        try:
            pdf_bytes = generate_pdf_report(twin)
            save_pdf_report(twin, pdf_bytes)  # keep a copy in reports/
            st.download_button(
                label="Download Report (PDF)",
                data=pdf_bytes,
                file_name=f"{safe_name}_digital_twin_report.pdf",
                mime="application/pdf",
                key=f"download_report_{safe_name}",
            )
        except Exception as e:
            st.error(f"Error generating downloadable report: {e}")

        st.markdown("&nbsp;")

        # ---- RSV Risk Screening card ----
        _render_rsv_risk_card(rsv_risk)

        st.markdown("&nbsp;")

        # ---- Metric cards ----
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Allergy Risk", allergy["predicted_class"])
        m2.metric("Side Effect Risk", side_effect["predicted_class"])
        m3.metric("Overall Risk", overall_risk)
        if rsv_risk:
            m4.metric("RSV Risk", rsv_risk.get("risk_level", "N/A"))

        # ---- Progress bars for probabilities ----
        st.markdown("#### Prediction Probabilities")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Allergy Risk Probabilities**")
            for cls, prob in allergy["probabilities"].items():
                st.write(f"{cls}: {prob * 100:.1f}%")
                st.progress(min(max(prob, 0.0), 1.0))
        with col2:
            st.markdown("**Side Effect Risk Probabilities**")
            for cls, prob in side_effect["probabilities"].items():
                st.write(f"{cls}: {prob * 100:.1f}%")
                st.progress(min(max(prob, 0.0), 1.0))

        # ---- Risk gauges ----
        st.markdown("#### Risk Gauges")
        g1, g2 = st.columns(2)
        with g1:
            allergy_top_prob = allergy["probabilities"].get(allergy["predicted_class"], 0)
            fig1 = _risk_gauge("Allergy Risk", allergy["predicted_class"], allergy_top_prob)
            if fig1:
                st.plotly_chart(fig1, use_container_width=True)
        with g2:
            se_top_prob = side_effect["probabilities"].get(side_effect["predicted_class"], 0)
            fig2 = _risk_gauge("Side Effect Risk", side_effect["predicted_class"], se_top_prob)
            if fig2:
                st.plotly_chart(fig2, use_container_width=True)

        # ---- Bar chart comparing probability distributions ----
        st.markdown("#### Risk Probability Comparison")
        chart_df = pd.DataFrame({
            "Risk Level": list(allergy["probabilities"].keys()) + list(side_effect["probabilities"].keys()),
            "Probability": list(allergy["probabilities"].values()) + list(side_effect["probabilities"].values()),
            "Prediction Type": (["Allergy Risk"] * len(allergy["probabilities"])) +
                                (["Side Effect Risk"] * len(side_effect["probabilities"])),
        })
        fig3 = px.bar(
            chart_df, x="Risk Level", y="Probability", color="Prediction Type",
            barmode="group", color_discrete_sequence=["#3498db", "#9b59b6"],
        )
        fig3.update_layout(yaxis_tickformat=".0%")
        st.plotly_chart(fig3, use_container_width=True)

    except Exception as e:
        st.error(f"Error rendering Digital Twin card: {e}")


def render_batch_summary(twins: list, key_prefix: str = "batch"):
    """Renders the batch summary table, aggregate charts, and a
    per-patient drill-down for a list of Digital Twin results. Public
    so other pages (e.g. CSV Upload) can render this inline right after
    processing, without requiring a trip to the Dashboard page.

    key_prefix keeps widget keys unique when this is called from more
    than one page (only one page runs per script execution, but a
    distinct prefix avoids any ambiguity)."""
    try:
        st.markdown(f"### Batch Summary — {len(twins)} Patients")

        summary_rows = []
        for twin in twins:
            rsv = twin.get("rsv_risk") or {}
            summary_rows.append({
                "PatientName": twin["patient_details"].get("PatientName"),
                "Age": twin["patient_details"].get("Age"),
                "Gender": twin["patient_details"].get("Gender"),
                "Allergy_Risk": twin["allergy_risk"]["predicted_class"],
                "SideEffect_Risk": twin["side_effect_risk"]["predicted_class"],
                "Overall_Risk": twin["overall_risk_level"],
                "Recommendation": twin["recommendation"],
                "RSV_Risk": rsv.get("risk_level", "N/A"),
                "RSV_Result": rsv.get("recommendation", "N/A"),
            })
        summary_df = pd.DataFrame(summary_rows)
        st.dataframe(summary_df, use_container_width=True)

        _summary_csv = summary_df.to_csv(index=False).encode("utf-8")
        save_batch_summary(_summary_csv)  # keep a copy in reports/
        st.download_button(
            label="Download Batch Summary (CSV)",
            data=_summary_csv,
            file_name="digital_twin_batch_summary.csv",
            mime="text/csv",
            key=f"{key_prefix}_download_batch_summary_csv",
        )

        # ---- Aggregate charts ----
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### Overall Risk Distribution")
            fig = px.pie(
                summary_df, names="Overall_Risk", color="Overall_Risk",
                color_discrete_map=RISK_COLORS,
            )
            st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_risk_pie")
        with c2:
            st.markdown("##### Recommendation Breakdown")
            fig2 = px.histogram(summary_df, x="Recommendation", color="Overall_Risk",
                                 color_discrete_map=RISK_COLORS)
            st.plotly_chart(fig2, use_container_width=True, key=f"{key_prefix}_rec_hist")

        st.markdown("##### Drill Down: View a Specific Patient")
        selected_name = st.selectbox(
            "Select Patient", summary_df["PatientName"].tolist(),
            key=f"{key_prefix}_select_patient",
        )
        selected_twin = next(
            (t for t in twins if t["patient_details"].get("PatientName") == selected_name), None
        )
        if selected_twin:
            st.markdown("---")
            render_digital_twin_card(selected_twin)

    except Exception as e:
        st.error(f"Error rendering batch summary: {e}")


def render_dashboard():
    """Renders the full Dashboard page."""
    try:
        st.title("Digital Twin Dashboard")

        has_single = "current_twin" in st.session_state
        has_batch = "batch_twins" in st.session_state and st.session_state["batch_twins"]

        if not has_single and not has_batch:
            st.warning(
                "No Digital Twin data available yet. Please generate one via "
                "**CSV Upload**, **Manual Entry**, or **Medical Report Upload** first."
            )
            return

        view_mode = st.radio(
            "Select View",
            ["Current Patient"] + (["Batch (CSV) Overview"] if has_batch else []),
            horizontal=True,
        )

        if view_mode == "Current Patient":
            if has_single:
                render_digital_twin_card(st.session_state["current_twin"])
            else:
                st.info("No single-patient Digital Twin found yet.")

        elif view_mode == "Batch (CSV) Overview":
            render_batch_summary(st.session_state["batch_twins"], key_prefix="dashboard_batch")

    except Exception as e:
        st.error(f"Error rendering Dashboard page: {e}")