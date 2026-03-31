from __future__ import annotations

import streamlit as st

from utils.hospital_db import (
    append_dataset_csv,
    append_dataset_entry,
    count_patient_reports,
    create_doctor,
    create_receptionist,
    dataset_row_count,
    init_database,
    list_doctors,
    list_receptionists,
    set_doctor_active,
    set_receptionist_active,
)
from utils.patient_workflow import clear_rag_pipeline_cache
from utils.portal import apply_shared_styles, init_session_state, logout_user, require_role


st.set_page_config(page_title="Admin Portal", layout="wide")
init_database()
init_session_state()
apply_shared_styles()
admin_user = require_role("admin")


header_left, header_right = st.columns([5, 1])
with header_left:
    st.markdown(
        f"""
        <div class="portal-card">
            <div class="portal-title">Admin Portal</div>
            <p class="portal-subtitle">
                Logged in as {admin_user['full_name']}. Manage doctor and receptionist accounts, then append new dataset entries without exposing internal workflow pages to patients.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with header_right:
    if st.button("Logout", width="stretch"):
        logout_user()
        st.switch_page("app.py")


metric_columns = st.columns(4)
with metric_columns[0]:
    st.metric("Doctor Accounts", len(list_doctors()))
with metric_columns[1]:
    st.metric("Receptionists", len(list_receptionists()))
with metric_columns[2]:
    st.metric("Dataset Rows", dataset_row_count())
with metric_columns[3]:
    st.metric("Patient Reports", count_patient_reports())


st.markdown("## Doctor Accounts")
doctor_columns = st.columns([1.3, 1])

with doctor_columns[0]:
    with st.form("create_doctor_form", clear_on_submit=True):
        st.markdown("### Add Doctor")
        doctor_name = st.text_input("Doctor Name")
        doctor_username = st.text_input("Doctor Username")
        doctor_specialization = st.text_input("Specialization")
        doctor_password = st.text_input("Temporary Password", type="password")
        create_submitted = st.form_submit_button("Create Doctor", width="stretch")

    if create_submitted:
        success, message = create_doctor(
            username=doctor_username,
            password=doctor_password,
            full_name=doctor_name,
            specialization=doctor_specialization,
        )
        if success:
            st.success(message)
            st.rerun()
        st.error(message)

with doctor_columns[1]:
    doctors = list_doctors()
    if doctors:
        doctor_options = {
            f"{doctor['full_name']} ({doctor['username']})": doctor for doctor in doctors
        }
        selected_label = st.selectbox("Select Doctor", list(doctor_options.keys()))
        selected_doctor = doctor_options[selected_label]
        new_state = st.toggle(
            "Doctor Active",
            value=bool(selected_doctor["is_active"]),
            key=f"doctor_active_{selected_doctor['id']}",
        )
        if st.button("Save Doctor Status", width="stretch"):
            set_doctor_active(selected_doctor["id"], new_state)
            st.success("Doctor status updated.")
            st.rerun()

        st.caption(
            f"Specialization: {selected_doctor['specialization'] or 'Not provided'}"
        )
    else:
        st.info("No doctors have been created yet.")

st.dataframe(
    [
        {
            "Name": doctor["full_name"],
            "Username": doctor["username"],
            "Specialization": doctor["specialization"] or "-",
            "Active": "Yes" if doctor["is_active"] else "No",
            "Created": doctor["created_at"],
        }
        for doctor in list_doctors()
    ],
    width="stretch",
    hide_index=True,
)


st.markdown("## Receptionist Accounts")
receptionist_columns = st.columns([1.3, 1])

with receptionist_columns[0]:
    with st.form("create_receptionist_form", clear_on_submit=True):
        st.markdown("### Add Receptionist")
        receptionist_name = st.text_input("Receptionist Name")
        receptionist_username = st.text_input("Receptionist Username")
        receptionist_password = st.text_input("Temporary Password", type="password")
        receptionist_submitted = st.form_submit_button("Create Receptionist", width="stretch")

    if receptionist_submitted:
        success, message = create_receptionist(
            username=receptionist_username,
            password=receptionist_password,
            full_name=receptionist_name,
        )
        if success:
            st.success(message)
            st.rerun()
        st.error(message)

with receptionist_columns[1]:
    receptionists = list_receptionists()
    if receptionists:
        receptionist_options = {
            f"{receptionist['full_name']} ({receptionist['username']})": receptionist
            for receptionist in receptionists
        }
        receptionist_label = st.selectbox(
            "Select Receptionist",
            list(receptionist_options.keys()),
        )
        selected_receptionist = receptionist_options[receptionist_label]
        receptionist_active = st.toggle(
            "Receptionist Active",
            value=bool(selected_receptionist["is_active"]),
            key=f"receptionist_active_{selected_receptionist['id']}",
        )
        if st.button("Save Receptionist Status", width="stretch"):
            set_receptionist_active(selected_receptionist["id"], receptionist_active)
            st.success("Receptionist status updated.")
            st.rerun()

        st.caption("Receptionists can view the live queue and download patient PDFs.")
    else:
        st.info("No receptionists have been created yet.")

st.dataframe(
    [
        {
            "Name": receptionist["full_name"],
            "Username": receptionist["username"],
            "Role": "Receptionist",
            "Active": "Yes" if receptionist["is_active"] else "No",
            "Created": receptionist["created_at"],
        }
        for receptionist in list_receptionists()
    ],
    width="stretch",
    hide_index=True,
)


st.markdown("## Dataset Management")
dataset_columns = st.columns(2)

with dataset_columns[0]:
    with st.form("manual_dataset_form", clear_on_submit=True):
        st.markdown("### Add Single Dataset Entry")
        disease_name = st.text_input("Disease")
        symptoms_input = st.text_area(
            "Symptoms",
            placeholder="chest pain, sweating, breathlessness",
            help="Enter comma-separated symptoms for one disease row.",
        )
        manual_submitted = st.form_submit_button("Append Entry", width="stretch")

    if manual_submitted:
        success, message = append_dataset_entry(
            disease=disease_name,
            symptoms=[value.strip() for value in symptoms_input.split(",")],
        )
        if success:
            clear_rag_pipeline_cache()
            st.success(message)
        else:
            st.error(message)

with dataset_columns[1]:
    st.markdown("### Bulk CSV Upload")
    uploaded_file = st.file_uploader(
        "Upload a CSV to append",
        type=["csv"],
        help="CSV must include a Disease column. Any additional columns are treated as symptom columns.",
    )
    if st.button("Append Uploaded CSV", width="stretch", disabled=uploaded_file is None):
        success, message = append_dataset_csv(uploaded_file.getvalue() if uploaded_file else b"")
        if success:
            clear_rag_pipeline_cache()
            st.success(message)
        else:
            st.error(message)

st.caption("Dataset updates clear the cached RAG pipeline so the next patient run rebuilds against the new data.")
