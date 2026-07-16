import os
import unittest
from unittest.mock import patch

from web.routes import settings


class SettingsSecurityTests(unittest.TestCase):
    def test_get_settings_redacts_stored_credentials(self):
        stored = {
            "upload_post_key": "private-upload-key",
            "fish_audio_key": "private-fish-key",
            "schedule_hour": "18",
        }
        llm_status = {"proxy_url": "http://127.0.0.1:3458", "model": "gpt-test"}

        with patch.object(settings, "get_all_settings", return_value=stored.copy()):
            with patch("web.claude_client.get_llm_status", return_value=llm_status):
                with patch.dict(os.environ, {}, clear=False):
                    result = settings.get_settings()

        self.assertEqual(result["upload_post_key"], "")
        self.assertEqual(result["fish_audio_key"], "")
        self.assertTrue(result["upload_post_key_set"])
        self.assertTrue(result["fish_audio_key_set"])
        self.assertEqual(result["schedule_hour"], "18")

    def test_blank_password_fields_do_not_erase_existing_credentials(self):
        body = settings.SettingsUpdate(
            upload_post_key="",
            fish_audio_key="   ",
            autopilot_enabled="false",
        )

        with patch.object(settings, "set_setting") as set_setting:
            with patch.object(settings, "get_settings", return_value={}):
                settings.update_settings(body)

        set_setting.assert_called_once_with("autopilot_enabled", "false")


if __name__ == "__main__":
    unittest.main()
