---
name: ai-pre-diagnosis-system
description: Build and maintain an AI-based hospital pre-diagnosis system with voice input, embedding-based symptom extraction, ML prediction, severity scoring, PDF generation, and smart queue management.
---

# AI Pre-Diagnosis System Skill

## Purpose
This skill helps build a complete AI-powered hospital triage system that:
- Takes patient symptoms via voice input
- Converts speech to text (Tamil + English supported)
- Extracts symptoms using embeddings (NOT keyword matching)
- Predicts disease using a trained ML model
- Calculates severity level
- Generates a PDF report
- Manages a smart priority queue

---

## System Architecture

Follow this exact pipeline:

Voice Input → Speech-to-Text → Translation → Embedding Symptom Extraction → Symptom Vector → ML Model → Prediction → Severity → PDF → Queue System

---

## Core Rules (VERY IMPORTANT)

1. NEVER use hardcoded symptom lists
   - Always load symptoms from dataset columns

2. ALWAYS use embedding-based symptom extraction
   - Use sentence-transformers
   - Avoid simple keyword matching

3. Maintain consistency:
   - Symptom order must match dataset columns
   - Save and reuse symptoms list

4. Code must be modular:
   - utils/
   - model/
   - report/
   - queue/

5. Keep functions reusable and clean

---

## Modules to Build

### 1. Model Training
- Use RandomForestClassifier
- Load dataset from `data/dataset.csv`
- Save model as `model.pkl`
- Save symptoms list as `symptoms.pkl`

---

### 2. Embedding Symptom Engine
- Use: sentence-transformers (all-MiniLM-L6-v2)
- Convert symptoms to readable format
- Precompute embeddings
- Match input text to symptoms using cosine similarity

---

### 3. Voice Input
- Use Sarvam AI for speech-to-text and translation
- Support Tamil + English

---

### 4. Translation Layer
- Translate Tamil → English
- Ensure consistent processing

---

### 5. Severity Calculation
- Use scoring system:
  - critical symptoms → high score
  - moderate → medium
  - mild → low

---

### 6. PDF Report
Include:
- Patient ID
- Symptoms
- Predicted disease
- Severity
- Timestamp

---

### 7. Queue System
- Priority-based:
  - HIGH → immediate
  - MEDIUM → normal
  - LOW → delayed

- Special rule:
  LOW patients must wait until 5 higher-priority patients are processed

---

## Coding Guidelines

- Use Python
- Use clear function names
- Avoid unnecessary prints
- Keep code readable and structured
- Use separate files for each module

---

## Trigger Examples

Use this skill when prompts include:
- "build ai diagnosis system"
- "connect symptoms to model"
- "generate medical pdf"
- "priority queue hospital system"
- "voice to disease prediction"

---

## Output Expectations

When implementing features:
- Provide complete working code
- Maintain module structure
- Ensure integration between components

---

## Important Notes

- This is a pre-diagnosis system only
- Do not claim medical accuracy
- Focus on system design and implementation


