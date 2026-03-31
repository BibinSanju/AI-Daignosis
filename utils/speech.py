import os
from pathlib import Path

import requests


APP_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = APP_DIR / ".env"
SARVAM_API_BASE_URL = "https://api.sarvam.ai"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120
MAX_REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_STT_MODEL = "saaras:v3"
DEFAULT_TRANSLATION_MODEL = "mayura:v1"
DEFAULT_SOURCE_LANGUAGE = "ta-IN"
DEFAULT_TARGET_LANGUAGE = "en-IN"


def transcribe_audio(file_path: str) -> dict[str, str]:
    """Transcribe Tamil audio to Tamil text, then translate it to English with Sarvam."""
    _load_local_env()

    api_key = os.environ.get("SARVAM_API_KEY", "").strip()
    if not api_key or api_key == "your_sarvam_api_key_here":
        raise RuntimeError(
            "Missing SARVAM_API_KEY. Add your real key to `.env` as "
            "`SARVAM_API_KEY=...`."
        )

    audio_path = Path(file_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    source_language = os.environ.get("SARVAM_SOURCE_LANGUAGE", DEFAULT_SOURCE_LANGUAGE)
    target_language = os.environ.get("SARVAM_TARGET_LANGUAGE", DEFAULT_TARGET_LANGUAGE)

    try:
        tamil_text = _speech_to_text(api_key, audio_path, source_language)
        if not tamil_text:
            raise RuntimeError("Sarvam returned an empty Tamil transcript.")

        english_text = _translate_text(
            api_key,
            tamil_text,
            source_language,
            target_language,
        )
        if not english_text:
            raise RuntimeError("Sarvam returned an empty English translation.")

        return {
            "source_text": tamil_text,
            "translated_text": english_text,
        }
    except requests.RequestException as exc:
        raise RuntimeError(_format_request_exception(exc)) from exc


def _load_local_env() -> None:
    if not ENV_PATH.exists():
        return

    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _request_timeout_seconds() -> int:
    raw_timeout = os.environ.get("SARVAM_REQUEST_TIMEOUT_SECONDS", "").strip()
    try:
        configured_timeout = int(raw_timeout) if raw_timeout else DEFAULT_REQUEST_TIMEOUT_SECONDS
    except ValueError:
        configured_timeout = DEFAULT_REQUEST_TIMEOUT_SECONDS

    configured_timeout = max(1, configured_timeout)
    return min(configured_timeout, MAX_REQUEST_TIMEOUT_SECONDS)


def _speech_to_text(api_key: str, audio_path: Path, language_code: str) -> str:
    headers = {
        "api-subscription-key": api_key,
    }
    data = {
        "model": os.environ.get("SARVAM_STT_MODEL", DEFAULT_STT_MODEL),
        "language_code": language_code,
        "mode": "transcribe",
    }

    with audio_path.open("rb") as audio_file:
        response = requests.post(
            f"{SARVAM_API_BASE_URL}/speech-to-text",
            headers=headers,
            data=data,
            files={"file": (audio_path.name, audio_file, "audio/wav")},
            timeout=_request_timeout_seconds(),
        )

    _debug_response("speech-to-text", response)
    response.raise_for_status()
    payload = response.json()
    return str(payload.get("transcript", "")).strip()


def _translate_text(
    api_key: str,
    input_text: str,
    source_language_code: str,
    target_language_code: str,
) -> str:
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "input": input_text,
        "source_language_code": source_language_code,
        "target_language_code": target_language_code,
        "model": os.environ.get(
            "SARVAM_TRANSLATION_MODEL",
            DEFAULT_TRANSLATION_MODEL,
        ),
        "mode": "formal",
        "numerals_format": "international",
    }

    response = requests.post(
        f"{SARVAM_API_BASE_URL}/translate",
        headers=headers,
        json=payload,
        timeout=_request_timeout_seconds(),
    )
    _debug_response("translate", response)
    response.raise_for_status()
    body = response.json()
    return str(body.get("translated_text", "")).strip()


def _debug_response(label: str, response: requests.Response) -> None:
    try:
        body = response.json()
    except ValueError:
        body = response.text

    body_preview = str(body)
    if len(body_preview) > 1200:
        body_preview = f"{body_preview[:1200]}...<truncated>"

    print(f"[Sarvam] {label}: {response.status_code} {body_preview}")


def _format_request_exception(exc: requests.RequestException) -> str:
    if exc.response is not None:
        try:
            body = exc.response.json()
        except ValueError:
            body = exc.response.text
        return (
            f"Sarvam API request failed with HTTP {exc.response.status_code}: {body}"
        )

    return f"Unable to reach Sarvam API: {exc}"
