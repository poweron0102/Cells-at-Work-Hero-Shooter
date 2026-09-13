"""Original procedural prototype sound cues. No external recordings."""
import math
from pathlib import Path
import random
import struct
import wave

ROOT = Path(__file__).resolve().parents[1] / "Assets" / "audio"


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(1146)
    for name, duration, frequency in [("shot", .11, 150), ("hit", .065, 1500), ("hurt", .16, 95), ("event", .65, 590)]:
        samples = []
        for i in range(int(22050*duration)):
            t = i/22050
            envelope = math.exp(-t/duration*7)
            tone = math.sin(math.tau*frequency*t*(1-.3*t/duration))
            noise = rng.uniform(-1, 1)
            value = (tone*.55+noise*(.6 if name == "shot" else .12))*envelope*.36
            samples.append(struct.pack("<h", int(max(-1, min(1, value))*32767)))
        with wave.open(str(ROOT/f"{name}.wav"), "wb") as file:
            file.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            file.writeframes(b"".join(samples))


if __name__ == "__main__":
    main()
