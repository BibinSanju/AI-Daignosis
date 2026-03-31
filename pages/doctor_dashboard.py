from __future__ import annotations

from html import escape

import streamlit as st

from utils.hospital_db import (
    init_database,
    list_patient_reports,
    load_report_pdf,
    mark_report_reviewed,
)
from utils.portal import apply_shared_styles, init_session_state, logout_user, require_role


st.set_page_config(page_title="Doctor Dashboard", layout="wide")
init_database()
init_session_state()
apply_shared_styles()
doctor_user = require_role("doctor")


header_left, header_right = st.columns([5, 1])
with header_left:
    st.markdown(
        f"""
        <div class="portal-card">
            <div class="portal-title">Doctor Dashboard</div>
            <p class="portal-subtitle">
                Logged in as {doctor_user['full_name']}. Patient PDFs are ordered by urgency first, then higher severity score, then token number.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with header_right:
    if st.button("Logout", width="stretch"):
        logout_user()
        st.switch_page("app.py")


include_reviewed = st.toggle("Show reviewed reports", value=False)
reports = list_patient_reports(include_reviewed=include_reviewed)

queued_reports = [report for report in reports if report["status"] == "queued"]
high_count = sum(1 for report in queued_reports if report["severity_level"] == "high")
medium_count = sum(1 for report in queued_reports if report["severity_level"] == "medium")
low_count = sum(1 for report in queued_reports if report["severity_level"] == "low")

metric_columns = st.columns(4)
with metric_columns[0]:
    st.metric("Queued", len(queued_reports))
with metric_columns[1]:
    st.metric("High Priority", high_count)
with metric_columns[2]:
    st.metric("Medium Priority", medium_count)
with metric_columns[3]:
    st.metric("Low Priority", low_count)

if not reports:
    st.info("No patient reports are in the queue yet.")

for report in reports:
    payload = report.get("payload", {})
    diagnosis = payload.get("diagnosis", {}) if isinstance(payload, dict) else {}
    pdf_bytes = load_report_pdf(report)
    top_disease = report["top_disease"] or "Unavailable"
    status_label = report["status"].title()
    priority_label = str(report["severity_level"]).title()
    expander_title = (
        f"Token #{report['token_number']} | {report['patient_name']} | "
        f"{priority_label} | {top_disease} | {status_label}"
    )

    with st.expander(expander_title, expanded=False):
        summary_columns = st.columns(4)
        with summary_columns[0]:
            st.markdown(
                f"""
                <div class="metric-card">
                    <strong>Token</strong><br/>{report['token_number']}
                </div>
                """,
                unsafe_allow_html=True,
            )
        with summary_columns[1]:
            st.markdown(
                f"""
                <div class="metric-card">
                    <strong>Severity</strong><br/>{priority_label} ({report['severity_score']})
                </div>
                """,
                unsafe_allow_html=True,
            )
        with summary_columns[2]:
            st.markdown(
                f"""
                <div class="metric-card">
                    <strong>Created</strong><br/>{report['created_at']}
                </div>
                """,
                unsafe_allow_html=True,
            )
        with summary_columns[3]:
            reviewer = report["reviewed_by_name"] or (
                "Front Desk" if report["status"] == "reviewed" else "Pending"
            )
            st.markdown(
                f"""
                <div class="metric-card">
                    <strong>Reviewed By</strong><br/>{reviewer}
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### Patient Snapshot")
        st.markdown(
            f"""
            <div class="portal-card" style="margin-top: 0.5rem;">
                <strong>Patient Name:</strong> {escape(str(report["patient_name"]))}<br/>
                <strong>Age:</strong> {escape(str(report["age"] if report["age"] is not None else "Not provided"))}<br/>
                <strong>Gender:</strong> {escape(str(report["gender"] or "Not provided"))}<br/>
                <strong>Phone / ID:</strong> {escape(str(report["phone"] or "Not provided"))}<br/>
                <strong>Top Disease:</strong> {escape(str(top_disease))}<br/>
                <strong>Recommended Action:</strong> {escape(str(report["recommended_action"] or "Not provided"))}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Translation and Matching")
        matched_dataset_symptoms = payload.get("matched_dataset_symptoms", [])
        st.markdown(
            f"""
            <div class="portal-card" style="margin-top: 0.5rem;">
                <strong>Tamil Transcript:</strong><br/>{escape(str(payload.get("source_transcript", "") or "Not available"))}<br/><br/>
                <strong>English Translation:</strong><br/>{escape(str(payload.get("translated_text", "") or "Not available"))}<br/><br/>
                <strong>Matched Dataset Symptoms:</strong><br/>{escape(", ".join(matched_dataset_symptoms) if matched_dataset_symptoms else "None")}
            </div>
            """,
            unsafe_allow_html=True,
        )

        possible_diseases = diagnosis.get("possible_diseases", [])
        if possible_diseases:
            st.markdown("### Predicted Diseases")
            st.dataframe(
                [
                    {
                        "Disease": disease.get("name", ""),
                        "Confidence %": round(float(disease.get("confidence", 0.0) or 0.0) * 100, 1),
                        "Matched Symptoms": ", ".join(disease.get("matched_symptoms", [])),
                        "Reason": disease.get("reason", ""),
                    }
                    for disease in possible_diseases
                ],
                width="stretch",
                hide_index=True,
            )

        action_columns = st.columns(2)
        with action_columns[0]:
            st.download_button(
                "Download Patient PDF",
                data=pdf_bytes,
                file_name=f"token-{report['token_number']:04d}.pdf",
                mime="application/pdf",
                width="stretch",
                key=f"download_pdf_{report['id']}",
                disabled=not pdf_bytes,
            )
        with action_columns[1]:
            if report["status"] == "queued":
                if st.button(
                    "Mark Reviewed",
                    width="stretch",
                    key=f"review_report_{report['id']}",
                ):
                    mark_report_reviewed(report["id"], int(doctor_user["id"]))
                    st.success(f"Token #{report['token_number']} marked as reviewed.")
                    st.rerun()
            else:
                st.caption(f"Reviewed at {report['reviewed_at'] or 'Unknown time'}")
