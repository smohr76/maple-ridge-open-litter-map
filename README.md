# Maple Ridge OpenLitterMap GIS Pipeline - Update September 19, 2026

This repository hosts an automated, zero-cost geospatial ETL pipeline and interactive web visualization for personal OpenLitterMap (OLM) data contributions in Maple Ridge, British Columbia.

---

## CI and Test Workflow

This project includes a lightweight GitHub Actions test gate to help protect the data transformation layer.

### Automated test workflow

The repository runs a Python test workflow on every push and pull request via:

- `.github/workflows/tests.yml`

What it does:

- checks out the repository
- sets up Python 3.11
- installs `pytest` and `requests`
- runs `pytest -q`

Current validation status:

- the workflow is expected to pass for core OLM normalization and validation logic
- test coverage currently targets the ingestion helper functions, tag normalization, GeoJSON validation, and success-marker behavior

### Hardening rules in effect

The current hardening branch is intentionally enforcing a few operational safeguards:

- validate GeoJSON before writing or publishing it
- reject empty or malformed FeatureCollections
- ensure coordinates are numeric and within valid latitude/longitude bounds
- write GeoJSON atomically to avoid partially written files during interrupted runs
- keep a backup of the previous working dataset when an update is attempted
- retry transient HTTP requests with exponential backoff for OLM auth and fetch calls
- write a `.last_success.txt` marker after successful pipeline execution for traceability

These safeguards are designed to keep the GitHub Pages map and the ingestion pipeline resilient without introducing paid infrastructure or external services.

---

## Technical Summary: Stage 1 Architectural Milestones

### Objective & Architectural Goals

The Stage 1 goal was to establish an automated, continuous integration and data delivery pipeline to extract raw, multi-page spatial data from the OpenLitterMap API, map complex nested litter tagging formats into a normalized flat schema, and render an interactive spatial map via a client-side interface.

The core architectural constraints required maintaining a **$0.00/month infrastructure cost** while eliminating manual data exports, deployment file path drift, and third-party SaaS API dependencies.

### Engineering Accomplishments & Implementation Details

#### 1. Resilient Sentinel-Based Ingestion (`scripts/sync_data.py`)

* **API Paradigm Shift**: Migrated from legacy endpoints to the OpenLitterMap `v3` endpoint (`/api/v3/user/photos`) using bearer token authentication.

* **Pagination Remediation**: Standardized pagination on a **Sentinel-Based (Page-Until-Empty)** traversal strategy (`?page=1`, `?page=2`, `...`). This decoupled ingestion from volatile server-side pagination metadata keys (`last_page`, `meta.last_page`, `next_page_url`), successfully scaling dataset extraction from an initial 8-record stub to the full 1,600+ georeferenced feature collection.

* **Defensive Error Handling**: Implemented exponential backoff retries, safety page circuit breakers, and network exception handling to prevent job crashes during automated execution.

#### 2. Schema Normalization & Classification

* **Tag Resolution**: Built mapping functions (`resolve_new_tags_format` and `resolve_summary_format`) to handle structural variations between legacy tag summaries and new OLM tag hierarchies.

* **Flattened Feature Flags**: Computed top-level boolean properties (`has_litter`, `has_pet_waste`, `has_substances`) within each GeoJSON feature to support high-performance client-side spatial queries.

#### 3. Continuous Delivery & Dual-Path Asset Staging (`.github/workflows/sync_data.yml`)

* **Automation**: Configured a scheduled GitHub Actions workflow executing every 12 hours (`0 */12 * * *`) on `ubuntu-latest` runners.

* **Dual Target Writing**: Pipeline exports compiled GeoJSON payloads to both `data/litter.geojson` and `public/data/litter.geojson` simultaneously, resolving build-target path discrepancies across static hosting environments.

* **No-Op Commit Filtering**: Evaluates staged `git diff` state prior to committing, preventing empty automated commits when source data remains unchanged.

#### 4. High-Performance Client Rendering (`index.html`)

* **Engine**: Built with MapLibre GL JS utilizing CARTO Positron vector basemaps.

* **Data Ingestion**: Features a fallback `fetch()` loader checking `./data/litter.geojson` and `./public/data/litter.geojson`.

* **Interactive UI**: Supports real-time boolean attribute filtering and dynamic spatial bounding (`LngLatBounds.fitBounds`).

---

## Infrastructure & Operational Cost Analysis

| Component | Technology | Cost / Overhead |
| --- | --- | --- |
| **Compute / ETL** | GitHub Actions (`ubuntu-latest`) | **$0.00** (~180 free runner mins/month out of 2,000) |
| **Static Hosting** | GitHub Pages | **$0.00** (Free static distribution) |
| **Map Rendering** | MapLibre GL JS + CARTO Basemaps | **$0.00** (Open-source GL library & free vector tile tiers) |
| **Data Storage** | Native Repository Git LFS / File Tracking | **$0.00** (Flat GeoJSON text artifacts) |

---

## Stage 2 Roadmap: Advanced Spatial Analytics & Data Enrichment

With the core ETL pipeline and baseline visualization fully operational, Stage 2 focuses on expanding spatial analysis capabilities, client-side rendering performance, and data engagement.

```
┌────────────────────────┐      ┌──────────────────────────┐      ┌──────────────────────────┐
│  OLM v3 API Ingestion  │ ───► │  GitHub Actions Pipeline │ ───► │ Static GeoJSON Datasets  │
│  (Page-Until-Empty)    │      │  (Dual-Path Target Sync) │      │  (data / public/data)    │
└────────────────────────┘      └──────────────────────────┘      └──────────────────────────┘
                                                                               │
                                                                               ▼
┌────────────────────────┐      ┌──────────────────────────┐      ┌──────────────────────────┐
│  Spatial Heatmaps &    │ ◄─── │ Advanced Client-Side UI  │ ◄─── │ MapLibre GL Vector Engine│
│  Time-Series Analytics │      │ (Filtering & Popups)     │      │ (Flat Boolean Filters)   │
└────────────────────────┘      └──────────────────────────┘      └──────────────────────────┘
```

### Planned Technical Objectives

* **High-Density Clustering & Heatmap Rendering**: Implement `supercluster` integration or MapLibre `heatmap` layer types to gracefully handle expanding point density in high-volume collection routes without UI frame drops.

* **Temporal & Time-Series Analytics**: Expose time-based filtering controls (e.g., date-range sliders) driven by the extracted ISO `datetime` properties to visualize litter accumulation patterns over time.

* **Rich Spatial Popups & Media Links**: Enhance interactive map nodes with contextual modal popups displaying detailed item tags, brand categorization, and high-resolution photo asset previews sourced directly from OLM storage.

--------------------------------------------------------------------------------------
# Next Steps: Production-Quality Hardening

The current application is fully functional and suitable for the project’s intended use. The next development phase will focus on improving reliability, maintainability, accessibility, and automated quality control.

Planned improvements include:

    Add unit tests for API response parsing, tag normalization, classification, coordinate validation, and GeoJSON generation.
    Strengthen API error handling with retries, exponential backoff, rate-limit support, and explicit failure behavior.
    Validate API responses, latitude/longitude ranges, and generated GeoJSON before publishing updates.
    Prevent incomplete datasets from overwriting the existing production data.
    Write GeoJSON files atomically to avoid partial files if a workflow is interrupted.
    Add Python type hints, structured logging, dependency pinning, and automated linting.
    Add CI quality gates for tests, Python linting, HTML validation, JavaScript validation, and GeoJSON schema validation.
    Improve the map interface’s accessibility with semantic form controls, keyboard support, ARIA status messaging, and a non-map data summary.
    Add MapLibre error handling and clearer user-facing messages when the basemap or dataset cannot be loaded.
    Review external CDN dependencies and consider Subresource Integrity, a Content Security Policy, and pinned action versions.
    Reduce duplication between the canonical and deployed GeoJSON paths where practical.

These improvements will preserve the current low-cost architecture while making the ETL pipeline and web client more resilient, testable, secure, and maintainable.

* **Automated Data Validation & Metric Badging**: Add schema validation tests (e.g., GeoJSON validation via `jsonschema` or `turf`) into the CI pipeline, alongside dynamic README badges displaying live dataset statistics (e.g., total point counts, last sync date).

------------------------------------------------
## Where the project is now end of day Sept 18

The branch `hardening/olm-ingestion-and-audit` currently has:

### Completed

- API retry and backoff behavior
- Pagination through all available pages
- Coordinate validation
- GeoJSON FeatureCollection validation
- Rejection of empty datasets
- Atomic dataset writes
- Backup/rollback behavior
- A last-success marker
- Unit tests for representative tag formats
- Basic normalized fields such as:
  - `groups`
  - `has_litter`
  - `has_pet_waste`
  - `has_substances`
  - `color_group`

### Not completed

The tests do **not yet establish that the classification is semantically correct across the full dataset**.

They currently answer questions like:

> “Does this known smoking example become `substances`?”

They do not answer:

> “Are all 1,600 records grouped and named correctly according to the project’s intended crosswalk?”

That distinction is important.

The README uses “validation” in two different senses:

1. **Structural validation** — Is this valid GeoJSON with valid coordinates?
2. **Semantic validation** — Is a cigarette actually classified as substances, is dog waste classified as pet waste, and are material/brand categories being assigned correctly?

The first is substantially implemented. The second is still in progress.

## The map is already exposing a classification issue

The hardening branch adds a `color_group` field and displays it on the map. However, there are signs that the crosswalk is not yet stable.

For example, `infer_color_group()` can produce values such as:

- `material`
- `brand`
- `single_use`
- `plastic`
- `paper`
- `metal`
- `glass`
- `pet_waste`
- `substances`

But the MapLibre color expression does not explicitly define every possible value. The map has explicit colors for several categories, but unknown values fall back to the default green color.

That means a record classified as `material` or `brand` may appear visually as ordinary green litter, even though it has a more specific classification. This is exactly the kind of problem you need to see on the map before approving the crosswalk.

There is another potential inconsistency:

- `classify_tag_group()` only treats specific pet items such as `dogshit` and `dogshit_in_bag` as `pet_waste`.
- `infer_color_group()` treats the broader category `pets` as `pet_waste`.

So the grouping flags and the display color could disagree for some records.

## Recommended direction for this phase

I would pause major GIS feature development temporarily and define the current phase as:

> **Crosswalk verification and data observability**

The goal should be to make the normalized litter objects inspectable by a human before building more analytics.

### 1. Create a dedicated data-review mode

The map should become a review tool, not just a visualization.

Clicking a point should show:

- OpenLitterMap photo ID
- Date/time
- Original raw category/object
- Normalized tags
- `groups`
- `color_group`
- `has_litter`
- `has_pet_waste`
- `has_substances`
- Any material or brand values
- Photo link, if available

The popup should show both:

```text
Source classification: smoking / cigarette
Normalized group: substances
Display group: substances
```

That lets you verify whether the crosswalk is doing what you intended.

### 2. Add a visible data table

A map alone is not enough for reviewing 1,600 objects.

Add a table or side panel containing:

- ID
- date
- normalized name
- category
- group
- color group
- coordinates
- photo link

Selecting a row should highlight the point on the map. Selecting a point should highlight the row.

This would allow you to review records systematically rather than trying to interpret colors in a dense map.

### 3. Add a “classification audit” report

The ingestion process should generate a small report such as:

```text
Total records: 1600

Groups:
  litter: 1200
  substances: 280
  pet_waste: 120
  multiple groups: 35

Color groups:
  substances: 280
  pet_waste: 120
  plastic: 300
  paper: 150
  material: 400
  brand: 25
  fallback/unknown: 25
```

The report should also list:

- unknown categories
- unknown objects
- records with no tags
- records with conflicting flags
- records where `color_group` is not represented in the UI
- records assigned to a fallback color

Those are the records you need to inspect first.

### 4. Establish a human-approved crosswalk

Before adding more GIS analysis, create a formal mapping table:

| Source category/object | Normalized group | Display group | Approved? |
|---|---|---|---|
| smoking / cigarette | substances | substances | yes |
| pets / dogshit | pet_waste | pet_waste | yes |
| plastic / bottle | litter | plastic | yes |
| material / paper | litter | paper | yes |
| unknown object | litter | unknown | review |

This should become the authoritative definition of the project’s categories.

The code and tests should then be driven from this table rather than from scattered conditionals.

### 5. Add representative fixtures from the real dataset

The current tests use hand-built examples. Add a small reviewed fixture file taken from actual OLM responses containing examples of:

- cigarette
- alcohol
- THC/cannabis
- dog waste
- bagged dog waste
- plastic
- paper
- metal
- glass
- branded objects
- multiple tags on one photo
- unknown/custom tags
- records with multiple groups

For each fixture, record the expected result. Then test the entire normalized output, not only one boolean.

## A sensible phase gate

I would not consider the data layer ready for broader GIS analytics until these conditions are true:

- Every displayed `color_group` has a defined color and legend entry.
- No records silently fall into an unexplained fallback color.
- Group flags and display groups agree.
- Multi-category records have an explicit precedence rule.
- Unknown source categories are reported.
- A human can inspect a point and see exactly why it received its group.
- A reviewed sample of real records passes.
- The audit report is generated during every sync.
- The map and table show the same normalized values.

## Suggested project sequence

### Phase A — Crosswalk verification

Current priority.

- stabilize naming
- inspect real records
- build the review table
- add audit summaries
- fix unknown/fallback categories
- approve the crosswalk

### Phase B — Classification regression protection

After you approve the behavior:

- add reviewed real-data fixtures
- add expected classification tests
- fail CI when classifications unexpectedly change
- version the crosswalk/schema

### Phase C — GIS feature development

Only after Phase A and B:

- heatmaps
- clustering improvements
- time sliders
- spatial summaries
- hotspot analysis
- filtering by material/category
- export tools

The good news is that the map work already added on this branch can be reused. It should now be treated as the **verification interface for the data crosswalk**, rather than moving immediately into advanced GIS analysis.

The clearest direction for the next task would be:

> Build a classification-review panel that exposes every normalized object and its source tags on the map, plus an automated category-count audit report. Do not add new GIS analytics until those outputs are reviewed and approved.
