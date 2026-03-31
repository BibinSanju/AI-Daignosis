from __future__ import annotations

from hashlib import md5
from io import BytesIO
from pathlib import Path

import streamlit as st

from utils.hospital_db import (
    authenticate_user,
    default_staff_credentials,
    init_database,
    list_patient_reports,
    mark_report_reviewed,
    save_patient_report,
)
from utils.patient_workflow import analyze_patient_audio
from utils.portal import (
    apply_shared_styles,
    clear_patient_submission_state,
    init_session_state,
    login_user,
    switch_for_logged_in_user,
)

try:
    from audiorecorder import audiorecorder
except ImportError:
    audiorecorder = None


APP_DIR = Path(__file__).resolve().parent
AUDIO_PATH = APP_DIR / "audio.wav"


def should_show_patient_queue_sidebar() -> bool:
    return (
        st.session_state.get("patient_portal_mode") == "Patient Intake"
        and bool(st.session_state.get("show_patient_queue_sidebar", False))
    )


st.set_page_config(
    page_title="Hospital Intake Portal",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_database()
init_session_state()
apply_shared_styles(hide_sidebar=not should_show_patient_queue_sidebar())
switch_for_logged_in_user()


def audio_segment_to_wav(audio_segment) -> bytes:
    buffer = BytesIO()
    audio_segment.export(buffer, format="wav")
    return buffer.getvalue()


def cache_patient_audio(audio_segment) -> None:
    audio_bytes = audio_segment_to_wav(audio_segment)
    digest = md5(audio_bytes).hexdigest()
    if st.session_state.patient_audio_digest == digest:
        return

    st.session_state.patient_audio_bytes = audio_bytes
    st.session_state.patient_audio_digest = digest
    st.session_state.patient_submission_result = None
    st.session_state.patient_processing_error = None


def submit_patient_case(
    patient_name: str,
    age: int | None,
    gender: str,
    phone: str,
) -> None:
    audio_bytes = st.session_state.get("patient_audio_bytes")
    if not audio_bytes:
        st.session_state.patient_processing_error = "Please record the patient's symptom note first."
        return

    AUDIO_PATH.write_bytes(audio_bytes)

    try:
        analysis = analyze_patient_audio(AUDIO_PATH)
        saved_report = save_patient_report(
            patient_name=patient_name,
            age=age,
            gender=gender,
            phone=phone,
            source_transcript=str(analysis.get("source_transcript", "")),
            translated_text=str(analysis.get("translated_text", "")),
            diagnosis=analysis.get("diagnosis", {}),
            matched_dataset_symptoms=analysis.get("matched_dataset_symptoms", []),
            symptom_matches=analysis.get("symptom_matches", []),
        )
    except Exception as exc:
        st.session_state.patient_submission_result = None
        st.session_state.patient_processing_error = str(exc)
        return

    st.session_state.patient_submission_result = saved_report
    st.session_state.patient_processing_error = None
    st.session_state.patient_audio_bytes = None
    st.session_state.patient_audio_digest = None
    st.session_state.patient_recorder_version = st.session_state.get("patient_recorder_version", 0) + 1
    if AUDIO_PATH.exists():
        AUDIO_PATH.unlink()


def render_patient_queue_sidebar() -> None:
    with st.sidebar:
        if st.button("Hide Queue Sidebar", key="hide_patient_queue_sidebar", width="stretch"):
            st.session_state.show_patient_queue_sidebar = False
            st.rerun()

        st.markdown("## Calling Queue")
        st.caption("Tokens are listed in calling order so staff can call patients easily.")

        queued_reports = list_patient_reports(include_reviewed=False)
        if not queued_reports:
            st.info("No waiting tokens right now.")
            return

        for order_index, report in enumerate(queued_reports, start=1):
            with st.container(border=True):
                st.markdown(f"**Order {order_index}**")
                st.write(f"Token: #{report['token_number']}")
                st.write(f"Patient: {report['patient_name']}")
            if st.button(
                f"Mark Token #{report['token_number']} as Read",
                key=f"sidebar_mark_read_{report['id']}",
                width="stretch",
            ):
                mark_report_reviewed(report["id"], doctor_user_id=None)
                st.success(f"Token #{report['token_number']} marked as read.")
                st.rerun()


def render_patient_queue_board(queued_reports: list[dict]) -> None:
    if not queued_reports:
        st.info("No waiting tokens right now.")
        return

    next_report = queued_reports[0]
    st.markdown(
        f"""
        <div class="portal-card" style="margin-top: 1rem; background: linear-gradient(135deg, rgba(24, 126, 84, 0.10), rgba(255,255,255,0.96));">
            <div style="font-size: 0.88rem; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: #4f697d;">Now Calling</div>
            <div style="font-size: 2rem; font-weight: 800; color: #173047; margin-top: 0.35rem;">Token #{next_report['token_number']}</div>
            <div style="font-size: 1.1rem; color: #173047; margin-top: 0.2rem;">{next_report['patient_name']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Queue Order")
    for order_index, report in enumerate(queued_reports, start=1):
        order_columns = st.columns([3.2, 1.1], gap="small", vertical_alignment="center")
        with order_columns[0]:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div style="font-size: 0.8rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; color: #4f697d;">
                        Order {order_index}
                    </div>
                    <div style="font-size: 1.05rem; font-weight: 800; color: #173047; margin-top: 0.3rem;">
                        Token #{report['token_number']}
                    </div>
                    <div style="font-size: 1rem; color: #173047; margin-top: 0.25rem;">
                        {report['patient_name']}
                    </div>
                    <div style="font-size: 0.9rem; color: #4f697d; margin-top: 0.3rem;">
                        Submitted {report['created_at']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with order_columns[1]:
            if st.button(
                "Mark Read",
                key=f"board_mark_read_{report['id']}",
                width="stretch",
            ):
                mark_report_reviewed(report["id"], doctor_user_id=None)
                st.success(f"Token #{report['token_number']} marked as read.")
                st.rerun()


def render_patient_queue_controls() -> None:
    queue_is_open = bool(st.session_state.get("show_patient_queue_board", True))
    sidebar_is_open = bool(st.session_state.get("show_patient_queue_sidebar", False))
    st.markdown(
        f"""
        <div class="metric-card" style="margin-bottom: 1rem;">
            <div style="font-size: 0.8rem; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; color: #4f697d;">
                Queue Controls
            </div>
            <div style="font-size: 1rem; font-weight: 800; color: #173047; margin-top: 0.3rem;">
                Display {"Visible" if queue_is_open else "Hidden"}
            </div>
            <div style="font-size: 0.9rem; color: #4f697d; margin-top: 0.3rem;">
                Sidebar {"Open" if sidebar_is_open else "Closed"}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    button_columns = st.columns(2, gap="small")
    with button_columns[0]:
        if st.button(
            "Hide Queue" if queue_is_open else "Show Queue",
            key="toggle_patient_queue_board",
            width="stretch",
        ):
            st.session_state.show_patient_queue_board = not queue_is_open
            st.rerun()
    with button_columns[1]:
        if st.button(
            "Hide Sidebar" if sidebar_is_open else "Show Sidebar",
            key="toggle_patient_queue_sidebar",
            width="stretch",
        ):
            st.session_state.show_patient_queue_sidebar = not sidebar_is_open
            st.rerun()


def render_patient_portal() -> None:
    queued_reports = list_patient_reports(include_reviewed=False)
    queue_board_visible = bool(st.session_state.get("show_patient_queue_board", True))
    render_patient_queue_sidebar()
    if queue_board_visible:
        intake_column, queue_column = st.columns([1.55, 0.95], gap="large", vertical_alignment="top")
    else:
        intake_column, queue_column = st.columns([1.9, 0.5], gap="large", vertical_alignment="top")

    with intake_column:
        st.markdown(
            """
            <div class="portal-card">
                <div class="portal-title">Patient Intake</div>
                <p class="portal-subtitle">
                    Record the patient symptom note once. The system will translate, diagnose,
                    generate a PDF report, assign a token number, and push the case into the doctor queue.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=False):
            patient_name = st.text_input("Patient Name")
            detail_columns = st.columns(3)
            with detail_columns[0]:
                age_value = st.number_input("Age", min_value=0, max_value=120, value=0, step=1)
            with detail_columns[1]:
                gender = st.selectbox("Gender", ["Not provided", "Female", "Male", "Other"])
            with detail_columns[2]:
                phone = st.text_input("Phone / ID")

        audio_bytes = st.session_state.get("patient_audio_bytes")
        if audiorecorder is None:
            st.error("Install `streamlit-audiorecorder` to record voice notes.")
        else:
            st.markdown("#### Record Symptom Note")
            audio_segment = audiorecorder(
                start_prompt="Start Recording",
                stop_prompt="Stop Recording",
                pause_prompt="",
                show_visualizer=False,
                custom_style={
                    "width": "100%",
                    "padding": "0.75rem 1rem",
                    "borderRadius": "999px",
                    "fontFamily": "Manrope, sans-serif",
                    "fontSize": "1rem",
                    "fontWeight": "800",
                    "textAlign": "center",
                },
                start_style={
                    "background": "linear-gradient(135deg, #ff6156 0%, #e53935 100%)",
                    "color": "white",
                },
                stop_style={
                    "background": "linear-gradient(135deg, #23c06e 0%, #169454 100%)",
                    "color": "white",
                },
                key=f"patient_intake_recorder_{st.session_state.patient_recorder_version}",
            )
            if len(audio_segment) > 0:
                cache_patient_audio(audio_segment)
                audio_bytes = st.session_state.get("patient_audio_bytes")

        if audio_bytes:
            st.audio(audio_bytes, format="audio/wav")
            st.caption("Voice note ready for submission.")

        if st.session_state.get("patient_processing_error"):
            st.error(st.session_state["patient_processing_error"])

        submit_disabled = not patient_name.strip() or not audio_bytes
        action_columns = st.columns(2)
        with action_columns[0]:
            if st.button("Submit to Doctor Queue", width="stretch", disabled=submit_disabled):
                with st.spinner("Generating patient report, token, and doctor queue entry..."):
                    normalized_age = int(age_value) if int(age_value) > 0 else None
                    normalized_gender = "" if gender == "Not provided" else gender
                    submit_patient_case(
                        patient_name=patient_name.strip(),
                        age=normalized_age,
                        gender=normalized_gender,
                        phone=phone.strip(),
                    )
                st.rerun()
        with action_columns[1]:
            if st.button("Clear Intake", width="stretch"):
                clear_patient_submission_state()
                if AUDIO_PATH.exists():
                    AUDIO_PATH.unlink()
                st.rerun()

        report = st.session_state.get("patient_submission_result")
        if report:
            st.success(
                f"Report submitted successfully. Token #{report['token_number']} is now in the doctor queue."
            )
            st.markdown(
                f"""
                <div class="portal-card" style="margin-top: 1rem;">
                    <div class="metric-card">
                        <strong>Patient:</strong> {report['patient_name']}<br/>
                        <strong>Token Number:</strong> {report['token_number']}<br/>
                        <strong>Status:</strong> Sent to doctor dashboard
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with queue_column:
        render_patient_queue_controls()
        if queue_board_visible:
            render_patient_queue_board(queued_reports)
        else:
            st.markdown(
                """
                <div class="portal-card" style="margin-top: 1rem;">
                    <div style="font-size: 1.1rem; font-weight: 800; color: #173047;">Token queue hidden</div>
                    <div style="font-size: 0.95rem; color: #4f697d; margin-top: 0.35rem;">
                        Use Show Queue to display the calling order on the right side again.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_staff_login() -> None:
    credentials = default_staff_credentials()
    left_spacer, center_column, right_spacer = st.columns([1.1, 1.4, 1.1], gap="large")

    with center_column:
        st.markdown(
            """
            <div class="portal-card">
                <div class="portal-title">Staff Login</div>
                <p class="portal-subtitle">
                    Doctors, receptionists, and admins are authenticated from the local hospital database before they can access their dashboards.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("staff_login_form", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", width="stretch")

        if submitted:
            user = authenticate_user(username=username, password=password)
            if user is None:
                st.session_state.staff_login_error = "Invalid credentials or inactive staff account."
            else:
                login_user(user)
                if user["role"] == "admin":
                    st.switch_page("pages/admin_portal.py")
                elif user["role"] == "receptionist":
                    st.switch_page("pages/receptionist_dashboard.py")
                else:
                    st.switch_page("pages/doctor_dashboard.py")

        if st.session_state.get("staff_login_error"):
            st.error(st.session_state["staff_login_error"])

        with st.expander("Default Seeded Accounts"):
            st.write(
                f"Admin: `{credentials['admin_username']}` / `{credentials['admin_password']}`"
            )
            st.write(
                f"Doctor: `{credentials['doctor_username']}` / `{credentials['doctor_password']}`"
            )
            st.write(
                f"Receptionist: `{credentials['receptionist_username']}` / `{credentials['receptionist_password']}`"
            )


mode_left, mode_center, mode_right = st.columns([1.1, 1.4, 1.1], gap="large")
with mode_center:
    mode = st.radio(
        "Portal Access",
        ["Patient Intake", "Staff Login"],
        horizontal=True,
        key="patient_portal_mode",
    )

if mode == "Patient Intake":
    render_patient_portal()
else:
    render_staff_login()
