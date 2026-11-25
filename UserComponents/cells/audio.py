"""Feedback sonoro local; observa o estado replicado (o servidor nao toca audio).

Tudo aqui so le o estado que ja chega em cada cliente (atores, efeitos, tracos, zonas,
paredes, torretas), entao nao ha RPC novo: cada peer decide sozinho o que tocar.
Sons do mundo sao posicionados (volume pela distancia, pan pela direcao); os do proprio
jogador tocam cheios. Vozes: ``voice.VoiceBank``; idioma em ``settings``.
"""
import math
import random
from pathlib import Path
import pyray as rl
from EasyCells3D.Components import Component
from . import settings
from .catalog import HEROES, CELLS, BACTERIA
from .voice import VoiceBank

AUDIO = Path("Assets/audio")
# Copias simultaneas de cada som (aliases do raylib): tiros se sobrepoem muito.
POLY = {"shot_rifle": 8, "shot_shotgun": 4, "shot_sniper": 3, "shot_organic": 8, "shot_spit": 6,
        "hit": 4, "pop": 4, "swing": 3, "punch": 3}
SFX = ("shot_rifle", "shot_shotgun", "shot_sniper", "shot_organic", "shot_spit", "reload", "swing", "punch",
       "slam", "dash", "explosion", "splash", "net", "chain", "needle", "ult", "ult_ready", "kill", "death",
       "respawn", "heal", "shield", "absorb", "receptor", "turret", "wall", "crumble", "pop", "hiss", "rain",
       "hit", "hurt", "event", "heartbeat")

# Arma principal de cada heroi: (som, pitch).
GUN = {"neutrophil": ("shot_rifle", 1.0), "macrophage": ("shot_shotgun", 1.0), "b_cell": ("shot_sniper", 1.05),
       "killer_t": ("shot_rifle", .82), "pneumococcus": ("shot_organic", .85), "staphylococcus": ("shot_organic", 1.1),
       "pseudomonas": ("shot_spit", 1.0), "streptococcus": ("shot_organic", 1.35)}
# Tracos de habilidade (actor.fire_kind) -> (som, pitch).
TRACE = {"net": ("net", 1.0), "hook": ("chain", 1.0), "chain": ("chain", 1.2), "flagellum": ("chain", .8),
         "perforin": ("needle", 1.0), "toxin": ("shot_spit", 1.3), "capsule": ("shield", 1.0),
         "sticky": ("shot_organic", .75)}
# Efeitos replicados (arena.effects) -> (som, pitch, volume).
EFFECT = {"heal": ("heal", 1.0, .5), "repair": ("heal", .8, .4), "backstab": ("punch", 1.3, .8),
          "punch": ("punch", 1.0, .9), "slam": ("slam", 1.0, 1.0), "antibody": ("explosion", 1.2, .8),
          "burst": ("splash", 1.0, .8), "ult": ("ult", 1.0, .9), "spit": ("slam", .8, 1.0),
          "perforin": ("needle", .6, .8), "pop": ("pop", 1.0, .6), "spawn": ("pop", .7, .5),
          "crumble": ("crumble", 1.0, .8), "shatter": ("crumble", 1.3, .6), "launch": ("dash", .7, .8)}
ZONE = {"cloud": ("hiss", .8, .7), "rain": ("rain", 1.0, .9), "acid": ("hiss", 1.3, .35),
        "biofilm": ("splash", .6, .6), "dome": ("shield", .7, .8), "mature": ("hiss", .6, .7)}
THROW = {"acid": ("swing", .8, .6), "antibody": ("swing", .9, .6)}
DASH_PITCH = {"neutrophil": 1.15, "pneumococcus": .8, "pseudomonas": 1.0, "streptococcus": 1.3}
HEARING = 45.0     # alcance de sons do mundo (m)
VOICE_RANGE = 28.0  # alcance de falas de outros jogadores (m)


class AudioFeedback(Component):
    def __init__(self, arena):
        self.arena = arena
        self.sounds = {}       # nome -> [Sound, aliases...]
        self.next = {}         # nome -> proximo indice do rodizio
        self.voices = VoiceBank()
        self.settings_rev = -1
        self.owns_device = False
        self.tracked = {}      # slot -> estado anterior do ator
        self.me_prev = None
        self.colony_timer = 0.0
        self.notice = ""
        self.winner = ""
        self.started = False
        self.platelet_timer = 2.0
        self.escort = 0.0
        self.go_timer = -1.0
        self.walls, self.minions = set(), set()
        self.systole = None     # coracao: fase anterior do batimento
        self.valves = {}        # coracao: estado anterior de cada valva (aberta?)

    # -- carga ----------------------------------------------------------------
    def init(self):
        if not rl.is_audio_device_ready():
            rl.init_audio_device()
            self.owns_device = rl.is_audio_device_ready()
        if not rl.is_audio_device_ready():
            return
        for name in SFX:
            path = AUDIO/f"{name}.wav"
            if path.exists():
                base = rl.load_sound(str(path))
                self.sounds[name] = [base]+[rl.load_sound_alias(base) for _ in range(POLY.get(name, 2)-1)]
                self.next[name] = 0
        self.apply_settings()

    def apply_settings(self):
        self.settings_rev = settings.revision
        self.sfx_volume = float(settings.get("sfx_volume"))
        self.voices.volume = float(settings.get("voice_volume"))
        language = settings.get("voice_language")
        if language != self.voices.language:
            self.voices.load(language)

    # -- reproducao -----------------------------------------------------------
    def play(self, name, volume=.35, pitch=1.0, pan=0.0):
        copies = self.sounds.get(name)
        if not copies or volume <= .01:
            return
        i = self.next[name]
        self.next[name] = (i+1) % len(copies)
        sound = copies[i]
        rl.set_sound_volume(sound, min(1.0, volume*self.sfx_volume))
        rl.set_sound_pitch(sound, pitch*random.uniform(.96, 1.04))
        rl.set_sound_pan(sound, pan)
        rl.play_sound(sound)

    def listener(self):
        me = self.arena.actors.get(self.game.session.local_slot)
        if me is None:
            # Sem herói local (replay): quem quiser ouvir de outro ponto registra ``game.audio_listener``.
            hook = getattr(self.game, "audio_listener", None)
            return hook() if hook else None
        return me.eye.to_tuple, me.yaw

    def spatial(self, position, reach=HEARING):
        """(ganho 0..1, pan) de um som em ``position`` para o jogador local."""
        ear = self.listener()
        if ear is None or position is None:
            return 1.0, 0.0
        (x, y, z), yaw = ear
        dx, dy, dz = position[0]-x, position[1]-y, position[2]-z
        dist = math.sqrt(dx*dx+dy*dy+dz*dz)
        gain = max(0.0, 1-dist/reach)**1.6
        if dist < 1.5:
            return gain, 0.0
        right = (dx*math.cos(yaw)+dz*math.sin(yaw))/dist
        return gain, max(-1.0, min(1.0, right*.7))

    def play_at(self, name, position, volume=.35, pitch=1.0, reach=HEARING):
        gain, pan = self.spatial(position, reach)
        self.play(name, volume*gain, pitch, pan)

    def is_me(self, actor):
        """O heroi deste computador. (``actor.local`` tambem vale para os bots que o anfitriao
        simula, que devem soar como qualquer outro jogador.)"""
        return actor is not None and actor.slot == self.game.session.local_slot

    def say(self, actor, event, chance=1.0, force=False, floor=0.0):
        """Fala do heroi ``actor``: cheia se for o jogador local, posicionada se nao."""
        if self.is_me(actor):
            return self.voices.play(actor.hero, event, actor.slot, 1.0, 0.0, chance, force)
        gain, pan = self.spatial(actor.transform.position.to_tuple, VOICE_RANGE)
        return self.voices.play(actor.hero, event, actor.slot, max(floor, gain)*.85, pan, chance, force)

    # -- laco -----------------------------------------------------------------
    def loop(self):
        if not self.sounds:
            return
        if self.settings_rev != settings.revision:
            self.apply_settings()
        dt = self.game.delta_time
        self.voices.update(dt)
        if self.game.session.status != "playing":
            return
        state = self.arena.state
        if not self.started:
            self.started = True
            if state.elapsed < 8:
                self.voices.play("global", "start", force=True)
                self.go_timer = 1.6
        if self.go_timer > 0:
            self.go_timer -= dt
            if self.go_timer <= 0:
                self.voices.play("platelet", "go", volume=.8)
        for actor in list(self.arena.actors.values()):
            self.watch_actor(actor)
        self.watch_world()
        me = self.arena.actors.get(self.game.session.local_slot)
        if me is not None:
            self.watch_me(me, dt)
        if state.notice != self.notice and state.notice:
            self.play("event", .35)
        self.notice = state.notice
        if state.winner and state.winner != self.winner:
            self.voices.play("neutrophil" if state.winner == CELLS else "pneumococcus", "win", "narrator",
                             force=True)
        self.winner = state.winner
        self.watch_platelets(me, dt)
        self.watch_heart()

    def watch_heart(self):
        """Coracao: "tum-tum" a cada sistole e o baque dos portoes das valvas (posicionado)."""
        arena = self.arena
        if not arena.valves:
            return
        from .heart import beat
        systole = beat(arena.state.elapsed)[0]
        if systole and self.systole is False:
            self.play("heartbeat", .5)
        self.systole = systole
        for v in arena.valves:
            opened = arena.valve_open.get(v['id'], True)
            before = self.valves.get(v['id'])
            if before is not None and opened != before:
                self.play_at("slam", tuple(v['pos']), .7, .62 if not opened else .9, 40.0)
            self.valves[v['id']] = opened

    def watch_actor(self, actor):
        """Eventos visiveis de qualquer ator: tiros, especial, mortes (com a fala do autor)."""
        prev = self.tracked.get(actor.slot)
        ult = 'ult' in actor.fx or actor.ult_on
        now = dict(serial=actor.fire_serial, alive=actor.alive, ult=ult, hero=actor.hero)
        self.tracked[actor.slot] = now
        if prev is None:
            return
        position = actor.transform.position.to_tuple
        if now['serial'] != prev['serial'] and actor.alive:
            kind = actor.fire_kind
            name, pitch = GUN.get(actor.hero, ("shot_rifle", 1.0)) if kind == 'shot' else TRACE.get(kind, (None, 1))
            if name:
                if self.is_me(actor):
                    self.play(name, .3 if kind == 'shot' else .45, pitch)
                else:
                    self.play_at(name, position, .32, pitch)
        if ult and not prev['ult']:
            self.say(actor, "ult", force=True, floor=.35 if actor.team != self.local_team() else .2)
        if prev['alive'] and not actor.alive:
            self.voices.forget(actor.slot)
            self.say(actor, "death")
            killer = self.arena.actors.get(actor.killer) if actor.killer is not None else None
            if killer is not None and not self.is_me(killer) and killer.alive:
                self.say(killer, "kill", chance=.35)

    def local_team(self):
        me = self.arena.actors.get(self.game.session.local_slot)
        return me.team if me is not None else None

    def watch_world(self):
        arena = self.arena
        for fx in arena.effects:
            if fx.get('_heard'):
                continue
            fx['_heard'] = True
            spec = EFFECT.get(fx['kind'])
            if spec:
                self.play_at(spec[0], fx['pos'], spec[2], spec[1])
        for tr in arena.tracers:
            if tr.get('_heard'):
                continue
            tr['_heard'] = True
            if tr['kind'] in ('turret', 'clone'):
                name, pitch = ("shot_rifle", 1.35) if tr['kind'] == 'turret' else ("shot_organic", 1.45)
                self.play_at(name, tr['a'], .22, pitch)
        for zone in arena.zones:
            if zone.get('_heard'):
                continue
            zone['_heard'] = True
            spec = ZONE.get(zone['kind'])
            if spec:
                self.play_at(spec[0], zone['pos'], spec[2], spec[1])
        for p in arena.projectiles:
            if p.get('_heard'):
                continue
            p['_heard'] = True
            spec = THROW.get(p['kind'])
            if spec:
                self.play_at(spec[0], p['pos'], spec[2], spec[1])
            owner = arena.actors.get(p['slot'])
            if self.is_me(owner):
                self.say(owner, "rmb" if p['kind'] == 'acid' else "e", chance=.45)
        for ident in set(arena.walls)-self.walls:
            self.play_at("wall", arena.walls[ident]['pos'], .7)
        self.walls = set(arena.walls)
        for ident in set(arena.minions)-self.minions:
            m = arena.minions[ident]
            if m['kind'] == 'turret':
                self.play_at("turret", m['pos'], .7)
        self.minions = set(arena.minions)

    def watch_me(self, me, dt):
        """Sons e falas que so o proprio jogador ouve (marcadores, recarga, cooldowns)."""
        state = self.arena.state
        weapon = getattr(me, 'weapon', None)
        now = dict(hero=me.hero, alive=me.alive, health=me.health.value, hit=me.hit_marker, kill=me.kill_marker,
                   ability=me.ability_cd, ability2=me.ability2_cd, dash=me.dash, swing=me.swing,
                   absorbed=me.absorbed_fx, charge=me.charge, reload=weapon.reload_time if weapon else 0,
                   lowhp=self.low_enemies(me), front=me.front, charges=me.q_charges)
        prev, self.me_prev = self.me_prev, now
        if prev is None or prev['hero'] != now['hero']:
            if me.alive:
                self.say(me, "spawn")
            return
        if not prev['alive'] and me.alive:
            self.play("respawn", .35)
            self.say(me, "spawn", chance=.6)
        if prev['alive'] and not me.alive:
            self.play("death", .45)
        if not me.alive:
            return
        if now['health'] < prev['health']:
            self.play("hurt", .35)
        if now['hit'] > prev['hit']:
            self.play("hit", .3)
        if now['kill'] > prev['kill']:
            self.play("kill", .45)
            healed = me.hero == 'macrophage' and now['health'] > prev['health']
            if not (healed and self.say(me, "heal")):
                self.say(me, "kill", chance=.75)
        if now['absorbed'] > prev['absorbed']:
            self.play("absorb", .35, random.uniform(.9, 1.1))
        if now['charge'] >= 100 > prev['charge']:
            self.play("ult_ready", .4)
        if now['reload'] > prev['reload'] + .5:
            self.play("reload", .35, 1.2 if me.hero in HEROES and HEROES[me.hero].team == BACTERIA else 1.0)
        if now['swing'] != prev['swing']:
            self.play("swing", .35)
        if now['dash'] > prev['dash'] + .05:
            self.play("dash", .4, DASH_PITCH.get(me.hero, 1.0))
        # Q por cargas (Streptococcus) nao mexe no cooldown: conta a carga gasta.
        if now['ability'] > prev['ability'] + .3 or (me.hero == 'streptococcus' and now['charges'] < prev['charges']):
            if me.hero == 'killer_t':
                self.play("dash", .45, .7)
            self.say(me, "q", chance=.45)
        if now['ability2'] > prev['ability2'] + .3:
            self.say(me, "e", chance=.45)
        # Engolir da Macrofago (botao direito segurado): comentario ao abrir a membrana.
        if me.hero == 'macrophage' and now['front'] == 'engulf' and prev['front'] != 'engulf':
            self.say(me, "rmb", chance=.4)
        # Receptor do Neutrofilo: algum inimigo acabou de ficar visivel (vida < 50%).
        if me.hero == 'neutrophil' and now['lowhp'] and not prev['lowhp']:
            self.play("receptor", .4)
            self.say(me, "passive")
        for fx in self.arena.effects:
            if fx['kind'] == 'punch' and not fx.get('_voiced') and me.hero == 'killer_t' and fx['radius'] > 1.2 \
                    and math.dist(fx['pos'], me.eye.to_tuple) < 3:
                fx['_voiced'] = True
                self.say(me, "punch", chance=.6)
        for tr in self.arena.tracers:
            if tr['kind'] == 'net' and tr.get('slot') == me.slot and tr.get('impact') == 'actor' \
                    and not tr.get('_voiced'):
                tr['_voiced'] = True
                self.say(me, "net", force=True)
        # Colonias proximas pulsam (mais perto = mais alto e mais rapido).
        nearest = min((math.dist(c['pos'], me.feet) for c in state.colonies), default=99)
        self.colony_timer -= dt
        if nearest < 16 and self.colony_timer <= 0:
            self.play("event", .45*(1-nearest/16)+.05, .55)
            self.colony_timer = .6+nearest*.08

    def low_enemies(self, me):
        if me.hero != 'neutrophil':
            return 0
        return sum(1 for a in self.arena.actors.values()
                   if a.team != me.team and a.alive and a.health.value < HEROES[a.hero].health*.5)

    def watch_platelets(self, me, dt):
        """Plaquetas avancando perto do jogador: "Heave-ho!" de vez em quando."""
        state = self.arena.state
        moving = state.escort > self.escort+1e-4
        self.escort = state.escort
        self.platelet_timer -= dt
        if not moving or me is None or self.platelet_timer > 0 or state.winner:
            return
        head = self.arena.path.at(state.escort)
        gain, pan = self.spatial(head, 22.0)
        if gain > .05:
            self.voices.play("platelet", "heave", volume=gain*.7, pan=pan)
            self.platelet_timer = random.uniform(14, 26)

    def on_destroy(self):
        self.voices.unload()
        for copies in self.sounds.values():
            for alias in copies[1:]:
                rl.unload_sound_alias(alias)
            rl.unload_sound(copies[0])
        if self.owns_device:
            rl.close_audio_device()
