# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A fork of [wmgeolab/geoBoundaries](https://github.com/wmgeolab/geoBoundaries) (remote: `logichulk/bhulok-administrative-regions`), being repurposed as the administrative-boundary source for **Bhulok**. It is a data repository: there is no application code, build system, linter, or test suite here. The upstream build scripts and QA checks live in a separate repo, [geoBoundaryBot](https://github.com/wmgeolab/geoBoundaryBot) (`gbBuild.py`), which is not vendored.

## Bhulok-specific data

`Bhulok_220_Regions_by_Zone.xlsx` is the authoritative list of the 220 Bhulok regions:
- **Regions** sheet: `#`, `Administrative region`, `ISO alpha-2`, `Numeric code`, `Zone code`, `Zone`, `Onboarded`.
- **Zones** sheet: 8 zones — `BRT` (Bhārat), `USSR`, `EUR`, `JPN` (Nippon), `AFR`, `AMR`, `OZ` (Oceania & Antarctica), `OTH` — with region counts as `COUNTIF` formulas.
- **Notes** sheet: data was derived from the app's seed files `app/db/seed/S904__zones.sql` and `S905__bhulok_220.sql` (those live in the app repo, not here).

Key mapping caveats when joining Bhulok regions to geoBoundaries:
- The sheet uses **ISO 3166-1 alpha-2**; geoBoundaries keys everything by **alpha-3** (`IND`, `PAK`, …). Use the numeric code as the bridge.
- Numeric codes **900–924** are user-assigned for entries with no ISO code (e.g. Tibet, Bougainville, Kurdistan, Zanzibar, England/Scotland/Wales/Northern Ireland). These have no geoBoundaries ADM0 and must be derived from ADM1/ADM2 of a parent country or another source.
- Bougainville (OZ), Kurdistan (OTH), Zanzibar (AFR) and the four UK home nations (OTH) are assigned zones explicitly; Diego Garcia is `BRT`.
- Only India (`IN`) is marked `Onboarded = Yes`.

Read the xlsx with `python3 -c "import openpyxl; ..."` (openpyxl is available); note the Zones counts are formulas, so load with `data_only=True` only if the file was last saved by Excel.

## geoBoundaries layout (inherited)

- `sourceData/<releaseType>/<ISO3>_<ADMn>.zip` — raw submissions. Each zip contains a boundary file (`.geojson` or shapefile), `meta.txt` (key/value metadata: year, ISO, boundary type, canonical name, sources, license), and `license.png`. Only ~29 zips are present locally (e.g. `IND_ADM1`, `PAK_ADM2`, `NPL_ADM2/3`, `USA_ADM1`).
- `releaseData/gbOpen/<ISO3>/<ADMn>/` — built outputs (geojson/topojson/shp, simplified variants, `-metaData.json`, preview PNG). Locally these directories are **empty**; only `releaseData/geoBoundariesOpen-meta.csv` (one row per country/ADM level, with `staticDownloadLink` URLs into upstream) has content. `releaseData/CGAZ/` (global composite) is also empty.
- Release types: `gbOpen` (CC-BY/ODbL/PD), `gbHumanitarian`, `gbAuthoritative`.
- Submission conventions (see CONTRIBUTING.md): EPSG:4326 only; `Name` and `Level` fields required, plus `ISO_Code` for ADM0/ADM1; terrestrial boundaries only; disputed territory is included in **every** claimant's file (e.g. Kashmir appears in both IND and PAK) — relevant when assigning Bhulok regions like Tibet or Kashmir.

## Git / LFS

- `.gitattributes` routes everything under `sourceData/**` and `releaseData/**` through **Git LFS**. Don't add large geodata without LFS, and avoid blanket `git add -A` — the history has ~12.9k tracked files.
- Upstream clones over HTTPS hit GitHub LFS rate limits; use SSH (`git@github.com:...`) or `gh repo clone`.
- `.github/workflows/` are upstream geoBoundaries automations (`yDISPATCH_gBLayer` runs `gbBuild.py` in the `geogdan/geoboundaries` container and pushes to wmgeolab; `zPR_Auto_Response` validates PRs touching `sourceData/**`). They reference upstream secrets/repos and will not work as-is on this fork.
