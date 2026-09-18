# 🚀 Sales Order (SO) & PO REST & gRPC API Documentation

This document provides a comprehensive, end-to-end technical guide on how the API works: how it receives allocation files, interacts with Google Sheets and MySQL databases, processes the business logic, and generates structured JSON and downloadable outputs.

---

## 📑 Table of Contents
1. [Architecture & System Overview](#1-architecture--system-overview)
2. [End-to-End Processing Lifecycle](#2-end-to-end-processing-lifecycle)
   - [Phase 1: Request Ingestion & Validation](#phase-1-request-ingestion--validation)
   - [Phase 2: Google Sheets Cloud Automation](#phase-2-google-sheets-cloud-automation)
   - [Phase 3: Database Lookups (MySQL)](#phase-3-database-lookups-mysql)
   - [Phase 4: Transformation & Formatting](#phase-4-transformation--formatting)
   - [Phase 5: Response Serialization & Delivery](#phase-5-response-serialization--delivery)
3. [SO Type Classification Matrix](#3-so-type-classification-matrix)
4. [REST API Endpoints Reference](#4-rest-api-endpoints-reference)
   - [1. Discovery & Metadata](#1-discovery--metadata)
   - [2. Grocery SO (`POST /api/v1/gro/process`)](#2-grocery-so-post-apiv1groprocess)
   - [3. Fruits & Vegetables SO (`POST /api/v1/fnv/process`)](#3-fruits--vegetables-so-post-apiv1fnvprocess)
   - [4. Brand PO (`POST /api/v1/brand-po/process`)](#4-brand-po-post-apiv1brand-poprocess)
   - [5. Combined GRO + FnV (`POST /api/v1/combined/process`)](#5-combined-gro--fnv-post-apiv1combinedprocess)
5. [Code Examples & Client Integration](#5-code-examples--client-integration)
6. [Error Handling & Reliability](#6-error-handling--reliability)

---

## 1. Architecture & System Overview

```
                      ┌────────────────────────────────────────────────┐
                      │             API Consumers / Clients            │
                      │  (Web Dashboard, Python Scripts, Cron, Postman) │
                      └───────────────────────┬────────────────────────┘
                                              │ HTTP / JSON
                                              ▼
                      ┌────────────────────────────────────────────────┐
                      │          Flask API Gateway (/api/v1)           │
                      │    (Railway Container / Vercel Serverless)     │
                      └──────────────┬──────────────────┬──────────────┘
                                     │                  │
               ┌─────────────────────┴──────┐    ┌──────┴──────────────────────┐
               ▼                            ▼    ▼                             ▼
       [ GRO Pipeline ]             [ FnV Pipeline ]                   [ Brand PO Pipeline ]
     (Single City Grocery)       (Multi-City 2-Phase Batch)           (Vendor-Level Indent)
               │                            │                                  │
               ├────────────────────────────┼──────────────────────────────────┤
               ▼                            ▼                                  ▼
      ┌──────────────────┐        ┌──────────────────┐               ┌──────────────────┐
      │  Google Sheets   │        │ Direct DB Lookup │               │ In-Memory Caching│
      │ (Formula Engine) │        │ (MySQL Read-Only)│               │   & Base64 S3    │
      └──────────────────┘        └──────────────────┘               └──────────────────┘
```

The API runs as a unified microservice capable of being deployed on **Railway** (for long-running, multi-threaded workloads) and **Vercel** (for web dashboard requests).

---

## 2. End-to-End Processing Lifecycle

Every API request follows a 5-phase execution pipeline:

```
[ Upload Files ] ──► [ Google Sheets Sync ] ──► [ MySQL DB Lookup ] ──► [ Business Rules ] ──► [ JSON & Files ]
    Phase 1                 Phase 2                    Phase 3                 Phase 4               Phase 5
```

### Phase 1: Request Ingestion & Validation
1. Client sends a `POST` request with `multipart/form-data` containing:
   - File upload(s): `.xlsx` or `.csv` allocation sheet.
   - Form fields: `city`, `date` (YYYY-MM-DD), `format` (`Standard` or `Institutional`).
2. The API securely streams the file to temporary storage (`tempfile.mkdtemp()`) and extracts metadata.

### Phase 2: Google Sheets Cloud Automation
1. **Authentication**: Connects to Google Drive/Sheets API using the OAuth2 Service Account (`ecom-so-reader-credetials.json` or `ECOM_SO_CREDENTIALS_JSON` environment variable).
2. **Sheet Identification**: Opens target city worksheets (e.g., `Bangalore`, `Chennai`, `FnV_Allocation`).
3. **Data Injection**: Writes the uploaded allocation matrix into the Google Sheet starting at row 2.
4. **Formula Calculation**:
   - **For GRO SO**: Drags internal Google Sheet VLOOKUP formulas to compute SKU matches, pricing, and required pack sizes.
   - **For FnV SO (Two-Phase Batch)**: Writes all 7 cities in parallel, pauses for 10 seconds to allow Google's cloud formula engine to evaluate all cells concurrently, then reads back all results in a single batch read.

### Phase 3: Database Lookups (MySQL)
1. If SKUs or customer details require database resolution, [`db_lookup.py`](file:///d:/CUS%20SO/db_lookup.py) establishes a read-only transaction:
   - `asgard.Sku` & `vormir.ProductExternalInternalMapping` ➔ Resolves FSN ➔ SKU ID & Lot ID.
   - `cyclops.sku` & `cyclops.vendor_sku_set_map` ➔ Resolves Customer Pricing.
   - `asgard.Customer` ➔ Resolves customer contact numbers and satellite facility codes.
2. **Resilience**: If the database is unreachable, the system gracefully falls back to Google Sheet cached lookups without crashing.

### Phase 4: Transformation & Formatting
1. Data is filtered into **Valid SO Items** vs **NA / Discrepancy Items**.
2. Headers are mapped to the chosen format:
   - **Standard Format (16 Columns)**: Includes verbose headers, delivery slots, standard order modes (`DELIVERY`).
   - **Institutional Format (15 Columns)**: Compact headers (`sku_id(req)`, `quantity(req)`, `delivery_date(DD-MM-YYYY)`, `lot_id(req)`, `skuTypeId`, `CustomerId`).
3. Summary metrics (Total SKUs, Total Quantity, Total Value, NA Counts) are calculated.

### Phase 5: Response Serialization & Delivery
1. The API caches the processed run in memory under a unique `run_id` (UUID4).
2. Physical CSV and Excel audit workbooks are generated and encoded in `base64` so clients can download them immediately without secondary requests.
3. A standardized JSON response is returned containing the `so_type`, `headers`, `items`, `stats`, and file download payloads.

---

## 3. SO Type Classification Matrix

Every response explicitly contains an `so_type` identifier:

| `so_type` | Business Meaning | Scope | Key Endpoints |
|---|---|---|---|
| **`GRO_SO`** | Grocery Sales Order | Single City | `POST /api/v1/gro/process`<br>`GET /api/v1/gro/headers`<br>`GET /api/v1/gro/items` |
| **`FNV_SO`** | Fruits & Vegetables Sales Order | Multi-City (BLR, CHN, MUM, HYD, TRY, CBE, NSK) | `POST /api/v1/fnv/process`<br>`GET /api/v1/fnv/results` |
| **`BRAND_PO`** | Brand Purchase Order | Vendor PO Indent | `POST /api/v1/brand-po/process` |
| **`GRO_FNV_COMBINED`** | Parallel Combined SO | Both GRO & FnV pipelines | `POST /api/v1/combined/process` |

---

## 4. REST API Endpoints Reference

### 1. Discovery & Metadata

#### `GET /api/v1`
Returns interactive API map and list of all supported endpoints.

#### `GET /api/v1/so/types`
Returns full documentation, supported cities, and schema definitions for all 4 SO types.

---

### 2. Grocery SO (`POST /api/v1/gro/process`)

Processes a Grocery Allocation Excel sheet for a specific city.

* **URL**: `/api/v1/gro/process`
* **Method**: `POST`
* **Content-Type**: `multipart/form-data`

#### Request Parameters
| Parameter | Type | Required | Description |
|---|---|:---:|---|
| `file` | Binary File | Yes | Excel (`.xlsx`) or CSV allocation file |
| `city` | String | Yes | City name: `Bangalore`, `Chennai`, `Mumbai`, `Hyderabad`, `Trichy`, `Coimbatore`, `Nashik` |
| `date` | String | No | Target delivery date (`YYYY-MM-DD`). Defaults to tomorrow. |
| `format` | String | No | `Standard` or `Institutional` (Default: `Standard`) |

#### Example Response (`200 OK`)
```json
{
  "success": true,
  "so_type": "GRO_SO",
  "run_id": "9f7b1e4c-1234-4567-89ab-cdef01234567",
  "city": "Bangalore",
  "date": "2026-09-19",
  "format": "Standard",
  "headers": [
    "Facility Name", "Delivery Date", "Store Code", "Store Name",
    "Sku Code", "SKU Name", "Qty", "Selling Price", "Total Value",
    "Slot", "order_type", "sub_type(optional)", "ordering_mode(optional)"
  ],
  "stats": {
    "total_rows": 142,
    "total_qty": 3850.0,
    "total_val": 184200.0,
    "na_count": 2
  },
  "items": [
    {
      "Facility Name": "Bangalore Staples",
      "Delivery Date": "19-09-2026",
      "Store Code": "BLR_001",
      "Store Name": "Indiranagar Store",
      "Sku Code": "SKU10029",
      "SKU Name": "Sugar 1kg Premium",
      "Qty": 50,
      "Selling Price": 42.0,
      "Total Value": 2100.0
    }
  ],
  "files": {
    "so_csv": {
      "filename": "Bangalore XD SO 19-09-2026.csv",
      "base64": "..."
    },
    "audit_excel": {
      "filename": "Bangalore XD SO 19-09-2026.xlsx",
      "base64": "..."
    }
  }
}
```

---

### 3. Fruits & Vegetables SO (`POST /api/v1/fnv/process`)

Runs the multi-city batch evaluation for Fruits & Vegetables.

* **URL**: `/api/v1/fnv/process`
* **Method**: `POST`
* **Content-Type**: `multipart/form-data`

#### Request Parameters
| Parameter | Type | Required | Description |
|---|---|:---:|---|
| `file` | Binary File | Yes | Consolidated multi-city FnV allocation file |
| `date` | String | No | Target delivery date (`YYYY-MM-DD`) |

#### Example Response (`200 OK`)
```json
{
  "success": true,
  "so_type": "FNV_SO",
  "run_id": "3a8c2f1e-4567-89ab-cdef-0123456789ab",
  "date": "2026-09-19",
  "grand_totals": {
    "total_cities": 7,
    "total_rows": 890,
    "total_qty": 14500.5,
    "total_val": 642000.0
  },
  "cities": {
    "Bangalore": {
      "headers": [...],
      "stats": { "total_rows": 210, "total_qty": 4200.0, "total_val": 180000.0 },
      "items": [...]
    },
    "Chennai": {
      "headers": [...],
      "stats": { "total_rows": 180, "total_qty": 3100.0, "total_val": 140000.0 },
      "items": [...]
    }
  }
}
```

---

### 4. Brand PO (`POST /api/v1/brand-po/process`)

Generates Brand Purchase Orders grouped by vendor.

* **URL**: `/api/v1/brand-po/process`
* **Method**: `POST`
* **Content-Type**: `multipart/form-data` or `application/x-www-form-urlencoded`

#### Request Parameters
| Parameter | Type | Required | Description |
|---|---|:---:|---|
| `city` | String | No | City code: `MUM` (Default), `BLR`, `CHN`, `HYD` |
| `date` | String | No | Order date (`YYYY-MM-DD`) |
| `exclude_direct` | Boolean | No | Exclude direct vendor fulfillment (`true` or `false`) |

#### Example Response (`200 OK`)
```json
{
  "success": true,
  "so_type": "BRAND_PO",
  "run_id": "brand-po-mum-2026-09-19",
  "city": "MUM",
  "date": "2026-09-19",
  "total_vendors": 14,
  "grand_total_qty": 18500,
  "grand_total_val": 940000.0,
  "vendors": [
    {
      "vendor_name": "ITC Limited",
      "sku_count": 28,
      "total_qty": 2400,
      "total_val": 128000.0,
      "items": [
        {
          "sku_id": "SKU55401",
          "sku_name": "Aashirvaad Atta 10kg",
          "indent_qty": 100,
          "allocated_qty": 100,
          "rate": 390.0,
          "amount": 39000.0
        }
      ]
    }
  ]
}
```

---

### 5. Combined GRO + FnV (`POST /api/v1/combined/process`)

Executes both Grocery SO and FnV SO pipelines simultaneously in parallel background threads and returns a single merged response.

* **URL**: `/api/v1/combined/process`
* **Method**: `POST`
* **Content-Type**: `multipart/form-data`

#### Request Parameters
| Parameter | Type | Required | Description |
|---|---|:---:|---|
| `gro_file` | Binary File | Yes* | Grocery allocation file |
| `fnv_file` | Binary File | Yes* | FnV multi-city allocation file |
| `city` | String | No | Grocery city (e.g. `Bangalore`) |
| `date` | String | No | Target delivery date (`YYYY-MM-DD`) |
| `format` | String | No | `Standard` or `Institutional` |

*\*At least one file must be provided. If one fails, the other still returns valid data.*

#### Example Response (`200 OK`)
```json
{
  "success": true,
  "so_type": "GRO_FNV_COMBINED",
  "run_id": "combined-20260919-8f3a",
  "date": "2026-09-19",
  "summary": {
    "total_gro_rows": 142,
    "total_fnv_rows": 890,
    "combined_rows": 1032,
    "combined_qty": 18350.5,
    "combined_val": 826200.0
  },
  "gro": {
    "city": "Bangalore",
    "headers": [...],
    "stats": { ... },
    "items": [ ... ]
  },
  "fnv": {
    "grand_totals": { ... },
    "cities": {
      "Bangalore": { ... },
      "Chennai": { ... }
    }
  },
  "errors": {
    "gro": null,
    "fnv": null
  }
}
```

---

## 5. Code Examples & Client Integration

### Python Client Example

```python
import requests

BASE_URL = "https://cus-so-production.up.railway.app"  # or http://127.0.0.1:5000

# Process Grocery Sales Order
with open("BLR_Allocation.xlsx", "rb") as f:
    files = {"file": f}
    data = {
        "city": "Bangalore",
        "format": "Institutional",
        "date": "2026-09-20"
    }
    response = requests.post(f"{BASE_URL}/api/v1/gro/process", files=files, data=data)
    res_data = response.json()

if res_data.get("success"):
    print(f"Successfully processed {len(res_data['items'])} items for {res_data['city']}")
    # Download the CSV file directly from base64
    import base64
    csv_bytes = base64.b64decode(res_data["files"]["so_csv"]["base64"])
    with open(res_data["files"]["so_csv"]["filename"], "wb") as out_f:
        out_f.write(csv_bytes)
```

---

### cURL Example

```bash
# Process FnV Sales Order across all cities
curl -X POST "https://cus-so-production.up.railway.app/api/v1/fnv/process" \
  -F "file=@FnV_Consolidated.xlsx" \
  -F "date=2026-09-20"
```

---

### JavaScript / Web Frontend (`fetch`) Example

```javascript
const formData = new FormData();
formData.append('gro_file', groFileInput.files[0]);
formData.append('fnv_file', fnvFileInput.files[0]);
formData.append('city', 'Bangalore');

const res = await fetch('https://cus-so-production.up.railway.app/api/v1/combined/process', {
  method: 'POST',
  body: formData
});

const result = await res.json();
console.log('Combined SO Output:', result.summary, result.gro, result.fnv);
```

---

## 6. Error Handling & Reliability

### Standard Error Response Format
Whenever an error occurs (e.g. invalid file, missing parameters, Google Sheet permissions), the API returns a standard JSON error:

```json
{
  "success": false,
  "error": "Permission denied! Please ensure you have shared the Google Sheet with Editor access to the service account.",
  "so_type": "GRO_SO"
}
```

### HTTP Status Code Reference
* `200 OK`: Request succeeded, data processed and returned.
* `400 Bad Request`: Missing mandatory parameters (e.g. no file uploaded, invalid city).
* `404 Not Found`: Target sheet, worksheet, or cached `run_id` not found.
* `500 Internal Server Error`: Unhandled automation or formula evaluation failure (includes detailed error message).
