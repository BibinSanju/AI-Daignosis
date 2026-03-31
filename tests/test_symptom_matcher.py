from __future__ import annotations

import unittest

from medical_rag.symptom_matcher import _extract_candidate_phrases, _minimum_similarity_for_phrase


class SymptomMatcherHelpersTests(unittest.TestCase):
    def test_multi_symptom_text_does_not_keep_full_sentence_phrase(self) -> None:
        phrases = _extract_candidate_phrases("a fever, a cold, and nose is running")
        self.assertEqual(phrases, ["fever", "cold", "nose is running"])

    def test_single_word_phrases_need_stronger_similarity(self) -> None:
        self.assertEqual(_minimum_similarity_for_phrase("cold", 0.60), 0.78)
        self.assertEqual(_minimum_similarity_for_phrase("fever", 0.60), 0.78)

    def test_multi_word_phrases_keep_base_similarity(self) -> None:
        self.assertEqual(_minimum_similarity_for_phrase("shortness of breath", 0.60), 0.60)
        self.assertEqual(_minimum_similarity_for_phrase("nose is running", 0.60), 0.60)


if __name__ == "__main__":
    unittest.main()
