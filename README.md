# Studio Lights Portal

Localhost web GUI to control all room lights from an interactive room diagram.

![localhost:5337](https://img.shields.io/badge/localhost-5337-blue)

## What it does

Visual top-down room map with clickable zones for each light:

- **Philips Hue:** TechoOficina, Ofilamp, Iris
- **Nanoleaf:** 8-panel wall array
- **Internal RGB:** RAM (DDR5 via i2cset), GPU (RTX 5070 via OpenRGB), Mobo + Cooler (OpenRGB zones)

Click a zone → color picker → apply. Also has master controls:
- Set All (one color, all lights)
- All Off
- Mood Sync (re-extract colors from current wallpaper)
- New Wallpaper (fetch from Unsplash + sync)

## Requirements

- Python 3.10+
- Flask (`pip install flask`)
- Existing light control scripts on `$PATH`:
  - `rgb-set`, `rgb-dual.sh`, `sync-lights.sh`, `change-wallpaper.sh`
  - `openhue`, `nanoleaf-set`
  - `openrgb`, `i2cset`

## Usage

```bash
cd ~/Documents/Projects/studio-lights-portal
python3 server.py
```

Open http://localhost:5337

## Quick launch

Add to `~/.bashrc`:
```bash
alias studio-lights='python3 ~/Documents/Projects/studio-lights-portal/server.py'
```

## Architecture

```
Browser (localhost:5337)
    │
    ▼
Flask server (server.py)
    │
    ├── /api/all         → rgb-set <hex>
    ├── /api/all/off     → rgb-set off
    ├── /api/hue/<id>    → openhue set light ...
    ├── /api/nanoleaf    → nanoleaf-set ...
    ├── /api/rgb/ram     → i2cset (direct register writes)
    ├── /api/rgb/gpu     → openrgb -d "RTX 5070" ...
    ├── /api/rgb/mobo    → openrgb -d "B650 AORUS" ...
    ├── /api/mood/sync   → sync-lights.sh
    └── /api/mood/new    → change-wallpaper.sh
```

Single HTML file with inline SVG + vanilla JS. No build step, no npm.

## License

MIT
