# Error Log, Known Edge Cases & Troubleshooting Matrix

This document records known failure modes, runtime errors, edge cases, automatic fallback mechanisms, and troubleshooting steps for the **CUS SO & FnV Sales Order Automation Platform**.

---

## 1. Automatic Fallback Mechanisms

To maximize pipeline resilience, the platform implements multi-tier automatic fallbacks for data resolution.

### 1.1 Hybrid Data Resolution (Google Sheets → Direct MySQL)

```
[Store Allocation File Ingested]
               │
               ▼
   [Primary: Read Google Sheet Tab]
               │
      Is Data Missing / NA?
        ├── NO  ► Use Google Sheet Value
        └── YES ► Trigger Direct MySQL Fallback (db_lookup.py)
                     │
            Query MySQL Databases:
            - asgard.Sku + vormir.ProductExternalInternalMapping (FSN → sku_id, lot_id)
            - cyclops.sku + cyclops.vendor_sku_set_map (Sku Name → Customer Price)
            - asgard.Customer (Store Name/Id → Contact Number)
                     │
            Is Data Found in DB?
              ├── YES ► Populate output with DB result
              └── NO  ► Mark as NA & log to NA Rows tab in Excel
```

### 1.2 Customer Contact Number Fallback Chain

When looking up buyer/warehouse contact numbers from `asgard.Customer`:
1. **Pass 1: City-Scoped Exact Match** — Queries `asgard.Customer` where `CityId = city_id` and `Name` or `Id` matches.
2. **Pass 1.5: Global Cross-City Fallback** — If missing in target city, queries `asgard.Customer` across all cities.
   - *Reason*: Satellite stores like `Rta_113_Thanjavur` (Trichy region) are registered under Coimbatore (`CityId = 90`) in `asgard.Customer`.
3. **Pass 2: Fuzzy Store Prefix Match** — If exact match fails, splits store code (e.g. `mum_172_wh_hl_01` -> prefix `mum_172%`) and performs `LIKE` query.
4. **Pass 3: Default Hardcoded Fallback** — Fallback contact numbers defined in `automation_script.py` for specific city hubs.

---

## 2. Known Errors & Troubleshooting Matrix

| # | Error / Log Pattern | Root Cause | Impact | Automated / Manual Fix |
|---|---------------------|------------|--------|------------------------|
| **E01** | `[DB ERROR] Failed to load DB credentials: FileNotFoundError` | `db_credentials.json` missing in workspace root. | DB fallback skipped; pipeline relies solely on Google Sheets. | Create `db_credentials.json` with host, port, user, password, database. |
| **E02** | `[DB WARN] Unknown city 'X' for DB lookup` | Unmapped city string passed to `CITY_ID_MAP` in `db_lookup.py`. | DB lookup aborted for city. | Add city name & CityId to `CITY_ID_MAP` and `CITY_FACILITY_ID`. |
| **E03** | `[WARN] Could not find SO tab 'X' to drag formulas` | Tab name mismatch between `CITY_CONFIG` and actual Google Sheet. | Formula auto-fill fails; rows below row 2 have empty formulas. | Verify tab names in Google Sheets and update `CITY_CONFIG` dictionary. |
| **E04** | `APIError: 429 Too Many Requests` | Google Sheets API rate limit exceeded during frequent write operations. | Batch update fails or hangs. | The FnV engine uses two-phase batch write/read to minimize API quota usage. If error occurs, wait 60s or check service account quota. |
| **E05** | `UnicodeEncodeError: 'charmap' codec can't encode character` | Windows terminal stdout attempting to print non-ASCII characters. | Script crashes on print statements. | Script includes automatic stdout reconfigure: `sys.stdout.reconfigure(encoding='utf-8')`. |
| **E06** | FSN floating point formatting (e.g., `8901234567.0`) | Pandas reading numeric FSN column as float. | DB query fails due to `.0` suffix mismatch. | Implemented `.replace('.0', '').strip().upper()` in FSN clean function. |
| **E07** | `sub_type` populated as `22` in output | Default formula value in legacy Google Sheet templates. | Order rejection in GRO / FnV SO processing. | Institutional output generator explicitly overrides `sub_type` to `1`. |
| **E08** | Missing credentials file `xd-allocation-9640b0ce66d2.json` | Google Service Account key missing in server directory. | Cannot authenticate with Google Sheets API. | Place valid Google service account JSON file in root directory. |
| **E09** | `pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")` | Database server unreachable or firewall block. | DB queries fail gracefully; system falls back to GSheet data. | Verify VPN connection or DB host/port access in `db_credentials.json`. |

---

## 3. Detailed Edge Case Analysis

### 3.1 Cross-City Store Registration Edge Case
- **Symptom**: Customer contact numbers for stores in satellite towns (e.g. Thanjavur, Erode, Hosur) return blank when querying target city.
- **Root Cause**: Store master entries in `asgard.Customer` were created under primary regional hub `CityId` rather than local satellite `CityId`.
- **Solution**: Implemented `_DB_CONTACT_LOOKUP_GLOBAL_QUERY` in `db_lookup.py` to search globally across all `CityId` values if city-scoped lookup returns empty.

### 3.2 Google Sheets Formula Evaluation Lag in Multi-City Runs
- **Symptom**: When executing FnV processing for 7 cities sequentially, fetching calculated SO tabs immediately after writing PO inputs resulted in blank values (`#N/A` or `#REF!`).
- **Root Cause**: Google Sheets cloud engine calculates complex `VLOOKUP` and array formulas asynchronously.
- **Solution**: Designed the **Two-Phase Architecture** (`fnv_automation.py`):
  1. Write PO inputs and auto-fill formulas for **ALL** cities in a single loop.
  2. Issue a single `time.sleep(10)` pause so Google Cloud evaluates all sheets in parallel.
  3. Read calculated SO tabs in a secondary loop.

### 3.3 Numeric Formatting Artifacts in Output CSVs
- **Symptom**: Phone numbers or SKU IDs exported with trailing decimals or scientific notation (e.g. `9.87654E+09`).
- **Solution**: Sanitized column formatting prior to CSV writing:
  ```python
  df['customer_contact_number(req)'] = df['customer_contact_number(req)'].astype(str).str.replace(r'\.0$', '', regex=True)
  ```

---

## 4. Error Logging & Diagnostics Guidelines

When an error occurs during processing:
1. Inspect the terminal console output or Flask application logs.
2. Check if the error originated from:
   - **File Parsing**: Allocation file format or header mismatch.
   - **Google Sheets API**: Check for `gspread.exceptions.APIError`.
   - **MySQL Database**: Check for `[DB WARN]` or `[DB ERROR]` print prefixes.
3. Review the `NA Rows` tab in the generated Excel audit file (`<City> XD SO <Date>_full.xlsx`) to examine unmapped rows.
