"""Preferências (``settings``) e lógica da tela de configurações (``options``), sem janela."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pyray as rl
from UserComponents.cells import settings
from UserComponents.cells.options import SettingsScreen, blocking, _rows
from UserComponents.cells.ui_base import Canvas


class IsolatedSettings(unittest.TestCase):
    """Cada teste usa um config.json temporário e um cache limpo."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patches = [mock.patch.object(settings, "PATH", Path(self.tmp.name) / "config.json"),
                   mock.patch.object(settings, "_cache", None), mock.patch.object(settings, "_dirty", False)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def saved(self):
        return json.loads(settings.PATH.read_text(encoding="utf-8"))


class SettingsTests(IsolatedSettings):
    def test_corrupted_values_fall_back_to_defaults(self):
        settings.PATH.write_text(json.dumps({
            "fov": "wide", "fps_limit": 75, "display_mode": "exclusive", "vsync": "yes", "resolution": "big",
            "mouse_sensitivity": 99, "master_volume": -3, "unknown": 1}), encoding="utf-8")
        self.assertEqual(settings.get("fov"), 75)
        self.assertEqual(settings.get("fps_limit"), 60)
        self.assertEqual(settings.get("display_mode"), "window")
        self.assertIs(settings.get("vsync"), False)
        self.assertEqual(settings.get("resolution"), "1280x720")
        self.assertEqual(settings.get("mouse_sensitivity"), 4.0)  # fora da faixa: grampeia
        self.assertEqual(settings.get("master_volume"), 0.0)
        self.assertNotIn("unknown", settings.load())

    def test_old_config_files_keep_their_values(self):
        settings.PATH.write_text(json.dumps({"voice_language": "en", "sfx_volume": .5}), encoding="utf-8")
        self.assertEqual(settings.get("voice_language"), "en")
        self.assertEqual(settings.get("sfx_volume"), .5)
        self.assertEqual(settings.get("shadow_quality"), "high")

    def test_set_value_sanitizes_and_bumps_revision(self):
        before = settings.revision
        settings.set_value("fov", 140.7)
        self.assertEqual(settings.get("fov"), 110)
        self.assertGreater(settings.revision, before)
        self.assertEqual(self.saved()["fov"], 110)

    def test_dragging_defers_the_write_until_save(self):
        settings.set_value("sfx_volume", .3, save_now=False)
        self.assertFalse(settings.PATH.exists())
        settings.save()
        self.assertEqual(self.saved()["sfx_volume"], .3)

    def test_reset_restores_only_the_given_keys(self):
        settings.set_value("fov", 100)
        settings.set_value("invert_y", True)
        settings.reset(["fov"])
        self.assertEqual(settings.get("fov"), 75)
        self.assertIs(settings.get("invert_y"), True)


class SettingsScreenTests(IsolatedSettings):
    def screen(self):
        screen = SettingsScreen()
        screen.item = SimpleNamespace(game=SimpleNamespace(time=1000.0))  # Component.game = item.game
        return screen

    def test_every_row_points_at_a_known_setting(self):
        for tab, rows in _rows().items():
            for key, kind, *_ in rows:
                self.assertIn(key, settings.DEFAULTS, tab)
                if kind == "slider":
                    self.assertIn(key, settings.RANGES)

    def test_slider_snaps_to_its_step_and_clamps(self):
        screen = self.screen()
        track = rl.Rectangle(100, 0, 200, 1)
        screen.slide((track, "fov", 60, 110, 1), 100 + 200 * .503)
        self.assertEqual(settings.get("fov"), 85)
        screen.slide((track, "fov", 60, 110, 1), 9999)
        self.assertEqual(settings.get("fov"), 110)

    def test_choice_cycles_both_ways(self):
        screen = self.screen()
        options = settings.CHOICES["fps_limit"]
        screen.cycle("fps_limit", options, 1)
        self.assertEqual(settings.get("fps_limit"), 120)
        screen.cycle("fps_limit", options, -1)
        screen.cycle("fps_limit", options, -1)
        self.assertEqual(settings.get("fps_limit"), 30)
        screen.cycle("fps_limit", options, -1)
        self.assertEqual(settings.get("fps_limit"), 0)  # volta para "sem limite"

    def test_open_panel_blocks_other_screens_until_the_next_frame_after_closing(self):
        screen = self.screen()
        game = screen.game
        game.options = screen
        other = Canvas()
        other.item = screen.item
        self.assertFalse(blocking(game))
        screen.open()
        self.assertTrue(blocking(game))
        self.assertTrue(other.blocked())
        self.assertFalse(screen.blocked())  # o próprio painel continua recebendo cliques
        screen.close()
        self.assertTrue(blocking(game))  # mesmo quadro: o Esc/clique que fechou não vaza
        game.time += 16
        self.assertFalse(blocking(game))
        self.assertFalse(other.blocked())


if __name__ == "__main__":
    unittest.main()
