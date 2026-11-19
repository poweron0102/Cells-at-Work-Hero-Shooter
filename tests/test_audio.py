"""Gatilhos de som e de fala do ``AudioFeedback`` (motor real, sem dispositivo de audio)."""
import math
import unittest
from pathlib import Path
from unittest import mock
from simulation_support import headless_game, mount_arena, step
from EasyCells3D.Geometry import Vec3
from UserComponents.cells import settings, voice
from UserComponents.cells.audio import AudioFeedback, SFX
from UserComponents.cells.catalog import HEROES
from UserComponents.cells.session import connect
from UserComponents.cells.voice import ROOT as VOICES


class FakeVoices:
    """Substitui o VoiceBank: registra as falas pedidas em vez de toca-las."""
    def __init__(self):
        self.language, self.volume, self.playing, self.said, self.loaded = None, 1.0, {}, [], []

    def load(self, language):
        self.language = language
        self.loaded.append(language)

    def unload(self):
        pass

    def update(self, dt):
        pass

    def forget(self, key):
        pass

    def play(self, speaker, event, key=None, volume=1.0, pan=0.0, chance=1.0, force=False):
        self.said.append((speaker, event))
        return True


class RecordingAudio(AudioFeedback):
    def init(self):
        self.sounds = {name: [None] for name in SFX}
        self.voices = FakeVoices()
        self.played = []
        self.apply_settings()

    def play(self, name, volume=.35, pitch=1.0, pan=0.0):
        self.played.append(name)

    def on_destroy(self):
        pass


class AudioTriggerTests(unittest.TestCase):
    def setUp(self):
        self.game = headless_game()
        self.net = connect(self.game, "127.0.0.1", 0, True, "Audio test")
        self.net.start(True)
        for p in self.net.roster.value.values():
            p["bot"] = False
        self.arena = mount_arena(self.game)
        self.audio = self.game.CreateItem().AddComponent(RecordingAudio(self.arena))
        for _ in range(60):
            step(self.game)
        self.me = self.arena.actors[self.game.session.local_slot]
        self.enemy = next(a for a in self.arena.actors.values() if a.team != self.me.team)
        self.me.body.teleport(Vec3(0, 1, 60))
        self.enemy.body.teleport(Vec3(0, 1, 54))
        self.me.yaw = self.me.pitch = self.enemy.pitch = 0
        self.enemy.yaw = math.pi
        self.settle()
        self.audio.played.clear()
        self.audio.voices.said.clear()

    def tearDown(self):
        self.game.close()

    def settle(self, seconds=1/60):
        for _ in range(max(1, int(seconds*60))):
            step(self.game)

    def hero(self, actor, key):
        actor.hero = key
        actor.reset_kit()
        actor.health.value = HEROES[key].health
        actor.weapon.ammo = HEROES[key].magazine
        self.settle()

    def tap(self, actor, key):
        actor.controls = {key: True}
        self.settle()
        actor.controls = {}
        self.settle()

    def test_each_hero_fires_its_own_gun_sound(self):
        self.hero(self.me, 'macrophage')
        self.me.weapon.fire()
        self.settle()
        self.assertIn('shot_shotgun', self.audio.played)
        self.assertEqual(self.audio.played.count('shot_shotgun'), 1)  # chumbos contam como 1 disparo

    def test_ultimate_plays_stinger_and_hero_line(self):
        self.hero(self.me, 'neutrophil')
        self.me.charge = 100
        self.tap(self.me, 'ultimate')
        self.assertIn('ult', self.audio.played)
        self.assertIn(('neutrophil', 'ult'), self.audio.voices.said)

    def test_kill_plays_confirmation_and_kill_line(self):
        self.hero(self.me, 'killer_t')
        self.enemy.shield.value = 0
        self.enemy.damage(HEROES[self.enemy.hero].health*3, self.me)
        self.settle(.1)
        self.assertFalse(self.enemy.alive)
        self.assertIn('kill', self.audio.played)
        self.assertIn(('killer_t', 'kill'), self.audio.voices.said)

    def test_net_hit_says_capture_line(self):
        self.hero(self.me, 'neutrophil')
        self.tap(self.me, 'ability2')
        self.assertGreater(self.enemy.root, 0)
        self.assertIn('net', self.audio.played)
        self.assertIn(('neutrophil', 'net'), self.audio.voices.said)

    def test_receptor_beeps_when_an_enemy_drops_below_half(self):
        self.hero(self.me, 'neutrophil')
        self.enemy.health.value = HEROES[self.enemy.hero].health*.4
        self.settle()
        self.assertIn('receptor', self.audio.played)
        self.assertIn(('neutrophil', 'passive'), self.audio.voices.said)

    def test_changing_the_voice_language_reloads_the_lines(self):
        old = settings.get("voice_language")
        other = "en" if old == "ja" else "ja"
        try:
            settings._cache["voice_language"] = other   # sem gravar saves/config.json no teste
            settings.revision += 1
            self.settle()
            self.assertEqual(self.audio.voices.loaded[-1], other)
        finally:
            settings._cache["voice_language"] = old
            settings.revision += 1


class FakeSound:
    def __init__(self, name):
        self.name, self.playing = name, False


class FakeRaylib:
    """Só o que o VoiceBank usa; ``finish()`` encerra o clipe que está tocando."""
    def __init__(self):
        self.started = []

    def play_sound(self, sound):
        sound.playing = True
        self.started.append(sound.name)

    def stop_sound(self, sound):
        sound.playing = False

    def is_sound_playing(self, sound):
        return sound.playing

    def set_sound_volume(self, sound, volume):
        pass

    def set_sound_pan(self, sound, pan):
        pass


class VoiceArbitrationTests(unittest.TestCase):
    def setUp(self):
        self.rl = FakeRaylib()
        self.patch = mock.patch.object(voice, "rl", self.rl)
        self.patch.start()
        self.bank = voice.VoiceBank()
        for speaker in ("global", "neutrophil", "macrophage", "platelet"):
            for event in ("start", "spawn", "ult", "kill", "e", "go"):
                self.bank.lines[(speaker, event)] = [FakeSound(f"{speaker}/{event}")]

    def tearDown(self):
        self.patch.stop()

    def finish(self):
        self.bank.current['sound'].playing = False
        for _ in range(30):
            self.bank.update(.05)

    def test_match_start_lines_play_one_after_another(self):
        self.bank.play("global", "start")
        self.bank.play("neutrophil", "spawn", 0)
        self.bank.play("platelet", "go")
        self.assertEqual(self.rl.started, ["global/start"])
        self.finish()
        self.assertEqual(self.rl.started, ["global/start", "neutrophil/spawn"])

    def test_trivial_lines_are_dropped_while_someone_talks(self):
        self.bank.play("neutrophil", "kill", 0)
        self.assertFalse(self.bank.play("macrophage", "e", 1))
        self.finish()
        self.assertEqual(self.rl.started, ["neutrophil/kill"])

    def test_ultimate_cuts_a_trivial_line(self):
        self.bank.play("macrophage", "e", 1)
        self.bank.play("neutrophil", "ult", 0)
        self.assertEqual(self.rl.started, ["macrophage/e", "neutrophil/ult"])

    def test_queued_line_expires(self):
        self.bank.play("global", "start")
        self.bank.play("neutrophil", "spawn", 0)
        for _ in range(60):
            self.bank.update(.05)   # a abertura ainda fala por 3 s
        self.finish()
        self.assertEqual(self.rl.started, ["global/start"])

    def test_dead_speaker_leaves_the_queue(self):
        self.bank.play("global", "start")
        self.bank.play("neutrophil", "kill", 0)
        self.bank.forget(0)
        self.finish()
        self.assertEqual(self.rl.started, ["global/start"])


class VoiceAssetTests(unittest.TestCase):
    def test_every_hero_has_core_lines_in_both_languages(self):
        for language in ("ja", "en"):
            for hero in HEROES:
                for event in ("spawn", "kill", "ult"):
                    found = list((Path(VOICES)/language/hero).glob(f"{event}_*.ogg"))
                    self.assertTrue(found, f"{language}/{hero}/{event}")


if __name__ == "__main__":
    unittest.main()
