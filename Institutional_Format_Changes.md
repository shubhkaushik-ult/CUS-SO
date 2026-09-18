# Institutional SO Output Format & Changes Documentation

This document details the exact **column header mappings** and **default value changes** implemented when generating output files in the **Institutional Format** (`<City> XD SO <Date> (Institution).csv`) compared to the Standard format.

---

## 1. Column Header Mappings

The Institutional format uses concise, API-standardized column headers. Below is the side-by-side comparison with the Standard format:

| # | Standard Format Header | Institutional Format Header | Description / Changes |
|---|------------------------|-----------------------------|-----------------------|
| 1 | `customer_contact_number(req)` | `customer_contact_number(req)` | Preserved as-is |
| 2 | `NC ID` | `sku_id(req)` | Renamed to `sku_id(req)` |
| 3 | `NC Name` | `NC NAME` | Capitalized to `NC NAME` |
| 4 | `QTY` | `quantity(req)` | Renamed to `quantity(req)` |
| 5 | `Date` | `delivery_date(DD-MM-YYYY)` | Renamed & standardized format |
| 6 | `lot weight ID` | `lot_id(req)` | Renamed to `lot_id(req)` |
| 7 | `ordering_mode(optional)` | `ordering_mode(optional)` | Value changed (see Section 2) |
| 8 | `cancelled (optional)By default should be 0` | `cancelled(optional)` | Shortened header |
| 9 | `purchaseOrder` | `purchaseOrder` | Preserved as-is |
| 10 | `Sales Price` | `Sales Price` | Hardcoded to `1` |
| 11 | `DELIVERY_CHARGE(opt)` | `DELIVERY_CHARGE(opt)` | Preserved (empty) |
| 12 | `sale_order_id(optional- leave empty)` | `sale_order_id(optional)` | Shortened header |
| 13 | `sub_type (optional- leave empty)` | `sub_type(optional)` | Shortened header & default value changed |
| 14 | *N/A (New Column)* | `skuTypeId` | Added (Value: `1`) |
| 15 | *N/A (New Column)* | `CustomerId` | Added (Empty string `""`) |

---

## 2. Default Values & Data Field Changes

Below are the specific default and transformed field values applied in the Institutional format:

### A. Sub-Type (`sub_type(optional)`)
- **Old / GSheet Default**: `22`
- **Updated Value**: **`1`**
- **Reason**: Corrected per explicit requirement for GRO / FnV SO processing.

### B. Sales Price (`Sales Price`)
- **Default Value**: **`1`** across all SKUs.
- **Reason**: SKU pricing is standardized to `1` so mapping relies directly on allocation quantities.

### C. Ordering Mode (`ordering_mode(optional)`)
- **Standard Format Value**: `"DELIVERY"` (String)
- **Institutional Format Value**: **`1`** (Numeric code)

### D. Date Format (`delivery_date(DD-MM-YYYY)`)
- **Format**: Strictly formatted as **`DD-MM-YYYY`** (e.g., `26-08-2026`).

### E. Additional Institutional Fields
- **`skuTypeId`**: Default value set to **`1`**.
- **`CustomerId`**: Set to empty string `""` (optional field).
- **`CITY_ID(req)` & `grocerFlow` & `CategoryId`**: Excluded from Institutional format CSV output.

---

## 3. Summary of Output File Formats Generated

When a batch is processed, the system automatically generates:

1. **Standard SO CSV**: `<City> XD SO <Date>.csv` (16 columns)
2. **Institutional SO CSV**: `<City> XD SO <Date> (Institution).csv` (15 columns)
3. **Complete Excel Report**: `<City> XD SO <Date>_full.xlsx` (Contains `SO Output` & `NA Rows` tabs)
4. **PO ID Mapping File**: `<City> XD PO Mapping <Date>.xlsx`
