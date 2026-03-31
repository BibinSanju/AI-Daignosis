# AI Diagnosis Intake Portal

This project is a Streamlit-based hospital intake system for voice-driven pre-diagnosis.

It currently includes:

- Patient intake with voice recording
- Sarvam speech-to-text and translation
- Medical RAG diagnosis with Groq
- PDF report generation for each patient
- Priority queue with token numbers
- Doctor dashboard
- Receptionist dashboard
- Admin dashboard for dataset and staff management

## Project Structure

- `app.py` - patient intake page and staff login
- `pages/admin_portal.py` - admin dashboard
- `pages/doctor_dashboard.py` - doctor dashboard
- `pages/receptionist_dashboard.py` - receptionist dashboard
- `medical_rag/` - retrieval, symptom matching, severity scoring, LLM reasoning
- `utils/speech.py` - Sarvam API integration
- `utils/hospital_db.py` - SQLite users, queue, reports, tokens
- `utils/reporting.py` - patient PDF generation
- `latest data med/dataset.csv` - medical dataset

## 1. Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 2. Install Dependencies

```powershell
pip install streamlit streamlit-audiorecorder requests chromadb sentence-transformers groq pillow transformers
```

If your environment does not already provide PyTorch, install it as well:

```powershell
pip install torch
```

## 3. Add API Keys and Optional Staff Logins

Copy `.env.example` to `.env`, then paste your real keys.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Paste your values in `.env` like this:

```env
# Required APIs
SARVAM_API_KEY=paste_your_real_sarvam_key_here
GROQ_API_KEY=paste_your_real_groq_key_here

# Optional Sarvam settings
SARVAM_STT_MODEL=saaras:v3
SARVAM_TRANSLATION_MODEL=mayura:v1
SARVAM_SOURCE_LANGUAGE=ta-IN
SARVAM_TARGET_LANGUAGE=en-IN
SARVAM_REQUEST_TIMEOUT_SECONDS=120

# Optional staff login overrides
APP_ADMIN_USERNAME=admin
APP_ADMIN_PASSWORD=admin123
APP_DOCTOR_USERNAME=doctor1
APP_DOCTOR_PASSWORD=doctor123
APP_RECEPTIONIST_USERNAME=reception1
APP_RECEPTIONIST_PASSWORD=reception123
```

Notes:

- `SARVAM_API_KEY` is required for audio transcription and translation.
- `GROQ_API_KEY` is required for the diagnosis pipeline.
- If you do not override the staff logins, the default seeded accounts above are used automatically.
- `.env` is ignored by Git through `.gitignore`.

## 4. Run the Project

Start the Streamlit app from the project root:

```powershell
streamlit run app.py
```

Then open:

```text
http://localhost:8501
```

## 5. App Flow

### Patient Intake

- Enter patient details
- Record the symptom note
- Submit to generate:
  - translated text
  - diagnosis result
  - severity score
  - patient PDF
  - token number
  - queue entry

### Staff Login

Available staff roles:

- Admin
- Doctor
- Receptionist

### Admin Dashboard

- Create and manage doctor accounts
- Create and manage receptionist accounts
- Append single dataset entries
- Upload CSV rows into the dataset

### Doctor Dashboard

- View reports ordered by priority
- Open structured patient details
- Download patient PDFs
- Mark reports as reviewed

### Receptionist Dashboard

- View the live queue
- Open patient details
- Download the generated patient PDF for handover

## Generated Files and Data

These are created automatically while the app runs:

- `storage/hospital.db` - SQLite hospital database
- `storage/reports/` - generated patient PDFs
- `storage/chroma/` - local Chroma vector store
- `audio.wav` - temporary recorded audio during intake

These generated files are ignored by Git.

## Running Tests

```powershell
python -m unittest discover -s tests
```

## Important Notes

- The patient-facing translation page is no longer exposed directly.
- The intake queue can be shown on the right side and in the sidebar.
- PDF generation supports Tamil text.
- Sarvam request timeout is capped at 120 seconds.
