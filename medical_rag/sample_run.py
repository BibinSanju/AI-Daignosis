from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

from .pipeline import MedicalRAGPipeline


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    sample_input = "fever, joint pain, headache"
    with contextlib.redirect_stdout(io.StringIO()):
        with contextlib.redirect_stderr(io.StringIO()):
            pipeline = MedicalRAGPipeline(
                dataset_csv=project_root / "latest data med" / "dataset.csv",
                symptom_severity_csv=project_root / "latest data med" / "Symptom-severity.csv",
                chroma_path=project_root / "storage" / "chroma",
            )
            pipeline.build_index()
            result = pipeline.diagnose(sample_input)

    print(json.dumps({"input": sample_input, "output": result}, indent=2))


if __name__ == "__main__":
    main()
