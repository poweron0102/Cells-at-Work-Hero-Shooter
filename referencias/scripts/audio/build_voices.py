"""Extrai as falas dos personagens dos episódios do anime (ver ``referencias/audio/voice_clips.json``).

Para cada clipe e idioma (``ja`` = áudio original, ``en`` = dublagem):
1. recorta o trecho do .mkv (faixa ``jpn``/``eng``) com folga;
2. separa a voz da música/efeitos com Demucs (htdemucs);
3. apara o silêncio nas pontas, corta graves (< 70 Hz) e normaliza o volume;
4. grava ``Assets/audio/voice/<idioma>/<falante>/<evento>_<n>.ogg``.

Requer ffmpeg no PATH e um Python com ``demucs``, ``torch`` e ``soundfile``
(fica fora do requirements.txt do jogo por ser pesado):

    python -m venv .voice-env
    .voice-env/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    .voice-env/Scripts/python -m pip install demucs soundfile
    .voice-env/Scripts/python referencias/scripts/audio/build_voices.py --episodes "D:/Series e Filmes/Cells at Work!"

Opções: ``--lang ja|en`` (padrão: os dois), ``--only <id>`` (repetível), ``--work <pasta>``
para guardar os intermediários (padrão: pasta temporária). ``--sources`` só reescreve
``referencias/audio/SOURCES.md`` a partir do manifesto (não precisa de Demucs nem dos episódios).

Manifesto: cada clipe tem ``episode``, ``use`` (arquivos gerados) e, por idioma, ``time``
(início/fim em segundos no .mkv), ``text`` e opcionalmente ``trim`` ([início, fim] em s,
ajuste fino da janela) e ``skip`` (motivo para não gerar aquele idioma).
"""
import argparse
import glob
import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REFS = ROOT/"referencias"/"audio"
MANIFEST = REFS/"voice_clips.json"
OUT = ROOT/"Assets"/"audio"/"voice"
TRACK = {"ja": "jpn", "en": "eng"}
PAD = 1.0          # folga extraída antes/depois (contexto para o Demucs)
SR = 44100


EVENTS = {"spawn": "entrar em campo", "kill": "eliminação", "ult": "especial (F)", "death": "morte",
          "q": "habilidade Q", "e": "habilidade E", "rmb": "botão direito", "punch": "soco carregado",
          "net": "Rede NET acerta", "heal": "Fagocitose (cura ao eliminar)", "passive": "Receptor detecta inimigo",
          "win": "vitória do time", "start": "início da partida", "go": "início da escolta",
          "heave": "plaquetas avançando"}
SOURCES_HEAD = """# Falas dos personagens

Clipes de voz recortados dos episódios de *Cells at Work!* (*Hataraku Saibou*, temporada 1),
com a voz isolada da trilha e dos efeitos pelo Demucs. `ja/` usa o áudio original japonês e
`en/` a dublagem em inglês. O conteúdo pertence aos detentores dos direitos do anime
(Akane Shimizu/Kodansha, Aniplex, David Production; dublagem: Crunchyroll/Funimation) e é usado
aqui apenas neste protótipo de fã, sem fins comerciais.

- Manifesto (episódio, tempos, textos, ajustes): [`referencias/audio/voice_clips.json`](voice_clips.json)
- Geração: [`referencias/scripts/audio/build_voices.py`](../scripts/audio/build_voices.py) (instruções no topo do arquivo;
  esta página sai de `build_voices.py --sources`)
- Uso no jogo: `UserComponents/cells/voice.py` e `audio.py`; idioma em `saves/config.json`
  (`{"voice_language": "en"}`) ou `CELLS_VOICE=en`. Padrão: `ja`.

O falante de cada trecho foi conferido pelos quadros do vídeo no momento da fala. As legendas
seguem o áudio japonês; na dublagem, o trecho foi localizado transcrevendo a mesma cena (Whisper),
e os clipes finais dos dois idiomas foram transcritos de novo para conferir o conteúdo.

| Arquivo | Evento | Ep. | JA (tempo · legenda) | EN (tempo · fala) |
| --- | --- | --- | --- | --- |
"""


def stamp(seconds):
    return f"{int(seconds)//60:02d}:{int(seconds)%60:02d}"


def write_sources(clips):
    def cell(take):
        if not take or take.get("skip"):
            return "—"
        return f"{stamp(take['time'][0])} · {take['text']}"
    rows = sorted((target, clip) for clip in clips for target in clip["use"])
    lines = []
    for target, clip in rows:
        event = target.split("/")[1].rsplit("_", 1)[0]
        lines.append(f"| `{target}.ogg` | {EVENTS.get(event, event)} | {clip['episode']} | "
                     f"{cell(clip.get('ja'))} | {cell(clip.get('en'))} |")
    (REFS/"SOURCES.md").write_text(SOURCES_HEAD+"\n".join(lines)+"\n", encoding="utf-8")


def save_manifest(data):
    """Um clipe por linha: diffs legíveis quando um tempo é ajustado."""
    body = ",\n".join("  "+json.dumps(c, ensure_ascii=False) for c in data["clips"])
    note = json.dumps(data["note"], ensure_ascii=False)
    MANIFEST.write_text(f'{{\n "note": {note},\n "clips": [\n{body}\n ]\n}}\n', encoding="utf-8")


def episode_file(folder, episode):
    found = glob.glob(os.path.join(folder, "**", f"{episode}*.mkv"), recursive=True)
    if not found:
        raise FileNotFoundError(f"{episode}*.mkv em {folder}")
    return found[0]


def extract(mkv, lang, start, end, dest):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start-PAD:.3f}", "-i", mkv,
                    "-t", f"{end-start+2*PAD:.3f}", "-map", f"0:a:m:language:{TRACK[lang]}",
                    "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", str(dest)], check=True)


class Separator:
    def __init__(self, name="htdemucs"):
        import torch
        from demucs.pretrained import get_model
        from demucs.apply import apply_model
        self.torch, self.apply_model = torch, apply_model
        self.model = get_model(name)
        self.model.eval()
        self.index = self.model.sources.index("vocals")

    def vocals(self, path):
        import soundfile as sf
        wav, sr = sf.read(str(path), dtype="float32", always_2d=True)
        x = self.torch.from_numpy(wav.T.copy())
        ref = x.mean(0)
        mean, std = ref.mean(), ref.std()+1e-8
        with self.torch.no_grad():
            y = self.apply_model(self.model, ((x-mean)/std)[None], shifts=1, split=True, overlap=.25,
                                 progress=False)[0]
        return (y[self.index]*std+mean).numpy().T, sr


def clean(voice, sr, length, trim=(0.0, 0.0)):
    """Mono, janela da fala (+ ajuste manual ``trim`` em s), apara silêncio e normaliza."""
    import numpy as np
    x = voice.mean(axis=1)
    a = int(sr*(PAD-.15+trim[0]))
    b = int(sr*(PAD+length+.3+trim[1]))
    x = x[max(0, a):min(len(x), b)]
    # passa-altas simples (graves que sobram da trilha)
    spec = np.fft.rfft(x)
    spec[np.fft.rfftfreq(len(x), 1/sr) < 70] = 0
    x = np.fft.irfft(spec, len(x))
    hop = int(sr*.01)
    frames = len(x)//hop
    rms = np.sqrt(np.mean(x[:frames*hop].reshape(frames, hop)**2, axis=1))+1e-9
    db = 20*np.log10(rms)
    loud = np.nonzero(db > max(-48.0, db.max()-30))[0]
    if len(loud):
        x = x[max(0, loud[0]*hop-int(sr*.05)):min(len(x), (loud[-1]+1)*hop+int(sr*.15))]
        voiced = rms[loud[0]:loud[-1]+1]
        level = np.sqrt(np.mean(voiced[voiced > 10**((db.max()-20)/20)]**2))
        x = x*min(10**(-16/20)/level, .9/(np.max(np.abs(x))+1e-9))
    fade_in, fade_out = int(sr*.012), int(sr*.06)
    x[:fade_in] *= np.linspace(0, 1, fade_in)
    x[-fade_out:] *= np.linspace(1, 0, fade_out)
    return x


def encode(samples, sr, dest):
    import soundfile as sf
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp.wav")
    sf.write(str(tmp), samples, sr, subtype="PCM_16")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-c:a", "libvorbis", "-q:a", "5",
                    str(dest)], check=True)
    tmp.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", help="pasta com os .mkv (busca recursiva)")
    parser.add_argument("--lang", choices=sorted(TRACK), action="append")
    parser.add_argument("--only", action="append")
    parser.add_argument("--work")
    parser.add_argument("--sources", action="store_true", help="só reescreve SOURCES.md")
    args = parser.parse_args()
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    save_manifest(data)
    write_sources(data["clips"])
    if args.sources:
        return
    if not args.episodes:
        parser.error("--episodes é obrigatório para gerar os áudios")
    clips = data["clips"]
    if args.only:
        clips = [c for c in clips if c["id"] in args.only]
    work = Path(args.work or tempfile.mkdtemp(prefix="voices-"))
    work.mkdir(parents=True, exist_ok=True)
    separator = Separator()
    for lang in args.lang or sorted(TRACK):
        for clip in clips:
            take = clip.get(lang)
            if not take or take.get("skip"):
                continue
            raw = work/f"{lang}_{clip['id']}.wav"
            start, end = take["time"]
            if not raw.exists():
                extract(episode_file(args.episodes, clip["episode"]), lang, start, end, raw)
            voice, sr = separator.vocals(raw)
            samples = clean(voice, sr, end-start, tuple(take.get("trim", (0.0, 0.0))))
            for target in clip["use"]:
                encode(samples, sr, OUT/lang/f"{target}.ogg")
            print(lang, clip["id"], "->", ", ".join(clip["use"]), flush=True)


if __name__ == "__main__":
    main()
