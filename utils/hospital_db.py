from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Sequence


APP_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = APP_DIR / "storage"
REPORTS_DIR = STORAGE_DIR / "reports"
DATABASE_PATH = STORAGE_DIR / "hospital.db"
DATASET_PATH = APP_DIR / "latest data med" / "dataset.csv"

DEFAULT_ADMIN_USERNAME = os.environ.get("APP_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.environ.get("APP_ADMIN_PASSWORD", "admin123")
DEFAULT_DOCTOR_USERNAME = os.environ.get("APP_DOCTOR_USERNAME", "doctor1")
DEFAULT_DOCTOR_PASSWORD = os.environ.get("APP_DOCTOR_PASSWORD", "doctor123")
DEFAULT_RECEPTIONIST_USERNAME = os.environ.get("APP_RECEPTIONIST_USERNAME", "reception1")
DEFAULT_RECEPTIONIST_PASSWORD = os.environ.get("APP_RECEPTIONIST_PASSWORD", "reception123")


def init_database() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with _db_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'doctor', 'receptionist')),
                full_name TEXT NOT NULL,
                specialization TEXT DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS patient_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_number INTEGER NOT NULL UNIQUE,
                patient_name TEXT NOT NULL,
                age INTEGER,
                gender TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                source_transcript TEXT DEFAULT '',
                translated_text TEXT DEFAULT '',
                diagnosis_json TEXT NOT NULL,
                top_disease TEXT DEFAULT '',
                severity_score REAL NOT NULL,
                severity_level TEXT NOT NULL,
                recommended_action TEXT DEFAULT '',
                priority_rank INTEGER NOT NULL,
                pdf_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued', 'reviewed')),
                reviewed_by INTEGER,
                reviewed_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(reviewed_by) REFERENCES users(id)
            );
            """
        )
        _ensure_users_table_supports_receptionists(connection)
        _seed_default_users(connection)


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    candidate_username = username.strip().lower()
    if not candidate_username or not password:
        return None

    with _db_connection() as connection:
        row = connection.execute(
            """
            SELECT id, username, password_hash, salt, role, full_name, specialization, is_active
            FROM users
            WHERE lower(username) = ?
            """,
            (candidate_username,),
        ).fetchone()

    if row is None or not row["is_active"]:
        return None

    computed_hash = _hash_password(password, row["salt"])
    if not hmac.compare_digest(computed_hash, row["password_hash"]):
        return None

    return _user_row_to_dict(row)


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with _db_connection() as connection:
        row = connection.execute(
            """
            SELECT id, username, role, full_name, specialization, is_active, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    return _user_row_to_dict(row) if row is not None else None


def list_doctors() -> list[dict[str, Any]]:
    return _list_users_by_role("doctor")


def list_receptionists() -> list[dict[str, Any]]:
    return _list_users_by_role("receptionist")


def _list_users_by_role(role: str) -> list[dict[str, Any]]:
    with _db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, username, role, full_name, specialization, is_active, created_at
            FROM users
            WHERE role = ?
            ORDER BY is_active DESC, full_name COLLATE NOCASE ASC
            """,
            (role,),
        ).fetchall()

    return [_user_row_to_dict(row) for row in rows]


def create_doctor(
    username: str,
    password: str,
    full_name: str,
    specialization: str = "",
) -> tuple[bool, str]:
    return _create_staff_user(
        username=username,
        password=password,
        full_name=full_name,
        role="doctor",
        specialization=specialization,
        required_label="Doctor",
        success_label="Doctor",
    )


def create_receptionist(
    username: str,
    password: str,
    full_name: str,
) -> tuple[bool, str]:
    return _create_staff_user(
        username=username,
        password=password,
        full_name=full_name,
        role="receptionist",
        specialization="",
        required_label="Receptionist",
        success_label="Receptionist",
    )


def _create_staff_user(
    username: str,
    password: str,
    full_name: str,
    role: str,
    specialization: str,
    required_label: str,
    success_label: str,
) -> tuple[bool, str]:
    cleaned_username = username.strip().lower()
    cleaned_name = full_name.strip()
    if not cleaned_username or not password or not cleaned_name:
        return False, f"{required_label} name, username, and password are required."

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)

    try:
        with _db_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (username, password_hash, salt, role, full_name, specialization, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    cleaned_username,
                    password_hash,
                    salt,
                    role,
                    cleaned_name,
                    specialization.strip(),
                ),
            )
    except sqlite3.IntegrityError:
        return False, f"Username `{cleaned_username}` already exists."

    return True, f"{success_label} account `{cleaned_username}` created."


def set_doctor_active(doctor_id: int, is_active: bool) -> None:
    _set_staff_active(doctor_id, is_active, "doctor")


def set_receptionist_active(receptionist_id: int, is_active: bool) -> None:
    _set_staff_active(receptionist_id, is_active, "receptionist")


def _set_staff_active(user_id: int, is_active: bool, role: str) -> None:
    with _db_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET is_active = ?
            WHERE id = ? AND role = ?
            """,
            (1 if is_active else 0, user_id, role),
        )


def save_patient_report(
    patient_name: str,
    age: int | None,
    gender: str,
    phone: str,
    source_transcript: str,
    translated_text: str,
    diagnosis: dict[str, Any],
    matched_dataset_symptoms: Sequence[str],
    symptom_matches: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    from .reporting import write_patient_report_pdf

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    top_disease = ""
    possible_diseases = diagnosis.get("possible_diseases", [])
    if possible_diseases:
        top_disease = str(possible_diseases[0].get("name", "")).strip()

    severity_level = str(diagnosis.get("severity_level", "low")).strip().lower() or "low"
    severity_score = float(diagnosis.get("severity_score", 0.0) or 0.0)
    recommended_action = str(diagnosis.get("recommended_action", "")).strip()
    priority_rank = _priority_rank_for_level(severity_level)

    with _db_connection() as connection:
        token_number = _next_token_number(connection)
        pdf_path = REPORTS_DIR / _build_pdf_filename(token_number, patient_name)
        report_payload = {
            "token_number": token_number,
            "patient_name": patient_name.strip(),
            "age": age,
            "gender": gender.strip(),
            "phone": phone.strip(),
            "source_transcript": source_transcript.strip(),
            "translated_text": translated_text.strip(),
            "diagnosis": diagnosis,
            "matched_dataset_symptoms": list(matched_dataset_symptoms),
            "symptom_matches": list(symptom_matches),
            "created_at": timestamp,
        }

        write_patient_report_pdf(pdf_path, report_payload)

        connection.execute(
            """
            INSERT INTO patient_reports (
                token_number,
                patient_name,
                age,
                gender,
                phone,
                source_transcript,
                translated_text,
                diagnosis_json,
                top_disease,
                severity_score,
                severity_level,
                recommended_action,
                priority_rank,
                pdf_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_number,
                patient_name.strip(),
                age,
                gender.strip(),
                phone.strip(),
                source_transcript.strip(),
                translated_text.strip(),
                json.dumps(report_payload, ensure_ascii=True),
                top_disease,
                round(severity_score, 2),
                severity_level,
                recommended_action,
                priority_rank,
                str(pdf_path),
            ),
        )

    return get_report_by_token(token_number) or {}


def list_patient_reports(include_reviewed: bool = True) -> list[dict[str, Any]]:
    query = """
        SELECT
            patient_reports.*,
            users.full_name AS reviewed_by_name
        FROM patient_reports
        LEFT JOIN users ON users.id = patient_reports.reviewed_by
    """
    params: tuple[Any, ...] = ()
    if not include_reviewed:
        query += " WHERE patient_reports.status = 'queued'"
    query += """
        ORDER BY
            CASE patient_reports.status WHEN 'queued' THEN 0 ELSE 1 END,
            patient_reports.priority_rank ASC,
            patient_reports.severity_score DESC,
            patient_reports.token_number ASC
    """

    with _db_connection() as connection:
        rows = connection.execute(query, params).fetchall()

    return [_report_row_to_dict(row) for row in rows]


def mark_report_reviewed(report_id: int, doctor_user_id: int | None = None) -> None:
    reviewed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _db_connection() as connection:
        connection.execute(
            """
            UPDATE patient_reports
            SET status = 'reviewed', reviewed_by = ?, reviewed_at = ?
            WHERE id = ?
            """,
            (doctor_user_id, reviewed_at, report_id),
        )


def get_report_by_token(token_number: int) -> dict[str, Any] | None:
    with _db_connection() as connection:
        row = connection.execute(
            """
            SELECT
                patient_reports.*,
                users.full_name AS reviewed_by_name
            FROM patient_reports
            LEFT JOIN users ON users.id = patient_reports.reviewed_by
            WHERE patient_reports.token_number = ?
            """,
            (token_number,),
        ).fetchone()

    return _report_row_to_dict(row) if row is not None else None


def load_report_pdf(report: dict[str, Any]) -> bytes:
    pdf_path = Path(str(report.get("pdf_path", "")))
    if not pdf_path.exists():
        return b""
    return pdf_path.read_bytes()


def count_patient_reports() -> int:
    with _db_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM patient_reports").fetchone()
    return int(row["total"]) if row is not None else 0


def dataset_row_count() -> int:
    if not DATASET_PATH.exists():
        return 0

    with DATASET_PATH.open(newline="", encoding="utf-8") as dataset_file:
        reader = csv.DictReader(dataset_file)
        return sum(1 for _ in reader)


def append_dataset_entry(disease: str, symptoms: Sequence[str]) -> tuple[bool, str]:
    cleaned_disease = disease.strip()
    cleaned_symptoms = [symptom.strip() for symptom in symptoms if symptom.strip()]
    if not cleaned_disease or not cleaned_symptoms:
        return False, "Disease name and at least one symptom are required."

    headers = _dataset_headers()
    if not headers:
        return False, "Dataset header could not be loaded."

    normalized_row = {header: "" for header in headers}
    normalized_row["Disease"] = cleaned_disease
    symptom_headers = [header for header in headers if header.lower().startswith("symptom_")]

    for index, symptom in enumerate(cleaned_symptoms[: len(symptom_headers)]):
        normalized_row[symptom_headers[index]] = symptom

    with DATASET_PATH.open("a", newline="", encoding="utf-8") as dataset_file:
        writer = csv.DictWriter(dataset_file, fieldnames=headers)
        writer.writerow(normalized_row)

    return True, f"Added `{cleaned_disease}` with {len(cleaned_symptoms[: len(symptom_headers)])} symptoms."


def append_dataset_csv(uploaded_bytes: bytes) -> tuple[bool, str]:
    headers = _dataset_headers()
    if not headers:
        return False, "Dataset header could not be loaded."

    uploaded_text = uploaded_bytes.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(uploaded_text))
    if not reader.fieldnames:
        return False, "Uploaded CSV must include a header row."

    header_lookup = {header.lower(): header for header in reader.fieldnames}
    if "disease" not in header_lookup:
        return False, "Uploaded CSV must include a `Disease` column."

    symptom_headers = [header for header in headers if header.lower().startswith("symptom_")]
    normalized_rows: list[dict[str, str]] = []

    for raw_row in reader:
        disease_value = str(raw_row.get(header_lookup["disease"], "")).strip()
        if not disease_value:
            continue

        normalized_row = {header: "" for header in headers}
        normalized_row["Disease"] = disease_value

        symptoms: list[str] = []
        for column_name in reader.fieldnames:
            if not column_name:
                continue
            if column_name.lower() == "disease":
                continue
            value = str(raw_row.get(column_name, "")).strip()
            if value:
                symptoms.append(value)

        for index, symptom in enumerate(symptoms[: len(symptom_headers)]):
            normalized_row[symptom_headers[index]] = symptom

        normalized_rows.append(normalized_row)

    if not normalized_rows:
        return False, "No usable dataset rows were found in the uploaded CSV."

    with DATASET_PATH.open("a", newline="", encoding="utf-8") as dataset_file:
        writer = csv.DictWriter(dataset_file, fieldnames=headers)
        writer.writerows(normalized_rows)

    return True, f"Appended {len(normalized_rows)} dataset rows."


def default_staff_credentials() -> dict[str, str]:
    return {
        "admin_username": DEFAULT_ADMIN_USERNAME,
        "admin_password": DEFAULT_ADMIN_PASSWORD,
        "doctor_username": DEFAULT_DOCTOR_USERNAME,
        "doctor_password": DEFAULT_DOCTOR_PASSWORD,
        "receptionist_username": DEFAULT_RECEPTIONIST_USERNAME,
        "receptionist_password": DEFAULT_RECEPTIONIST_PASSWORD,
    }


def _get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _db_connection():
    connection = _get_connection()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _seed_default_users(connection: sqlite3.Connection) -> None:
    existing_admin = connection.execute(
        "SELECT 1 FROM users WHERE role = 'admin' LIMIT 1"
    ).fetchone()
    existing_doctor = connection.execute(
        "SELECT 1 FROM users WHERE role = 'doctor' LIMIT 1"
    ).fetchone()
    existing_receptionist = connection.execute(
        "SELECT 1 FROM users WHERE role = 'receptionist' LIMIT 1"
    ).fetchone()

    if existing_admin is None:
        _insert_seed_user(
            connection=connection,
            username=DEFAULT_ADMIN_USERNAME,
            password=DEFAULT_ADMIN_PASSWORD,
            role="admin",
            full_name="Hospital Administrator",
            specialization="",
        )

    if existing_doctor is None:
        _insert_seed_user(
            connection=connection,
            username=DEFAULT_DOCTOR_USERNAME,
            password=DEFAULT_DOCTOR_PASSWORD,
            role="doctor",
            full_name="On-Call Doctor",
            specialization="General Medicine",
        )

    if existing_receptionist is None:
        _insert_seed_user(
            connection=connection,
            username=DEFAULT_RECEPTIONIST_USERNAME,
            password=DEFAULT_RECEPTIONIST_PASSWORD,
            role="receptionist",
            full_name="Front Desk Receptionist",
            specialization="Reception",
        )


def _insert_seed_user(
    connection: sqlite3.Connection,
    username: str,
    password: str,
    role: str,
    full_name: str,
    specialization: str,
) -> None:
    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    connection.execute(
        """
        INSERT INTO users (username, password_hash, salt, role, full_name, specialization, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (username.strip().lower(), password_hash, salt, role, full_name, specialization),
    )


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def _ensure_users_table_supports_receptionists(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = 'users'
        """
    ).fetchone()
    create_sql = str(row["sql"] or "") if row is not None else ""
    if "receptionist" in create_sql:
        return

    connection.executescript(
        """
        ALTER TABLE users RENAME TO users_legacy;

        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'doctor', 'receptionist')),
            full_name TEXT NOT NULL,
            specialization TEXT DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO users (id, username, password_hash, salt, role, full_name, specialization, is_active, created_at)
        SELECT id, username, password_hash, salt, role, full_name, specialization, is_active, created_at
        FROM users_legacy;

        DROP TABLE users_legacy;
        """
    )


def _user_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "role": str(row["role"]),
        "full_name": str(row["full_name"]),
        "specialization": str(row["specialization"] or ""),
        "is_active": bool(row["is_active"]),
        "created_at": str(row["created_at"]) if "created_at" in row.keys() else "",
    }


def _report_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(str(row["diagnosis_json"]))
    return {
        "id": int(row["id"]),
        "token_number": int(row["token_number"]),
        "patient_name": str(row["patient_name"]),
        "age": row["age"],
        "gender": str(row["gender"] or ""),
        "phone": str(row["phone"] or ""),
        "source_transcript": str(row["source_transcript"] or ""),
        "translated_text": str(row["translated_text"] or ""),
        "payload": payload,
        "top_disease": str(row["top_disease"] or ""),
        "severity_score": float(row["severity_score"] or 0.0),
        "severity_level": str(row["severity_level"] or ""),
        "recommended_action": str(row["recommended_action"] or ""),
        "priority_rank": int(row["priority_rank"]),
        "pdf_path": str(row["pdf_path"]),
        "status": str(row["status"]),
        "reviewed_by": row["reviewed_by"],
        "reviewed_by_name": str(row["reviewed_by_name"] or ""),
        "reviewed_at": str(row["reviewed_at"] or ""),
        "created_at": str(row["created_at"]),
    }


def _next_token_number(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(token_number), 0) + 1 AS next_token FROM patient_reports"
    ).fetchone()
    return int(row["next_token"]) if row is not None else 1


def _priority_rank_for_level(level: str) -> int:
    normalized_level = level.strip().lower()
    if normalized_level == "high":
        return 0
    if normalized_level == "medium":
        return 1
    return 2


def _build_pdf_filename(token_number: int, patient_name: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in patient_name.strip())
    slug = "-".join(part for part in slug.split("-") if part) or "patient"
    return f"token-{token_number:04d}-{slug}.pdf"


def _dataset_headers() -> list[str]:
    with DATASET_PATH.open(newline="", encoding="utf-8") as dataset_file:
        reader = csv.reader(dataset_file)
        try:
            return next(reader)
        except StopIteration:
            return []
