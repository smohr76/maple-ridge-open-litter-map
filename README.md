# Maple Ridge OpenLitterMap GIS Pipeline

This repository hosts an automated, zero-cost geospatial ETL pipeline and interactive web visualization for personal OpenLitterMap (OLM) data contributions in Maple Ridge, British Columbia.

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
| **Compute / ETL** | GitHub Actions (`ubuntu-latest`) | **$0.00** (~180 free runner mins/month out of 2,000)

 |
| **Static Hosting** | GitHub Pages | **$0.00** (Free static distribution)

 |
| **Map Rendering** | MapLibre GL JS + CARTO Basemaps | **$0.00** (Open-source GL library & free vector tile tiers)

 |
| **Data Storage** | Native Repository Git LFS / File Tracking | **$0.00** (Flat GeoJSON text artifacts)

 |

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
Next Steps: Production-Quality Hardening

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
