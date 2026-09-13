"""Global mouse mode used by gameplay and screen-space interfaces."""
import pyray as rl


def set_cursor_captured(captured: bool) -> None:
    """Capture the mouse only while gameplay is actively reading mouse deltas."""
    if captured:
        if not rl.is_cursor_hidden():
            rl.disable_cursor()
    elif rl.is_cursor_hidden():
        rl.enable_cursor()
