#!/usr/bin/env python3
"""
generate_brand_po.py
====================
Single-File Automated Multi-City Brand PO Generator & Local Web UI

Features:
  1. Google Sheets API Integration (service account auth & live sheet update)
  2. Multi-City & Batch All-Cities Generation (MUM, BLR, CHN, TRICHY, CBE, ALL)
  3. Calendar Date Picker in HTML Web UI (<input type="date">)
  4. Built-in Local Web UI (Flask + HTML5/CSS3 dashboard on http://localhost:8080)
  5. CLI execution option (--cli --city ALL --date 2026-09-02)

Usage:
  - Run Web UI: python generate_brand_po.py
  - Run CLI   : python generate_brand_po.py --cli --city ALL --date 2026-09-02
"""

import argparse
import io
import os
import sys
import time
import webbrowser
from datetime import datetime
import pandas as pd

# --------------------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# --------------------------------------------------------------------------

DEFAULT_CREDENTIALS_FILES = [
    "xd-allocation-9640b0ce66d2.json",
    "service_account.json"
]

ECOM_SHEET_ID = "14Lf3KRKWT6RJ-kct-VGfxOPjMkPqqr_pAM0UXqIzmPM"
NLC_3PL_SHEET_ID = "1qud5YPNkXCveSyVvE1PIXSTlCJjBoqh_NQG4EuRZMNI"
NINJACART_COSTING_SHEET_ID = "10_i6K9nM7aIIbC7_kE7u9ZvwDGkmhQ75zyb0YheZqnY"

# Configuration for all Cities & Sheet IDs
CITY_CONFIGS = {
    "MUM": {
        "city_name": "Mumbai",
        "indent_sheet_id": "1e3rd1kClSqWMg7ewfG-aPAUNyY4puzlGvfh126gxgEA",
        "indent_tab": "Mumbai Indent Plan",
        "fsn_col": "Mumbai FSN",
        "input_tab": "MUM PO Input",
        "vendor_po_tab": "MUM Vendor PO ",
        "costing_tab": "MUMBAI",
        "facility_id": 9892,
    },
    "BLR": {
        "city_name": "Bangalore",
        "indent_sheet_id": "1LR-UGBA9iOdrQ5eMm1ndHwV_w3rhVwtAcPBJJ__69dA",
        "indent_tab": "Bangalore Indent Plan",
        "fsn_col": "Bangalore FSN",
        "input_tab": "BLR PO Input",
        "vendor_po_tab": "BLR Vendor PO ",
        "costing_tab": "BLR",
        "facility_id": 9382,
    },
    "CHN": {
        "city_name": "Chennai",
        "indent_sheet_id": "1BquGJJri6WpJsUIre7JZLlpOeCR-etR3hLHYbHeOBOo",
        "indent_tab": "Chennai Indent Plan",
        "fsn_col": "Chennai FSN",
        "input_tab": "CHN GRO PO Input",
        "vendor_po_tab": "CHN GRO Vendor PO ",
        "costing_tab": "CHENNAI",
        "facility_id": 9920,
    },
    "TRICHY": {
        "city_name": "Trichy",
        "indent_sheet_id": "1lXWT-9x3WbNpYYXLZcP4_DEwfuAl1VWbWpouNfTzwXU",
        "indent_tab": "Trichy Indent Plan",
        "fsn_col": "Trichy FSN",
        "input_tab": "Trichy GRO PO Input",
        "vendor_po_tab": "Trichy GRO Vendor PO ",
        "costing_tab": "TRICHY",
        "facility_id": 10112,
    },
    "CBE": {
        "city_name": "Coimbatore",
        "indent_sheet_id": "19YLdB0JeEnTWEnvmVFVZIlc4D7T0eB1jRXotvSY6jJ8",
        "indent_tab": "Coimbatore Indent Plan",
        "fsn_col": "Coimbatore FSN",
        "input_tab": "CBE GRO PO Input",
        "vendor_po_tab": "CBE GRO Vendor PO ",
        "costing_tab": "CBE",
        "facility_id": 10071,
    },
}

EXCLUDED_VENDORS = [
    "MIMANS INDUSTRIES PRIVATE LIMITED",
    "Id Fresh Food (India) Private Limited",
    "RETRANZ INFOLABS PVT KTD - BLR",
    "MAHA PERIAVA FOODS PVT LTD",
]

OUTPUT_COLUMNS = [
    "vendorId",
    "vendorName",
    "poSubType",
    "skuId",
    "skuName",
    "skuQuantity",
    "skuPrice",
    "isRTV",
    "date",
    "vendorFlag",
]

# --------------------------------------------------------------------------
# GOOGLE SHEETS AUTH & DATA HELPERS
# --------------------------------------------------------------------------

def get_gspread_client(credentials_path=None):
    """Authenticate with Google Sheets via service account credentials (env vars or JSON files)."""
    import gspread
    from google.oauth2.service_account import Credentials
    import json
    import base64

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # 1. Environment variable with raw JSON content
    for env_key in ["XD_ALLOCATION_CREDENTIALS_JSON", "ECOM_SO_CREDENTIALS_JSON", "GOOGLE_CREDENTIALS_JSON", "GOOGLE_APPLICATION_CREDENTIALS_JSON"]:
        val = os.getenv(env_key)
        if val and val.strip():
            try:
                info = json.loads(val.strip())
                return gspread.authorize(Credentials.from_service_account_info(info, scopes=scopes))
            except Exception as e:
                print(f"[WARN] Failed to parse {env_key} JSON: {e}")

    # 2. Base64 encoded JSON in environment variable
    for env_key in ["XD_CREDENTIALS_BASE64", "ECOM_CREDENTIALS_BASE64", "GOOGLE_CREDENTIALS_BASE64"]:
        val = os.getenv(env_key)
        if val and val.strip():
            try:
                raw_json = base64.b64decode(val.strip()).decode("utf-8")
                info = json.loads(raw_json)
                return gspread.authorize(Credentials.from_service_account_info(info, scopes=scopes))
            except Exception as e:
                print(f"[WARN] Failed to parse {env_key} base64: {e}")

    # 3. File path passed explicitly or in env var
    if credentials_path and os.path.exists(credentials_path):
        return gspread.authorize(Credentials.from_service_account_file(credentials_path, scopes=scopes))

    for env_key in ["XD_ALLOCATION_CREDENTIALS_PATH", "ECOM_SO_CREDENTIALS_PATH", "GOOGLE_APPLICATION_CREDENTIALS"]:
        p = os.getenv(env_key)
        if p and os.path.exists(p):
            return gspread.authorize(Credentials.from_service_account_file(p, scopes=scopes))

    # 4. Check candidate file paths
    root_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(root_dir, "xd-allocation-9640b0ce66d2.json"),
        os.path.join(os.getcwd(), "xd-allocation-9640b0ce66d2.json"),
        "xd-allocation-9640b0ce66d2.json",
        os.path.join(root_dir, "ecom-so-reader-credetials.json"),
        os.path.join(os.getcwd(), "ecom-so-reader-credetials.json"),
        "ecom-so-reader-credetials.json",
        r"d:\PO\xd-allocation-9640b0ce66d2.json",
        r"d:\Mas SO\ecom-so-reader-credetials.json",
    ]
    for c in candidates:
        if os.path.exists(c):
            return gspread.authorize(Credentials.from_service_account_file(c, scopes=scopes))

    raise FileNotFoundError(
        "Google Service Account credentials not found for Brand PO!\n"
        "Please set 'XD_ALLOCATION_CREDENTIALS_JSON' or 'ECOM_SO_CREDENTIALS_JSON' in Environment Variables."
    )


def fetch_worksheet_df(client, sheet_id, tab_name, max_retries=5):
    for attempt in range(1, max_retries + 1):
        try:
            sh = client.open_by_key(sheet_id)
            try:
                ws = sh.worksheet(tab_name)
            except Exception:
                worksheets = {w.title.strip(): w for w in sh.worksheets()}
                if tab_name.strip() in worksheets:
                    ws = worksheets[tab_name.strip()]
                else:
                    raise KeyError(f"Tab '{tab_name}' not found in sheet '{sheet_id}'. Available: {list(worksheets.keys())}")

            vals = ws.get_all_values()
            if vals and len(vals) > 0:
                raw_headers = vals[0]
                seen = {}
                headers = []
                for i, h in enumerate(raw_headers):
                    h_str = str(h).strip() if h is not None else ""
                    if not h_str:
                        h_str = f"col_{i}"
                    if h_str in seen:
                        seen[h_str] += 1
                        headers.append(f"{h_str}_{seen[h_str]}")
                    else:
                        seen[h_str] = 1
                        headers.append(h_str)
                df = pd.DataFrame(vals[1:], columns=headers)
            else:
                df = pd.DataFrame()
            return df, ws
        except Exception as e:
            if ("429" in str(e) or "Quota exceeded" in str(e) or "RESOURCE_EXHAUSTED" in str(e)) and attempt < max_retries:
                wait_sec = attempt * 4
                print(f"[API RATE LIMIT] 429 Quota exceeded while fetching '{tab_name}'. Retrying in {wait_sec}s (Attempt {attempt}/{max_retries})...")
                time.sleep(wait_sec)
            else:
                raise e


def load_indent_plan(client, city_code):
    cfg = CITY_CONFIGS.get(city_code.upper(), CITY_CONFIGS["MUM"])
    sheet_id = cfg["indent_sheet_id"]
    target_tab = cfg["indent_tab"]

    print(f"Loading Indent Plan sheet ID '{sheet_id}' (tab '{target_tab}')...")
    df, ws = fetch_worksheet_df(client, sheet_id, target_tab)

    # Standardize date column (Prioritize D-2 date column strictly)
    date_col = None
    for c in ["Indent_date (D-2)", "Indent Date (D-2)", "Indent_Date (D-2)", "D-2 Date", "Indent_date", "Po Date (D-1)", "Date", "Date "]:
        if c in df.columns:
            date_col = c
            break

    if not date_col:
        raise KeyError(f"Could not find PO (D-2) Date column in Indent Plan. Found columns: {list(df.columns)}")

    df["po_date_parsed"] = pd.to_datetime(df[date_col], errors="coerce")
    return df, date_col, cfg


# --------------------------------------------------------------------------
# SINGLE CITY PIPELINE FUNCTION
# --------------------------------------------------------------------------

def process_single_city(
    client,
    city_code,
    selected_date,
    exclude_direct_vendors=False,
    output_dir="output",
    wait_time_sec=10,
):
    df_indent, date_col, cfg = load_indent_plan(client, city_code)

    # Date string parsing (support YYYY-MM-DD or MM/DD/YYYY)
    dt_obj = pd.to_datetime(selected_date)
    dt_str_us = dt_obj.strftime("%m/%d/%Y")
    dt_str_iso = dt_obj.strftime("%Y-%m-%d")

    mask = (
        df_indent[date_col].astype(str).str.contains(selected_date) |
        df_indent[date_col].astype(str).str.contains(dt_str_us) |
        (df_indent["po_date_parsed"].dt.strftime("%Y-%m-%d") == dt_str_iso)
    )
    filtered_indent = df_indent[mask].copy()

    if filtered_indent.empty:
        filtered_indent = df_indent.tail(200).copy()

    # Extract Po Date (D-1) from raw indents (e.g. 09/03/2026 -> 2026-09-03)
    po_d1_col = None
    for c in ["Po Date (D-1)", "PO Date (D-1)", "Po Date", "PO Date"]:
        if c in filtered_indent.columns:
            po_d1_col = c
            break

    po_d1_date_iso = dt_str_iso
    raw_po_d1_str = dt_str_us
    if po_d1_col:
        d1_series = filtered_indent[po_d1_col].dropna().astype(str).str.strip()
        if not d1_series.empty:
            raw_po_d1_str = d1_series.iloc[0]
            parsed_d1 = pd.to_datetime(raw_po_d1_str, errors="coerce")
            if pd.notna(parsed_d1):
                po_d1_date_iso = parsed_d1.strftime("%Y-%m-%d")

    print(f"Filtered {len(filtered_indent):,} raw indent rows for city '{city_code}' on Pick PO (D-2) Date '{selected_date}' -> Output PO (D-1) Date: '{po_d1_date_iso}' (Raw: '{raw_po_d1_str}')")

    fsn_col = cfg["fsn_col"]
    if fsn_col not in filtered_indent.columns:
        for alt in ["FSN", "Mumbai FSN", "Bangalore FSN", "fsn"]:
            if alt in filtered_indent.columns:
                fsn_col = alt
                break

    filtered_indent["fsn"] = filtered_indent[fsn_col].astype(str).str.strip().str.upper()
    qty_col = "PO qty" if "PO qty" in filtered_indent.columns else "po_qty"
    filtered_indent["po_qty"] = pd.to_numeric(filtered_indent[qty_col].astype(str).str.replace(",", "").str.strip(), errors="coerce").fillna(0)
    indent_qty_map = filtered_indent.groupby("fsn")["po_qty"].sum().to_dict()
    indent_total_qty = int(filtered_indent["po_qty"].sum())

    # Build per-FSN Po Date (D-1) mapping
    fsn_to_d1_map = {}
    for _, r in filtered_indent.iterrows():
        raw_d1 = str(r.get(po_d1_col, r.get("Po Date (D-1)", raw_po_d1_str)))
        parsed_d1 = pd.to_datetime(raw_d1, errors="coerce")
        d1_val = parsed_d1.strftime("%Y-%m-%d") if pd.notna(parsed_d1) else raw_d1
        for col_alias in [fsn_col, "FSN", "Mumbai FSN", "Bangalore FSN", "fsn"]:
            if col_alias in r and str(r[col_alias]).strip():
                fsn_to_d1_map[str(r[col_alias]).strip().upper()] = d1_val

    # Paste filtered indents to ECOM Sheet Input Tab
    formatted_delivery_date = raw_po_d1_str
    print(f"[STEP 1] Pasting filtered indents into ECOM tab '{cfg['input_tab']}'...")
    _, ws_input = fetch_worksheet_df(client, ECOM_SHEET_ID, cfg["input_tab"])
    ws_input.clear()

    input_headers = ["Po Date (D-1)", "Brand", fsn_col, "PO qty", "Vertical", "Title", "Delivery_Date"]
    input_rows = [input_headers]
    for _, row in filtered_indent.iterrows():
        row_po_d1 = str(row.get("Po Date (D-1)", row.get(date_col, formatted_delivery_date)))
        input_rows.append([
            row_po_d1,
            str(row.get("Brand", "")),
            str(row.get(fsn_col, "")),
            str(row.get(qty_col, "0")),
            str(row.get("Vertical", "")),
            str(row.get("Title", "")),
            row_po_d1,
        ])
    ws_input.update(input_rows, value_input_option="USER_ENTERED")

    if wait_time_sec > 0:
        print(f"[WAIT] Waiting {wait_time_sec}s for formulas in '{cfg['vendor_po_tab']}'...")
        time.sleep(wait_time_sec)

    # Read auto-populated Vendor PO Tab directly from ECOM Sheet
    target_vendor_tab = cfg["vendor_po_tab"]
    print(f"[STEP 2] Reading auto-populated rows from ECOM tab '{target_vendor_tab}'...")
    try:
        vendor_po_df, _ = fetch_worksheet_df(client, ECOM_SHEET_ID, target_vendor_tab)
    except Exception:
        worksheets = {w.title.strip(): w for w in client.open_by_key(ECOM_SHEET_ID).worksheets()}
        ws_target = worksheets.get(target_vendor_tab.strip())
        vendor_po_df = pd.DataFrame(ws_target.get_all_records())

    # Load NLC Master prices from NinjaCart Costing Sheet (Tier 2)
    nc_cost_map = {}
    costing_tab_name = cfg.get("costing_tab")
    if costing_tab_name:
        try:
            nc_df, _ = fetch_worksheet_df(client, NINJACART_COSTING_SHEET_ID, costing_tab_name)
            if not nc_df.empty:
                fsn_c = "FSN" if "FSN" in nc_df.columns else nc_df.columns[0]
                nlc_c = "NLC" if "NLC" in nc_df.columns else ("NLC+SC" if "NLC+SC" in nc_df.columns else nc_df.columns[4])
                for _, r in nc_df.iterrows():
                    f_val = str(r.get(fsn_c, "")).strip()
                    p_val = pd.to_numeric(r.get(nlc_c, 0), errors="coerce")
                    if f_val and pd.notna(p_val) and p_val > 0:
                        nc_cost_map[f_val] = float(p_val)
                print(f"Loaded {len(nc_cost_map)} NinjaCart NLC prices for '{city_code}' (tab '{costing_tab_name}')")
        except Exception as e:
            print(f"Notice: NinjaCart Costing Sheet fetch notice ({e})")

    # Load updated NLC 3PL prices from NLC 3PL Sheet (tab: 'Egg & Batter - New Margin ')
    nlc_3pl_map = {}
    city_name_map = {
        "MUM": "Mumbai",
        "BLR": "Bangalore",
        "CHN": "Chennai",
        "TRICHY": "Trichy",
        "CBE": "Coimbatore",
    }
    target_city_name = city_name_map.get(city_code.upper(), cfg.get("city_name", "Mumbai"))
    try:
        nlc_3pl_df, _ = fetch_worksheet_df(client, NLC_3PL_SHEET_ID, "Egg & Batter - New Margin ")
        if not nlc_3pl_df.empty:
            city_col = "CITY" if "CITY" in nlc_3pl_df.columns else nlc_3pl_df.columns[1]
            fsn_c = "FSN" if "FSN" in nlc_3pl_df.columns else nlc_3pl_df.columns[2]
            nlc_c = "NLC For 3rd Party- ( Brand To Third Party) (PO -3PL TO BRAND )" if "NLC For 3rd Party- ( Brand To Third Party) (PO -3PL TO BRAND )" in nlc_3pl_df.columns else ("NLC for FK(Third party TO Fk) (PO - FK TO 3PL)" if "NLC for FK(Third party TO Fk) (PO - FK TO 3PL)" in nlc_3pl_df.columns else "NLC")

            nlc_3pl_rows = {}
            sub_3pl = nlc_3pl_df[nlc_3pl_df[city_col].astype(str).str.strip().str.upper() == target_city_name.upper()]
            for _, r in sub_3pl.iterrows():
                f_val = str(r.get(fsn_c, "")).strip().upper()
                t_val = str(r.get("Title", "")).strip().lower()
                p_val = pd.to_numeric(r.get(nlc_c, 0), errors="coerce")
                if f_val and pd.notna(p_val) and p_val > 0:
                    if f_val not in nlc_3pl_rows:
                        nlc_3pl_rows[f_val] = []
                    nlc_3pl_rows[f_val].append({"title": t_val, "price": float(p_val)})
                    nlc_3pl_map[f_val] = float(p_val)
            print(f"Loaded {len(nlc_3pl_rows)} updated NLC 3PL prices for city '{target_city_name}' (tab 'Egg & Batter - New Margin ')")
    except Exception as e:
        print(f"Notice: NLC 3PL Egg & Batter tab fetch notice ({e})")

    ff_col = "FF"
    for candidate in ["FF", fsn_col, "FSN", "Mumbai FSN", "Bangalore FSN", "Chennai FSN", "Trichy FSN", "Coimbatore FSN"]:
        if candidate in vendor_po_df.columns:
            ff_col = candidate
            break
    if ff_col not in vendor_po_df.columns and len(vendor_po_df.columns) > 0:
        ff_col = vendor_po_df.columns[0]

    for col in OUTPUT_COLUMNS:
        if col not in vendor_po_df.columns:
            if col == "poSubType":
                vendor_po_df["poSubType"] = ""
            elif col == "isRTV":
                vendor_po_df["isRTV"] = False
            elif col == "vendorFlag":
                vendor_po_df["vendorFlag"] = 1
            elif col == "date":
                vendor_po_df["date"] = selected_date
            else:
                vendor_po_df[col] = ""

    vendor_po_df["skuQuantity_num"] = pd.to_numeric(vendor_po_df["skuQuantity"].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    clean_df = vendor_po_df[
        (vendor_po_df["skuQuantity_num"].notna()) &
        (vendor_po_df["skuQuantity_num"] > 0)
    ].copy()

    if exclude_direct_vendors:
        clean_df = clean_df[~clean_df["vendorName"].isin(EXCLUDED_VENDORS)].copy()

    # Build 3-Step Price Audit & Discrepancy Sheet
    # Step 1: ECOM SKU Config Price (ecomPrice)
    # Step 2: NLC 3PL Price (nlc3plPrice)
    # Step 3: NinjaCart Costing Price (ncCostingPrice)
    clean_df["skuPrice_num"] = pd.to_numeric(clean_df["skuPrice"].astype(str).str.replace(",", "").str.replace("₹", "").str.strip(), errors="coerce")

    audit_records = []
    final_prices = []
    discrepancies = []
    qty_discrepancies = []
    na_missing_records = []

    for _, r in clean_df.iterrows():
        fsn_code = str(r.get(ff_col, "")).strip().upper()
        title_sku = str(r.get("skuName", "")).strip().lower()
        ecom_p = r.get("skuPrice_num")
        ecom_p = round(float(ecom_p), 2) if (pd.notna(ecom_p) and ecom_p > 0) else None

        nlc_p = None
        if fsn_code in nlc_3pl_rows:
            candidates = nlc_3pl_rows[fsn_code]
            if len(candidates) == 1:
                nlc_p = candidates[0]["price"]
            else:
                import re
                grams_sku = re.findall(r"\d+\s*g", title_sku)
                matched_c = None
                for c in candidates:
                    grams_cand = re.findall(r"\d+\s*g", c["title"])
                    if grams_sku and grams_cand and grams_sku[0] == grams_cand[0]:
                        matched_c = c["price"]
                        break
                if matched_c is not None:
                    nlc_p = matched_c
                elif ecom_p is not None:
                    nlc_p = min(candidates, key=lambda x: abs(x["price"] - ecom_p))["price"]
                else:
                    nlc_p = candidates[0]["price"]
        nlc_p = round(nlc_p, 2) if nlc_p is not None else None
        nc_p = round(nc_cost_map[fsn_code], 2) if fsn_code in nc_cost_map else None

        # Determine final PO price preference: NLC 3PL > NC Costing > ECOM
        if nlc_p is not None:
            chosen_price = nlc_p
        elif nc_p is not None:
            chosen_price = nc_p
        elif ecom_p is not None:
            chosen_price = ecom_p
        else:
            chosen_price = 0.0

        final_prices.append(chosen_price)

        # Track missing required fields
        missing_fields = []
        v_id_str = str(r.get("vendorId", "")).strip()
        v_name_str = str(r.get("vendorName", "")).strip()
        s_id_str = str(r.get("skuId", "")).strip()

        if not v_id_str or v_id_str in ["#N/A", "0", "nan", "None", "<NA>"]:
            missing_fields.append("vendorId")
        if not v_name_str or v_name_str in ["#N/A", "nan", "None"]:
            missing_fields.append("vendorName")
        if not s_id_str or s_id_str in ["#N/A", "0", "nan", "None", "<NA>"]:
            missing_fields.append("skuId")
        if chosen_price == 0.0 or chosen_price is None:
            missing_fields.append("price")

        if missing_fields:
            na_missing_records.append({
                "City": city_code,
                "FF": fsn_code,
                "skuName": r.get("skuName", ""),
                "skuQuantity": r.get("skuQuantity", 0),
                "vendorId": v_id_str if v_id_str not in ["nan", "None"] else "",
                "vendorName": v_name_str if v_name_str not in ["nan", "None"] else "",
                "skuId": s_id_str if s_id_str not in ["nan", "None"] else "",
                "finalPOPrice": chosen_price,
                "missingFields": ", ".join(missing_fields),
            })

        # Compare ecomPrice vs nlc3plPrice / ncCostingPrice
        target_ref_p = nlc_p if nlc_p is not None else nc_p
        price_diff = 0.0
        if ecom_p is not None and target_ref_p is not None:
            price_diff = round(ecom_p - target_ref_p, 2)

        if ecom_p is None and nlc_p is not None:
            status = "FILLED FROM NLC 3PL"
        elif ecom_p is None and nc_p is not None:
            status = "FILLED FROM NINJACART COSTING"
        elif ecom_p is None and nc_p is None and nlc_p is None:
            status = "UNPRICED (MISSING)"
        elif abs(price_diff) > 0.01:
            status = f"MISMATCH (Diff: Rs.{price_diff:+.2f})"
            discrepancies.append(fsn_code)
        else:
            status = "MATCH"

        indent_q = int(indent_qty_map.get(fsn_code, 0))
        final_q = int(pd.to_numeric(r.get("skuQuantity_num", 0), errors="coerce") or 0)
        qty_diff = final_q - indent_q
        if indent_q != final_q:
            qty_status = f"MISMATCH (Indent: {indent_q}, PO: {final_q})"
            qty_discrepancies.append(fsn_code)
        else:
            qty_status = "MATCH"

        audit_records.append({
            "FF": fsn_code,
            "skuName": r.get("skuName"),
            "vendorName": r.get("vendorName"),
            "indentQuantity": indent_q,
            "finalPOQuantity": final_q,
            "qtyDiff": qty_diff,
            "qtyStatus": qty_status,
            "ecomPrice": ecom_p if ecom_p is not None else "#N/A",
            "nlc3plPrice": nlc_p if nlc_p is not None else "#N/A",
            "ncCostingPrice": nc_p if nc_p is not None else "#N/A",
            "finalPOPrice": chosen_price,
            "priceDiff": price_diff,
            "priceStatus": status,
        })

    # Track missing FSNs from Indent Plan that were not present in Vendor PO Tab
    clean_fsns = set(clean_df[ff_col].astype(str).str.strip().str.upper())
    for fsn_code, indent_q in indent_qty_map.items():
        if fsn_code not in clean_fsns and indent_q > 0:
            qty_discrepancies.append(fsn_code)
            audit_records.append({
                "FF": fsn_code,
                "skuName": "MISSING IN ECOM VENDOR PO TAB",
                "vendorName": "#N/A",
                "indentQuantity": int(indent_q),
                "finalPOQuantity": 0,
                "qtyDiff": -int(indent_q),
                "qtyStatus": f"MISSING IN PO TAB (Indent: {int(indent_q)}, PO: 0)",
                "ecomPrice": "#N/A",
                "nlc3plPrice": "#N/A",
                "ncCostingPrice": "#N/A",
                "finalPOPrice": 0.0,
                "priceDiff": 0.0,
                "priceStatus": "MISSING",
            })

    # Save Price & Qty Audit Sheet CSV
    audit_df = pd.DataFrame(audit_records)
    audit_path = os.path.join(output_dir, f"Price_and_Qty_Audit_Sheet_{city_code}_{dt_str_iso}.csv")
    try:
        audit_df.to_csv(audit_path, index=False)
    except PermissionError:
        ts = datetime.now().strftime("%H%M%S")
        audit_path = os.path.join(output_dir, f"Price_and_Qty_Audit_Sheet_{city_code}_{dt_str_iso}_{ts}.csv")
        audit_df.to_csv(audit_path, index=False)

    print(f"Created Price & Qty Audit Sheet: {audit_path} ({len(discrepancies)} price mismatches, {len(qty_discrepancies)} qty mismatches)")

    clean_df["skuQuantity"] = clean_df["skuQuantity_num"].astype(int)
    clean_df["skuPrice"] = final_prices
    clean_df["skuId"] = pd.to_numeric(clean_df["skuId"], errors="coerce").astype("Int64")
    clean_df["vendorId"] = pd.to_numeric(clean_df["vendorId"], errors="coerce").astype("Int64")
    clean_df["poSubType"] = ""
    clean_df["date"] = clean_df[ff_col].astype(str).str.strip().str.upper().map(fsn_to_d1_map).fillna(
        pd.to_datetime(clean_df["date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna(po_d1_date_iso)
    )

    # For CHN (Chennai) only: Shift PO date by +1 day for all Aavin, Hatsun, and Arokya SKUs
    if city_code.upper() == "CHN":
        def shift_date_if_matching(row):
            d_val = str(row["date"]).strip()
            s_name = str(row.get("skuName", "")).lower()
            v_name = str(row.get("vendorName", "")).lower()
            
            is_target_brand = any(b in s_name or b in v_name for b in ["aavin", "hatsun", "arokya"])
            
            if is_target_brand:
                try:
                    dt = pd.to_datetime(d_val)
                    if pd.notna(dt):
                        return (dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                except Exception:
                    pass
            return d_val

        clean_df["date"] = clean_df.apply(shift_date_if_matching, axis=1)

    clean_df["vendorFlag"] = 1

    final_df = clean_df[OUTPUT_COLUMNS].copy()

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"Brand_PO_{city_code}_ALL_{dt_str_iso}.csv")
    try:
        final_df.to_csv(out_path, index=False)
    except PermissionError:
        ts = datetime.now().strftime("%H%M%S")
        out_path = os.path.join(output_dir, f"Brand_PO_{city_code}_ALL_{dt_str_iso}_{ts}.csv")
        final_df.to_csv(out_path, index=False)

    total_qty = int(final_df["skuQuantity"].sum())
    total_val = float(final_df["skuPrice"].sum())

    na_missing_df = pd.DataFrame(na_missing_records)
    na_count = len(na_missing_df)
    na_qty = int(pd.to_numeric(na_missing_df["skuQuantity"], errors="coerce").sum()) if not na_missing_df.empty else 0

    na_missing_path = None
    if not na_missing_df.empty:
        na_missing_path = os.path.join(output_dir, f"Missing_Details_Sheet_{city_code}_{dt_str_iso}.csv")
        try:
            na_missing_df.to_csv(na_missing_path, index=False)
        except PermissionError:
            ts = datetime.now().strftime("%H%M%S")
            na_missing_path = os.path.join(output_dir, f"Missing_Details_Sheet_{city_code}_{dt_str_iso}_{ts}.csv")
            na_missing_df.to_csv(na_missing_path, index=False)

    valid_vendors_df = final_df[
        (final_df["vendorName"].notna()) &
        (final_df["vendorName"].astype(str).str.strip() != "") &
        (final_df["vendorName"].astype(str).str.strip() != "#N/A")
    ]
    vendor_date_df = valid_vendors_df[["vendorName", "date"]].drop_duplicates()
    date_vendor_counts = vendor_date_df.groupby("date")["vendorName"].count().to_dict()
    date_qty_sums = final_df.groupby("date")["skuQuantity"].sum().to_dict()

    all_dates = sorted(set(date_vendor_counts.keys()).union(set(date_qty_sums.keys())))
    date_breakdown_detail = {}
    for d in all_dates:
        date_breakdown_detail[d] = {
            "vendors": date_vendor_counts.get(d, 0),
            "qty": int(date_qty_sums.get(d, 0)),
        }

    indent_diff_qty = max(0, indent_total_qty - total_qty)

    return {
        "city": city_code,
        "output_path": out_path,
        "audit_path": audit_path,
        "audit_df": audit_df,
        "na_missing_path": na_missing_path,
        "na_missing_df": na_missing_df,
        "na_count": na_count,
        "na_qty": na_qty,
        "discrepancies_count": len(discrepancies),
        "qty_discrepancies_count": len(qty_discrepancies),
        "final_df": final_df,
        "total_skus": len(final_df),
        "indent_total_qty": indent_total_qty,
        "total_qty": total_qty,
        "indent_diff_qty": indent_diff_qty,
        "total_val": total_val,
        "vendor_count": len(vendor_date_df),
        "date_vendor_breakdown": date_vendor_counts,
        "date_breakdown_detail": date_breakdown_detail,
    }


# --------------------------------------------------------------------------
# PROCESS BRAND PO (SINGLE OR ALL CITIES)
# --------------------------------------------------------------------------

def process_brand_po(
    city_code,
    selected_date,
    credentials_path=None,
    exclude_direct_vendors=False,
    output_dir="output",
    wait_time_sec=8,
):
    client = get_gspread_client(credentials_path)

    if city_code.upper() == "ALL":
        print(f"\n========================================================")
        print(f"[START] RUNNING BATCH BRAND PO GENERATION FOR ALL CITIES")
        print(f"========================================================\n")
        all_results = []
        all_dfs = []

        for c_code in CITY_CONFIGS.keys():
            print(f"\n--- Processing City: {c_code} ({CITY_CONFIGS[c_code]['city_name']}) ---")
            try:
                res = process_single_city(
                    client=client,
                    city_code=c_code,
                    selected_date=selected_date,
                    exclude_direct_vendors=exclude_direct_vendors,
                    output_dir=output_dir,
                    wait_time_sec=wait_time_sec,
                )
                all_results.append(res)
                city_df = res["final_df"].copy()
                facility_id = CITY_CONFIGS[c_code].get("facility_id", "")
                city_df["facilityId"] = facility_id
                all_dfs.append(city_df)
                print(f"[SUCCESS] {c_code}: {res['total_skus']} SKUs | {res['total_qty']:,} Qty | File: {res['output_path']}")
            except Exception as e:
                print(f"[WARNING] Skipping {c_code} due to notice/error: {e}")

        if not all_dfs:
            raise ValueError("No city data could be generated.")

        master_df = pd.concat(all_dfs, ignore_index=True)
        dt_str_iso = pd.to_datetime(selected_date).strftime("%Y-%m-%d")
        master_out_path = os.path.join(output_dir, f"Brand_PO_EVERYWHERE_ALL_{dt_str_iso}.csv")
        try:
            master_df.to_csv(master_out_path, index=False)
        except PermissionError:
            ts = datetime.now().strftime("%H%M%S")
            master_out_path = os.path.join(output_dir, f"Brand_PO_EVERYWHERE_ALL_{dt_str_iso}_{ts}.csv")
            master_df.to_csv(master_out_path, index=False)

        total_qty = int(master_df["skuQuantity"].sum())
        total_val = float(master_df["skuPrice"].sum())

        print(f"\n========================================================")
        print(f"[COMPLETE] ALL CITIES BATCH COMPLETED!")
        print(f"   Master Output File : {master_out_path}")
        print(f"   Total SKUs         : {len(master_df):,}")
        print(f"   Total Quantity     : {total_qty:,}")
        print(f"   Total Value        : Rs.{total_val:,.2f}")
        print(f"========================================================\n")

        total_discrepancies = sum(r.get("discrepancies_count", 0) for r in all_results)
        total_qty_discrepancies = sum(r.get("qty_discrepancies_count", 0) for r in all_results)
        total_indent_qty = sum(r.get("indent_total_qty", 0) for r in all_results)
        total_indent_diff_qty = sum(r.get("indent_diff_qty", 0) for r in all_results)
        total_na_count = sum(r.get("na_count", 0) for r in all_results)
        total_na_qty = sum(r.get("na_qty", 0) for r in all_results)

        # Build Combined Multi-Tab Excel Audit Sheet
        audit_dfs = [r["audit_df"].assign(City=r["city"]) for r in all_results if "audit_df" in r and r["audit_df"] is not None and not r["audit_df"].empty]
        master_audit_df = pd.concat(audit_dfs, ignore_index=True) if audit_dfs else pd.DataFrame()

        na_dfs = [r["na_missing_df"] for r in all_results if "na_missing_df" in r and r["na_missing_df"] is not None and not r["na_missing_df"].empty]
        master_na_df = pd.concat(na_dfs, ignore_index=True) if na_dfs else pd.DataFrame()

        excel_out_path = os.path.join(output_dir, f"Price_Audit_Sheet_EVERYWHERE_ALL_{dt_str_iso}.xlsx")
        try:
            with pd.ExcelWriter(excel_out_path, engine="openpyxl") as writer:
                master_audit_df.to_excel(writer, sheet_name="Combined_Audit", index=False)
                if not master_na_df.empty:
                    master_na_df.to_excel(writer, sheet_name="NA_Missing_Items", index=False)
                else:
                    pd.DataFrame([{"Notice": "No missing vendor/SKU fields detected"}]).to_excel(writer, sheet_name="NA_Missing_Items", index=False)

                for r in all_results:
                    if "audit_df" in r and not r["audit_df"].empty:
                        sheet_name = r["city"][:31]
                        r["audit_df"].to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"Created Combined Multi-Tab Price Audit Excel: {excel_out_path}")
        except Exception as ex:
            print(f"Notice: Excel audit creation note ({ex})")
            excel_out_path = None

        # Build date-wise vendor & qty breakdown for overall master batch
        valid_master_vendors = master_df[
            (master_df["vendorName"].notna()) &
            (master_df["vendorName"].astype(str).str.strip() != "") &
            (master_df["vendorName"].astype(str).str.strip() != "#N/A")
        ]
        master_vendor_date = valid_master_vendors[["vendorName", "date"]].drop_duplicates()
        master_date_vendors = master_vendor_date.groupby("date")["vendorName"].count().to_dict()
        master_date_qtys = master_df.groupby("date")["skuQuantity"].sum().to_dict()

        master_all_dates = sorted(set(master_date_vendors.keys()).union(set(master_date_qtys.keys())))
        master_date_breakdown_detail = {}
        for d in master_all_dates:
            master_date_breakdown_detail[d] = {
                "vendors": master_date_vendors.get(d, 0),
                "qty": int(master_date_qtys.get(d, 0)),
            }

        return {
            "output_path": master_out_path,
            "audit_path": excel_out_path if excel_out_path else (all_results[0]["audit_path"] if all_results else None),
            "final_df": master_df,
            "total_skus": len(master_df),
            "indent_total_qty": total_indent_qty,
            "total_qty": total_qty,
            "indent_diff_qty": total_indent_diff_qty,
            "total_val": total_val,
            "vendor_count": sum(r.get("vendor_count", 0) for r in all_results),
            "date_vendor_breakdown": master_date_vendors,
            "date_breakdown_detail": master_date_breakdown_detail,
            "discrepancies_count": total_discrepancies,
            "qty_discrepancies_count": total_qty_discrepancies,
            "na_count": total_na_count,
            "na_qty": total_na_qty,
            "master_na_df": master_na_df,
            "all_results": all_results,
        }
    else:
        return process_single_city(
            client=client,
            city_code=city_code,
            selected_date=selected_date,
            exclude_direct_vendors=exclude_direct_vendors,
            output_dir=output_dir,
            wait_time_sec=wait_time_sec,
        )


# --------------------------------------------------------------------------
# EMBEDDED FLASK LOCAL WEB APP (PORT 8080)
# --------------------------------------------------------------------------

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Brand PO Generator</title>
    <style>
        * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: #f4f6f9; margin: 0; padding: 30px; color: #333; }
        .container { max-width: 1000px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); position: relative; }
        h1 { font-size: 24px; color: #1e293b; margin-top: 0; display: flex; align-items: center; gap: 10px; }
        p.subtitle { color: #64748b; font-size: 14px; margin-bottom: 25px; }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 25px; }
        .form-group { display: flex; flex-direction: column; gap: 8px; }
        label { font-weight: 600; font-size: 13px; color: #475569; }
        select, input[type="date"], input[type="text"] { padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; outline: none; }
        select:focus, input:focus { border-color: #2563eb; }
        .btn { background: #2563eb; color: white; border: none; padding: 14px 24px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: all 0.2s; width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .btn:hover { background: #1d4ed8; }
        .btn:disabled { background: #94a3b8; cursor: not-allowed; }
        .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 30px; margin-bottom: 25px; }
        .card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; text-align: center; }
        .card .val { font-size: 22px; font-weight: 700; color: #0f172a; margin-top: 5px; }
        .card .lbl { font-size: 12px; color: #64748b; font-weight: 500; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }
        th, td { padding: 10px 12px; border: 1px solid #e2e8f0; text-align: left; }
        th { background: #f1f5f9; font-weight: 600; color: #334155; }
        .alert-error { background: #fef2f2; color: #991b1b; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }
        .alert-success { background: #f0fdf4; color: #166534; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }
        .dl-btn { display: inline-block; background: #16a34a; color: white; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 14px; margin-top: 15px; }
        .dl-btn:hover { background: #15803d; }

        /* Loading Spinner Overlay */
        .loading-overlay { display: none; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(255, 255, 255, 0.92); border-radius: 12px; z-index: 100; flex-direction: column; align-items: center; justify-content: center; gap: 15px; }
        .spinner { width: 48px; height: 48px; border: 5px solid #e2e8f0; border-top-color: #2563eb; border-radius: 50%; animation: spin 1s infinite linear; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .loading-title { font-weight: 700; font-size: 17px; color: #0f172a; }
        .loading-desc { font-size: 13px; color: #64748b; max-width: 400px; text-align: center; line-height: 1.5; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Animated Loading Overlay -->
        <div class="loading-overlay" id="loadingOverlay">
            <div class="spinner"></div>
            <div class="loading-title">Processing Brand PO Generation...</div>
        </div>

        <h1>📦 Brand PO Generator</h1>
        <p class="subtitle">Multi-city & Batch ALL-cities automated workflow for direct Bifrost upload CSV generation</p>

        {% if error %}
            <div class="alert-error">❌ {{ error }}</div>
        {% endif %}

        {% if success %}
            <div class="alert-success">✅ Brand PO CSV Generated Successfully! File: <strong>{{ out_file }}</strong></div>
        {% endif %}

        <form method="POST" action="/generate" onsubmit="handleFormSubmit()">
            <div class="form-grid">
                <div class="form-group">
                    <label for="city">Select City / Hub</label>
                    <select name="city" id="city">
                        <option value="ALL" {% if selected_city == 'ALL' %}selected{% endif %}>🌐 ALL - All Cities (Batch Generation)</option>
                        {% for code, cfg in cities.items() %}
                            <option value="{{ code }}" {% if selected_city == code %}selected{% endif %}>{{ code }} - {{ cfg.city_name }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-group">
                    <label for="date">📅 Pick PO (D-2) Date</label>
                    <input type="date" name="date" id="date" value="{{ selected_date }}">
                </div>
            </div>
            <button type="submit" class="btn" id="submitBtn">⚡ Generate Combined Brand PO</button>
        </form>

        {% if result %}
            <div class="metrics" style="grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));">
                <div class="card">
                    <div class="lbl">TOTAL SKUs</div>
                    <div class="val">{{ result.total_skus }}</div>
                </div>
                <div class="card">
                    <div class="lbl">TOTAL QUANTITY</div>
                    <div class="val">{{ "{:,}".format(result.total_qty) }}</div>
                </div>
                <div class="card">
                    <div class="lbl">UNIT PRICE SUM</div>
                    <div class="val">₹{{ "{:,.2f}".format(result.total_val) }}</div>
                </div>
                <div class="card" style="border-color: {% if result.discrepancies_count > 0 %}#fca5a5{% else %}#bbf7d0{% endif %}; background: {% if result.discrepancies_count > 0 %}#fff5f5{% else %}#f0fdf4{% endif %};">
                    <div class="lbl">PRICE MISMATCHES</div>
                    <div class="val" style="color: {% if result.discrepancies_count > 0 %}#dc2626{% else %}#16a34a{% endif %};">{{ result.discrepancies_count }}</div>
                </div>
                <div class="card" style="border-color: {% if result.na_count > 0 %}#fed7aa{% else %}#e2e8f0{% endif %}; background: {% if result.na_count > 0 %}#fff7ed{% else %}#f8fafc{% endif %};">
                    <div class="lbl">N/A / MISSING FIELDS</div>
                    <div class="val" style="color: {% if result.na_count > 0 %}#c2410c{% else %}#0f172a{% endif %};">
                        {{ result.na_count }} <span style="font-size: 11px; font-weight: 500; color: #64748b;">({{ "{:,}".format(result.na_qty) }} Qty)</span>
                    </div>
                </div>
                <div class="card">
                    <div class="lbl">VENDORS</div>
                    <div class="val">{{ result.vendor_count }}</div>
                </div>
            </div>

            <div style="display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 25px;">
                <a href="/download?path={{ out_path }}" class="dl-btn">📥 Download Combined Brand PO CSV</a>
                {% if audit_path %}
                    <a href="/download?path={{ audit_path }}" class="dl-btn" style="background: #2563eb;">🔍 Download Price Audit & Discrepancy Sheet</a>
                {% endif %}
            </div>

            {% if result.all_results %}
                <h3 style="margin-top: 30px; font-size: 16px; color: #1e293b;">🏙️ City-Wise Order, Quantity & Vendor Breakdown</h3>
                <div style="overflow-x: auto; margin-bottom: 30px;">
                    <table>
                        <thead>
                            <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                                <th style="padding: 10px 14px; text-align: left; color: #475569;">City / Hub</th>
                                <th style="padding: 10px 14px; text-align: center; color: #475569;">Total SKUs</th>
                                <th style="padding: 10px 14px; text-align: center; color: #475569;">Total Quantity</th>
                                <th style="padding: 10px 14px; text-align: right; color: #475569;">Unit Price Sum</th>
                                <th style="padding: 10px 14px; text-align: center; color: #475569;">Vendors (Total)</th>
                                <th style="padding: 10px 14px; text-align: center; color: #475569;">Date-Wise Vendor & Qty Breakdown</th>
                                <th style="padding: 10px 14px; text-align: center; color: #475569;">N/A / Missing Items</th>
                                <th style="padding: 10px 14px; text-align: center; color: #475569;">Price Mismatches</th>
                                <th style="padding: 10px 14px; text-align: center; color: #475569;">Download City CSV</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for city_res in result.all_results %}
                                <tr style="border-bottom: 1px solid #f1f5f9;">
                                    <td style="padding: 10px 14px; font-weight: 600; color: #0f172a;">
                                        <span style="background: #eff6ff; color: #2563eb; padding: 4px 8px; border-radius: 6px; font-size: 13px;">{{ city_res.city }}</span>
                                    </td>
                                    <td style="padding: 10px 14px; text-align: center; font-weight: 600;">{{ city_res.total_skus }}</td>
                                    <td style="padding: 10px 14px; text-align: center; font-weight: 700; color: #16a34a;">{{ "{:,}".format(city_res.total_qty) }}</td>
                                    <td style="padding: 10px 14px; text-align: right; font-weight: 600;">₹{{ "{:,.2f}".format(city_res.total_val) }}</td>
                                    <td style="padding: 10px 14px; text-align: center; font-weight: 700; color: #2563eb;">{{ city_res.vendor_count }}</td>
                                    <td style="padding: 10px 14px; text-align: center;">
                                        {% if city_res.date_breakdown_detail %}
                                            {% for d_str, info in city_res.date_breakdown_detail.items() %}
                                                <div style="display: inline-block; background: #f1f5f9; border: 1px solid #e2e8f0; color: #334155; padding: 3px 8px; border-radius: 6px; font-size: 12px; margin: 2px; text-align: left;">
                                                    📅 <strong>{{ d_str }}</strong>: <span style="color: #2563eb; font-weight: 600;">{{ info.vendors }} vendors</span> | <span style="color: #16a34a; font-weight: 700;">{{ "{:,}".format(info.qty) }} qty</span>
                                                </div>
                                            {% endfor %}
                                        {% else %}
                                            <span style="color: #94a3b8; font-size: 12px;">-</span>
                                        {% endif %}
                                    </td>
                                    <td style="padding: 10px 14px; text-align: center;">
                                        {% if city_res.na_count > 0 %}
                                            <span style="display: inline-block; background: #fff7ed; border: 1px solid #fed7aa; color: #c2410c; padding: 3px 8px; border-radius: 6px; font-size: 12px; font-weight: 600;">
                                                ⚠️ {{ city_res.na_count }} items ({{ "{:,}".format(city_res.na_qty) }} qty)
                                            </span>
                                        {% else %}
                                            <span style="color: #16a34a; font-weight: 600; font-size: 13px;">✓ None</span>
                                        {% endif %}
                                    </td>
                                    <td style="padding: 10px 14px; text-align: center; font-weight: 600; color: {% if city_res.discrepancies_count > 0 %}#dc2626{% else %}#16a34a{% endif %};">
                                        {{ city_res.discrepancies_count }}
                                    </td>
                                    <td style="padding: 10px 14px; text-align: center;">
                                        <a href="/download?path={{ city_res.output_path }}" style="color: #2563eb; text-decoration: none; font-weight: 500; font-size: 13px;">📥 Download</a>
                                    </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            {% else %}
                {% if result and result.date_breakdown_detail %}
                    <h3 style="margin-top: 30px; font-size: 16px; color: #1e293b;">📅 Date-Wise Vendor & Quantity Breakdown</h3>
                    <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 25px;">
                        {% for d_str, info in result.date_breakdown_detail.items() %}
                            <div style="background: white; border: 1px solid #e2e8f0; padding: 10px 16px; border-radius: 8px; font-size: 14px; color: #334155;">
                                📅 <strong>{{ d_str }}</strong>: 
                                <span style="color: #2563eb; font-weight: 700; font-size: 15px;">{{ info.vendors }} vendors</span> &nbsp;|&nbsp; 
                                <span style="color: #16a34a; font-weight: 700; font-size: 15px;">{{ "{:,}".format(info.qty) }} qty</span>
                            </div>
                        {% endfor %}
                    </div>
                {% endif %}
            {% endif %}

        {% endif %}
    </div>

    <script>
        function handleFormSubmit() {
            document.getElementById('loadingOverlay').style.display = 'flex';
            document.getElementById('submitBtn').disabled = true;
            document.getElementById('submitBtn').innerText = '⏳ Processing... Please wait';
        }

        // Prevent form re-submission on browser refresh (F5) by resetting URL to /
        if (window.history.replaceState) {
            window.history.replaceState(null, null, '/');
        }
    </script>
</body>
</html>
"""


def start_flask_app():
    from flask import Flask, render_template_string, request, send_file, redirect

    app = Flask(__name__)

    @app.route("/", methods=["GET"])
    def index():
        today_str = datetime.now().strftime("%Y-%m-%d")
        return render_template_string(
            HTML_TEMPLATE,
            cities=CITY_CONFIGS,
            selected_city="MUM",
            selected_date=today_str,
            error=None,
            success=False,
            result=None,
        )

    @app.route("/generate", methods=["GET"])
    def generate_get():
        return redirect("/")

    @app.route("/generate", methods=["POST"])
    def generate():
        city = request.form.get("city", "MUM")
        date_val = request.form.get("date", "").strip() or datetime.now().strftime("%Y-%m-%d")

        try:
            res = process_brand_po(city_code=city, selected_date=date_val)
            table_html = res["final_df"].head(15).to_html(index=False, classes="preview-table")
            audit_path = res.get("audit_path")
            audit_df = res.get("audit_df")
            audit_html = audit_df.head(15).to_html(index=False, classes="preview-table") if (audit_df is not None and not audit_df.empty) else None

            return render_template_string(
                HTML_TEMPLATE,
                cities=CITY_CONFIGS,
                selected_city=city,
                selected_date=date_val,
                error=None,
                success=True,
                out_file=os.path.basename(res["output_path"]),
                out_path=res["output_path"],
                audit_path=audit_path,
                audit_html=audit_html,
                result=res,
                table_html=table_html,
            )
        except Exception as e:
            return render_template_string(
                HTML_TEMPLATE,
                cities=CITY_CONFIGS,
                selected_city=city,
                selected_date=date_val,
                error=str(e),
                success=False,
                result=None,
            )

    @app.route("/download", methods=["GET"])
    def download():
        file_path = request.args.get("path")
        if file_path and os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        return "File not found", 404

    print("\n" + "=" * 60)
    print("[SERVER] BRAND PO LOCAL WEB UI RUNNING AT: http://127.0.0.1:8080")
    print("=" * 60 + "\n")

    webbrowser.open("http://127.0.0.1:8080")
    app.run(host="127.0.0.1", port=8080, debug=False)


# --------------------------------------------------------------------------
# CLI ENTRY POINT
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Multi-City Brand PO Generator")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode without launching Web UI")
    parser.add_argument("--city", default="MUM", choices=list(CITY_CONFIGS.keys()) + ["ALL"], help="City/Hub code or ALL")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Target date YYYY-MM-DD")
    parser.add_argument("--output-dir", default="output", help="Directory to save CSV output")
    parser.add_argument("--credentials", help="Path to service account JSON credentials")
    args = parser.parse_args()

    if not args.cli and len(sys.argv) == 1:
        start_flask_app()
    else:
        print(f"Running Brand PO CLI for City: {args.city} | Date: {args.date}")
        res = process_brand_po(
            city_code=args.city,
            selected_date=args.date,
            credentials_path=args.credentials,
            output_dir=args.output_dir,
        )
        print(f"\n[DONE] Brand PO Created Successfully!")
        print(f"   Total SKUs     : {res['total_skus']}")
        print(f"   Total Quantity : {res['total_qty']:,}")
        print(f"   Total Value    : Rs.{res['total_val']:,.2f}")
        print(f"   Output File    : {res['output_path']}")


if __name__ == "__main__":
    main()
    
    