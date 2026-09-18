# Technical Architecture & System Design

This document details the end-to-end technical architecture, system components, database schemas, and data pipelines for the **CUS SO & FnV Sales Order Automation Platform**.

---

## 1. High-Level Architecture Overview

The system is constructed as a decoupled, multi-tiered Python web application. It integrates local file ingestion, cloud Google Sheets synchronization, direct read-only MySQL queries, and standardized output file generation.

```mermaid
graph TD
    Client[Web Dashboard / Frontend UI] -->|HTTP POST Form Data / Files| API[Flask Web API - api/index.py]
    
    subgraph Processing Engines
        API -->|GRO SO Request| GRO[GRO Automation - automation_script.py]
        API -->|FnV SO Request| FNV[FnV Multi-City Automation - fnv_automation.py]
        API -->|Brand PO Request| BPO[Brand PO Generator - generate_brand_po.py]
    end

    subgraph Data Resolution Layer
        GRO & FNV & BPO -->|Primary Lookup| GSheet[Google Sheets API - gspread]
        GRO & FNV & BPO -->|Fallback / Direct Lookup| DBLookup[Direct DB Engine - db_lookup.py]
    end

    subgraph External Infrastructure
        DBLookup -->|Read-Only MySQL| MySQL[(MySQL Database: cyclops, asgard, vormir)]
        GSheet -->|Cloud Calc Engine| GoogleCloud[Google Sheets Cloud Infrastructure]
    end

    subgraph Output Generation
        GRO & FNV -->|Generate CSV/XLSX| Out1[Standard CSV: <City> XD SO <Date>.csv]
        GRO & FNV -->|Generate Inst CSV| Out2[Institutional CSV: <City> XD SO <Date> (Institution).csv]
        GRO & FNV -->|Generate Excel| Out3[Full Audit Excel: <City> XD SO <Date>_full.xlsx]
        FNV -->|Bundle Multi-City| Out4[ZIP Archive: all_cities_fnv_so.zip]
    end
```

---

## 2. Core Components

### 2.1 API & Application Server (`app.py` & `api/index.py`)
- **Framework**: Flask (deployed on local host or Vercel serverless environment).
- **Responsibilities**:
  - Request routing, multipart file handling, and temporary workspace management (`tempfile.mkdtemp()`).
  - Auto-detection of target city based on uploaded allocation file header/filename inspect (`/detect-city`).
  - Standardized JSON responses containing execution statistics (`total`, `valid`, `na`, `po`) and base64-encoded output files for instant browser download.

### 2.2 GRO SO Automation Engine (`automation_script.py`)
- **Responsibilities**:
  - Parses uploaded store/vendor allocation files (Excel `.xlsx` / `.xls` or CSV).
  - Synchronizes allocation data with Google Sheets (populating PO tabs, auto-filling VLOOKUP formulas on SO tabs).
  - Invokes direct DB fallbacks (`db_lookup.py`) for missing SKU IDs, Lot IDs, Prices, and Customer Contact Numbers.
  - Transforms processed data simultaneously into **Standard GRO SO** (16 columns) and **Institutional SO** (15 columns) CSVs.

### 2.3 FnV Multi-City Engine (`fnv_automation.py`)
- **Responsibilities**:
  - Processes multi-city Fruits & Vegetables allocation spreadsheets containing satellite cities (e.g. Hosur mapped under Bangalore, Erode mapped under Coimbatore).
  - Implements an **Optimized Two-Phase Execution Model**:
    - **Phase A (Write)**: Writes allocation data to PO tabs and triggers formula auto-fill for all cities using a single shared Google Sheets connection.
    - **Phase B (Parallel Calc)**: Executes a single 10-second sleep (`time.sleep(10)`), allowing Google Sheets cloud engine to evaluate formulas across all city tabs simultaneously in parallel (reducing total latency from ~35s to ~10s).
    - **Phase C (Read & Export)**: Fetches calculated SO tabs and builds individual city output files plus a combined ZIP archive.

### 2.4 Brand PO Generator (`generate_brand_po.py`)
- **Responsibilities**:
  - Merges multi-city indent plans with master costing and vendor details.
  - Interrogates `cyclops.vendor_sku_set_map` for costing validation.
  - Outputs Vendor PO summaries, discrepancy audit reports, and missing NA reports.

### 2.5 Direct Database Connector (`db_lookup.py`)
- **Responsibilities**:
  - Implements read-only, transaction-isolated MySQL queries using `pymysql`.
  - Automatically enforces `SET SESSION TRANSACTION READ ONLY` to prevent accidental database mutations.
  - Handles SKU mapping (`_DB_SKU_LOOKUP_QUERY`), pricing lookup (`_DB_PRICE_BY_NAME_QUERY`), exact contact lookup (`_DB_CONTACT_LOOKUP_QUERY`), global contact fallback (`_DB_CONTACT_LOOKUP_GLOBAL_QUERY`), and fuzzy store-prefix matching.

---

## 3. Database Schema & Query Specifications

The system queries three MySQL databases in the production environment: `asgard`, `vormir`, and `cyclops`.

### 3.1 Direct SKU & Lot Lookup Query
Fetches `sku_id`, `sku_name`, `lot_id`, and `city_id` using FSN code and City ID:

```sql
SELECT DISTINCT
    peim.fsnCode           AS fsn,
    s.Id                   AS sku_id,
    s.Name                 AS sku_name,
    peim.lotWeightId       AS lot_id,
    peim.cityId            AS city_id
FROM asgard.Sku s
JOIN vormir.ProductExternalInternalMapping peim
    ON peim.skuId = s.Id
WHERE s.Deleted IN (0, 1)
  AND peim.cityId = %(city_id)s
  AND peim.fsnCode IN %(fsn_list)s;
```

### 3.2 SKU Pricing Lookup Query
Fetches customer price for facility using SKU name:

```sql
SELECT DISTINCT
    s.Name AS skuname,
    ssc.sku_id,
    vssm.reference_id,
    vssm.customer_price AS price
FROM cyclops.sku s
LEFT JOIN cyclops.sku_set_configuration ssc
    ON ssc.sku_id = s.id AND ssc.deleted = 0
LEFT JOIN cyclops.vendor_sku_set_map vssm
    ON vssm.sku_set_config_id = ssc.id AND vssm.deleted = 0
WHERE s.deleted IN (1, 0)
  AND vssm.reference_type = 'FACILITY'
  AND vssm.reference_id IN %(facility_id)s
  AND s.name IN %(name_list)s;
```

### 3.3 Customer Contact Lookup Query & Fuzzy Matching
Fetches store contact number using Customer ID or Name with global and fuzzy prefix fallback:

```sql
-- 1. City-Scoped Exact Match
SELECT Id, Name, ContactNumber 
FROM asgard.Customer 
WHERE CityId = %(city_id)s
  AND (Name IN %(keys)s OR Id IN %(keys)s);

-- 2. Global Cross-City Fallback (if missing in target city)
SELECT Id, Name, ContactNumber 
FROM asgard.Customer 
WHERE Name IN %(keys)s OR Id IN %(keys)s;

-- 3. Fuzzy Prefix Match (e.g. 'mum_172_wh_hl_01' -> 'mum_172%')
SELECT Id, Name, ContactNumber 
FROM asgard.Customer 
WHERE CityId = %(city_id)s 
  AND Name LIKE %(prefix)s 
LIMIT 1;
```

---

## 4. Configuration Matrices

### 4.1 GRO City Configuration

| City | City ID (`city_id`) | PO Prefix | Facility ID | Allocation Name | SO Sheet Tab | PO Sheet Tab |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bangalore** | `2` | `NCXDB` | `9382` | Bangalore | BLR FK GRO SO | BLR FK Gro PO FIle |
| **Chennai** | `3` | `NCXDC` | `9920` | Chennai | CHN FK GRO SO | CHN FK Gro PO FIle |
| **Mumbai** | `14` | `NCXDM` | `9892` | Mumbai | MUM FK GRO SO | MUM FK Gro PO FIle |
| **Hyderabad** | `13` (or `5`) | `NCXDH` | `9575` | Hyderabad | HYD FK GRO SO | HYD FK Gro PO FIle |
| **Trichy** | `102` (or `6`) | `NCXDT` | `10112` | Trichy | Trichy FK GRO SO | Trichy FK Gro PO FIle |
| **Coimbatore** | `90` (or `7`) | `NCXDCBE` | `10071` | Coimbatore | CBE FK GRO SO | CBE FK Gro PO FIle |
| **Nashik** | `8` | `NCNSH` | `10078` | Nashik | Nashik FK SO | Nashik FK PO FIle |

### 4.2 FnV Satellite City Mappings

| Main City Hub | Satellite Cities Included in Allocation |
| :--- | :--- |
| **Bangalore** | Bangalore, Bengaluru, Hosur, Mandya, Mysore, Tumkur |
| **Coimbatore** | Coimbatore, Erode, Palakkad, Salem, Tirupur |
| **Chennai** | Chennai |
| **Mumbai** | Mumbai |

---

## 5. API Routes Specification

| Route | Method | Payload / Params | Description |
| :--- | :--- | :--- | :--- |
| `/` | `GET` | None | Serves HTML dashboard web interface. |
| `/detect-city` | `POST` | `file`: Multipart allocation file | Inspects filename and spreadsheet headers to detect target city. |
| `/process` | `POST` | `city`, `date`, `allocation_file`, `gsheet_url` | Runs GRO Sales Order generation pipeline. |
| `/process_fnv` | `POST` | `date`, `fnv_file`, `fnv_prev_file`, `gsheet_url` | Runs FnV Multi-City Sales Order generation pipeline. |
| `/process_brand_po` | `POST` | `city`, `date`, `exclude_direct` | Runs Brand Purchase Order generation pipeline. |
| `/download/<run_id>/<file_type>` | `GET` | `run_id`, `file_type` | Downloads generated CSV/Excel output file by run ID. |
| `/download_path` | `GET` | `path`: Base64 encoded file path | Securely serves files from local temp output directory. |
