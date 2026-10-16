"""Keep native title bar appearance in sync without opening a real window."""

import unittest
from pathlib import Path
from unittest import mock

from steam_modern import DesktopApi


class DesktopThemeTests(unittest.TestCase):
    def test_theme_changes_reach_only_the_attached_window(self):
        api = DesktopApi(mock.Mock(), Path("unused.log"))
        window = mock.Mock()
        api._attach_window(window)
        with mock.patch("steam_modern._set_native_title_bar_theme") as setter:
            api.set_theme("light")
            setter.assert_called_once_with(window, dark=False)
            setter.reset_mock()
            api.set_theme("dark")
            setter.assert_called_once_with(window, dark=True)

    def test_unknown_theme_is_rejected_before_native_calls(self):
        api = DesktopApi(mock.Mock(), Path("unused.log"))
        with mock.patch("steam_modern._set_native_title_bar_theme") as setter:
            with self.assertRaisesRegex(RuntimeError, "未知界面主题"):
                api.set_theme("invalid")
            setter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
