"""Feedback sonoro local; observa o estado replicado (o servidor nao toca audio)."""
import math
from pathlib import Path
import pyray as rl
from EasyCells3D.Components import Component


class AudioFeedback(Component):
    def __init__(self, arena):
        self.arena = arena
        self.sounds = {}
        self.shot = 0
        self.health = 10000
        self.last_hit = self.last_kill = 0
        self.notice = ""
        self.owns_device = False
        self.colony_timer = 0.0
        self.ability = 0

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

    def play(self, name, volume=.35, pitch=1.0):
        if name in self.sounds:
            sound = self.sounds[name]
            rl.set_sound_volume(sound, volume)
            rl.set_sound_pitch(sound, pitch)
            rl.play_sound(sound)

    def loop(self):
        actor = self.arena.actors.get(self.game.session.local_slot)
        if actor is None:
            return
        state = self.arena.state
        if actor.shot != self.shot:
            self.play("shot", .3, 1.0 if actor.team == "cells" else .85)
        if actor.health.value < self.health and self.health < 10000:
            self.play("hurt")
        if actor.hit_marker > self.last_hit:
            self.play("hit")
        if actor.kill_marker > self.last_kill:
            self.play("hit", .5, 1.6)
        if actor.ability_cd > self.ability + .5:
            self.play("event", .25, 1.4)
        if state.notice != self.notice and state.notice:
            self.play("event", .35)
        # Nearby colonies pulse audibly (closer = louder and faster).
        nearest = min((math.dist(c['pos'], actor.feet) for c in state.colonies), default=99)
        self.colony_timer -= self.game.delta_time
        if nearest < 16 and actor.alive and self.colony_timer <= 0:
            self.play("event", .45*(1-nearest/16)+.05, .55)
            self.colony_timer = .6+nearest*.08
        self.shot, self.health, self.last_hit = actor.shot, actor.health.value, actor.hit_marker
        self.last_kill, self.notice, self.ability = actor.kill_marker, state.notice, actor.ability_cd

    def on_destroy(self):
        for sound in self.sounds.values():
            rl.unload_sound(sound)
        if self.owns_device:
            rl.close_audio_device()
