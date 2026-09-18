# System Changelog & Version History

All notable changes, architectural updates, format modifications, and bug fixes for the **CUS SO & FnV Sales Order Automation Platform** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.2.0] - Dual Railway/Vercel Deployment, Combined Pipelines & REST Expansion - 2026-09-18

### Added
- **Combined GRO + FnV Parallel Processing Endpoint (`POST /api/v1/combined/process`)**:
  - Accepts both Grocery and FnV allocation files simultaneously.
  - Spawns parallel Python threads (`threading.Thread`) to run GRO and FnV automations concurrently, reducing total turnaround time from ~45s to ~30s.
  - Returns unified JSON response with `so_type: "GRO_FNV_COMBINED"`, segregated `gro` and `fnv` sections, combined grand total metrics, and isolated error reporting.
- **Brand Purchase Order (PO) REST Endpoint (`POST /api/v1/brand-po/process`)**:
  - Full vendor PO generation via REST API returning structured JSON with `so_type: "BRAND_PO"`.
  - Supports city selection (`MUM`, `BLR`, etc.), date filtering, direct vendor exclusion (`exclude_direct`), and base64 output payloads.
- **Explicit SO Type Tagging**:
  - Standardized `so_type` field on all REST responses (`"GRO_SO"`, `"FNV_SO"`, `"BRAND_PO"`, `"GRO_FNV_COMBINED"`).
  - Added discovery endpoint `GET /api/v1/so/types` providing metadata, required parameters, and JSON schemas for all SO types.
- **Dual-Platform Cloud Deployment Support (Vercel + Railway)**:
  - Added [`railway.json`](file:///d:/CUS%20SO/railway.json) configuring Nixpacks builder, health check policies, and Gunicorn start command.
  - Added [`Procfile`](file:///d:/CUS%20SO/Procfile) with `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 300` for long-running batch jobs.
  - Updated [`app.py`](file:///d:/CUS%20SO/app.py) to bind to `0.0.0.0` and read `$PORT` dynamically from environment variables.
  - Maintained complete [`vercel.json`](file:///d:/CUS%20SO/vercel.json) compatibility for existing web UI users.
- **Centralized Environment Configuration**:
  - Added [`.env`](file:///d:/CUS%20SO/.env) and [`.env.example`](file:///d:/CUS%20SO/.env.example) managing Database, Google API, gRPC, and server configurations.
  - Updated [`db_lookup.py`](file:///d:/CUS%20SO/db_lookup.py) to read `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`, `DB_DATABASE` from environment variables before falling back to local files.
  - Added robust `.env` loader with zero-dependency fallback parser in [`api/index.py`](file:///d:/CUS%20SO/api/index.py).
  - Updated [`.gitignore`](file:///d:/CUS%20SO/.gitignore) to protect `.env`, `.env.local`, and credential files.

---

## [2.1.0] - Institutional Format & Direct DB Integration - 2026-09-17

### Added
- **Institutional Format Output Pipeline**:
  - Automatic generation of Institutional SO CSV (`<City> XD SO <Date> (Institution).csv`) alongside standard GRO SO CSV.
  - Standardized 15-column layout with concise API headers (`sku_id(req)`, `quantity(req)`, `delivery_date(DD-MM-YYYY)`, `lot_id(req)`, `skuTypeId`, `CustomerId`).
- **Direct Read-Only MySQL Connector (`db_lookup.py`)**:
  - Queries `asgard.Sku` and `vormir.ProductExternalInternalMapping` for instantaneous FSN-to-SKU and Lot ID resolution.
  - Queries `cyclops.sku` and `cyclops.vendor_sku_set_map` for customer pricing.
  - Read-only transaction enforcement (`SET SESSION TRANSACTION READ ONLY`) to protect production databases.
- **Global & Fuzzy Customer Contact Lookup**:
  - Global cross-city fallback in `asgard.Customer` for satellite store codes (e.g. `Rta_113_Thanjavur`).
  - Fuzzy prefix matching (e.g. `mum_172_wh_hl_01` → `mum_172%`).
- **gRPC API Service** (`grpc_service/`):
  - Protobuf definition file ([`so_service.proto`](file:///d:/CUS%20SO/grpc_service/so_service.proto)) defining the `SalesOrderService`.
  - Python stubs, gRPC server, and CLI test client.
- **REST API v1** (`/api/v1/`):
  - `GET /api/v1` discovery endpoint, `POST /api/v1/gro/process`, `POST /api/v1/fnv/process`, `GET /api/v1/gro/headers`, `GET /api/v1/gro/items`.

### Changed
- Standardized `sub_type(optional)` default value from `22` to `1` across GRO and FnV outputs.
- Standardized `Sales Price` to hardcoded `1` for allocation-based pricing.
- Standardized `ordering_mode(optional)` to numeric code `1` in Institutional output.
- Formatted `delivery_date` strictly as `DD-MM-YYYY`.

---

## [2.0.0] - FnV Two-Phase Parallelization & Web UI Refresh - 2026-09-15

### Added
- **FnV Two-Phase Batch Optimization (`fnv_automation.py`)**:
  - Refactored multi-city FnV processing into Phase A (Batch Write & Formula Drag), Phase B (Single 10s Parallel Cloud Calc Pause), Phase C (Batch Read & Export).
  - Reduced multi-city Google Sheets evaluation wait time from ~35s to ~10s.
- **Automated City Detection (`/detect-city`)**:
  - Auto-detection API endpoint inspecting uploaded file headers and filenames.
- **Base64 File Streaming (`/download_path`)**:
  - Direct base64 file encoding for single-click downloads in web dashboard without page reloads.

### Fixed
- Fixed Windows terminal character encoding crashes by injecting `sys.stdout.reconfigure(encoding='utf-8')`.
- Fixed trailing float decimal parsing artifacts (e.g. `890123.0` → `890123`).

---

## [1.0.0] - Initial Release

### Added
- Initial release of GRO Sales Order (SO) automation pipeline.
- Single-city processing for Bangalore, Chennai, Mumbai, Hyderabad, Trichy, Coimbatore, Nashik.
- Excel audit report generation (`SO Output` & `NA Rows` tabs).
- PO Mapping file export.
