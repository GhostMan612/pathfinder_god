# NOTICE — Pathfinder God

Code in this repository is licensed under the MIT License (see `LICENSE`).
Bundled data and assets below are **not** covered by the MIT License.

## Rules data (`pathfinder_rag.db` and the device extract)

44,620 rows built from open sources (reproducible via `hub/scripts/`):

- Paizo PRD text under the **Open Game License 1.0a (OGL 1.0a)**.
- Pf2ools JSON under the **MIT License**.
- Targeted gap-fill scrapes under Paizo's **Community Use Policy (CUP)**.

Personal / non-commercial use is unrestricted. Adventure-path prose and
Golarion lore (Product Identity) are deliberately *not* scraped — mechanics
only. **Commercial redistribution of the CUP-sourced rows is not authorized**
without a Paizo license; a commercially distributable build requires a Paizo
license or a rebuild excluding CUP sources. See `README.md` and
`docs/database.md#redistribution-terms`.

Note: the device extract ships via Git LFS at
`spoke_kt/app/src/main/assets/rules/pathfinder_rag.db` and contains
CUP-sourced rows. Treat public redistribution of that asset under the same
CUP restriction above.

## Media and assets

- Audio and icon credits are registered in `docs/audio-credits.md` and
  `docs/asset-credits.md`, and mirrored in-app (Setup → Audio Credits).
- Kenney icons are CC0; game-icons.net icons are CC BY 3.0;
  bundled audio includes CC BY 4.0 and CC BY 3.0 tracks as registered there.

## Third-party code

Android and Python dependencies (Compose/Material 3, Room, Filament,
OkHttp/Retrofit, FastAPI/uvicorn, etc.) are used under their respective
open-source licenses; see `spoke_kt/gradle/libs.versions.toml` and
`hub/requirements.txt` / `hub/pyproject.toml`.
