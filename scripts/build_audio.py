"""Efeitos sonoros procedurais originais (sem gravações externas).

Gera ``Assets/audio/<nome>.wav`` (44,1 kHz, mono, 16 bits). Rodar de novo sobrescreve
os arquivos com o mesmo resultado (semente fixa). As vozes dos personagens ficam em
``Assets/audio/voice`` e são geradas por ``scripts/build_voices.py``.

    python scripts/build_audio.py
"""
from pathlib import Path
import wave
import numpy as np

ROOT = Path(__file__).resolve().parents[1] / "Assets" / "audio"
SR = 44100
rng = np.random.default_rng(1146)


# ---------------------------------------------------------------- blocos básicos
def t_axis(seconds):
    return np.arange(int(SR*seconds))/SR


def noise(seconds):
    return rng.uniform(-1, 1, int(SR*seconds))


def band(x, low=0.0, high=None):
    """Filtro passa-faixa ideal via FFT (sons curtos, sem pressa)."""
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1/SR)
    mask = (freqs >= low) & (freqs <= (high or SR))
    return np.fft.irfft(spec*mask, len(x))


def sweep(f0, f1, seconds, curve=1.0, shape='sine'):
    """Oscilador com frequência indo de f0 a f1 (curve>1: cai rápido no começo)."""
    t = t_axis(seconds)
    k = (t/seconds)**curve
    freq = f0+(f1-f0)*k
    phase = 2*np.pi*np.cumsum(freq)/SR
    if shape == 'square':
        return np.sign(np.sin(phase))*.7
    if shape == 'saw':
        return 2*((phase/(2*np.pi)) % 1)-1
    return np.sin(phase)


def decay(seconds, speed=6.0, attack=.002):
    t = t_axis(seconds)
    env = np.exp(-t/seconds*speed)
    a = max(1, int(SR*attack))
    env[:a] *= np.linspace(0, 1, a)
    return env


def swell(seconds, peak=.5):
    t = t_axis(seconds)/seconds
    return np.where(t < peak, (t/peak)**2, np.exp(-(t-peak)/(1-peak)*4))


def pad(x, seconds):
    out = np.zeros(int(SR*seconds))
    out[:min(len(x), len(out))] += x[:len(out)]
    return out


def mix(*layers):
    size = max(len(x) for x in layers)
    out = np.zeros(size)
    for x in layers:
        out[:len(x)] += x
    return out


def at(x, start, total):
    out = np.zeros(int(SR*total))
    i = int(SR*start)
    n = min(len(x), len(out)-i)
    out[i:i+n] += x[:n]
    return out


def pluck(freq, seconds, damping=.996):
    """Karplus-Strong: corda pinçada (rede, corrente)."""
    n = int(SR/freq)
    buf = rng.uniform(-1, 1, n)
    out = np.zeros(int(SR*seconds))
    for i in range(len(out)):
        out[i] = buf[i % n]
        buf[i % n] = damping*.5*(buf[i % n]+buf[(i+1) % n])
    return out


def whoosh(seconds, low=300, high=2500, rise=True):
    """Ruído cuja faixa sobe (ou desce) - deslocamento de ar."""
    steps = 8
    seg = int(SR*seconds/steps)
    out = np.zeros(seg*steps)
    for i in range(steps):
        k = i/(steps-1) if rise else 1-i/(steps-1)
        f = low+(high-low)*k
        chunk = band(noise(seg*2/SR), f*.6, f*1.6)[:seg*2]
        w = np.hanning(len(chunk))
        start = i*seg-seg//2
        lo = max(0, start)
        out[lo:start+len(chunk)] += (chunk*w)[lo-start:len(out)-start]
    env = swell(len(out)/SR, .45)
    return out*np.pad(env, (0, max(0, len(out)-len(env))))[:len(out)]


def bell(freq, seconds, partials=(1, 2.76, 5.4), speed=5.0):
    t = t_axis(seconds)
    return sum(np.sin(2*np.pi*freq*p*t)/(i+1) for i, p in enumerate(partials))*decay(seconds, speed)


def normalize(x, peak=.8):
    m = np.max(np.abs(x)) or 1
    x = x/m*peak
    fade = min(len(x), int(SR*.006))
    x[-fade:] *= np.linspace(1, 0, fade)
    return x


# ---------------------------------------------------------------- receitas
def shot_rifle():
    crack = band(noise(.16), 900, 7000)*decay(.16, 9)
    thump = sweep(160, 70, .12, 2)*decay(.12, 6)
    return mix(crack, thump*.9)


def shot_shotgun():
    blast = band(noise(.38), 120, 3500)*decay(.38, 7)
    thump = sweep(110, 45, .25, 2)*decay(.25, 5)
    return mix(blast, thump*1.2)


def shot_sniper():
    crack = band(noise(.05), 2500, 12000)*decay(.05, 6)
    boom = sweep(90, 40, .5, 2)*decay(.5, 5)
    tail = band(noise(.75), 200, 1800)*decay(.75, 5)*.45
    return mix(crack*1.3, boom, tail)


def shot_organic():
    blob = sweep(620, 160, .2, .6)*decay(.2, 5)
    wet = band(noise(.2), 400, 2400)*decay(.2, 8)*(.6+.4*np.sin(2*np.pi*45*t_axis(.2)))
    return mix(blob, wet*.7)


def shot_spit():
    t = t_axis(.3)
    blob = sweep(300, 90, .3, .5)*decay(.3, 4)*(.7+.3*np.sin(2*np.pi*30*t))
    hiss = band(noise(.3), 1500, 6000)*decay(.3, 10)*.4
    return mix(blob, hiss)


def reload():
    click = lambda: band(noise(.04), 1500, 9000)*decay(.04, 10)
    slide = band(noise(.18), 700, 3000)*swell(.18, .7)*.35
    return mix(at(click(), 0, .62), at(slide, .12, .62), at(click()*1.2, .42, .62), at(click()*.6, .5, .62))


def swing():
    return whoosh(.24, 400, 3200)


def punch():
    thump = sweep(120, 45, .26, 2)*decay(.26, 6)
    smack = band(noise(.06), 600, 5000)*decay(.06, 8)
    return mix(thump*1.2, smack*.8)


def slam():
    thump = sweep(80, 32, .7, 2)*decay(.7, 5)
    crunch = band(noise(.45), 150, 2500)*decay(.45, 6)
    return mix(thump*1.3, crunch*.8)


def dash():
    return whoosh(.38, 250, 2600)*1.2


def explosion():
    boom = sweep(70, 28, 1.1, 2)*decay(1.1, 5)
    body = band(noise(1.1), 40, 1400)*decay(1.1, 4)
    sizzle = band(noise(1.1), 2500, 8000)*decay(1.1, 9)*.3
    return mix(boom*1.3, body, sizzle)


def splash():
    t = t_axis(.55)
    wet = band(noise(.55), 350, 3200)*decay(.55, 5)*(.55+.45*np.abs(np.sin(2*np.pi*23*t)))
    plop = sweep(420, 120, .15, .5)*decay(.15, 5)
    return mix(wet, plop*.8)


def net():
    return mix(pluck(196, .5, .995)*.8, whoosh(.3, 500, 2200)*.6)


def chain():
    out = np.zeros(int(SR*.5))
    for i in range(9):
        tick = bell(1800+rng.uniform(-200, 300), .08, (1, 2.4, 4.1), 9)
        out += at(tick*(1-i/11), i*.045, .5)
    return mix(out, whoosh(.5, 600, 2400)*.4)


def needle():
    zip_ = sweep(2200, 5200, .14, .8)*decay(.14, 4)*.5
    tick = band(noise(.02), 3000, 10000)*decay(.02, 6)
    return mix(zip_, tick)


def ult():
    seconds = 1.3
    t = t_axis(seconds)
    chord = sum(np.sin(2*np.pi*f*t)+.35*np.sin(2*np.pi*f*2*t) for f in (110, 165, 220, 277))
    rise = whoosh(seconds, 200, 4000)*.7
    hit = sweep(150, 40, .5, 2)*decay(.5, 4)
    return mix(chord*swell(seconds, .35)*.35, rise, at(hit, .42, seconds)*1.2)


def ult_ready():
    out = np.zeros(int(SR*.75))
    for i, f in enumerate((660, 880, 1320)):
        out += at(bell(f, .45, (1, 2, 3), 6), i*.09, .75)
    return out


def kill():
    return mix(bell(1320, .35, (1, 2), 6), at(bell(1760, .3, (1, 2), 7)*.7, .07, .4))


def death():
    tone = sweep(420, 70, .9, .7, 'saw')*decay(.9, 3)
    tone = band(tone, 0, 1800)
    dust = band(noise(.9), 300, 2000)*decay(.9, 5)*.3
    return mix(tone, dust)


def respawn():
    shimmer = sweep(220, 880, .6, 1.5)*swell(.6, .7)*.6
    return mix(shimmer, at(bell(1320, .4, (1, 2), 6)*.6, .45, .9))


def heal():
    out = np.zeros(int(SR*.6))
    for i, f in enumerate((523, 659, 784)):
        out += at(np.sin(2*np.pi*f*t_axis(.3))*decay(.3, 5), i*.08, .6)
    return out


def shield():
    t = t_axis(.55)
    hum = (np.sin(2*np.pi*180*t)+.5*np.sin(2*np.pi*362*t)+.3*np.sin(2*np.pi*545*t))*swell(.55, .3)
    return mix(hum*.6, whoosh(.55, 800, 3000)*.35)


def absorb():
    t = t_axis(.16)
    gulp = sweep(320, 110, .16, .6)*decay(.16, 3)*(.6+.4*np.sin(2*np.pi*40*t))
    return gulp


def receptor():
    """O "pikon" da antena: dois bipes agudos."""
    beep = lambda: sweep(1900, 2100, .07, 1, 'square')*decay(.07, 2)
    return band(mix(at(beep(), 0, .3), at(beep(), .12, .3)), 0, 9000)


def turret():
    clunk = sweep(140, 60, .2, 2)*decay(.2, 6)
    servo = sweep(400, 900, .35, 1, 'saw')*swell(.35, .5)*.25
    return mix(clunk, at(band(servo, 0, 4000), .15, .55))


def wall():
    crackle = np.zeros(int(SR*.7))
    for _ in range(26):
        crackle += at(band(noise(.03), 400, 4000)*decay(.03, 6)*rng.uniform(.3, 1), rng.uniform(0, .55), .7)
    goo = sweep(160, 70, .7, 1)*swell(.7, .2)*.6
    return mix(crackle, goo)


def crumble():
    out = band(noise(.7), 150, 3000)*decay(.7, 4)
    for _ in range(14):
        out += at(band(noise(.04), 300, 2500)*decay(.04, 6), rng.uniform(0, .5), .7)
    return out


def pop():
    return sweep(900, 250, .09, .5)*decay(.09, 4)


def ui_click():
    return band(noise(.03), 2000, 9000)*decay(.03, 8)+sweep(1400, 900, .03)*decay(.03, 6)*.4


def hiss():
    return band(noise(.9), 2500, 9000)*swell(.9, .25)*.7


def rain():
    out = np.zeros(int(SR*1.4))
    for _ in range(30):
        out += at(pop()*rng.uniform(.3, 1), rng.uniform(0, 1.25), 1.4)
    return out


def hit():
    return mix(sweep(1800, 1500, .06)*decay(.06, 5), band(noise(.03), 3000, 9000)*decay(.03, 6)*.4)


def hurt():
    thud = sweep(130, 70, .18, 1.5)*decay(.18, 5)
    grit = band(noise(.18), 200, 1500)*decay(.18, 6)*.5
    return mix(thud, grit)


def event():
    return mix(bell(590, .65, (1, 2, 3.01), 5), at(bell(885, .5, (1, 2), 5)*.5, .08, .65))


SOUNDS = dict(
    shot_rifle=shot_rifle, shot_shotgun=shot_shotgun, shot_sniper=shot_sniper,
    shot_organic=shot_organic, shot_spit=shot_spit, reload=reload, swing=swing, punch=punch, slam=slam,
    dash=dash, explosion=explosion, splash=splash, net=net, chain=chain, needle=needle, ult=ult,
    ult_ready=ult_ready, kill=kill, death=death, respawn=respawn, heal=heal, shield=shield, absorb=absorb,
    receptor=receptor, turret=turret, wall=wall, crumble=crumble, pop=pop, ui_click=ui_click, hiss=hiss,
    rain=rain, hit=hit, hurt=hurt, event=event,
)


def write(name, samples):
    data = (np.clip(samples, -1, 1)*32767).astype('<i2').tobytes()
    with wave.open(str(ROOT/f"{name}.wav"), "wb") as file:
        file.setparams((1, 2, SR, 0, "NONE", "not compressed"))
        file.writeframes(data)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, recipe in SOUNDS.items():
        write(name, normalize(recipe()))
    print(f"{len(SOUNDS)} sons em {ROOT}")


if __name__ == "__main__":
    main()
