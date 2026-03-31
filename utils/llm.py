from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
import json
import re

model_name = "peteparker456/medical_diagnosis_llama2"

model = AutoModelForCausalLM.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)

pipe = pipeline(
    task="text-generation",
    model=model,
    tokenizer=tokenizer,
    max_length=300
)

# -------------------------
# 1. SYMPTOM EXTRACTION
# -------------------------

def extract_symptoms_llm(text):
    prompt = f"""
Extract the symptoms from the following sentence.
Return ONLY a Python list.

Sentence: "{text}"

Output example:
["fever", "headache"]
"""

    result = pipe(prompt)[0]["generated_text"]

    # Extract list using regex
    match = re.search(r"\[(.*?)\]", result)

    if match:
        try:
            symptoms = json.loads(f"[{match.group(1)}]")
            return [s.lower() for s in symptoms]
        except:
            return []
    return []

# -------------------------
# 2. FALLBACK DIAGNOSIS
# -------------------------

def predict_with_llm(text):
    prompt = f"""
You are a medical assistant.

Given the symptoms, return top 5 possible diseases.

Return STRICT JSON:
{{
  "predictions": [
    {{"disease": "...", "confidence": 0.0}}
  ]
}}

Symptoms: "{text}"
"""

    result = pipe(prompt)[0]["generated_text"]

    # Extract JSON
    match = re.search(r"\{.*\}", result, re.DOTALL)

    if match:
        try:
            return json.loads(match.group())
        except:
            return {"predictions": []}

    return {"predictions": []}