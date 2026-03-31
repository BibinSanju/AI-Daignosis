from __future__ import annotations

from html import escape

import streamlit as st

from utils.hospital_db import init_database, list_patient_reports, load_report_pdf
from utils.portal import apply_shared_styles, init_session_state, logout_user, require_role


st.set_page_config(page_title="Receptionist Dashboard", layout="wide")
init_database()
init_session_state()
apply_shared_styles()
receptionist_user = require_role("receptionist")


header_left, header_right = st.columns([5, 1])
with header_left:
    st.markdown(
        f"""
        <div class="portal-card">
            <div class="portal-title">Receptionist Desk</div>
            <p class="portal-subtitle">
                Logged in as {receptionist_user['full_name']}. View the live queue in priority order, open each patient record, and download the generated PDF for handover.
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
    st.info("No patient reports are available yet.")

for report in reports:
    pdf_bytes = load_report_pdf(report)
    status_label = report["status"].title()
    priority_label = str(report["severity_level"]).title()
    expander_title = (
        f"Token #{report['token_number']} | {report['patient_name']} | "
        f"{priority_label} | {status_label}"
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
                    <strong>Priority</strong><br/>{priority_label} ({report['severity_score']})
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
            st.markdown(
                f"""
                <div class="metric-card">
                    <strong>Status</strong><br/>{status_label}
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### Patient Details")
        st.markdown(
            f"""
            <div class="portal-card" style="margin-top: 0.5rem;">
                <strong>Patient Name:</strong> {escape(str(report["patient_name"]))}<br/>
                <strong>Age:</strong> {escape(str(report["age"] if report["age"] is not None else "Not provided"))}<br/>
                <strong>Gender:</strong> {escape(str(report["gender"] or "Not provided"))}<br/>
                <strong>Phone / ID:</strong> {escape(str(report["phone"] or "Not provided"))}<br/>
                <strong>Queue Status:</strong> {escape(status_label)}<br/>
                <strong>Recommended Action:</strong> {escape(str(report["recommended_action"] or "Not provided"))}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.download_button(
            "Download Patient PDF",
            data=pdf_bytes,
            file_name=f"token-{report['token_number']:04d}.pdf",
            mime="application/pdf",
            width="stretch",
            key=f"receptionist_download_pdf_{report['id']}",
            disabled=not pdf_bytes,
        )
