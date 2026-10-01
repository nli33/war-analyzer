#!/usr/bin/env python3
"""Download Correlates of War National Material Capabilities v7 into `data/raw/cow_cinc/`.

`data/raw/` is gitignored (large, regenerable), so `war.rules.load_cinc_table`'s input has to
be re-downloadable rather than committed. Idempotent: skips the download if the CSV is already
there. Run before task C2/C6 pipeline runs that need `resource_backing_tier` after 1816.
"""

import sys
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "raw" / "cow_cinc"
OUT_CSV = OUT_DIR / "NMC-70-abridged.csv"

NMC_ZIP_URL = "https://correlatesofwar.org/wp-content/uploads/NMCv7.zip"
USER_AGENT = "war-analyzer-research-scraper/0.1 (dataset fetch, not for direct citation)"


def main() -> int:
    if OUT_CSV.exists():
        print(f"already present: {OUT_CSV}")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    request = urllib.request.Request(NMC_ZIP_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        outer_zip = zipfile.ZipFile(BytesIO(response.read()))

    inner_name = next(n for n in outer_zip.namelist() if n.endswith("NMC-v7-abridged.zip"))
    inner_zip = zipfile.ZipFile(BytesIO(outer_zip.read(inner_name)))
    csv_name = next(n for n in inner_zip.namelist() if n.endswith("NMC-70-abridged.csv"))
    OUT_CSV.write_bytes(inner_zip.read(csv_name))

    print(f"wrote {OUT_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
