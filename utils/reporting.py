from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

from PIL import Image, ImageDraw, ImageFont


PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754
LEFT_MARGIN = 90
TOP_MARGIN = 100
RIGHT_MARGIN = 90
BOTTOM_MARGIN = 90
BODY_FONT_SIZE = 28
TITLE_FONT_SIZE = 42
LINE_GAP = 16


def write_patient_report_pdf(pdf_path: Path, report_payload: dict[str, Any]) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pages = _render_pages(_report_lines(report_payload))
    if not pages:
        pages = [_blank_page()]

    rgb_pages = [page.convert("RGB") for page in pages]
    rgb_pages[0].save(
        pdf_path,
        "PDF",
        resolution=150.0,
        save_all=True,
        append_images=rgb_pages[1:],
    )


def _report_lines(report_payload: dict[str, Any]) -> list[str]:
    diagnosis = report_payload.get("diagnosis", {}) if isinstance(report_payload, dict) else {}
    possible_diseases = diagnosis.get("possible_diseases", []) if isinstance(diagnosis, dict) else []
    matched_dataset_symptoms = report_payload.get("matched_dataset_symptoms", [])
    symptom_matches = report_payload.get("symptom_matches", [])

    lines = [
        "AI PRE-DIAGNOSIS REPORT",
        "",
        f"Generated At: {report_payload.get('created_at', '')}",
        f"Token Number: {report_payload.get('token_number', '')}",
        f"Patient Name: {report_payload.get('patient_name', '')}",
        f"Age: {report_payload.get('age', '') or 'Not provided'}",
        f"Gender: {report_payload.get('gender', '') or 'Not provided'}",
        f"Phone: {report_payload.get('phone', '') or 'Not provided'}",
        "",
        "Diagnosis Summary",
        f"Top Disease: {_top_disease_name(possible_diseases)}",
        f"Severity Score: {diagnosis.get('severity_score', 0.0)}",
        f"Severity Level: {str(diagnosis.get('severity_level', '')).title()}",
        f"Recommended Action: {diagnosis.get('recommended_action', '')}",
        "",
        f"Tamil Transcript: {report_payload.get('source_transcript', '') or 'Not available'}",
        f"English Translation: {report_payload.get('translated_text', '') or 'Not available'}",
        "",
        f"Matched Dataset Symptoms: {', '.join(matched_dataset_symptoms) if matched_dataset_symptoms else 'None'}",
        "",
        "Symptom Understanding",
    ]

    if symptom_matches:
        for item in symptom_matches:
            lines.append(
                f"- {item.get('query_phrase', '')} -> {item.get('matched_symptom', '')} "
                f"(similarity {item.get('similarity', '')})"
            )
    else:
        lines.append("No symptom interpretation details available.")

    lines.extend(["", "Possible Diseases"])
    if possible_diseases:
        for index, disease in enumerate(possible_diseases, start=1):
            confidence_value = round(float(disease.get("confidence", 0.0) or 0.0) * 100, 1)
            matched_symptoms = ", ".join(disease.get("matched_symptoms", [])) or "No direct symptom match"
            lines.append(
                f"{index}. {disease.get('name', '')} | Confidence {confidence_value}% | "
                f"Matched: {matched_symptoms}"
            )
            lines.append(f"   Reason: {disease.get('reason', '')}")
    else:
        lines.append("No disease candidates available.")

    return lines


def _render_pages(lines: Sequence[str]) -> list[Image.Image]:
    body_font = _load_font(BODY_FONT_SIZE)
    title_font = _load_font(TITLE_FONT_SIZE)

    pages: list[Image.Image] = []
    image, draw, cursor_y = _page_canvas()

    for raw_line in lines:
        font = title_font if raw_line == "AI PRE-DIAGNOSIS REPORT" else body_font
        wrapped_lines = _wrap_line(raw_line, draw, font)

        for line in wrapped_lines:
            line_height = _line_height(font) + (LINE_GAP if line else LINE_GAP // 2)
            if cursor_y + line_height > PAGE_HEIGHT - BOTTOM_MARGIN:
                pages.append(image)
                image, draw, cursor_y = _page_canvas()

            draw.text((LEFT_MARGIN, cursor_y), line, fill="#173047", font=font)
            cursor_y += line_height

    pages.append(image)
    return pages


def _page_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    image = _blank_page()
    draw = ImageDraw.Draw(image)
    return image, draw, TOP_MARGIN


def _blank_page() -> Image.Image:
    return Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "white")


def _wrap_line(
    text: object,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> list[str]:
    content = str(text)
    if not content:
        return [""]

    max_width = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
    words = content.split()
    if not words:
        return [content]

    wrapped: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            wrapped.append(current)
            current = word

    wrapped.append(current)
    return wrapped


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _font_candidates():
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _font_candidates() -> list[Path]:
    windows_fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    return [
        windows_fonts / "Nirmala.ttc",
        windows_fonts / "seguisb.ttf",
        windows_fonts / "segoeui.ttf",
        windows_fonts / "arial.ttf",
    ]


def _line_height(font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    left, top, right, bottom = font.getbbox("Ag")
    return bottom - top


def _top_disease_name(possible_diseases: Sequence[dict[str, Any]]) -> str:
    if not possible_diseases:
        return "Unavailable"
    return str(possible_diseases[0].get("name", "") or "Unavailable")
