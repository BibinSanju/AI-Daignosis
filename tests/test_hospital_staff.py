from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from utils import hospital_db


class HospitalStaffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_root = Path(self.temp_dir.name)

        self.original_storage_dir = hospital_db.STORAGE_DIR
        self.original_reports_dir = hospital_db.REPORTS_DIR
        self.original_database_path = hospital_db.DATABASE_PATH

        hospital_db.STORAGE_DIR = temp_root / "storage"
        hospital_db.REPORTS_DIR = hospital_db.STORAGE_DIR / "reports"
        hospital_db.DATABASE_PATH = hospital_db.STORAGE_DIR / "hospital.db"

    def tearDown(self) -> None:
        hospital_db.STORAGE_DIR = self.original_storage_dir
        hospital_db.REPORTS_DIR = self.original_reports_dir
        hospital_db.DATABASE_PATH = self.original_database_path
        self.temp_dir.cleanup()

    def test_default_receptionist_can_authenticate(self) -> None:
        hospital_db.init_database()

        credentials = hospital_db.default_staff_credentials()
        user = hospital_db.authenticate_user(
            credentials["receptionist_username"],
            credentials["receptionist_password"],
        )

        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "receptionist")

    def test_existing_database_is_migrated_for_receptionist_role(self) -> None:
        hospital_db.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(hospital_db.DATABASE_PATH)
        try:
            connection.execute(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'doctor')),
                    full_name TEXT NOT NULL,
                    specialization TEXT DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

        hospital_db.init_database()

        receptionists = hospital_db.list_receptionists()
        self.assertTrue(receptionists)
        self.assertEqual(receptionists[0]["role"], "receptionist")


if __name__ == "__main__":
    unittest.main()
