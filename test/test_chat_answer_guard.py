import unittest

from chat_answer_guard import validate_answer


class ChatAnswerGuardTests(unittest.TestCase):
    def test_blank_evidence_is_noop_for_general_answers(self):
        result = validate_answer(
            "The framework was released in 2023 and a plan costs $20 per month.",
            evidence_corpus="",
            sources=[],
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.violations, [])
        self.assertIsNone(result.corrected_answer)

    def test_partial_date_must_not_gain_unsupported_year(self):
        result = validate_answer(
            "ราคาล่าสุด ณ วันที่ 26 มิ.ย. 2561 อยู่ในตาราง [web:1]",
            evidence_corpus="อัปเดต 26 มิ.ย. ราคาขายปลีกน้ำมัน",
            sources=[{"index": 1, "url": "https://example.com"}],
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("partial date" in violation for violation in result.violations))
        self.assertTrue(any("unsupported year" in violation for violation in result.violations))
        self.assertIn("26 มิ.ย.", result.corrected_answer)
        self.assertNotIn("2561", result.corrected_answer)

    def test_evidence_year_present_is_allowed(self):
        result = validate_answer(
            "Gasoline prices were updated on 22-Jun-2026 [web:1].",
            evidence_corpus="Thailand Gasoline prices, 22-Jun-2026",
            sources=[{"index": 1, "url": "https://example.com"}],
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.violations, [])
        self.assertIsNone(result.corrected_answer)

    def test_price_missing_from_evidence_is_flagged_and_annotated(self):
        result = validate_answer(
            "ราคาน้ำมันอยู่ที่ 49.59 บาทต่อลิตร [web:1]",
            evidence_corpus="ราคาน้ำมันอยู่ที่ 39.50 บาทต่อลิตร",
            sources=[{"index": 1, "url": "https://example.com"}],
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("unsupported price" in violation for violation in result.violations))
        self.assertIn("49.59", result.corrected_answer)
        self.assertIn("not found in evidence", result.corrected_answer)

    def test_price_from_structured_table_evidence_is_allowed(self):
        result = validate_answer(
            "เบนซิน 95 อยู่ที่ 39.50 บาท [web:1]",
            evidence_corpus="เบนซิน 95: 39.50",
            sources=[{"index": 1, "url": "https://example.com"}],
        )

        self.assertTrue(result.ok)

    def test_uniform_price_table_answer_is_flagged_as_suspicious(self):
        result = validate_answer(
            "Gasoline 95: 30.00 THB/litre\nDiesel B7: 30.00 THB/litre\nE20: 30.00 THB/litre [web:1]",
            evidence_corpus="Gasoline 95: 30.00 | Diesel B7: 30.00 | E20: 30.00",
            sources=[{"index": 1, "url": "https://example.com"}],
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("uniform" in violation for violation in result.violations))

    def test_uniform_thai_baht_price_table_answer_is_flagged_as_suspicious(self):
        result = validate_answer(
            "Gasoline 95: 30.00 บาท/ลิตร\nDiesel B7: 30.00 บาท/ลิตร\nE20: 30.00 บาท/ลิตร [web:1]",
            evidence_corpus="Gasoline 95: 30.00 | Diesel B7: 30.00 | E20: 30.00",
            sources=[{"index": 1, "url": "https://example.com"}],
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("uniform" in violation for violation in result.violations))

    def test_numeric_normalization_accepts_equivalent_decimal_price(self):
        result = validate_answer(
            "ราคาอยู่ที่ 39.50 THB per liter [web:1]",
            evidence_corpus="Price: 39.5 THB per liter",
            sources=[{"index": 1, "url": "https://example.com"}],
        )

        self.assertTrue(result.ok)

    def test_numeric_boundary_does_not_match_inside_larger_number(self):
        result = validate_answer(
            "ราคาอยู่ที่ 49.59 THB per liter [web:1]",
            evidence_corpus="Price: 149.59 THB per liter",
            sources=[{"index": 1, "url": "https://example.com"}],
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("49.59" in violation for violation in result.violations))

    def test_dangling_citation_is_flagged(self):
        result = validate_answer(
            "ข้อมูลนี้มาจาก [web:3]",
            evidence_corpus="ข้อมูลนี้มาจากแหล่งที่หนึ่ง",
            sources=[{"index": 1}, {"index": 2}],
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("dangling citation" in violation for violation in result.violations))

    def test_allow_values_prevent_false_positive_year_or_echoed_number(self):
        result = validate_answer(
            "วันนี้คือปี 2026 และคุณถามถึงเลข 12345",
            evidence_corpus="",
            sources=[],
            allow=("2026", "12345"),
        )

        self.assertTrue(result.ok)

    def test_allowed_current_year_cannot_be_attached_to_yearless_evidence_date(self):
        result = validate_answer(
            "Fuel prices were updated on 26 Jun 2026 [web:1].",
            evidence_corpus="Fuel prices updated 26 Jun",
            sources=[{"index": 1, "url": "https://example.test/fuel"}],
            allow=("2026",),
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("partial date" in violation for violation in result.violations))
        self.assertNotIn("2026", result.corrected_answer)

    def test_ordinary_counts_are_not_flagged(self):
        result = validate_answer(
            "มี 3 แหล่งข้อมูลที่เกี่ยวข้อง และมี 2 แนวทางหลัก",
            evidence_corpus="",
            sources=[],
        )

        self.assertTrue(result.ok)

    def test_version_like_number_is_not_flagged_without_fact_context(self):
        result = validate_answer(
            "ใช้ engine version 2026 เพื่อทดสอบภายใน",
            evidence_corpus="",
            sources=[],
        )

        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
