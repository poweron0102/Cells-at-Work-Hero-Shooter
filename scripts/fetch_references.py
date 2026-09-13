"""Download the official transparent character references, without modifying them."""
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1] / "Assets" / "characters"
CHARACTERS = {"red_blood_cell": "01", "neutrophil": "02", "killer_t": "03",
              "macrophage": "04", "platelet": "05"}

if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, number in CHARACTERS.items():
        url = f"https://cellsatwork-anime.com/assets/img/character/chara_{number}.png"
        with urlopen(url, timeout=30) as response:
            data = response.read()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"Not a PNG: {url}")
        (ROOT / f"{name}.png").write_bytes(data)
        print(f"{name}: {len(data)} bytes")
