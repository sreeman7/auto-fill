"""Create a store ZIP only after the publish-readiness checks pass."""

import json
import sys
import zipfile
from pathlib import Path

from verify_release import DIST, ROOT, verify


def main() -> None:
    verify(publish_ready=True)
    manifest_path = DIST / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["name"] = "auto-fill BETA"
    manifest["description"] = "BETA: Review and fill job applications with a profile you control. You submit each application yourself."
    output = ROOT / "release/out" / f"auto-fill-beta-{manifest['version']}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(DIST.rglob("*")):
            if file.is_file():
                relative = file.relative_to(DIST)
                if relative.as_posix() == "manifest.json":
                    archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
                else:
                    archive.write(file, relative.as_posix())
    print(output)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print(f"Beta package blocked: {error}", file=sys.stderr)
        raise SystemExit(1) from error
