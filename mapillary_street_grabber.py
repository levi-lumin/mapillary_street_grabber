#!/usr/bin/env python3
"""
Mapillary Street Grabber – v0.8.1
================================
Small QoL patch so you can verify exactly **which version** the CLI is picking
up at runtime.

* Adds `--version / -V` via `click.version_option("0.8.1")`.
* No behavioural changes otherwise (still includes `--geo-debug`).
"""

from __future__ import annotations

import csv
import math
import os
import pathlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

import click
import requests
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim
from PIL import Image
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed
from tqdm import tqdm

MAPILLARY_GRAPH_URL = "https://graph.mapillary.com"
FIELDS = "id,thumb_original_url,is_panorama,captured_at,width,height"
MAX_IMAGES = 10_000
AR_THRESHOLD = 1.9

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token() -> str:
    t = os.getenv("MAPILLARY_TOKEN")
    if not t:
        click.echo("ERROR: set MAPILLARY_TOKEN", err=True)
        sys.exit(1)
    return t


@retry(wait=wait_fixed(2), stop=stop_after_attempt(5), retry=retry_if_exception_type(requests.RequestException))
def api_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    p = params.copy()
    p["access_token"] = _token()
    r = requests.get(f"{MAPILLARY_GRAPH_URL}{path}", params=p, timeout=20)
    r.raise_for_status()
    return r.json()


def pick_road_bbox(query: str, debug: bool=False) -> Tuple[float, float, float, float]:
    geocoder = Nominatim(user_agent="mapillary_street_grabber")
    results = RateLimiter(geocoder.geocode, min_delay_seconds=1)(query, exactly_one=False, limit=10)
    if not results:
        raise ValueError(f"Could not geocode '{query}'.")
    chosen = next((loc for loc in results if loc.raw.get("class") == "highway"), results[0])
    if debug:
        bb = chosen.raw.get("boundingbox")
        click.echo(f"Geocoder pick → class={chosen.raw.get('class')} type={chosen.raw.get('type')} bbox={bb}")
    south, north, west, east = map(float, chosen.raw["boundingbox"])
    return west, south, east, north


def pad_bbox(bbox: Tuple[float, float, float, float], metres: float) -> Tuple[float, float, float, float]:
    w, s, e, n = bbox
    lat_km = 111.32
    lon_km = lat_km * math.cos(math.radians((n + s) / 2))
    dlat = metres / 1000 / lat_km
    dlon = metres / 1000 / lon_km
    return w - dlon, s - dlat, e + dlon, n + dlat


def fetch_metadata(bbox: Tuple[float, float, float, float]) -> List[Dict[str, Any]]:
    metas: List[Dict[str, Any]] = []
    params = {"bbox": ",".join(map(str, bbox)), "fields": FIELDS, "limit": 500}
    cursor = None
    while True:
        if cursor:
            params["after"] = cursor
        data = api_get("/images", params)
        metas.extend(data.get("data", []))
        if len(metas) > MAX_IMAGES:
            click.echo(f"Stopping early – >{MAX_IMAGES} images. Narrow bbox.")
            break
        cursor = data.get("paging", {}).get("cursors", {}).get("after")
        if not cursor:
            break
    return metas


@retry(wait=wait_fixed(2), stop=stop_after_attempt(3), retry=retry_if_exception_type(requests.RequestException))
def _download(url: str, dest: pathlib.Path):
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        dest.write_bytes(r.content)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option("0.8.1", "-V", "--version")
@click.argument("street", nargs=-1, required=True)
@click.option("--radius", default=25.0, type=float, show_default=True)
@click.option("--out", "out_dir", default="./panos", type=click.Path())
@click.option("--threads", default=4, show_default=True)
@click.option("--pano", is_flag=True, help="Only save 360‑degree panoramas.")
@click.option("--debug", is_flag=True, help="Verbose filtering + geocoder info.")
@click.option("--geo-debug", is_flag=True, help="Always print geocoder pick regardless of --debug.")
def main(street: Tuple[str, ...], radius: float, out_dir: str, threads: int, pano: bool, debug: bool, geo_debug: bool):
    query = " ".join(street)
    click.echo(f"Geocoding: {query}")
    bbox = pad_bbox(pick_road_bbox(query, debug or geo_debug), radius)
    click.echo(f"Search bbox: {bbox}")

    click.echo("Fetching metadata …")
    metas = fetch_metadata(bbox)
    click.echo(f"{len(metas)} total image(s) found.")
    if not metas:
        click.echo("No images in area.")
        return

    out_path = pathlib.Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    csv_writer = csv.writer((out_path / "attribution.csv").open("w", newline="", encoding="utf-8"))
    csv_writer.writerow(["id", "filename", "captured_at", "is_pano", "w", "h", "attr"])

    pbar = tqdm(total=len(metas), unit="img")
    lock = threading.Lock()
    kept, dropped = 0, 0

    def worker(meta: Dict[str, Any]):
        nonlocal kept, dropped
        try:
            url = meta.get("thumb_original_url")
            if not url:
                dropped += 1
                return
            dest = out_path / f"img_{meta['id']}.jpg"
            _download(url, dest)
            if pano:
                try:
                    with Image.open(dest) as im:
                        w, h = im.size
                    if (w / h) < AR_THRESHOLD:
                        dest.unlink(missing_ok=True)
                        dropped += 1
                        return
                except Exception:
                    dest.unlink(missing_ok=True)
                    dropped += 1
                    return
            with lock:
                csv_writer.writerow([
                    meta["id"], dest.name, meta.get("captured_at"), meta.get("is_panorama"),
                    meta.get("width"), meta.get("height"), "Mapillary © contributors (CC‑BY‑SA 4.0)",
                ])
                kept += 1
        finally:
            pbar.update(1)

    with ThreadPoolExecutor(max_workers=threads) as pool:
        list(as_completed(pool.submit(worker, m) for m in metas))

    pbar.close()
    if debug:
        click.echo(f"Kept {kept}, dropped {dropped}")
    if kept == 0:
        click.echo("No images match criteria.")
    else:
        click.echo(f"Finished. {kept} file(s) in {out_path}.")


if __name__ == "__main__":
    main()
