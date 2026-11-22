"""Check beta artwork and block an incomplete store package."""

import argparse
import json
import struct
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "apps/extension/dist"
STORE = ROOT / "release/store"


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"Not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def verify(publish_ready: bool = False) -> None:
    manifest = json.loads((DIST / "manifest.json").read_text())
    package = json.loads((ROOT / "apps/extension/package.json").read_text())
    if manifest["version"] != package["version"]:
        raise ValueError("Built extension version does not match the source package")
    for size in (16, 32, 48, 128):
        relative = manifest["icons"][str(size)]
        if png_size(DIST / relative) != (size, size):
            raise ValueError(f"Extension icon has the wrong size: {relative}")
    if png_size(STORE / "promo-small-440x280.png") != (440, 280):
        raise ValueError("Small promotional image must be 440x280")
    if png_size(STORE / "screenshot-review-1280x800.png") != (1280, 800):
        raise ValueError("Review screenshot must be 1280x800")
    if png_size(STORE / "screenshot-privacy-1280x800.png") != (1280, 800):
        raise ValueError("Privacy screenshot must be 1280x800")
    if not (DIST / "privacy.html").exists():
        raise ValueError("Extension privacy page is missing")
    if publish_ready:
        policy = (ROOT / "docs/privacy-policy.md").read_text()
        if "[Add a monitored" in policy or "must be added before beta distribution" in (DIST / "privacy.html").read_text():
            raise ValueError("Add a monitored privacy contact before publishing")
        if not manifest.get("host_permissions") or "identity" not in manifest.get("permissions", []):
            raise ValueError("Build the cloud-enabled beta after configuring its service origins")
        policy_url_file = STORE / "public-policy-url.txt"
        if not policy_url_file.exists():
            raise ValueError("Set and verify the public privacy policy URL before publishing")
        policy_url = urlparse(policy_url_file.read_text().strip())
        if policy_url.scheme != "https" or not policy_url.hostname:
            raise ValueError("The public privacy policy URL must use HTTPS and include a hostname")
    print("Release assets verified" + ("; store package is ready for manual review" if publish_ready else "; beta publication gate remains separate"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish-ready", action="store_true")
    verify(parser.parse_args().publish_ready)
