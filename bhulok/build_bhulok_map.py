# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "geopandas>=1.0",
#     "shapely>=2.1",
#     "pyogrio>=0.9",
#     "pyproj>=3.6",
#     "openpyxl>=3.1",
#     "pycountry>=24.6",
#     "matplotlib>=3.8",
# ]
# ///
"""Build the Bhulok map: 220 administrative regions grouped into 8 zones.

Region list and zones come from Bhulok_220_Regions_by_Zone.xlsx at the repo root.
Geometry comes from geoBoundaries CGAZ (ADM0 + ADM1, pinned to the upstream commit
this fork is based on), with Natural Earth v5.1.2 used for areas CGAZ cannot
express (breakaway regions, Cook Islands/Niue/Chagos masks) and as the reference
for India's official boundary.

Boundary policy: every dispute involving India is resolved in India's favour
(all of Jammu & Kashmir and Ladakh incl. PoK, Gilgit-Baltistan, Shaksgam and
Aksai Chin; Siachen; the middle-sector and Arunachal areas claimed by China;
Kalapani; Sir Creek). See bhulok/README.md for the full list of decisions.

Run from the repo root:  uv run --managed-python bhulok/build_bhulok_map.py
"""

from __future__ import annotations

import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import numpy as np
import openpyxl
import pycountry
import shapely
from shapely import STRtree
from shapely.geometry import MultiPolygon, Point, box

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CACHE = HERE / ".cache"
OUT = HERE / "output"
SHEET = REPO / "Bhulok_220_Regions_by_Zone_v1.xlsx"

GB_COMMIT = "5c25134028196d43ce97b5071934fd0cfc92f09f"
GB_URL = f"https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/{GB_COMMIT}/releaseData/CGAZ"
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/10m_cultural"
NE_LAYERS = ["ne_10m_admin_0_countries", "ne_10m_admin_0_countries_ind", "ne_10m_admin_0_disputed_areas"]

GRID = 1e-7          # snap-rounding precision (degrees, ~1 cm) for robust overlays
EMPTY = MultiPolygon()
EQUAL_AREA = "EPSG:8857"  # Equal Earth
SIMPLIFY_TOLERANCE = 0.01  # degrees, for the published GeoJSON

INDIA = "Bharat (India)"
UK_OTHER = "United Kingdom (overseas territories & Crown dependencies)"

ZONE_COLORS = {  # validated pairwise for zones that share a border (dataviz validate_palette.js)
    "BRT": "#eda100", "USSR": "#e34948", "EUR": "#2a78d6", "JPN": "#6250d6",
    "AFR": "#eb6834", "AMR": "#008300", "OZ": "#1baf7a", "OTH": "#8f8d86",
}

# Areas not on the sheet: (zone_code or None, note). Zones follow the sovereign/claimants.
UNLISTED = {
    UK_OTHER: ("OTH", "Not on the sheet; UK home nations are all OTH. Includes the Falkland Islands."),
    "Abyei Area": ("AFR", "Sudan/South Sudan dispute under UN administration; both claimants are AFR."),
    "Koualou": ("AFR", "Benin/Burkina Faso dispute; both claimants are AFR."),
    "Latrun No Man's Land": ("OTH", "Israel/Palestine armistice no-man's land; both are OTH."),
    "Spratly Islands": (None, "Claimants span BRT, JPN and OTH zones; left unassigned."),
}

# CGAZ disputed-area features (shapeGroup 111-129) -> region.
DISPUTED = {
    "Abyei": "Abyei Area",
    "Aksai Chin": INDIA,
    "CH-IN": INDIA,               # middle-sector areas (Barahoti etc.) claimed by China
    "Demchok": INDIA,
    "Dragonja": "Croatia",
    "Dramana-Shakatoe": "Bhutan",
    "Falkland Islands (UK)": UK_OTHER,
    "Gaza Strip": "Palestine",
    "Kalapani": INDIA,
    "Isla Brasilera": "Brazil",
    "Siachen-Saltoro": INDIA,
    "Koualou": "Koualou",
    "Liancourt Rocks": "South Korea",
    "No Man's Land": "Latrun No Man's Land",
    "Paracel Is": "China",
    "Sanafir & Tiran Is.": "Saudi Arabia",
    "Senkakus": "Japan",
    "Spratly Is": "Spratly Islands",
    "West Bank": "Palestine",
    "Western Sahara": "Western Sahara",
}

# India's claim (Natural Earth India point-of-view) is applied only inside these
# disputed sectors, so ordinary cartographic differences elsewhere don't move borders.
INDIA_CLAIM_SECTORS = {
    "Jammu & Kashmir and Ladakh": ((72.3, 32.2, 80.6, 37.2), ["Pakistan", "China", "Tibet"]),
    "Himachal & Uttarakhand (middle sector)": ((77.5, 29.6, 81.0, 32.9), ["China", "Tibet"]),
    "Kalapani": ((80.4, 29.8, 81.2, 30.5), ["Nepal", "China", "Tibet"]),
    "North Sikkim": ((88.0, 27.6, 89.0, 28.2), ["China", "Tibet"]),
    "Arunachal Pradesh": ((91.5, 26.5, 97.5, 29.6), ["China", "Tibet"]),
    "Sir Creek": ((68.0, 23.2, 69.4, 24.1), ["Pakistan"]),
}

CHECK_POINTS = {  # (lat, lon) -> expected region; asserted after the build
    "Gilgit": ((35.92, 74.31), INDIA), "Skardu": ((35.30, 75.63), INDIA),
    "Muzaffarabad": ((34.37, 73.47), INDIA), "Mirpur": ((33.15, 73.75), INDIA),
    "Aksai Chin (Lake)": ((35.20, 79.83), INDIA), "Aksai Chin (north)": ((35.64, 79.99), INDIA),
    "Shaksgam Valley": ((36.00, 76.60), INDIA), "Siachen": ((35.40, 77.10), INDIA),
    "Leh": ((34.16, 77.58), INDIA), "Srinagar": ((34.08, 74.80), INDIA),
    "Tawang": ((27.59, 91.86), INDIA), "Lahore": ((31.55, 74.34), "Pakistan"),
    "Quetta": ((30.18, 67.00), "Balochistan"), "Lhasa": ((29.65, 91.10), "Tibet"),
    "Kashgar": ((39.47, 75.99), "China"), "Erbil": ((36.19, 44.01), "Kurdistan"),
    "Hargeisa": ((9.56, 44.06), "Somaliland"), "Tiraspol": ((46.84, 29.63), "Transnistria"),
    "Tskhinvali": ((42.23, 43.97), "South Ossetia"), "Sukhumi": ((43.00, 41.02), "Abkhazia"),
    "Kyrenia": ((35.33, 33.32), "Northern Cyprus"), "Edinburgh": ((55.95, -3.19), "Scotland"),
    "Belfast": ((54.60, -5.93), "Northern Ireland"), "Cardiff": ((51.48, -3.18), "Wales"),
    "London": ((51.51, -0.13), "England"), "Arawa": ((-6.23, 155.56), "Bougainville"),
    "Zanzibar (Unguja)": ((-6.00, 39.30), "Zanzibar"), "Ramallah": ((31.90, 35.20), "Palestine"),
    "Nuuk": ((64.18, -51.72), "Denmark"),
}


# ---------------------------------------------------------------- geometry helpers

def polys(g) -> MultiPolygon:
    """Keep only the polygonal parts of a geometry, as a MultiPolygon."""
    out, stack = [], [g]
    while stack:
        x = stack.pop()
        if x is None or x.is_empty:
            continue
        if x.geom_type == "Polygon":
            out.append(x)
        elif x.geom_type in ("MultiPolygon", "GeometryCollection"):
            stack.extend(shapely.get_parts(x))
    return MultiPolygon(out) if out else EMPTY


def union(geoms) -> MultiPolygon:
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    return polys(shapely.union_all(geoms, grid_size=GRID)) if geoms else EMPTY


def inter(a, b) -> MultiPolygon:
    return polys(shapely.intersection(a, b, grid_size=GRID))


def diff(a, b) -> MultiPolygon:
    if b is None or b.is_empty:
        return polys(a)
    return polys(shapely.difference(a, b, grid_size=GRID))


def clean(series: gpd.GeoSeries) -> np.ndarray:
    # snapping can collapse slivers to lines (e.g. CGAZ NZL), which overlays reject as mixed-dimension
    return np.array([polys(g) for g in shapely.set_precision(shapely.make_valid(series.values), GRID)], dtype=object)


def opening(g, w):
    """Morphological opening: drops parts of g narrower than ~2w."""
    return polys(g.buffer(-w).buffer(w))


def voronoi_split(part, candidates: dict[str, object], reach: float) -> dict[str, MultiPolygon]:
    """Split `part` between candidate units by nearest unit boundary."""
    zone = part.buffer(reach)
    xmin, ymin, xmax, ymax = zone.bounds
    coords, labels = [], []
    for label, g in candidates.items():
        b = shapely.clip_by_rect(g.boundary, xmin, ymin, xmax, ymax)
        c = shapely.get_coordinates(shapely.segmentize(b, 0.002)) if not b.is_empty else np.empty((0, 2))
        coords.append(c)
        labels += [label] * len(c)
    pts = np.round(np.vstack(coords), 7)
    _, first = np.unique(pts, axis=0, return_index=True)
    first.sort()
    pts, labels = pts[first], [labels[i] for i in first]
    if len(pts) < 3:
        nearest = min(candidates, key=lambda k: part.distance(candidates[k]))
        return {nearest: polys(part)}
    cells = shapely.get_parts(shapely.voronoi_polygons(shapely.MultiPoint(pts), extend_to=zone.envelope, ordered=True))
    by_label = defaultdict(list)
    for cell, label in zip(cells, labels):
        by_label[label].append(cell)
    out, assigned = {}, EMPTY
    order = sorted(by_label, key=lambda k: -len(by_label[k]))
    for label in order[1:]:
        out[label] = inter(part, union(by_label[label]))
        assigned = union([assigned, out[label]])
    out[order[0]] = diff(part, assigned)  # largest takes the remainder so nothing is lost
    return out


def partition(parent, targets: list[tuple[str, object]], rest_unit, default: str, reach: float = 0.25):
    """Split a CGAZ country polygon into labelled pieces.

    `targets` are (label, mask) pairs taken in priority order; `rest_unit` is the mask
    for the remainder (or None). Parent areas covered by no mask (CGAZ ADM1 does not
    exactly tile ADM0) go to the nearest mask within `reach` degrees, split along a
    Voronoi line when several masks are near; anything farther goes to `default`.
    """
    masks, taken = [], EMPTY
    for label, m in targets:
        m = diff(m, taken)
        masks.append((label, m))
        taken = union([taken, m])
    if rest_unit is not None:
        rest_unit = diff(rest_unit, taken)

    pieces = defaultdict(list)
    for label, m in masks:
        pieces[label].append(inter(parent, m))
    if rest_unit is not None:
        pieces[default].append(inter(parent, rest_unit))
    leftover = diff(parent, union([g for gs in pieces.values() for g in gs]))
    parts = shapely.get_parts(leftover)
    if len(parts):
        mask_geoms = [m for _, m in masks]
        shapely.prepare(mask_geoms)
        tree = STRtree(mask_geoms)
        pi, mi = tree.query(parts, predicate="dwithin", distance=reach)
        near = defaultdict(set)
        for p, m in zip(pi, mi):
            near[p].add(masks[m][0])
        for k, part in enumerate(parts):
            labels = near.get(k)
            if not labels:
                pieces[default].append(part)
                continue
            cands = {lab: union([m for l2, m in masks if l2 == lab]) for lab in labels}
            if rest_unit is not None:
                xmin, ymin, xmax, ymax = part.buffer(reach).bounds
                local_rest = shapely.clip_by_rect(rest_unit, xmin, ymin, xmax, ymax)
                if not local_rest.is_empty and part.distance(local_rest) <= reach:
                    cands[default] = local_rest
            if len(cands) == 1:
                pieces[next(iter(cands))].append(part)
            elif part.area < 1e-6:
                pieces[min(cands, key=lambda c: part.distance(cands[c]))].append(part)
            else:
                for lab, g in voronoi_split(part, cands, reach).items():
                    pieces[lab].append(g)
    return {label: union(gs) for label, gs in pieces.items()}


# ---------------------------------------------------------------- inputs

def fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        print(f"  downloading {url}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(dest)
    return dest


def load_inputs():
    print("Loading inputs")
    a0 = gpd.read_file(fetch(f"{GB_URL}/geoBoundariesCGAZ_ADM0.gpkg", CACHE / "cgaz_adm0.gpkg"))
    a1 = gpd.read_file(fetch(f"{GB_URL}/geoBoundariesCGAZ_ADM1.gpkg", CACHE / "cgaz_adm1.gpkg"))
    ne = {}
    for layer in NE_LAYERS:
        for ext in ("shp", "shx", "dbf", "prj"):
            fetch(f"{NE_URL}/{layer}.{ext}", CACHE / "ne_v5.1.2" / f"{layer}.{ext}")
        ne[layer] = gpd.read_file(CACHE / "ne_v5.1.2" / f"{layer}.shp")
    for df in [a0, a1, *ne.values()]:
        df.set_crs(4326, allow_override=True, inplace=True)
        df["geometry"] = clean(df.geometry)
    return a0, a1, ne


def load_sheet():
    ws = openpyxl.load_workbook(SHEET)["Regions"]
    header, *rows = list(ws.iter_rows(values_only=True))
    assert header[:7] == ("#", "Administrative region", "ISO alpha-2", "Numeric code", "Zone code", "Zone", "Onboarded"), header
    regions = [dict(bhulok_id=r[0], name=r[1], iso_a2=r[2], numeric_code=r[3], zone_code=r[4], zone=r[5],
                    onboarded=r[6] == "Yes") for r in rows if r[0] is not None]
    assert len(regions) == 220, len(regions)
    return regions


# ---------------------------------------------------------------- build

def build(a0, a1, ne, regions):
    names = {r["name"] for r in regions}
    by_iso3 = {}
    for r in regions:
        c = pycountry.countries.get(alpha_2=r["iso_a2"])
        if c:
            by_iso3[c.alpha_3] = r["name"]
    by_iso3["XKX"] = "Kosovo"
    by_iso3["GRL"] = "Denmark"  # Greenland is not on the sheet; it follows Denmark like the Faroes do

    def adm1(iso, *unit_names):
        sel = a1[(a1.shapeGroup == iso) & a1.shapeName.isin(unit_names)]
        missing = set(unit_names) - set(sel.shapeName)
        assert not missing, (iso, missing)
        return union(sel.geometry)

    def adm1_rest(iso, *unit_names):
        return union(a1[(a1.shapeGroup == iso) & ~a1.shapeName.isin(unit_names)].geometry)

    nec = ne["ne_10m_admin_0_countries"]
    ned = ne["ne_10m_admin_0_disputed_areas"]

    def ne_country(*a3):
        return union(nec[nec.ADM0_A3.isin(a3)].geometry)

    def ne_disputed(brk_name):
        return union(ned[ned.BRK_NAME == brk_name].geometry)

    south_ossetia = ne_disputed("South Ossetia")
    splits = {
        "CHN": ([("Tibet", adm1("CHN", "Tibet Autonomous Region")),
                 ("Hong Kong", adm1("CHN", "Hong Kong Special Administrative Region")),
                 ("Macau", adm1("CHN", "Macau Special Administrative Region"))],
                adm1_rest("CHN", "Tibet Autonomous Region", "Hong Kong Special Administrative Region",
                          "Macau Special Administrative Region"), "China"),
        "PAK": ([(INDIA, adm1("PAK", "Azad Kashmir", "Gilgit-Baltistan")),
                 ("Balochistan", adm1("PAK", "Balochistan"))],
                adm1_rest("PAK", "Azad Kashmir", "Gilgit-Baltistan", "Balochistan"), "Pakistan"),
        "IRQ": ([("Kurdistan", adm1("IRQ", "Erbil", "Dohuk", "Al-Sulaimaniyah"))],
                adm1_rest("IRQ", "Erbil", "Dohuk", "Al-Sulaimaniyah"), "Iraq"),
        "TZA": ([("Zanzibar", adm1("TZA", "North Pemba", "South Pemba", "Zanzibar North",
                                   "Zanzibar South & Central", "Zanzibar Urban/West"))],
                adm1_rest("TZA", "North Pemba", "South Pemba", "Zanzibar North",
                          "Zanzibar South & Central", "Zanzibar Urban/West"), "Tanzania"),
        "PNG": ([("Bougainville", adm1("PNG", "Autonomous Region of Bougainville"))],
                adm1_rest("PNG", "Autonomous Region of Bougainville"), "Papua New Guinea"),
        "GBR": ([("England", adm1("GBR", "England")), ("Scotland", adm1("GBR", "Scotland")),
                 ("Wales", adm1("GBR", "Wales")), ("Northern Ireland", adm1("GBR", "Northern Ireland")),
                 ("Diego Garcia", ne_country("IOT").buffer(0.5))],
                None, UK_OTHER),
        "GEO": ([("South Ossetia", south_ossetia),
                 ("Abkhazia", adm1("GEO", "Abkhazia"))],
                adm1_rest("GEO", "Abkhazia"), "Georgia"),
        "MDA": ([("Transnistria", adm1("MDA", "Transnistria", "Bender"))],
                adm1_rest("MDA", "Transnistria", "Bender"), "Moldova"),
        "SOM": ([("Somaliland", adm1("SOM", "Awdal", "Woqooyi Galbeed", "Togdheer", "Sool", "Sanaag"))],
                adm1_rest("SOM", "Awdal", "Woqooyi Galbeed", "Togdheer", "Sool", "Sanaag"), "Somalia"),
        "USA": ([("Puerto Rico", adm1("USA", "Puerto Rico")), ("Guam", adm1("USA", "Guam")),
                 ("American Samoa", adm1("USA", "American Samoa"))],
                adm1_rest("USA", "Puerto Rico", "Guam", "American Samoa"), "United States"),
        "NZL": ([("Cook Islands", ne_country("COK").buffer(0.3)), ("Niue", ne_country("NIU").buffer(0.3))],
                union(a1[a1.shapeGroup == "NZL"].geometry), "New Zealand"),
        "CYP": ([("Northern Cyprus", ne_country("CYN"))], ne_country("CYP", "CNM"), "Cyprus"),
    }

    geoms = defaultdict(list)
    sources = defaultdict(set)
    for _, row in a0.iterrows():
        iso, geom = row.shapeGroup, row.geometry
        if row.shapeType == "DISP":
            target = DISPUTED[row.shapeName]
            geoms[target].append(geom)
            sources[target].add(f"CGAZ disputed area: {row.shapeName}")
        elif iso in splits:
            print(f"  splitting {iso}")
            targets, rest_unit, default = splits[iso]
            for label, g in partition(geom, targets, rest_unit, default).items():
                geoms[label].append(g)
                sources[label].add(f"CGAZ ADM0 {iso} (split by CGAZ ADM1 / Natural Earth masks)")
        else:
            target = by_iso3[iso]
            geoms[target].append(geom)
            sources[target].add(f"CGAZ ADM0 {iso}")

    # CGAZ ADM0 covers only part of American Samoa; add the rest of its ADM1 islands.
    all_land = union(a0.geometry)
    geoms["American Samoa"].append(diff(adm1("USA", "American Samoa"), all_land))

    regions_geom = {name: union(gs) for name, gs in geoms.items()}
    regions_geom = apply_india_claim(regions_geom, ne["ne_10m_admin_0_countries_ind"], sources)
    regions_geom = resolve_overlaps(regions_geom)

    unknown = set(regions_geom) - names - set(UNLISTED)
    assert not unknown, f"labels not on the sheet: {unknown}"
    missing = [n for n in names if regions_geom.get(n, EMPTY).is_empty]
    assert not missing, f"regions without geometry: {missing}"
    return regions_geom, sources


def apply_india_claim(regions_geom, ne_ind, sources):
    """Move every area inside India's official claim (in the disputed sectors) to India."""
    print("Applying India's claimed boundary")
    pov = union(ne_ind[ne_ind.ADM0_A3 == "IND"].geometry)
    for sector, (bbox, donors) in INDIA_CLAIM_SECTORS.items():
        sector_box = box(*bbox)
        claim = inter(pov, sector_box)
        moved = []
        for donor in donors:
            d = regions_geom[donor]
            raw = diff(inter(d, claim), regions_geom[INDIA])
            # keep real claimed areas, not 1-2 km drawing differences between datasets
            keep = [p for p in shapely.get_parts(raw) if opening(p, 0.01).area > 5e-4]
            if keep:
                piece = union(keep)
                regions_geom[donor] = diff(d, piece)
                moved.append(piece)
        if moved:
            regions_geom[INDIA] = union([regions_geom[INDIA], *moved])
        # absorb thin donor slivers left between India and its claim line
        near_claim = claim.buffer(0.02)
        for donor in donors:
            d_local = inter(regions_geom[donor], sector_box)
            thin = diff(d_local, opening(d_local, 0.01))
            india = regions_geom[INDIA]
            grab = [p for p in shapely.get_parts(thin)
                    if p.within(near_claim) and p.distance(india) < 1e-6]
            if grab:
                piece = union(grab)
                regions_geom[donor] = diff(regions_geom[donor], piece)
                regions_geom[INDIA] = union([regions_geom[INDIA], piece])
                moved.append(piece)
        area = gpd.GeoSeries(moved, crs=4326).to_crs(EQUAL_AREA).area.sum() / 1e6 if moved else 0
        print(f"  {sector}: {area:,.0f} km² moved to India")
        if moved:
            sources[INDIA].add(f"India's claim (Natural Earth India view): {sector}")
    return regions_geom


def resolve_overlaps(regions_geom):
    """Remove residual slivers (from repairing invalid CGAZ input, e.g. LTU/RUS) from the larger region."""
    labels = list(regions_geom)
    geoms = [regions_geom[k] for k in labels]
    a, b = STRtree(geoms).query(geoms, predicate="intersects")
    for i, j in zip(a, b):
        if i < j:
            gi, gj = regions_geom[labels[i]], regions_geom[labels[j]]
            ov = inter(gi, gj)
            if ov.area > 0:
                big = labels[i] if gi.area >= gj.area else labels[j]
                print(f"  removing {ov.area:.1e} deg² overlap of {labels[i]} / {labels[j]} from {big}")
                regions_geom[big] = diff(regions_geom[big], ov)
    return regions_geom


# ---------------------------------------------------------------- checks & outputs

def to_frame(regions, regions_geom, sources):
    rows = []
    for r in regions:
        rows.append({**r, "on_sheet": True, "note": None,
                     "source": "; ".join(sorted(sources[r["name"]])), "geometry": regions_geom[r["name"]]})
    for name, (zone_code, note) in UNLISTED.items():
        if name in regions_geom and not regions_geom[name].is_empty:
            zone = next((r["zone"] for r in regions if r["zone_code"] == zone_code), None)
            rows.append({"bhulok_id": None, "name": name, "iso_a2": None, "numeric_code": None,
                         "zone_code": zone_code, "zone": zone, "onboarded": False, "on_sheet": False,
                         "note": note, "source": "; ".join(sorted(sources[name])), "geometry": regions_geom[name]})
    gdf = gpd.GeoDataFrame(rows, crs=4326)
    gdf["area_km2"] = gdf.to_crs(EQUAL_AREA).area.div(1e6).round(1)
    # label point is guaranteed inside the region (unlike the centroid of e.g. Chile or an archipelago)
    label = gdf.representative_point()
    gdf["label_lat"], gdf["label_lon"] = label.y.round(5), label.x.round(5)
    bounds = gdf.bounds.round(5)
    gdf["bbox_west"], gdf["bbox_south"] = bounds.minx, bounds.miny
    gdf["bbox_east"], gdf["bbox_north"] = bounds.maxx, bounds.maxy
    return gdf


def check(gdf):
    print("Checking")
    geoms = gdf.geometry.values
    tree = STRtree(geoms)
    a, b = tree.query(geoms, predicate="intersects")
    overlaps = []
    for i, j in zip(a, b):
        if i < j:
            ov = inter(geoms[i], geoms[j]).area
            if ov > 1e-8:
                overlaps.append((gdf.name.iloc[i], gdf.name.iloc[j], ov))
    assert not overlaps, f"overlapping regions: {overlaps[:10]}"
    failures = []
    for label, ((lat, lon), expected) in CHECK_POINTS.items():
        hits = gdf[gdf.contains(Point(lon, lat))].name.tolist()
        if hits != [expected]:
            failures.append((label, expected, hits))
    assert not failures, f"check points in the wrong region: {failures}"
    on_sheet = gdf[gdf.on_sheet]
    assert len(on_sheet) == 220 and on_sheet.name.is_unique
    print(f"  {len(on_sheet)} sheet regions + {len(gdf) - len(on_sheet)} unlisted areas, no overlaps, "
          f"{len(CHECK_POINTS)} check points OK")


def simplify(gdf):
    geoms = gdf.geometry.values
    if shapely.coverage_is_valid(geoms):
        simplified = shapely.coverage_simplify(geoms, SIMPLIFY_TOLERANCE)
    else:
        print("  coverage not exactly valid; simplifying regions independently")
        simplified = shapely.simplify(geoms, SIMPLIFY_TOLERANCE / 2, preserve_topology=True)
    out = gdf.copy()
    out["geometry"] = [polys(shapely.make_valid(g)) for g in simplified]
    return out


def write_outputs(gdf):
    print("Writing outputs")
    OUT.mkdir(exist_ok=True)
    gdf.to_file(CACHE / "bhulok_regions_full.gpkg", driver="GPKG")
    gdf.drop(columns="geometry").to_csv(OUT / "bhulok_regions.csv", index=False)

    small = simplify(gdf)
    small.to_file(OUT / "bhulok_regions.geojson", driver="GeoJSON",
                  layer_options={"COORDINATE_PRECISION": 4, "RFC7946": "YES"})
    zones = (small[small.zone_code.notna()]
             .dissolve(by=["zone_code", "zone"], aggfunc={"name": "count", "on_sheet": "sum"})
             .rename(columns={"name": "areas", "on_sheet": "regions"}).reset_index())
    zones["geometry"] = [polys(g) for g in shapely.make_valid(zones.geometry.values)]
    zones.to_file(OUT / "bhulok_zones.geojson", driver="GeoJSON",
                  layer_options={"COORDINATE_PRECISION": 4, "RFC7946": "YES"})
    render(small, zones)


def render(regions, zones):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    ink, muted, surface = "#1f1f1d", "#5f5e58", "#fcfcfb"
    order = ["BRT", "USSR", "EUR", "JPN", "AFR", "AMR", "OZ", "OTH"]
    counts = regions[regions.on_sheet].zone_code.value_counts()
    zone_names = dict(zip(zones.zone_code, zones.zone))
    proj = regions.to_crs(EQUAL_AREA)
    color = proj.zone_code.map(ZONE_COLORS).fillna("#e4e3de")

    # World map
    fig, ax = plt.subplots(figsize=(16, 8.6), facecolor=surface)
    proj.plot(ax=ax, color=color, edgecolor=surface, linewidth=0.25)
    zones.to_crs(EQUAL_AREA).boundary.plot(ax=ax, color=ink, linewidth=0.5)
    labels = {"BRT": (79, 21), "USSR": (85, 58), "EUR": (12, 49), "JPN": (138, 37), "AFR": (21, 4),
              "AMR": (-95, 40), "OZ": (134, -26), "OTH": (102, 34)}
    pts = gpd.GeoSeries([Point(lon, lat) for lon, lat in labels.values()], crs=4326).to_crs(EQUAL_AREA)
    for code, p in zip(labels, pts):
        ax.annotate(zone_names[code], (p.x, p.y), ha="center", va="center", fontsize=11, weight="bold",
                    color=ink, bbox=dict(boxstyle="round,pad=0.25", fc=surface, ec="none", alpha=0.85))
    ax.legend(handles=[Patch(facecolor=ZONE_COLORS[c], edgecolor=ink, linewidth=0.4,
                             label=f"{zone_names[c]} ({c}) · {counts.get(c, 0)}") for c in order],
              loc="lower left", frameon=False, fontsize=10, labelcolor=ink, title="Zone · regions",
              title_fontproperties={"weight": "bold", "size": 10})
    ax.set_title("Bhulok — 220 administrative regions in 8 zones", loc="left", fontsize=16, color=ink, weight="bold")
    ax.text(0, 1.0, "Region borders in white, zone borders in black. India shown with its claimed boundary.",
            transform=ax.transAxes, fontsize=10, color=muted, va="bottom")
    ax.set_axis_off()
    fig.savefig(OUT / "bhulok_zones_map.png", dpi=160, bbox_inches="tight", facecolor=surface)
    plt.close(fig)

    # India close-up
    view = box(60, 5, 100, 39)
    local = regions[regions.intersects(view)].copy()
    local["geometry"] = local.geometry.intersection(view)
    fig, ax = plt.subplots(figsize=(11, 10), facecolor=surface)
    local.plot(ax=ax, color=local.zone_code.map(ZONE_COLORS).fillna("#e4e3de"), edgecolor=surface, linewidth=0.6)
    local[local.name == INDIA].boundary.plot(ax=ax, color=ink, linewidth=1.4)
    for name, (lon, lat) in {"Gilgit-Baltistan": (75.0, 36.2), "PoK": (73.7, 34.1), "Aksai Chin": (79.6, 35.2),
                             "Shaksgam": (76.5, 36.15), "Arunachal": (93.8, 28.0)}.items():
        ax.annotate(name, (lon, lat), ha="center", fontsize=9, color=ink,
                    bbox=dict(boxstyle="round,pad=0.2", fc=surface, ec="none", alpha=0.8))
    for name in ["Bharat (India)", "Pakistan", "Balochistan", "Tibet", "China", "Nepal", "Afghanistan",
                 "Bangladesh", "Myanmar", "Sri Lanka", "Bhutan"]:
        g = local[local.name == name].geometry
        if len(g):
            p = g.iloc[0].representative_point() if name != "Bharat (India)" else Point(78.5, 22.5)
            ax.annotate(name, (p.x, p.y), ha="center", fontsize=10, weight="bold", color=ink)
    ax.set_title("Bhārat zone close-up — India's boundary as claimed", loc="left", fontsize=14, color=ink, weight="bold")
    ax.set_xlim(60, 100); ax.set_ylim(5, 39); ax.set_axis_off()
    fig.savefig(OUT / "bhulok_india_closeup.png", dpi=160, bbox_inches="tight", facecolor=surface)
    plt.close(fig)


def main():
    regions = load_sheet()
    a0, a1, ne = load_inputs()
    regions_geom, sources = build(a0, a1, ne, regions)
    gdf = to_frame(regions, regions_geom, sources)
    check(gdf)
    write_outputs(gdf)
    print(f"Done: {OUT}")


if __name__ == "__main__":
    sys.exit(main())
