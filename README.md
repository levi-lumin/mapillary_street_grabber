# Mapillary Street Grabber — v0.8.1

A command‑line utility for Windows, macOS and Linux that downloads every image—or only the equirectangular **360‑degree panoramas**—that Mapillary hosts along a given street.
Writen using OpenAI's o3.

## Contents
1. [Key features](#1-key-features)
2. [Quick install](#2-quick-install)
3. [Setting your Mapillary token](#3-setting-your-mapillary-token)
4. [Basic usage examples](#4-basic-usage-examples)
5. [Command-line options](#5-command-line-options)
6. [Output files](#6-output-files)
7. [Licence & attribution requirements](#7-licence--attribution-requirements)

---

### 1. Key features
- **Street-level bounding box** — Geocodes any street name, then pads the Open-Street-Map bounding box by a user-defined radius.
- **Panorama filter (`--pano`)** — Keeps only true 2 : 1 equirectangular JPEGs; fisheye and flat photos are discarded.
- **Robust geocoding** — Prefers results whose OSM `class == "highway"`, avoiding building nodes that share the same street name.
- **Multi-threaded downloads** — Adjustable thread pool and automatic retry / back-off.
- **CSV attribution file** — Lists every downloaded image with capture time and mandatory CC-BY-SA credit line.
- **Version flag (`-V`)** — Check exactly what build you’re running.

---

### 2. Quick install
```powershell
# Clone or copy the script
cd path\to\folder
python -m venv .venv
.venv\Scripts\activate       # Linux/macOS: source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

### 3. Setting your Mapillary token
1. Log in to **mapillary.com → Developers → Access tokens**.
2. Create a *Client access token* and copy it.
3. In the same shell where you’ll run the grabber:
   ```powershell
   setx MAPILLARY_TOKEN "<your_token>"
   # reopen the terminal so the variable is available
   ```

---

### 4. Basic usage examples
```powershell
# All images (flat + fisheye + 360) within 25 m of Elizabeth St, Melbourne
python mapillary_street_grabber.py "Elizabeth St, Melbourne, AU" --radius 25

# Only 360-degree panoramas within 50 m
python mapillary_street_grabber.py "Elizabeth St, Melbourne, AU" --radius 50 --pano

# Verbose output with geocoder diagnostics
python mapillary_street_grabber.py "George St, Edinburgh, UK" --pano --debug --geo-debug
```

---

### 5. Command-line options

| Option | Default | Description |
|--------|---------|-------------|
| `STREET…` | – | Street name (+ city/country for accuracy). |
| `--radius FLOAT` | `25.0` | Extra metres added around the OSM bounding box. |
| `--out PATH` | `./panos` | Destination directory. |
| `--threads INT` | `4` | Concurrent download threads. |
| `--pano` | *(off)* | Keep only equirectangular 360s. |
| `--debug` | *(off)* | Show filter stats and (with `--geo-debug`) geocoder pick. |
| `--geo-debug` | *(off)* | Always print which geocoder result was chosen. |
| `-V`, `--version` | – | Print version number and exit. |
| `-h`, `--help` | – | Show full help. |

---

### 6. Output files
- **`img_<image_id>.jpg`** — One file per image.
- **`attribution.csv`** — Columns: `image_id, filename, captured_at, is_pano, width, height, attribution`.

> **Important:** Keep `attribution.csv` *with* the images if you redistribute them — that satisfies the CC-BY-SA licence.

---

### 7. Licence & attribution requirements
All imagery remains © the original Mapillary contributors and is released under **Creative Commons BY-SA 4.0**.  
You **must** credit *Mapillary* (e.g. “Mapillary © contributors, CC-BY-SA 4.0”) whenever the images are displayed or redistributed.

---


*Python 3.9 or newer is recommended.*
