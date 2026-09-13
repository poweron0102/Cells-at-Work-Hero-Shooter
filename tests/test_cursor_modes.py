import unittest
from unittest.mock import patch

from UserComponents.cells.cursor import set_cursor_captured


class CursorModeTests(unittest.TestCase):
    @patch("UserComponents.cells.cursor.rl.enable_cursor")
    @patch("UserComponents.cells.cursor.rl.is_cursor_hidden", return_value=True)
    def test_releasing_cursor_makes_it_available_for_ui(self, _hidden, enable):
        set_cursor_captured(False)
        enable.assert_called_once_with()

    @patch("UserComponents.cells.cursor.rl.disable_cursor")
    @patch("UserComponents.cells.cursor.rl.is_cursor_hidden", return_value=False)
    def test_capturing_cursor_is_reserved_for_gameplay(self, _hidden, disable):
        set_cursor_captured(True)
        disable.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
