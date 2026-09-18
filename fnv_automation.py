"""
FnV SO Automation — Optimized Two-Phase Approach
-------------------------------------------------
Phase A (Write):  For each city, prepare allocation data and write to PO tab
                  + drag SO formulas — all using ONE shared Google Sheets connection.
Phase B (Sleep):  Single sleep(10) for all cities' formulas to evaluate in parallel
                  on Google's servers (vs. 5s × 7 cities = 35s previously).
Phase C (Read):   For each city, fetch the SO tab and generate output files.

This mirrors the exact approach used in mas_so_app.py and reduces total
Google Sheets wait time from ~35s to ~10s.
"""

import os
import time
import tempfile
import zipfile
import traceback

import numpy as np
import pandas as pd

from automation_script import (
    FNV_CITY_CONFIG,
    FNV_SATELLITE_CITIES,
    get_gsheet_client,
    get_worksheet_flexible,
)


# ── Shared-connection helpers ─────────────────────────────────────

def _update_po_tab_with_conn(sh, po_sheet_name: str, upload_df: pd.DataFrame):
    """Write allocation data to the PO tab using an existing connection."""
    worksheet = get_worksheet_flexible(sh, po_sheet_name)
    worksheet.clear()
    df_upload = upload_df.fillna("")
    data = [df_upload.columns.values.tolist()] + df_upload.values.tolist()
    try:
        worksheet.update(values=data, range_name="A1", value_input_option="USER_ENTERED")
    except TypeError:
        worksheet.update(data, value_input_option="USER_ENTERED")


def _drag_so_formulas_with_conn(sh, so_sheet_name: str, target_rows: int):
    """Drag SO formulas using an existing connection."""
    try:
        so_ws = get_worksheet_flexible(sh, so_sheet_name)
    except Exception as e:
        print(f"       [WARN] Could not find SO tab '{so_sheet_name}' to drag formulas: {e}")
        return
    req = {
        "autoFill": {
            "useAlternateSeries": False,
            "sourceAndDestination": {
                "source": {
                    "sheetId": so_ws.id,
                    "startRowIndex": 1,
                    "endRowIndex": 2,
                    "startColumnIndex": 0,
                    "endColumnIndex": so_ws.col_count,
                },
                "dimension": "ROWS",
                "fillLength": max(0, target_rows - 1),
            },
        }
    }
    try:
        sh.batch_update({"requests": [req]})
        print(f"       ✅ Formulas dragged down in '{so_sheet_name}' to cover {target_rows} rows.")
    except Exception as e:
        print(f"       [WARN] Failed to auto-fill formulas in SO tab: {e}")


def _fetch_so_tab_with_conn(sh, so_sheet_name: str, max_rows: int = None) -> pd.DataFrame:
    """Fetch SO tab data using an existing connection."""
    try:
        worksheet = get_worksheet_flexible(sh, so_sheet_name)
    except Exception as e:
        raise ValueError(f"Could not find tab '{so_sheet_name}': {e}")
    
    if max_rows:
        # Fetch only the range containing active data to speed up API retrieval significantly
        data = worksheet.get(f"A1:Z{max_rows}")
    else:
        data = worksheet.get_all_values()
        
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data[1:], columns=data[0])


def _fetch_cust_sheet_with_conn(sh, cust_sheet: str) -> dict:
    """Fetch the customer sheet to build FK Site Name mapping using an existing connection."""
    try:
        cust_ws = get_worksheet_flexible(sh, cust_sheet)
        cust_data = cust_ws.get_all_values()
        if len(cust_data) < 2:
            return {}
        cust_df = pd.DataFrame(cust_data[1:], columns=cust_data[0])
        wh_code_possibles = ["wh code", "fk site id", "customer code", "site id", "store id"]
        fk_site_possibles = ["fk site name", "customer name", "site name", "store name", "nc name"]
        wh_name_possibles = ["wh name", "warehouse name", "store"]

        wh_code_col = next((c for c in cust_df.columns if str(c).strip().lower() in wh_code_possibles), None)
        fk_site_col = next((c for c in cust_df.columns if str(c).strip().lower() in fk_site_possibles), None)
        wh_name_col = next((c for c in cust_df.columns if str(c).strip().lower() in wh_name_possibles), None)

        fk_site_map = {}
        if fk_site_col:
            if wh_code_col:
                raw_map_1 = cust_df.set_index(wh_code_col)[fk_site_col].to_dict()
                fk_site_map.update({
                    str(k).strip().lower(): v
                    for k, v in raw_map_1.items()
                    if str(v).strip() not in ["", "nan", "None", "NAN"]
                })
            if wh_name_col:
                raw_map_2 = cust_df.set_index(wh_name_col)[fk_site_col].to_dict()
                fk_site_map.update({
                    str(k).strip().lower(): v
                    for k, v in raw_map_2.items()
                    if str(v).strip() not in ["", "nan", "None", "NAN"]
                })
        return fk_site_map
    except Exception as e:
        print(f"       [WARN] Failed to fetch customer sheet mapping: {e}")
        return {}


def _smart_read_excel(path: str) -> pd.DataFrame:
    """Auto-detect sheet containing allocation data (FSN / Title / QTY / PO)."""
    try:
        xl = pd.ExcelFile(path)
        for s in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=s)
            df.columns = df.columns.astype(str).str.strip()
            cols_lower = [c.lower() for c in df.columns]
            if any(f in cols_lower for f in ['fsn', 'fsn/isbn13', 'sku id', 'sku']):
                return df
        df = pd.read_excel(path, sheet_name=0)
        df.columns = df.columns.astype(str).str.strip()
        return df
    except Exception:
        df = pd.read_excel(path)
        df.columns = df.columns.astype(str).str.strip()
        return df


# ── Allocation prep (pure pandas, no network) ─────────────────────

def _prepare_city_alloc(fnv_alloc_path: str, city: str, delivery_date: str):
    """
    Phase A (local only): Read Excel, filter for this city, build PO IDs.
    Returns (alloc_df, upload_df, key_table, cfg) or raises on error.
    """
    cfg = FNV_CITY_CONFIG[city]
    satellite_cities = FNV_SATELLITE_CITIES.get(city, [city])

    print(f"\n{'='*60}")
    print(f"  FnV | {city}  |  PO Prefix: {cfg['po_prefix']}  |  Date: {delivery_date}")
    print(f"  Satellite cities: {satellite_cities}")
    print(f"{'='*60}\n")

    print("► [1/3] Reading FnV allocation file...")
    alloc = _smart_read_excel(fnv_alloc_path)


    # Filter by city
    city_col_actual = next(
        (c for c in ["City", "city", "Location", "location", "CITY"] if c in alloc.columns), None
    )
    if city_col_actual:
        satellite_lower = [s.lower().strip() for s in satellite_cities]
        mask = alloc[city_col_actual].astype(str).str.strip().str.lower().isin(satellite_lower)
        alloc = alloc[mask].copy()
        print(f"       Filtered by city column '{city_col_actual}': {satellite_cities}")
    else:
        print(f"       [WARN] City column not found — using all rows.")

    print(f"       {len(alloc)} rows for {city}")

    # Drop zero-QTY rows
    qty_col_alloc = next(
        (c for c in ["Final PO", "final po", "QTY", "Quantity", "Qty", "PO qty"] if c in alloc.columns), None
    )
    if qty_col_alloc:
        alloc[qty_col_alloc] = pd.to_numeric(alloc[qty_col_alloc], errors="coerce").fillna(0)
        before = len(alloc)
        alloc = alloc[alloc[qty_col_alloc] > 0].copy()
        print(f"       [Filter] Dropped {before - len(alloc)} zero-QTY rows. Remaining: {len(alloc)}")

    if alloc.empty:
        raise ValueError(f"No rows found for {city} after filtering.")

    # Normalise columns
    if "WH Code" in alloc.columns:
        alloc["Warehouse"] = alloc["WH Code"].astype(str).str.strip()
    elif "Store Site ID" in alloc.columns:
        alloc["Warehouse"] = alloc["Store Site ID"].astype(str).str.strip()
    elif "Warehouse" in alloc.columns:
        alloc["Warehouse"] = alloc["Warehouse"].astype(str).str.strip()
    else:
        alloc["Warehouse"] = ""

    if "WH Name" in alloc.columns:
        alloc["Store ID"] = alloc["WH Name"].astype(str).str.strip()
    elif "Store ID" not in alloc.columns and "Store" in alloc.columns:
        alloc["Store ID"] = alloc["Store"]
    elif "Store ID" not in alloc.columns:
        alloc["Store ID"] = alloc["Warehouse"]

    alloc["Supplier_ID"] = (
        alloc["Supplier ID"].astype(str).str.strip() if "Supplier ID" in alloc.columns else ""
    )
    store_id_col = alloc["Store ID"].astype(str).str.strip() if "Store ID" in alloc.columns else alloc["Warehouse"]
    store_id_col = store_id_col.replace(["", "NAN", "nan", "None"], pd.NA).fillna(alloc["Warehouse"])
    alloc["Key"] = (store_id_col + alloc["Supplier_ID"]).str.upper()

    unique_keys = list(dict.fromkeys(alloc["Key"].tolist()))
    key_to_poid = {k: f"{cfg['po_prefix']}{str(i+1).zfill(3)}" for i, k in enumerate(unique_keys)}
    alloc["PO_ID_generated"] = alloc["Key"].map(key_to_poid)

    key_table = (
        alloc[["Key", "Warehouse", "Supplier_ID", "PO_ID_generated", "Store ID"]]
        .drop_duplicates("Key")
        .rename(columns={"PO_ID_generated": "PO ID", "Supplier_ID": "Supplier ID", "Store ID": "Store"})
    )

    # Determine QTY and Title source
    if "Final PO" in alloc.columns:
        qty_series = pd.to_numeric(alloc["Final PO"], errors="coerce").fillna(0)
    elif "QTY" in alloc.columns:
        qty_series = pd.to_numeric(alloc["QTY"], errors="coerce").fillna(0)
    elif "Quantity" in alloc.columns:
        qty_series = pd.to_numeric(alloc["Quantity"], errors="coerce").fillna(0)
    elif "Qty" in alloc.columns:
        qty_series = pd.to_numeric(alloc["Qty"], errors="coerce").fillna(0)
    elif "PO qty" in alloc.columns:
        qty_series = pd.to_numeric(alloc["PO qty"], errors="coerce").fillna(0)
    else:
        qty_series = pd.Series(0, index=alloc.index)

    if "Title" in alloc.columns:
        title_series = alloc["Title"]
    elif "FSN_Title" in alloc.columns:
        title_series = alloc["FSN_Title"]
    elif "NC Name" in alloc.columns:
        title_series = alloc["NC Name"]
    else:
        title_series = pd.Series("", index=alloc.index)

    return alloc, qty_series, title_series, key_table, unique_keys, cfg


def _build_upload_df(alloc, qty_series, title_series, cust_sheet, fk_site_map):
    """Build the upload DataFrame for the PO tab (with VLOOKUP contact formula)."""
    _store_fallback = (
        alloc["Store ID"].astype(str).str.strip()
        if "Store ID" in alloc.columns
        else alloc["Warehouse"]
    )
    _store_fallback = _store_fallback.replace(["", "NAN", "nan", "None"], pd.NA).fillna(alloc["Warehouse"])
    _wh_code = alloc["Warehouse"].astype(str).str.strip()

    _mapped_store = _wh_code.str.lower().map(fk_site_map).replace(["", "nan", "None", "NAN"], pd.NA)
    _mapped_store = _mapped_store.fillna(
        _store_fallback.str.lower().map(fk_site_map).replace(["", "nan", "None", "NAN"], pd.NA)
    )
    _mapped_store = _mapped_store.fillna(_store_fallback)

    fsn_col = next((c for c in alloc.columns if str(c).strip().lower() in ["fsn", "fsn/isbn13"]), None)
    
    upload_df = pd.DataFrame({
        "FSN/ISBN13": alloc[fsn_col] if fsn_col else pd.Series("", index=alloc.index),
        "Title":      title_series,
        "QTY":        pd.to_numeric(qty_series, errors="coerce").fillna(0),
        "PO Number":  alloc["PO_ID_generated"],
        "Store":      _mapped_store,
    }, index=alloc.index)

    # Drop zero-QTY rows first
    upload_df = upload_df[upload_df["QTY"] > 0].copy()

    # ── KEY OPTIMIZATION: Aggregate by FSN + PO Number + Store ──────
    # The PO tab needs one row per FSN per store, not one row per
    # individual order line. Collapses e.g. 27,062 rows -> ~few hundred.
    upload_df = (
        upload_df.groupby(["FSN/ISBN13", "Title", "PO Number", "Store"], as_index=False)
        .agg({"QTY": "sum"})
    )
    upload_df["QTY"] = upload_df["QTY"].astype(int)
    # Restore column order: FSN, Title, QTY, PO Number, Store
    upload_df = upload_df[["FSN/ISBN13", "Title", "QTY", "PO Number", "Store"]]

    num_rows = len(upload_df)
    upload_df = upload_df.reset_index(drop=True)
    upload_df["Contact"] = [
        f"=VLOOKUP(E{i},'{cust_sheet}'!F:G,2,0)" for i in range(2, num_rows + 2)
    ]
    print(f"       Aggregated to {num_rows} unique FSN+Store rows for upload.")
    return upload_df, num_rows


# ── SO data processing (pure pandas, no network) ──────────────────

def _process_so_data(so_df, alloc, delivery_date, city):
    """Process the raw SO DataFrame into valid + NA rows."""
    from datetime import datetime

    so_df.columns = so_df.columns.str.strip()

    for c in ["SKU ID", "sku_id", "FSN", "fsn"]:
        if c in so_df.columns and "sku_id(req)" not in so_df.columns:
            so_df.rename(columns={c: "sku_id(req)"}, inplace=True)
            break
    for c in ["NC Name", "Title", "title"]:
        if c in so_df.columns and "NC NAME" not in so_df.columns:
            so_df.rename(columns={c: "NC NAME"}, inplace=True)
            break

    col_mappings = {
        "customer_contact_number(req)": ["Customer Contact Number", "customer contact", "contact", "phone"],
        "quantity(req)": ["QTY", "Quantity", "qty", "quantity"],
        "lot_id(req)": ["Lot ID", "lot_id", "lot id", "lot weight ID", "lot weight id"],
        "purchaseOrder": ["PO Number", "PO ID", "PO", "purchase_order", "purchase order"],
        "Sales Price": ["Price", "Sales price", "price"],
        "delivery_date(DD-MM-YYY)": ["Delivery Date", "delivery date", "delivery_date"],
        "CITY_ID(req)": ["CITY_ID", "City ID", "City", "city_id"],
    }
    for target, candidates in col_mappings.items():
        if target not in so_df.columns:
            for c in so_df.columns:
                if c.strip().lower() in [cand.lower() for cand in candidates]:
                    so_df.rename(columns={c: target}, inplace=True)
                    break

    print(f"       {len(so_df)} total rows in SO tab")
    so_df.replace(["#N/A", "#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#NUM!", "#NULL!"], np.nan, inplace=True)

    total_qty = pd.to_numeric(so_df.get("quantity(req)"), errors="coerce").sum()
    print(f"       Total QTY in Google Sheet before NA separation: {total_qty}")

    # Drop fully empty rows
    if "sku_id(req)" in so_df.columns and "customer_contact_number(req)" in so_df.columns:
        is_empty = (
            (so_df["sku_id(req)"].fillna("").astype(str).str.strip() == "") &
            (so_df["customer_contact_number(req)"].fillna("").astype(str).str.strip() == "")
        )
        so_df = so_df[~is_empty].copy()

    # Drop zero-QTY
    if "quantity(req)" in so_df.columns:
        valid_qty_mask = pd.to_numeric(so_df["quantity(req)"], errors="coerce").fillna(0) > 0
        so_df = so_df[valid_qty_mask].copy()

    fnv_cols = [
        "customer_contact_number(req)", "sku_id(req)", "NC NAME", "quantity(req)",
        "delivery_date(DD-MM-YYY)", "lot_id(req)", "ordering_mode(optional)",
        "cancelled (optional)By default should be 0", "purchaseOrder",
        "Sales Price", "DELIVERY_CHARGE(opt)", "CITY_ID(req)",
        "sale_order_id(optional- leave empty)", "sub_type (optional- leave empty)"
    ]
    for col in fnv_cols:
        if col not in so_df.columns:
            so_df[col] = np.nan
    so_df["Sales Price"] = 1

    # NA detection (excluding Sales Price as price is always forced to 1)
    fnv_check_cols = ["sku_id(req)", "lot_id(req)", "customer_contact_number(req)", "purchaseOrder"]
    actual_check_cols = [c for c in fnv_check_cols if c in so_df.columns]
    if actual_check_cols:
        is_null = so_df[actual_check_cols].isnull().any(axis=1)
        stripped = so_df[actual_check_cols].fillna("").astype(str).apply(lambda x: x.str.strip())
        is_blank = (stripped == "").any(axis=1)
        is_na_str = stripped.isin(["NA", "#N/A", "nan", "None", "na", "#n/a"]).any(axis=1)
        is_na = is_null | is_blank | is_na_str
    else:
        is_na = pd.Series(False, index=so_df.index)

    if "quantity(req)" in so_df.columns:
        is_invalid_qty = so_df["quantity(req)"].isna() | (
            pd.to_numeric(so_df["quantity(req)"], errors="coerce").fillna(0) <= 0
        )
        is_na = is_na | is_invalid_qty

    # Date formatting
    if "delivery_date(DD-MM-YYY)" in so_df.columns:
        so_df["delivery_date(DD-MM-YYY)"] = pd.to_datetime(
            so_df["delivery_date(DD-MM-YYY)"], errors="coerce"
        ).dt.date
    if so_df["delivery_date(DD-MM-YYY)"].isna().all():
        from datetime import datetime as _dt
        so_df["delivery_date(DD-MM-YYY)"] = _dt.strptime(delivery_date, "%d-%m-%Y").date()

    df_valid = so_df[~is_na][fnv_cols].copy()
    raw_df_na = so_df[is_na].copy()

    df_na = pd.DataFrame()
    if len(raw_df_na) > 0:
        fsn_col = next(
            (c for c in ["sku_id(req)", "SKU ID", "sku_id", "FSN", "fsn"]
             if c in raw_df_na.columns and raw_df_na[c].notna().any()), "sku_id(req)"
        )
        df_na["FSN"] = raw_df_na.get(fsn_col, pd.Series(dtype=str)).fillna("NA").replace("", "NA")
        title_col = next(
            (c for c in ["NC NAME", "NC Name", "Title", "title"]
             if c in raw_df_na.columns and raw_df_na[c].notna().any()), "NC NAME"
        )
        df_na["Title"] = raw_df_na.get(title_col, pd.Series(dtype=str)).fillna("NA").replace("", "NA")
        df_na["Price"] = raw_df_na.get("Sales Price", pd.Series(dtype=str)).fillna("NA")
        df_na["QTY"] = raw_df_na.get("quantity(req)", pd.Series(dtype=str)).fillna("NA")
        df_na = df_na.drop_duplicates()

        # Fill title from alloc
        alloc_fsn_col = next((c for c in alloc.columns if str(c).strip().lower() in ["fsn", "fsn/isbn13"]), None)
        alloc_title_col = next(
            (c for c in alloc.columns if str(c).strip().lower() in ["fsn_title", "title", "nc name", "nc_name"]), None
        )
        if alloc_fsn_col and alloc_title_col:
            def normalize_title(title_str):
                import re
                t = str(title_str).strip().lower()
                return re.sub(r'\s*-?\s*fk$', '', t).strip()

            alloc_title_map = (
                alloc[[alloc_fsn_col, alloc_title_col]]
                .dropna(subset=[alloc_fsn_col])
                .drop_duplicates(subset=[alloc_fsn_col])
                .set_index(alloc_fsn_col)[alloc_title_col]
                .to_dict()
            )
            def _fill_title(row):
                if str(row["Title"]).strip() in ("", "NA", "#N/A"):
                    return alloc_title_map.get(str(row["FSN"]).strip(), row["Title"])
                return row["Title"]
            df_na["Title"] = df_na.apply(_fill_title, axis=1)
            filled = (df_na["Title"].astype(str).str.strip() != "NA").sum()
            print(f"       [Alloc] Filled Title for {filled} NA rows from Allocation file.")

            # Reverse map: Title -> FSN (normalized)
            alloc_title_to_fsn_map = {}
            for _, r in alloc[[alloc_title_col, alloc_fsn_col]].dropna(subset=[alloc_title_col]).drop_duplicates(subset=[alloc_title_col]).iterrows():
                norm_key = normalize_title(r[alloc_title_col])
                alloc_title_to_fsn_map[norm_key] = r[alloc_fsn_col]

            def _fill_fsn(row):
                t = normalize_title(row["Title"])
                if t in alloc_title_to_fsn_map:
                    return alloc_title_to_fsn_map[t]
                # Try substring matching as a fallback
                for key, fsn_val in alloc_title_to_fsn_map.items():
                    if key in t or t in key:
                        return fsn_val
                # Try difflib fuzzy matching as a final fallback
                import difflib
                matches = difflib.get_close_matches(t, alloc_title_to_fsn_map.keys(), n=1, cutoff=0.7)
                if matches:
                    return alloc_title_to_fsn_map[matches[0]]
                return row["FSN"]
            
            df_na["FSN"] = df_na.apply(_fill_fsn, axis=1)
            filled_fsn = (df_na["FSN"].astype(str).str.strip() != "NA").sum()
            print(f"       [Alloc] Updated FSN for {filled_fsn} NA rows from Allocation file.")

        # DB price lookup
        need_price_mask = df_na["Price"].astype(str).str.strip().isin(["", "NA", "#N/A", "nan", "None", "0", "0.0"])
        names_for_db = df_na.loc[
            need_price_mask & ~df_na["Title"].astype(str).str.strip().isin(["", "NA", "#N/A"]),
            "Title"
        ].tolist()
        if names_for_db:
            try:
                import db_lookup
                price_map = db_lookup.fetch_price_by_name(names_for_db, city)
                if price_map:
                    def _fill_price(row):
                        if str(row["Price"]).strip() in ("", "NA", "#N/A", "nan", "None", "0", "0.0"):
                            return price_map.get(str(row["Title"]).strip().lower(), row["Price"])
                        return row["Price"]
                    df_na["Price"] = df_na.apply(_fill_price, axis=1)
            except Exception as db_err:
                print(f"       [DB WARN] Could not fetch price from DB: {db_err}")

    print(f"       ✓ Valid rows : {len(df_valid)}")
    print(f"       ✗ NA rows    : {len(df_na)} (distinct)")
    print(f"       ✓ Valid QTY  : {pd.to_numeric(df_valid.get('quantity(req)'), errors='coerce').sum()}")
    print(f"       ✗ NA QTY     : {pd.to_numeric(raw_df_na.get('quantity(req)'), errors='coerce').sum()}")

    return df_valid, df_na, len(so_df)


def _save_outputs(df_valid, df_na, key_table, delivery_date, city, output_dir):
    """Save CSV, Excel, and PO mapping files."""
    try:
        from datetime import datetime
        dt = datetime.strptime(delivery_date, "%d-%m-%Y")
        date_tag = dt.strftime("%B_%d")
    except Exception:
        date_tag = delivery_date.replace("-", "")

    base_name = f"{city} FnV CUS SO {date_tag}"
    csv_path = os.path.join(output_dir, f"{base_name}.csv")
    inst_csv_path = os.path.join(output_dir, f"{base_name} (Institution).csv")
    xlsx_path = os.path.join(output_dir, f"{base_name}_full.xlsx")
    po_path = os.path.join(output_dir, f"{city} FnV PO Mapping {date_tag}.xlsx")

    df_valid.to_csv(csv_path, index=False)
    
    # Generate Institution format CSV alongside Standard
    df_inst = df_valid.copy()
    df_inst = df_inst.rename(columns={
        "delivery_date(DD-MM-YYY)": "delivery_date(DD-MM-YYYY)",
        "cancelled (optional)By default should be 0": "cancelled(optional)",
        "sale_order_id(optional- leave empty)": "sale_order_id(optional)",
        "sub_type (optional- leave empty)": "sub_type(optional)"
    })
    
    from datetime import datetime
    try:
        dt_inst = datetime.strptime(delivery_date, "%d-%m-%Y")
        formatted_date = dt_inst.strftime("%d-%m-%Y")
    except ValueError:
        try:
            dt_inst = datetime.strptime(delivery_date, "%d/%m/%Y")
            formatted_date = dt_inst.strftime("%d-%m-%Y")
        except ValueError:
            formatted_date = delivery_date.replace("/", "-")
            
    df_inst["delivery_date(DD-MM-YYYY)"] = formatted_date
    df_inst["skuTypeId"] = 1
    df_inst["CustomerId"] = ""
    df_inst["ordering_mode(optional)"] = 1
    
    INSTITUTION_COLS = [
        "customer_contact_number(req)", "sku_id(req)", "NC NAME", "quantity(req)",
        "delivery_date(DD-MM-YYYY)", "lot_id(req)", "ordering_mode(optional)",
        "cancelled(optional)", "purchaseOrder", "Sales Price", "DELIVERY_CHARGE(opt)",
        "sale_order_id(optional)", "sub_type(optional)", "skuTypeId", "CustomerId"
    ]
    for col in INSTITUTION_COLS:
        if col not in df_inst.columns:
            df_inst[col] = ""
    df_inst = df_inst[INSTITUTION_COLS]
    
    df_inst.to_csv(inst_csv_path, index=False)

    with pd.ExcelWriter(xlsx_path, engine="openpyxl", datetime_format="DD-MM-YYYY", date_format="DD-MM-YYYY") as writer:
        df_valid.to_excel(writer, sheet_name="SO Output", index=False)
        if len(df_na) > 0:
            df_na.to_excel(writer, sheet_name="NA Rows", index=False)
        else:
            pd.DataFrame({"Message": ["No NA rows found"]}).to_excel(writer, sheet_name="NA Rows", index=False)

    key_table.to_excel(po_path, index=False)

    print(f"\n  ✅ CSV saved      → {csv_path}")
    print(f"  ✅ Inst CSV saved → {inst_csv_path}")
    print(f"  ✅ Excel saved    → {xlsx_path}")
    print(f"  ✅ PO Map saved   → {po_path}\n")

    return csv_path, inst_csv_path, xlsx_path, po_path


# ── Main optimized orchestrator ───────────────────────────────────

def process_all_fnv_cities(fnv_alloc_path=None, delivery_date=None, gsheet_url=None, output_dir=None, prev_allocation_path=None, allocation_path=None):
    fnv_alloc_path = fnv_alloc_path or allocation_path
    if not fnv_alloc_path:
        raise ValueError("Allocation file path is required.")


    """
    Optimized two-phase FnV processing:
      Phase A: Prepare all city data + write all PO tabs (one connection)
      Phase B: Single sleep(10) — all formulas evaluate in parallel on Google
      Phase C: Fetch all SO tabs + generate outputs (same connection)
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp()

    zip_path = os.path.join(output_dir, f"All cities_{delivery_date}_delivery.zip")
    total_valid = 0
    total_na = 0
    total_po = 0
    total_so_processed = 0
    city_stats = {}

    # ── Open ONE shared Google Sheets connection ──────────────────
    print("\n🔌 Connecting to Google Sheets (shared connection)...")
    sh, _ = get_gsheet_client(gsheet_url)
    print("   ✅ Connected.\n")

    # ── PHASE A: Read Excel + Write all PO tabs ───────────────────
    print("=" * 60)
    print("  PHASE A: Preparing & uploading all city PO tabs...")
    print("=" * 60)

    city_prepared = {}  # city -> (alloc, df_valid_placeholder, key_table, cfg, so_sheet, upload_rows)

    for city, cfg in FNV_CITY_CONFIG.items():
        so_sheet_name = cfg["so_sheet"]
        po_sheet_name = cfg["po_sheet"]
        city_output_dir = os.path.join(output_dir, city)
        os.makedirs(city_output_dir, exist_ok=True)

        try:
            alloc, qty_series, title_series, key_table, unique_keys, cfg_data = _prepare_city_alloc(
                fnv_alloc_path, city, delivery_date
            )

            cust_sheet = cfg.get("cust_sheet", "BLR FK Customers")
            print(f"  ► [{city}] Fetching customer mapping from '{cust_sheet}'...")
            fk_site_map = _fetch_cust_sheet_with_conn(sh, cust_sheet)

            upload_df, num_rows = _build_upload_df(
                alloc, qty_series, title_series, cust_sheet, fk_site_map
            )
            print(f"  ► [{city}] Writing {num_rows} rows → PO tab '{po_sheet_name}'...")
            _update_po_tab_with_conn(sh, po_sheet_name, upload_df)

            print(f"  ► [{city}] Dragging formulas in SO tab '{so_sheet_name}'...")
            _drag_so_formulas_with_conn(sh, so_sheet_name, num_rows)

            city_prepared[city] = {
                "alloc": alloc,
                "key_table": key_table,
                "unique_keys": unique_keys,
                "so_sheet": so_sheet_name,
                "output_dir": city_output_dir,
                "upload_rows": num_rows,
            }
        except Exception as e:
            traceback.print_exc()
            print(f"  ❌ [{city}] Phase A failed: {e}")
            city_stats[city] = {"valid": 0, "na": 0, "total_so": 0, "po": 0, "error": str(e)}

    if not city_prepared:
        raise ValueError("All cities failed in Phase A. Cannot proceed.")

    # ── PHASE B: Single sleep — all cities' formulas evaluate together ──
    print("\n" + "=" * 60)
    print(f"  PHASE B: Waiting 10s for all Google Sheet formulas to evaluate...")
    print("=" * 60)
    time.sleep(10)

    # ── PHASE C: Fetch all SO tabs + generate outputs ─────────────
    print("\n" + "=" * 60)
    print("  PHASE C: Fetching SO tabs and generating output files...")
    print("=" * 60)

    all_na_dfs = []

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for city, prep in city_prepared.items():
            print(f"\n► Processing outputs for {city}...")
            try:
                # Fetch only up to the number of rows uploaded + 1 for header
                so_df = _fetch_so_tab_with_conn(sh, prep["so_sheet"], max_rows=prep["upload_rows"] + 1)
                df_valid, df_na, total_so = _process_so_data(
                    so_df, prep["alloc"], delivery_date, city
                )
                csv_path, inst_csv_path, xlsx_path, po_path = _save_outputs(
                    df_valid, df_na, prep["key_table"], delivery_date, city, prep["output_dir"]
                )

                valid_len = len(df_valid)
                na_len = len(df_na)
                po_generated = len(prep["unique_keys"])

                if "quantity(req)" in df_valid.columns and not df_valid.empty:
                    valid_qty = int(pd.to_numeric(df_valid["quantity(req)"], errors="coerce").fillna(0).sum())
                else:
                    valid_qty = 0

                if "QTY" in df_na.columns and not df_na.empty:
                    na_qty = int(pd.to_numeric(df_na["QTY"], errors="coerce").fillna(0).sum())
                elif "quantity(req)" in df_na.columns and not df_na.empty:
                    na_qty = int(pd.to_numeric(df_na["quantity(req)"], errors="coerce").fillna(0).sum())
                else:
                    na_qty = 0

                total_qty = valid_qty + na_qty


                total_valid += valid_qty
                total_na += na_qty
                total_po += po_generated
                total_so_processed += total_qty

                if na_len > 0:
                    df_na_city = df_na.copy()
                    df_na_city.insert(0, "City", city)
                    all_na_dfs.append(df_na_city)

                has_csv = os.path.exists(csv_path)
                has_inst_csv = os.path.exists(inst_csv_path)

                if has_csv:
                    zf.write(csv_path, f"{city}/{os.path.basename(csv_path)}")
                if has_inst_csv:
                    zf.write(inst_csv_path, f"{city}/{os.path.basename(inst_csv_path)}")

                # Detect Lot ID mismatch between yesterday and today if prev_allocation_path is supplied
                mismatch_df, mismatch_summary, mismatch_path = _detect_lot_mismatch(
                    prev_allocation_path, fnv_alloc_path, city, prep["output_dir"]
                )

                if mismatch_path and os.path.exists(mismatch_path):
                    zf.write(mismatch_path, f"{city}/{os.path.basename(mismatch_path)}")

                city_stats[city] = {
                    "valid": valid_len,
                    "na": na_len,
                    "valid_qty": valid_qty,
                    "na_qty": na_qty,
                    "total_qty": total_qty,
                    "total_so": total_so,
                    "po": po_generated,
                    "lot_mismatch_count": mismatch_summary.get("count", 0),
                    "lot_mismatch_qty": mismatch_summary.get("total_qty", 0),
                    "mismatch_xlsx_path": mismatch_path if (mismatch_path and os.path.exists(mismatch_path)) else None,
                    "csv_path": csv_path if has_csv else None,
                    "inst_csv_path": inst_csv_path if has_inst_csv else None,
                    "xlsx_path": xlsx_path if os.path.exists(xlsx_path) else None,
                    "po_path": po_path if os.path.exists(po_path) else None,
                }


            except Exception as e:
                traceback.print_exc()
                print(f"  ❌ [{city}] Phase C failed: {e}")
                city_stats[city] = {"valid": 0, "na": 0, "total_so": 0, "po": 0, "error": str(e)}

    # Generate consolidated NA CSV
    try:
        from datetime import datetime
        dt = datetime.strptime(delivery_date, "%d-%m-%Y")
        date_tag = dt.strftime("%B_%d")
    except Exception:
        date_tag = delivery_date.replace("-", "")

    consolidated_na_path = os.path.join(output_dir, f"All_Cities_FnV_NA_{date_tag}.csv")
    if all_na_dfs:
        consolidated_na_df = pd.concat(all_na_dfs, ignore_index=True)
    else:
        consolidated_na_df = pd.DataFrame(columns=["City", "FSN", "Title", "Price", "QTY"])

    consolidated_na_df.to_csv(consolidated_na_path, index=False)
    
    # Also write it inside the zip
    with zipfile.ZipFile(zip_path, 'a', zipfile.ZIP_DEFLATED) as zf:
        zf.write(consolidated_na_path, os.path.basename(consolidated_na_path))

    print("\n✅ All cities processed.\n")
    return city_stats, {"valid": total_valid, "na": total_na, "total": total_so_processed, "po": total_po}, zip_path


def _detect_lot_mismatch(prev_alloc_path: str, today_alloc_path: str, city: str, output_dir: str):
    """
    Compare yesterday's and today's allocation files for a city to detect:
    1. Lot ID Present in Yesterday but missing in Today (or vice-versa).
    2. SKU / Store mapping differences between consecutive days.
    Returns (mismatch_df, summary_dict, excel_file_path).
    """
    if not prev_alloc_path or not os.path.exists(prev_alloc_path):
        return pd.DataFrame(), {"count": 0, "total_qty": 0}, None

    satellite_cities = FNV_SATELLITE_CITIES.get(city, [city])
    satellite_lower = [s.lower().strip() for s in satellite_cities]

    def _read_and_filter(path):
        df = _smart_read_excel(path)
        df.columns = df.columns.str.strip()


        empty_df = pd.DataFrame(columns=["FSN", "Store", "Lot_ID", "Title", "QTY"])

        c_col = next((c for c in df.columns if c.lower() in ["city", "location"]), None)
        if c_col:
            df = df[df[c_col].astype(str).str.strip().str.lower().isin(satellite_lower)].copy()
        
        # Ensure Store & FSN column matching
        store_c = next((c for c in df.columns if c.lower() in ["wh name", "store id", "wh code", "store site id", "warehouse", "store"]), None)
        fsn_c = next((c for c in df.columns if c.lower() in ["fsn", "fsn code", "fsn/isbn13", "fsn_code", "sku id", "sku"]), None)
        lot_c = next((c for c in df.columns if c.lower() in ["lot id", "lot_id", "lot weight id", "lotweightid", "lotid"]), None)
        title_c = next((c for c in df.columns if c.lower() in ["title", "fsn_title", "nc name", "sku name"]), None)
        qty_c = next((c for c in df.columns if c.lower() in ["final po", "qty", "quantity", "po qty"]), None)

        if not fsn_c:
            return empty_df

        records = []
        for _, r in df.iterrows():
            f_val = str(r.get(fsn_c, "")).strip().upper()
            if not f_val or f_val in ["NAN", "NONE", "", "NA"]:
                continue
            s_val = str(r.get(store_c, "")).strip() if store_c else "Store"
            l_val = str(r.get(lot_c, "")).strip() if lot_c else ""
            t_val = str(r.get(title_c, "")).strip() if title_c else ""
            q_val = pd.to_numeric(r.get(qty_c, 0), errors="coerce") or 0
            if q_val <= 0:
                continue
            records.append({
                "FSN": f_val,
                "Store": s_val,
                "Lot_ID": l_val,
                "Title": t_val,
                "QTY": q_val
            })
        if not records:
            return empty_df
        return pd.DataFrame(records)

    try:
        prev_df = _read_and_filter(prev_alloc_path)
        today_df = _read_and_filter(today_alloc_path)

        if prev_df.empty and today_df.empty:
            return pd.DataFrame(), {"count": 0, "total_qty": 0}, None

        # Gather all unique FSNs across yesterday and today to query MySQL DB for Lot IDs
        prev_fsns = prev_df["FSN"].tolist() if ("FSN" in prev_df.columns and not prev_df.empty) else []
        today_fsns = today_df["FSN"].tolist() if ("FSN" in today_df.columns and not today_df.empty) else []
        all_fsns = list(set(prev_fsns + today_fsns))


        db_skus = {}
        if all_fsns:
            try:
                import db_lookup
                db_skus = db_lookup.fetch_skus_from_db(all_fsns, city)
            except Exception as db_err:
                print(f"       [DB WARN] Could not fetch Lot IDs from DB for {city}: {db_err}")

        # Update Lot_ID from DB if empty in raw file
        for df_target in [prev_df, today_df]:
            if not df_target.empty:
                def _resolve_lot(row):
                    raw_lot = str(row.get("Lot_ID", "")).strip()
                    if raw_lot and raw_lot not in ["", "nan", "None", "NAN"]:
                        return raw_lot
                    fsn = row["FSN"]
                    info = db_skus.get(fsn, {})
                    l_id = info.get("lot_id")
                    if l_id and str(l_id).strip() not in ["", "nan", "None", "NAN"]:
                        return str(l_id).strip()
                    return "MISSING IN DB"
                df_target["Lot_ID"] = df_target.apply(_resolve_lot, axis=1)

        # ── 1. FSN-Level Aggregation & Comparison ────────────────────
        fsn_yest = (
            prev_df.groupby("FSN", as_index=False)
            .agg({"QTY": "sum", "Title": "first", "Lot_ID": "first"})
            .rename(columns={"QTY": "Yesterday_QTY", "Lot_ID": "Yesterday_Lot_ID"})
        ) if not prev_df.empty else pd.DataFrame(columns=["FSN", "Yesterday_QTY", "Title", "Yesterday_Lot_ID"])

        fsn_today = (
            today_df.groupby("FSN", as_index=False)
            .agg({"QTY": "sum", "Title": "first", "Lot_ID": "first"})
            .rename(columns={"QTY": "Today_QTY", "Lot_ID": "Today_Lot_ID"})
        ) if not today_df.empty else pd.DataFrame(columns=["FSN", "Today_QTY", "Title", "Today_Lot_ID"])

        map_y = fsn_yest.set_index("FSN").to_dict(orient="index") if not fsn_yest.empty else {}
        map_t = fsn_today.set_index("FSN").to_dict(orient="index") if not fsn_today.empty else {}

        all_fsn_keys = set(map_y.keys()).union(set(map_t.keys()))
        fsn_records = []

        for fsn in sorted(all_fsn_keys):
            item_y = map_y.get(fsn)
            item_t = map_t.get(fsn)

            q_y = int(item_y["Yesterday_QTY"]) if item_y else 0
            q_t = int(item_t["Today_QTY"]) if item_t else 0

            title_str = item_t["Title"] if item_t else (item_y["Title"] if item_y else fsn)
            lot_y = str(item_y["Yesterday_Lot_ID"]) if item_y else ""
            lot_t = str(item_t["Today_Lot_ID"]) if item_t else ""

            db_info = db_skus.get(fsn, {})
            sku_id = db_info.get("sku_id", "N/A")
            db_lot = db_info.get("lot_id", "N/A")

            status = "Matched"
            if item_y and not item_t:
                status = "Present Yesterday, Missing Today"
            elif item_t and not item_y:
                status = "Present Today, Missing Yesterday"
            elif lot_y != lot_t:
                status = f"Lot ID Changed ({lot_y} -> {lot_t})"
            elif q_y != q_t:
                status = f"QTY Changed ({q_y} -> {q_t})"

            fsn_records.append({
                "City": city,
                "FSN": fsn,
                "SKU_ID": sku_id,
                "DB_Lot_ID": db_lot,
                "Title": title_str,
                "Status": status,
                "Yesterday_QTY": q_y,
                "Today_QTY": q_t,
                "QTY_Diff": q_t - q_y
            })

        fsn_summary_df = pd.DataFrame(fsn_records)
        fsn_mismatch_df = fsn_summary_df[fsn_summary_df["Status"] != "Matched"].copy()

        # ── 2. Store-Level Details Comparison ────────────────────────
        prev_map = {}
        for _, r in prev_df.iterrows():
            key = (r["FSN"], r["Store"].lower())
            prev_map[key] = r

        today_map = {}
        for _, r in today_df.iterrows():
            key = (r["FSN"], r["Store"].lower())
            today_map[key] = r

        all_store_keys = set(prev_map.keys()).union(set(today_map.keys()))
        store_mismatches = []

        for key in all_store_keys:
            prev_item = prev_map.get(key)
            today_item = today_map.get(key)

            has_prev = prev_item is not None
            has_today = today_item is not None

            prev_lot = str(prev_item["Lot_ID"]) if has_prev else ""
            today_lot = str(today_item["Lot_ID"]) if has_today else ""

            prev_qty = int(prev_item["QTY"]) if has_prev else 0
            today_qty = int(today_item["QTY"]) if has_today else 0

            fsn_str = key[0]
            store_str = today_item["Store"] if has_today else (prev_item["Store"] if has_prev else "")
            title_str = today_item["Title"] if has_today else (prev_item["Title"] if has_prev else "")

            db_info = db_skus.get(fsn_str, {})
            sku_id = db_info.get("sku_id", "N/A")

            mismatch_type = None
            if has_prev and not has_today:
                mismatch_type = "Present Yesterday, Missing Today"
            elif has_today and not has_prev:
                mismatch_type = "Present Today, Missing Yesterday"
            elif prev_lot != today_lot:
                mismatch_type = f"Lot ID Value Changed ({prev_lot} -> {today_lot})"
            elif prev_qty != today_qty:
                mismatch_type = f"Store QTY Changed ({prev_qty} -> {today_qty})"

            if mismatch_type:
                store_mismatches.append({
                    "City": city,
                    "FSN": fsn_str,
                    "SKU_ID": sku_id,
                    "Store": store_str,
                    "Title": title_str,
                    "Mismatch_Type": mismatch_type,
                    "Yesterday_Lot_ID": prev_lot if prev_lot else "MISSING",
                    "Today_Lot_ID": today_lot if today_lot else "MISSING",
                    "Yesterday_QTY": prev_qty,
                    "Today_QTY": today_qty,
                    "QTY_Difference": abs(today_qty - prev_qty)
                })

        store_mismatch_df = pd.DataFrame(store_mismatches)

        total_mismatches = len(fsn_mismatch_df)
        if total_mismatches == 0 and store_mismatch_df.empty:
            return pd.DataFrame(), {"count": 0, "total_qty": 0}, None

        os.makedirs(output_dir, exist_ok=True)
        mismatch_path = os.path.join(output_dir, f"{city}_Lot_ID_Mismatch.xlsx")
        with pd.ExcelWriter(mismatch_path, engine="openpyxl") as writer:
            fsn_summary_df.to_excel(writer, sheet_name="FSN Level Summary", index=False)
            if not store_mismatch_df.empty:
                store_mismatch_df.to_excel(writer, sheet_name="Store Level Details", index=False)

        total_mismatch_qty = fsn_mismatch_df["Today_QTY"].sum() + fsn_mismatch_df["Yesterday_QTY"].sum()
        summary = {
            "count": len(fsn_mismatch_df),
            "total_qty": int(total_mismatch_qty),
            "file_path": mismatch_path
        }
        return fsn_mismatch_df, summary, mismatch_path

    except Exception as e:
        print(f"       [WARN] Error detecting lot mismatch for {city}: {e}")
        traceback.print_exc()
        return pd.DataFrame(), {"count": 0, "total_qty": 0}, None


