from __future__ import annotations

import os

from groq import Groq

from .retrieval import RetrievedDocument, format_retrieved_context


class GroqMedicalReasoner:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "llama3-70b-8192",
    ) -> None:
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key or self.api_key == "your_real_groq_api_key_here":
            raise RuntimeError(
                "Missing GROQ_API_KEY. Add your real key to `.env` as `GROQ_API_KEY=...`."
            )

        self.model_name = model_name
        self.client = Groq(api_key=self.api_key)

    def reason(
        self,
        symptom_text: str,
        retrieved_documents: list[RetrievedDocument],
        normalized_symptoms: list[str] | None = None,
    ) -> str:
        context = format_retrieved_context(retrieved_documents)
        normalized_symptom_text = ", ".join(normalized_symptoms or [])

        response = self.client.chat.completions.create(
            model=self.model_name,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a medical RAG assistant. Use only the retrieved context. "
                        "Do not hallucinate or add diseases not present in the context. "
                        "Reason internally with this ReAct-style loop: Thought -> identify "
                        "the most relevant retrieved diseases, Action -> compare user "
                        "symptoms against retrieved symptoms, Observation -> keep only "
                        "evidence grounded in the retrieved context, Final -> output a "
                        "single JSON object only. Never output the internal Thought, "
                        "Action, or Observation text. Confidence must be a number between "
                        "0 and 1."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "User symptoms:\n"
                        f"{symptom_text}\n\n"
                        "Normalized dataset symptom matches:\n"
                        f"{normalized_symptom_text or 'None'}\n\n"
                        "Retrieved context:\n"
                        f"{context}\n\n"
                        "Return STRICT JSON with exactly this shape:\n"
                        "{\n"
                        '  "possible_diseases": [\n'
                        "    {\n"
                        '      "name": "",\n'
                        '      "confidence": 0.0,\n'
                        '      "matched_symptoms": [],\n'
                        '      "reason": ""\n'
                        "    }\n"
                        "  ],\n"
                        '  "severity_score": 0.0,\n'
                        '  "severity_level": "",\n'
                        '  "recommended_action": ""\n'
                        "}\n\n"
                        "Rules:\n"
                        "1. Use only diseases from retrieved context.\n"
                        "2. Prefer the normalized dataset symptom matches when deciding matched_symptoms.\n"
                        "3. Return up to 5 diseases.\n"
                        "4. If context is weak, lower confidence instead of guessing.\n"
                        "5. Output JSON only, no markdown, no prose."
                    ),
                },
            ],
        )

        return response.choices[0].message.content or "{}"
