# Bhulok Administrative Regions

Administrative-boundary data for **[Project Bhulok](https://www.bhulok.org)** — *One Earth · One Family*.

Bhulok's [members](https://www.bhulok.org/Members.dc.html) are administrative regions, not only sovereign states: every region on Earth is represented, including contested and self-governing territories such as Tibet, Somaliland, Abkhazia, South Ossetia, Kurdistan, Zanzibar, Bougainville and the four UK home nations. This repository holds the boundaries those 220 member regions are drawn from and grouped into Bhulok's 8 zones.

## What's here

| Path | Contents |
| -- | -- |
| `Bhulok_220_Regions_by_Zone.xlsx` | Authoritative list of the 220 Bhulok regions (ISO alpha-2, numeric code, zone, onboarding status) and the 8 zones. |
| `bhulok/build_bhulok_map.py` | Builds the Bhulok region and zone boundaries from geoBoundaries CGAZ (ADM0 + ADM1), with Natural Earth v5.1.2 for areas CGAZ cannot express. Disputes involving India are resolved along India's claimed boundary. |
| `bhulok/output/` | Build outputs: `bhulok_regions.geojson`, `bhulok_zones.geojson`, `bhulok_regions.csv`, and preview maps. |
| `sourceData/`, `releaseData/` | The complete geoBoundaries source submissions and release builds, unchanged from upstream (stored in Git LFS). |

To rebuild the Bhulok boundaries from the repo root:

```
uv run --managed-python bhulok/build_bhulok_map.py
```

## Cloning

All files under `sourceData/` and `releaseData/` are stored in Git LFS (about 41 GB in total). Clone over SSH or with the GitHub CLI; HTTPS clones hit GitHub's LFS rate limits:

```
git clone git@github.com:logichulk/bhulok-administrative-regions.git
# or
gh repo clone logichulk/bhulok-administrative-regions
```

To skip the large LFS download and fetch only what you need:

```
GIT_LFS_SKIP_SMUDGE=1 git clone git@github.com:logichulk/bhulok-administrative-regions.git
git lfs pull --include "releaseData/gbOpen/IND/**"
```

## Attribution

This repository is a fork of [wmgeolab/geoBoundaries](https://github.com/wmgeolab/geoBoundaries), built by the geoBoundaries community and the [William & Mary geoLab](https://geolab.wm.edu/) and licensed CC BY 4.0 / ODbL. The only requirement for use is acknowledgement. Please cite geoBoundaries when using this data:

> Runfola, D. et al. (2020) geoBoundaries: A global database of political administrative boundaries. PLoS ONE 15(4): e0231866. https://doi.org/10.1371/journal.pone.0231866

Natural Earth data used by the Bhulok build is in the public domain.

---

# About geoBoundaries (upstream)

The rest of this README is the upstream geoBoundaries documentation, kept for reference.

![image](https://user-images.githubusercontent.com/7882645/216724015-071055db-e635-418b-83a6-acbdde726c6c.png)
Built by the [community](https://github.com/wmgeolab/geoBoundaries/) and [William & Mary geoLab](https://geolab.wm.edu/), the geoBoundaries Global Database of Political Administrative Boundaries Database is an online, open license (CC BY 4.0 / ODbL) resource of information on administrative boundaries (i.e., state, county) for every country in the world. Since 2016, we have tracked approximately 1 million boundaries within over 200 entities, including all UN member states. All boundaries are available to view or download in common file formats; the only requirement for use is acknowledgement.

## Related Repositories
The geoBoundaries project is made up of a number of different repositories; you are currently on the core repo which stores all input datasets and builds.  If you are interested in understanding other components of geoBoundaries, you can visit:
- [geoBoundaryBot](https://github.com/wmgeolab/geoBoundaryBot): where our build scripts live, as well as the various QA/QC algorithms applied to pull requests in this repository.  If you're interested in the specifics of our topology checks or simplification strategies, this is where to look.
- [gbWeb](https://github.com/wmgeolab/gbWeb): where the website itself lives, as well as the API.  Various scripts that aid in building the API and other things related to the website can be found here as well.
- [rgeoboundaries](https://github.com/wmgeolab/rgeoboundaries): built by community member @dickoa, this library allows you to retrieve and manipulate geoBoundaries data within the R programming environment.
- [pygeoboundaries](https://github.com/ibhalin/pygeoboundaries) built by community member @ibhalin, this package allows you to retrieve and manipulate geoBoundaries data within the python programming environment.

## Getting Involved
We welcome contributions to the geoBoundaries dataset.  Involvement can take many forms: assistance identifying errors in the database, contributing boundary files, or even contributing code for our build or website scripts.  To get started, you could:
- [Report Boundary Errors](https://github.com/wmgeolab/geoBoundaries/issues/new?assignees=&labels=&template=boundary-errata.md&title=%5BBOUNDARY+ERRATA%5D): While we try to ensure geoBoundaries is as error-free as possible, we are currently tracking around 300 million vertices across hundreds-of-thousands of geometries - there are bound to be issues!  We very much welcome any reports of errors across the database.
- [Contribute Boundaries](https://github.com/wmgeolab/geoBoundaries/blob/main/CONTRIBUTING.md): We carefully curate all boundaries that are submitted to the database, and have a very active community.  Join us in the fun!  We try to keep things simple for everyone, requiring only a zipfile upload. 
- [Fix Known Issues](https://github.com/wmgeolab/geoBoundaries/issues): We have a number of known issues with the database, and always welcome contributions that might fix any of these.  
- [Help with the Python Code](https://github.com/wmgeolab/geoBoundaryBot): We always welcome contributions to our codebase that improve the efficiency of our processing, or introduce new types of checks to automatically prevent errors.  Our code includes a number of different pieces, such as the www.geoboundaries.org website, API, the geoBoundaryBot (responds to PRs), and our formal build scripts.


## File Access

We provide three different mechanisms to download geoBoundaries data: a web-based GUI, HTML file access on GitHub (for archival versions), and an API. Releases come in both unsimplified and simplified types, and include a global composite of ADM0, ADM1, and ADM2 with gaps filled between borders ("CGAZ").  Acronyms describing these datasets you may encounter include:

_HPSC_  - High Precision Single Country. The premier geoBoundaries release, representing the highest precision files available for every country in the world. Every country is represented as that country represents itself, so (for example) two countries may overlap in the case of contested boundaries.

_SSC_  - Simplified Single Country. A simplified version of every file available for every country in the world, using the HPSCU product as a base. 

_CGAZ_  - Comprehensive Global Administrative Zones. A global composite of the SSC ADM0, ADM1 and ADM2, clipped to international boundaries (US Department of State), with gaps filled between borders.  Also available at higher levels of simplification.

## Versioned Releases for Research Replication

While geoBoundaries is always updating, we provide regular releases to facilitate future research replication. To download a file from any release, you can navigate to our [releases page](https://github.com/wmgeolab/geoBoundaries/releases/), and choose the release you are interested in retrieving files from, or you can navigate to the appropriate location using this table:
Release | Date | Link
-- | -- | --
geoBoundaries 6.0.0 | September 14, 2023 | [2d572d4](https://github.com/wmgeolab/geoBoundaries/tree/1289e40e366c7b320550be1ee0614a9472d572d4)
geoBoundaries 5.0.0 | December 19, 2022 | [997c6a8](https://github.com/wmgeolab/geoBoundaries/tree/b7dd6a55701c76a330500ad9d9240f2b9997c6a8)
geoBoundaries 4.0.0 | August 31, 2021 | [299e006](https://github.com/wmgeolab/geoBoundariesArchive_4_0_0/tree/299e00623ece6c03bcb9a751eda6094b1eac85a6)
geoBoundaries 3.0.0 | June 5, 2020 | [7c8dbc5](https://github.com/wmgeolab/geoBoundariesArchive_3_0_0/tree/7c8dbc599e312d9204e450aecfa66c204b8cf9b8)
geoBoundaries 2.0.1 | December 7, 2019 | [375ea48](https://github.com/wmgeolab/geoBoundariesArchive_2_0_1)
geoBoundaries 1.3.4 | November 11, 2018 | [d3f7490](https://github.com/wmgeolab/geoBoundariesArchive_1_3_3/)

If you are interested in releases prior to 1.3.4, please [contact us](mailto:team@geoboundaries.org).

## Programmatic / API Access
Full details on our API are available [here](https://www.geoboundaries.org/api.html).  

To find information on the most up-to-date boundaries available-

```
https://www.geoboundaries.org/api/current/gbOpen/[3-LETTER-ISO-CODE]/[ADM-LEVEL]/
```

Users can also enter the special phrase "ALL" for either "ADM" or "ISO" to get a multi-boundary return. Each requested boundary returns all metadata available for that boundary in the gBOpen release, including a link to both the full-resolution, large-file size and the simplified small-file size versions. Users can additionally replace "gbOpen" with either "gbAuthoritative" or "gbHumanitarian" to filter results to only include boundaries from those two respective releases.

Of note, to facilitate speed of queries against the API all JSONs are pre-cached and can be exported in bulk by cloning the [geoBoundaries Website repository](https://github.com/wmgeolab/gbWeb) for local use.

## Note on Cloning

As of geoBoundaries 5.0.0, all files in geoBoundaries are stored using Git's Large File Storage (LFS).  Because this entails such a large volume of files, a bug in the current GitHub API results in a rate limiting error if you attempt to clone using https methods (i.e., ``git clone https://github.com/wmgeolab/geoBoundaries.git`` will fail with a rate limiting error).  Cloning with SSH (``git clone git@github.com:wmgeolab/geoBoundaries.git``) and the GitHub CLI (``gh repo clone wmgeolab/geoBoundaries``) work without issue. 



<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->
