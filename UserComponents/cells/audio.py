"""Local feedback observes replicated state; the server does not play client audio."""
from pathlib import Path
import pyray as rl
from EasyCells3D.Components import Component


class AudioFeedback(Component):
    def __init__(self, arena):
        self.arena = arena
        self.sounds = {}
        self.shot = self.event = 0
        self.health = 10000
        self.last_hit = 0
        self.owns_device = False

    def init(self):
        if not rl.is_audio_device_ready():
            rl.init_audio_device()
            self.owns_device = rl.is_audio_device_ready()
        if rl.is_audio_device_ready():
            for name in ("shot", "hit", "hurt", "event"):
                path = Path("Assets/audio") / f"{name}.wav"
                if path.exists():
                    sound = rl.load_sound(str(path))
                    rl.set_sound_volume(sound, .35)
                    self.sounds[name] = sound

    def play(self, name):
        if name in self.sounds:
            rl.play_sound(self.sounds[name])

    def loop(self):
        actor = self.arena.actors.get(self.game.session.local_slot)
        if actor is None:
            return
        if actor.shot != self.shot:
            self.play("shot")
        if actor.health.value < self.health and self.health < 10000:
            self.play("hurt")
        if actor.hit_marker > self.last_hit:
            self.play("hit")
        if self.arena.state.event_index != self.event:
            self.play("event")
        self.shot, self.health, self.last_hit = actor.shot, actor.health.value, actor.hit_marker
        self.event = self.arena.state.event_index

    def on_destroy(self):
        for sound in self.sounds.values():
            rl.unload_sound(sound)
        if self.owns_device:
            rl.close_audio_device()
