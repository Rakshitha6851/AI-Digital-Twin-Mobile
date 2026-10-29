"""
report_generator.py
----------------------
Builds a downloadable PDF report from a Digital Twin profile (as
produced by utils/digital_twin.py). Used by the Dashboard page's
"Download Report" button.

Generates the PDF entirely in memory (io.BytesIO) so it can be handed
straight to Streamlit's st.download_button without touching disk.
"""

import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

RISK_COLORS = {
    "Low": colors.HexColor("#2ecc71"),
    "Medium": colors.HexColor("#f39c12"),
    "High": colors.HexColor("#e74c3c"),
}

# Plain hex strings for use inside reportlab's inline <font color='...'> markup,
# which needs a hex string, not a Color object.
RISK_COLOR_HEX = {
    "Low": "#2ecc71",
    "Medium": "#f39c12",
    "High": "#e74c3c",
}


def _risk_style(base_style, risk_level):
    """Returns a Paragraph style colored according to a risk level."""
    style = ParagraphStyle(
        f"risk_{risk_level}", parent=base_style,
        textColor=RISK_COLORS.get(risk_level, colors.HexColor("#3498db")),
        fontName="Helvetica-Bold",
    )
    return style


def generate_pdf_report(twin: dict) -> bytes:
    """
    Builds a PDF report summarizing a single patient's Digital Twin
    profile: patient details, Allergy/Side-Effect risk predictions,
    overall recommendation, and RSV risk screening.

    Args:
        twin: the dict returned by utils.digital_twin.create_digital_twin()

    Returns:
        The PDF file content as raw bytes.
    """
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=2 * cm, bottomMargin=2 * cm,
            leftMargin=2 * cm, rightMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleCustom", parent=styles["Title"],
            textColor=colors.HexColor("#0b3d59"), fontSize=20,
        )
        heading_style = ParagraphStyle(
            "HeadingCustom", parent=styles["Heading2"],
            textColor=colors.HexColor("#0b3d59"), spaceBefore=14, spaceAfter=6,
        )
        normal = styles["Normal"]
        caption = ParagraphStyle("Caption", parent=styles["Normal"], fontSize=9, textColor=colors.grey)

        details = twin.get("patient_details", {})
        allergy = twin.get("allergy_risk", {})
        side_effect = twin.get("side_effect_risk", {})
        overall_risk = twin.get("overall_risk_level", "N/A")
        recommendation = twin.get("recommendation", "N/A")
        rsv = twin.get("rsv_risk") or {}

        story = []

        # ---- Header ----
        story.append(Paragraph("AI Digital Twin Report", title_style))
        story.append(Paragraph("mRNA Vaccine Risk Simulation Platform", caption))
        story.append(Paragraph(
            f"Generated on {datetime.now().strftime('%d %b %Y, %I:%M %p')}", caption
        ))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", color=colors.HexColor("#0b3d59"), thickness=1.2))
        story.append(Spacer(1, 10))

        # ---- Patient Details ----
        story.append(Paragraph("Patient Details", heading_style))
        patient_table_data = [
            ["Name", str(details.get("PatientName", "N/A"))],
            ["Age", str(details.get("Age", "N/A"))],
            ["Gender", str(details.get("Gender", "N/A"))],
            ["ALT (U/L)", str(details.get("ALT", "N/A"))],
            ["AST (U/L)", str(details.get("AST", "N/A"))],
            ["Creatinine (mg/dL)", str(details.get("Creatinine", "N/A"))],
            ["CRP (mg/L)", str(details.get("CRP", "N/A"))],
        ]
        patient_table = Table(patient_table_data, colWidths=[6 * cm, 9 * cm])
        patient_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef5f8")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6e4ea")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(patient_table)

        # ---- Vaccine Risk Predictions ----
        story.append(Paragraph("mRNA Vaccine Risk Predictions", heading_style))

        pred_table_data = [["Prediction Type", "Risk Level", "Confidence"]]
        allergy_prob = allergy.get("probabilities", {}).get(allergy.get("predicted_class"), 0)
        side_effect_prob = side_effect.get("probabilities", {}).get(side_effect.get("predicted_class"), 0)
        pred_table_data.append([
            "Allergy Risk", allergy.get("predicted_class", "N/A"),
            f"{allergy_prob * 100:.1f}%"
        ])
        pred_table_data.append([
            "Side Effect Risk", side_effect.get("predicted_class", "N/A"),
            f"{side_effect_prob * 100:.1f}%"
        ])
        pred_table = Table(pred_table_data, colWidths=[5 * cm, 5 * cm, 5 * cm])
        pred_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b3d59")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6e4ea")),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(pred_table)
        story.append(Spacer(1, 8))

        story.append(Paragraph(
            f"<b>Overall Risk Level:</b> "
            f"<font color='{RISK_COLOR_HEX.get(overall_risk, '#000000')}'>{overall_risk}</font>",
            normal
        ))
        story.append(Paragraph(f"<b>Recommendation:</b> {recommendation}", normal))

        # ---- RSV Risk Screening ----
        if rsv:
            story.append(Paragraph("RSV Risk Screening", heading_style))
            risk_level = rsv.get("risk_level", "N/A")
            rsv_result = rsv.get("recommendation", "N/A")
            score = rsv.get("score", 0)
            max_score = rsv.get("max_score", 8)

            story.append(Paragraph(
                f"<b>RSV Risk Level:</b> "
                f"<font color='{RISK_COLOR_HEX.get(risk_level, '#000000')}'>{risk_level}</font>",
                normal
            ))
            story.append(Paragraph(f"<b>Result:</b> {rsv_result}", normal))
            story.append(Paragraph(f"Score: {score} / {max_score} (based on Age, CRP, ALT, AST)", caption))

            precautions = rsv.get("precautions") or []
            if precautions:
                story.append(Spacer(1, 6))
                story.append(Paragraph("<b>Precautions to take before vaccination:</b>", normal))
                for step in precautions:
                    story.append(Paragraph(f"&bull; {step}", normal))

        # ---- Footer ----
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", color=colors.HexColor("#d6e4ea"), thickness=0.8))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "This report was generated by the  Digital Twin platform using a "
            "synthetic dataset and demonstration ML models, for educational purposes.",
            caption
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        raise RuntimeError(f"Error generating PDF report: {e}")