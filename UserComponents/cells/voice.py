"""Falas dos personagens (clipes do anime, japonês ou inglês).

Os arquivos ficam em ``Assets/audio/voice/<idioma>/<falante>/<evento>_<n>.ogg``; o evento
é o nome sem o sufixo numérico, então basta soltar um novo ``kill_5.ogg`` na pasta para
ele entrar no sorteio. Falantes = ids dos heróis + ``global`` (narração) + ``platelet``.
Gerados por ``scripts/build_voices.py`` (veja ``Assets/audio/voice/SOURCES.md``).

Eventos usados pelo ``AudioFeedback``:
``spawn`` ``kill`` ``ult`` ``death`` ``q`` ``e`` ``rmb`` ``punch`` ``net`` ``heal``
``passive`` ``win`` (heróis); ``start`` (global); ``go`` ``heave`` (plaquetas).

Uma fala por vez: falas sobrepostas ficam ininteligíveis. Se alguém já está falando, uma
fala importante (prioridade >= ``QUEUE_RANK``) espera numa fila curta e toca em seguida,
desde que não tenha "envelhecido" (``WAIT``); as triviais são descartadas. Só especial e
vitória interrompem uma fala trivial em andamento.
"""
import random
from pathlib import Path
import pyray as rl

ROOT = Path("Assets/audio/voice")

PRIORITY = {"ult": 5, "win": 5, "start": 4, "death": 3, "kill": 3, "heal": 3, "spawn": 2, "net": 2,
            "passive": 2, "go": 2, "punch": 1, "q": 1, "e": 1, "rmb": 1, "heave": 0}
# Intervalo mínimo entre falas do mesmo evento e falante (segundos).
COOLDOWN = {"q": 12.0, "e": 12.0, "rmb": 12.0, "punch": 10.0, "kill": 4.0, "heal": 6.0, "passive": 25.0,
            "spawn": 8.0, "heave": 20.0, "net": 6.0}
QUEUE_RANK = 2     # a partir daqui a fala espera a vez em vez de ser descartada
WAIT = {5: 4.0, 4: 3.0, 3: 2.0, 2: 1.5}   # validade na fila, por prioridade (s)
QUEUE_SIZE = 3
GAP = .2           # respiro entre duas falas seguidas (s)
INTERRUPT = 4      # prioridade que corta uma fala de prioridade <= 1 em andamento


class VoiceBank:
    """Carrega os clipes de um idioma e coordena quem fala (um de cada vez)."""

    def __init__(self):
        self.language = None
        self.lines = {}        # (falante, evento) -> [Sound]
        self.last = {}         # (falante, evento) -> índice sorteado da última vez
        self.current = None    # pedido tocando agora
        self.queue = []        # pedidos esperando a vez
        self.cooldown = {}     # (chave, evento) -> instante liberado
        self.clock = 0.0
        self.free_at = 0.0
        self.volume = 1.0

    # -- carga ------------------------------------------------------------------
    def load(self, language):
        self.unload()
        self.language = language
        folder = ROOT/language
        if not folder.is_dir():
            return
        for speaker in sorted(p for p in folder.iterdir() if p.is_dir()):
            for path in sorted(speaker.glob("*.ogg")):
                event = path.stem.rsplit("_", 1)[0]
                sound = rl.load_sound(str(path))
                if sound.frameCount:
                    self.lines.setdefault((speaker.name, event), []).append(sound)

    def unload(self):
        self.stop()
        for sounds in self.lines.values():
            for sound in sounds:
                rl.unload_sound(sound)
        self.lines, self.last = {}, {}

    def has(self, speaker, event):
        return (speaker, event) in self.lines

    # -- coordenação ------------------------------------------------------------
    @property
    def talking(self):
        return self.current is not None

    def update(self, dt):
        self.clock += dt
        if self.current is not None and not rl.is_sound_playing(self.current['sound']):
            self.current = None
            self.free_at = self.clock+GAP
        if self.current is None and self.clock >= self.free_at:
            self.queue = [r for r in self.queue if r['expire'] > self.clock]
            if self.queue:
                best = max(self.queue, key=lambda r: (r['rank'], -r['order']))
                self.queue.remove(best)
                self.start(best)

    def stop(self):
        if self.current is not None:
            rl.stop_sound(self.current['sound'])
        self.current, self.queue = None, []

    def forget(self, key):
        """Quem morreu ou saiu não termina a frase nem fala depois."""
        self.queue = [r for r in self.queue if r['key'] != key]
        if self.current is not None and self.current['key'] == key:
            rl.stop_sound(self.current['sound'])
            self.current = None

    def play(self, speaker, event, key=None, volume=1.0, pan=0.0, chance=1.0, force=False):
        """Pede uma fala de ``speaker``/``event``; ``key`` identifica quem fala (slot do ator).
        Devolve True se a fala tocou ou entrou na fila."""
        sounds = self.lines.get((speaker, event))
        if not sounds or volume <= .01:
            return False
        key = speaker if key is None else key
        if not force and self.cooldown.get((key, event), 0) > self.clock:
            return False
        if random.random() > chance:
            return False
        rank = PRIORITY.get(event, 1)
        request = dict(speaker=speaker, event=event, key=key, volume=volume, pan=pan, rank=rank,
                       expire=self.clock+WAIT.get(rank, 0.0), order=self.clock)
        current = self.current
        if current is None and self.clock >= self.free_at and not self.queue:
            self.start(request)
        elif current is not None and rank >= INTERRUPT and current['rank'] <= 1:
            rl.stop_sound(current['sound'])
            self.start(request)
        elif rank >= QUEUE_RANK:
            if (current is not None and current['key'] == key and current['event'] == event) or \
                    any(r['key'] == key and r['event'] == event for r in self.queue):
                return False
            self.queue.append(request)
            if len(self.queue) > QUEUE_SIZE:
                self.queue.remove(min(self.queue, key=lambda r: (r['rank'], -r['order'])))
            if request not in self.queue:
                return False
        else:
            return False
        self.cooldown[(key, event)] = self.clock+COOLDOWN.get(event, 0.0)
        return True

    def start(self, request):
        sounds = self.lines[(request['speaker'], request['event'])]
        index = random.randrange(len(sounds))
        previous = self.last.get((request['speaker'], request['event']))
        if len(sounds) > 1 and index == previous:
            index = (index+random.randrange(1, len(sounds))) % len(sounds)
        self.last[(request['speaker'], request['event'])] = index
        sound = sounds[index]
        rl.set_sound_volume(sound, max(0.0, min(1.0, request['volume']*self.volume)))
        rl.set_sound_pan(sound, max(-1.0, min(1.0, request['pan'])))
        rl.play_sound(sound)
        request['sound'] = sound
        self.current = request
