import unittest

from chat_vision_assist import (
    DEFAULT_VISION_ASSIST_MODEL,
    build_vision_evidence_message,
    select_vision_assist,
)


class VisionAssistSelectionTests(unittest.TestCase):
    def test_missing_setting_defaults_to_off_to_avoid_unexpected_paid_usage(self):
        decision = select_vision_assist(
            [{"kind": "image", "data_url": "data:image/png;base64,ZmFrZQ=="}],
            None,
            supports_vision=lambda _model: True,
        )

        self.assertFalse(decision.enabled)
        self.assertEqual(decision.mode, "off")
        self.assertEqual(decision.reason, "disabled")

    def test_no_usable_image_does_not_start_assistant(self):
        decision = select_vision_assist(
            [{"kind": "image", "content": "Image metadata only."}],
            {"visionAssist": "auto"},
            supports_vision=lambda _model: True,
        )

        self.assertFalse(decision.enabled)
        self.assertEqual(decision.reason, "no-usable-image")

    def test_off_never_starts_assistant_for_a_real_image(self):
        decision = select_vision_assist(
            [{"kind": "image", "data_url": "data:image/png;base64,ZmFrZQ=="}],
            {"visionAssist": "off"},
            supports_vision=lambda _model: True,
        )

        self.assertFalse(decision.enabled)
        self.assertEqual(decision.reason, "disabled")

    def test_auto_selects_default_helper_only_when_it_supports_vision(self):
        decision = select_vision_assist(
            [{"kind": "image", "data_url": "data:image/png;base64,ZmFrZQ=="}],
            {"visionAssist": "auto"},
            supports_vision=lambda model: model == DEFAULT_VISION_ASSIST_MODEL,
        )

        self.assertTrue(decision.enabled)
        self.assertEqual(decision.helper_model, DEFAULT_VISION_ASSIST_MODEL)

    def test_unavailable_helper_returns_metadata_only_fallback(self):
        decision = select_vision_assist(
            [{"kind": "image", "data_url": "data:image/png;base64,ZmFrZQ=="}],
            {"visionAssist": "on", "visionModel": "zai:not-a-vision-model"},
            supports_vision=lambda _model: False,
        )

        self.assertFalse(decision.enabled)
        self.assertEqual(decision.reason, "helper-not-vision-capable")


class VisionAssistEvidenceTests(unittest.TestCase):
    def test_evidence_message_is_text_only_and_has_no_image_payload(self):
        message = build_vision_evidence_message(
            "- The button says Update.",
            "zai:glm-4.6v-flashx",
        )

        self.assertIn("Vision Evidence", message)
        self.assertIn("Update", message)
        self.assertNotIn("data:image", message)
        self.assertNotIn("base64", message)


if __name__ == "__main__":
    unittest.main()
