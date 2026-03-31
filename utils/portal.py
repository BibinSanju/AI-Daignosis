from __future__ import annotations

from typing import Any

import streamlit as st

from .hospital_db import get_user_by_id


def init_session_state() -> None:
    defaults: dict[str, Any] = {
        "authenticated_user": None,
        "patient_audio_bytes": None,
        "patient_audio_digest": None,
        "patient_submission_result": None,
        "patient_processing_error": None,
        "patient_portal_mode": "Patient Intake",
        "show_patient_queue_board": True,
        "show_patient_queue_sidebar": False,
        "staff_login_error": None,
        "patient_recorder_version": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_shared_styles(hide_sidebar: bool = True) -> None:
    sidebar_style = (
        """
        [data-testid="stSidebar"] {
            display: none;
        }
        """
        if hide_sidebar
        else ""
    )
    css = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: "Manrope", sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(36, 116, 171, 0.12), transparent 32%),
                linear-gradient(180deg, #f5f9fc 0%, #edf4f8 100%);
            color: #173047;
        }

        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        #MainMenu,
        footer,
        [data-testid="stSidebarNav"] {
            display: none;
        }

        __SIDEBAR_STYLE__

        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }

        .portal-card {
            padding: 1.5rem 1.6rem;
            border-radius: 24px;
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid rgba(105, 135, 159, 0.18);
            box-shadow: 0 22px 46px rgba(17, 42, 64, 0.10);
        }

        .portal-title {
            font-size: clamp(2rem, 5vw, 3rem);
            font-weight: 800;
            color: #173047;
            line-height: 1;
            margin-bottom: 0.5rem;
        }

        .portal-subtitle {
            color: #4f697d;
            line-height: 1.6;
            margin-bottom: 0;
        }

        .metric-card {
            padding: 1rem 1.1rem;
            border-radius: 18px;
            background: rgba(247, 250, 252, 0.98);
            border: 1px solid rgba(105, 135, 159, 0.16);
        }
        </style>
        """.replace("__SIDEBAR_STYLE__", sidebar_style)
    st.markdown(
        css,
        unsafe_allow_html=True,
    )


def login_user(user: dict[str, Any]) -> None:
    st.session_state.authenticated_user = user
    st.session_state.staff_login_error = None


def logout_user() -> None:
    st.session_state.authenticated_user = None


def current_user() -> dict[str, Any] | None:
    user = st.session_state.get("authenticated_user")
    if not user:
        return None

    fresh_user = get_user_by_id(int(user["id"]))
    if fresh_user is None or not fresh_user.get("is_active"):
        logout_user()
        return None

    st.session_state.authenticated_user = fresh_user
    return fresh_user


def require_role(*roles: str) -> dict[str, Any]:
    user = current_user()
    if user is None or user.get("role") not in roles:
        st.warning("Please log in to continue.")
        st.switch_page("app.py")
        st.stop()
    return user


def switch_for_logged_in_user() -> None:
    user = current_user()
    if user is None:
        return

    role = str(user.get("role", "")).lower()
    if role == "admin":
        st.switch_page("pages/admin_portal.py")
    elif role == "doctor":
        st.switch_page("pages/doctor_dashboard.py")
    elif role == "receptionist":
        st.switch_page("pages/receptionist_dashboard.py")


def clear_patient_submission_state() -> None:
    st.session_state.patient_audio_bytes = None
    st.session_state.patient_audio_digest = None
    st.session_state.patient_submission_result = None
    st.session_state.patient_processing_error = None
    st.session_state.patient_recorder_version = st.session_state.get("patient_recorder_version", 0) + 1
