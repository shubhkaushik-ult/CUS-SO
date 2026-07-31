import pandas as pd
import numpy as np
import os
import sys
import warnings

# Ensure prints don't crash on Windows with charmap encoding
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

warnings.filterwarnings('ignore')

# ── Column used to detect NA rows ──────────────────────────────
NA_CHECK_COLS = ["FSN", "NC ID", "Sales Price", "lot weight ID", "customer_contact_number(req)"]

OUTPUT_COLS = [
    "customer_contact_number(req)",
    "NC ID",
    "NC Name",
    "QTY",
    "Date",
    "lot weight ID",
    "ordering_mode(optional)",
    "cancelled (optional)By default should be 0",
    "purchaseOrder",
    "Sales Price",
    "DELIVERY_CHARGE(opt)",
    "CITY_ID(req)",
    "sale_order_id(optional- leave empty)",
    "sub_type (optional- leave empty)",
    "CategoryId (if empty then default is 1)",
    "grocerFlow",
]

# ── City config ─────────────────────────────────────────────────
CITY_CONFIG = {
    "Bangalore": {
        "po_prefix":        "NCXDB",
        "city_initial":     "B",
        "city_id":          2,
        "alloc_city_name":  "Bangalore",
        "so_sheet":         "BLR FK GRO SO",
        "po_sheet":         "BLR FK Gro PO FIle",
        "sku_sheet":        "BLR GRO SKU config",
        "nlc_sheet":        "BLR FK Gro NLC",
        "cust_sheet":       "BLR FK Customers",
    },
    "Chennai": {
        "po_prefix":        "NCXDC",
        "city_initial":     "C",
        "city_id":          3,
        "alloc_city_name":  "Chennai",
        "so_sheet":         "CHN FK GRO SO",
        "po_sheet":         "CHN FK Gro PO FIle",
        "sku_sheet":        "CHN GRO SKU config",
        "nlc_sheet":        "CHN FK GRO NLC",
        "cust_sheet":       "CHN FK Customers",
    },
    "Mumbai": {
        "po_prefix":        "NCXDM",
        "city_initial":     "M",
        "city_id":          4,
        "alloc_city_name":  "Mumbai",
        "so_sheet":         "MUM FK GRO SO",
        "po_sheet":         "MUM FK Gro PO FIle",
        "sku_sheet":        "MUM GRO SKU config",
        "nlc_sheet":        "MUM FK Gro NLC",
        "cust_sheet":       "MUM FK Customers",
    },
    "Hyderabad": {
        "po_prefix":        "NCXDH",
        "city_initial":     "H",
        "city_id":          5,
        "alloc_city_name":  "Hyderabad",
        "so_sheet":         "HYD FK GRO SO",
        "po_sheet":         "HYD FK Gro PO FIle",
        "sku_sheet":        "HYD GRO SKU config",
        "nlc_sheet":        "HYD FK Gro NLC",
        "cust_sheet":       "HYD FK Customers",
    },
    "Trichy": {
        "po_prefix":        "NCXDT",
        "city_initial":     "T",
        "city_id":          6,
        "alloc_city_name":  "Trichy",
        "so_sheet":         "Trichy FK GRO SO",
        "po_sheet":         "Trichy FK Gro PO FIle",
        "sku_sheet":        "Trichy GRO SKU config",
        "nlc_sheet":        "Trichy FK GRO NLC",
        "cust_sheet":       "Trichy FK Customers",
    },
    "Coimbatore": {
        "po_prefix":        "NCXDCBE",
        "city_initial":     "CBE",
        "city_id":          7,
        "alloc_city_name":  "Coimbatore",
        "so_sheet":         "CBE FK GRO SO",
        "po_sheet":         "CBE FK Gro PO FIle",
        "sku_sheet":        "Coimbatore GRO SKU config",
        "nlc_sheet":        "CBE FK GRO NLC",
        "cust_sheet":       "Coimbatore FK customer",
    },
}

# ── FnV City config ──────────────────────────────────────────────
FNV_CITY_CONFIG = {
    "Bangalore": {
        "po_prefix":        "NCBLR",
        "city_initial":     "B",
        "city_id":          2,
        "alloc_city_name":  "Bangalore",
        "so_sheet":         "BLR FK SO",
        "po_sheet":         "BLR FK PO FIle",
        "cust_sheet":       "BLR FK Customers",
    },
    "Chennai": {
        "po_prefix":        "NCCHN",
        "city_initial":     "C",
        "city_id":          3,
        "alloc_city_name":  "Chennai",
        "so_sheet":         "CHN FK SO",
        "po_sheet":         "CHN FK PO File",
        "cust_sheet":       "CHN FK Customers",
    },
    "Mumbai": {
        "po_prefix":        "NCMUM",
        "city_initial":     "M",
        "city_id":          4,
        "alloc_city_name":  "Mumbai",
        "so_sheet":         "MUM FK SO",
        "po_sheet":         "MUM FK PO FIle",
        "cust_sheet":       "MUM FK Customers",
    },
    "Hyderabad": {
        "po_prefix":        "NCHYD",
        "city_initial":     "H",
        "city_id":          5,
        "alloc_city_name":  "Hyderabad",
        "so_sheet":         "HYD FK SO",
        "po_sheet":         "HYD FK PO FIle",
        "cust_sheet":       "HYD FK Customers",
    },
    "Trichy": {
        "po_prefix":        "NCTRY",
        "city_initial":     "T",
        "city_id":          6,
        "alloc_city_name":  "Trichy",
        "so_sheet":         "Trichy FK SO",
        "po_sheet":         "Trichy FK PO File",
        "cust_sheet":       "Trichy FK Customers",
    },
    "Coimbatore": {
        "po_prefix":        "NCCBE",
        "city_initial":     "CBE",
        "city_id":          7,
        "alloc_city_name":  "Coimbatore",
        "so_sheet":         "Coimbatore FK SO",
        "po_sheet":         "Coimbatore FK PO File",
        "cust_sheet":       "Coimbatore FK customer",
    },
    "Nashik": {
        "po_prefix":        "NCNSH",
        "city_initial":     "N",
        "city_id":          8,
        "alloc_city_name":  "Nashik",
        "so_sheet":         "Nashik FK SO",
        "po_sheet":         "Nashik FK PO FIle",
        "cust_sheet":       "Nashik FK Customers",
    },
}

# ── FnV Satellite cities mapping ─────────────────────────────────
# The FnV all-city Excel has a City column; all rows matching any of
# these city names are treated as belonging to the main city.
FNV_SATELLITE_CITIES = {
    "Bangalore":  ["Bangalore", "Bengaluru", "Hosur", "Mandya", "Mysore", "Tumkur"],
    "Mumbai":     ["Mumbai"],
    "Chennai":    ["Chennai"],
    "Coimbatore": ["Coimbatore", "Erode", "Palakkad", "Salem", "Tirupur"],
    "Trichy":     ["Trichy", "Dindigul", "Karur", "Thanjavur", "Madurai"],
    "Nashik":     ["Nashik"],
    "Hyderabad":  ["Hyderabad"],
}


def get_gsheet_client(gsheet_url: str):
    """Authenticate and return the Google Sheets client and the sheet object."""
    import re, gspread
    from google.oauth2.service_account import Credentials
    
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', gsheet_url)
    if not match:
        raise ValueError("Could not extract sheet ID from URL")
    sheet_id = match.group(1)
    
    creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ecom-so-reader-credetials.json')
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"Service account credentials not found at {creds_path}")
        
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
    gc = gspread.authorize(credentials)
    
    try:
        sh = gc.open_by_key(sheet_id)
        return sh, credentials.service_account_email
    except gspread.exceptions.APIError as e:
        if e.response.status_code in (403, 404):
            raise ValueError(f"Permission denied! Please ensure you have shared the Google Sheet with Editor access to: {credentials.service_account_email}")
        raise ValueError(f"Google Sheets API Error: {str(e)}")
        

def get_worksheet_flexible(sh, target_name):
    target = target_name.strip().lower()
    for ws in sh.worksheets():
        if ws.title.strip().lower() == target:
            return ws
    raise ValueError(f"Could not find a tab named '{target_name}' in the Google Sheet. Please check the spelling and trailing spaces.")

def update_gsheet_po_file(gsheet_url: str, po_sheet_name: str, df: pd.DataFrame):
    """Clear the PO tab and upload the new Allocation data."""
    import gspread
    sh, sa_email = get_gsheet_client(gsheet_url)
    try:
        worksheet = get_worksheet_flexible(sh, po_sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        raise ValueError(f"Could not find a tab named '{po_sheet_name}' in the Google Sheet.")
        
    worksheet.clear()
    
    # Fill NaN with empty string for gspread compatibility
    df_upload = df.fillna("")
    
    # Convert dataframe to list of lists (including header)
    data = [df_upload.columns.values.tolist()] + df_upload.values.tolist()
    
    # Use USER_ENTERED so that formulas starting with '=' are evaluated by Google Sheets
    try:
        worksheet.update(values=data, range_name="A1", value_input_option="USER_ENTERED")
    except TypeError:
        # Fallback for older gspread versions
        worksheet.update(data, value_input_option="USER_ENTERED")

def drag_formulas_in_so(gsheet_url: str, so_sheet_name: str, target_rows: int):
    """Automatically drags down formulas from row 2 to target_rows in the SO sheet."""
    import gspread
    sh, sa_email = get_gsheet_client(gsheet_url)
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
                    "startRowIndex": 1,  # Row 2 (0-indexed)
                    "endRowIndex": 2,    # Row 2
                    "startColumnIndex": 0,
                    "endColumnIndex": so_ws.col_count
                },
                "dimension": "ROWS",
                "fillLength": max(0, target_rows - 1)  # How many additional rows to fill
            }
        }
    }
    try:
        sh.batch_update({"requests": [req]})
        print(f"       ✅ Formulas dragged down in '{so_sheet_name}' to cover {target_rows} rows.")
    except Exception as e:
        print(f"       [WARN] Failed to auto-fill formulas in SO tab: {e}")

def load_gsheet_so(gsheet_url: str, so_sheet_name: str) -> pd.DataFrame:
    """Fetch SO tab from a Google Sheet URL securely using service account."""
    import gspread
    sh, sa_email = get_gsheet_client(gsheet_url)
    
    try:
        worksheet = get_worksheet_flexible(sh, so_sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        raise ValueError(f"Could not find a tab named '{so_sheet_name}' in the Google Sheet.")
    except Exception as e:
        # Fallback catch for the specific PermissionError wrapper in newer gspread
        if type(e).__name__ == 'PermissionError':
            raise ValueError(f"Permission denied! Please veri fy the Google Sheet is shared as Viewer with: {credentials.service_account_email}")
        raise
    data = worksheet.get_all_values()  
    if not data:
        return pd.DataFrame()
    
    return pd.DataFrame(data[1:], columns=data[0])


def run_automation(
    allocation_path: str,
    ecom_path: str,
    city: str,
    delivery_date: str,
    output_dir: str = ".",
    gsheet_url: str = None,
    so_sheet_override: str = None,
    po_sheet_override: str = None,
):
    """
    Main automation.

    Steps:
      1. Read Allocation PO sheet → build Key & PO IDs
      2. Read E.com SO Placement sheet (BLR FK GRO SO) — from local file or G-sheet
      3. Separate valid vs NA rows
      4. Export: CSV (valid) + Excel with two tabs (valid + NA)
    """
    if city not in CITY_CONFIG:
        raise ValueError(f"Unknown city '{city}'. Options: {list(CITY_CONFIG.keys())}")

    cfg = CITY_CONFIG[city]
    os.makedirs(output_dir, exist_ok=True)
    
    so_sheet_name = so_sheet_override.strip() if so_sheet_override and so_sheet_override.strip() else cfg["so_sheet"]
    po_sheet_name = po_sheet_override.strip() if po_sheet_override and po_sheet_override.strip() else cfg["po_sheet"]

    print(f"\n{'='*60}")
    print(f"  {city}  |  PO Prefix: {cfg['po_prefix']}  |  Date: {delivery_date}")
    print(f"{'='*60}\n")

    # ── Step 1: Allocation PO sheet → build Key + PO IDs ────────
    print("► [1/3] Reading Allocation file...")
    alloc = pd.read_excel(allocation_path, sheet_name="PO")
    if "City" in alloc.columns:
        valid_cities = [cfg["alloc_city_name"].lower(), "bengaluru"] if city == "Bangalore" else [cfg["alloc_city_name"].lower()]
        alloc = alloc[alloc["City"].astype(str).str.strip().str.lower().isin(valid_cities)].copy()
    else:
        print("       Detected processed format — using all rows directly")
    print(f"       {len(alloc)} rows for {city}")

    # ── Drop zero-QTY rows from allocation BEFORE anything else ───
    qty_col_alloc = next((c for c in ["Final PO", "final po", "QTY", "Quantity", "Qty", "PO qty"] if c in alloc.columns), None)
    if qty_col_alloc:
        alloc[qty_col_alloc] = pd.to_numeric(alloc[qty_col_alloc], errors="coerce").fillna(0)
        before = len(alloc)
        alloc = alloc[alloc[qty_col_alloc] > 0].copy()
        print(f"       [Filter] Dropped {before - len(alloc)} zero-QTY rows. Remaining: {len(alloc)}")
    else:
        print("       [WARN] Could not detect QTY column — skipping zero-QTY filter.")

    if "Store Site ID" in alloc.columns:
        alloc["Warehouse"] = alloc["Store Site ID"].astype(str).str.strip()
    elif "Warehouse" in alloc.columns:
        alloc["Warehouse"] = alloc["Warehouse"].astype(str).str.strip()

    if "Store ID" not in alloc.columns and "Store" in alloc.columns:
        alloc["Store ID"] = alloc["Store"]
    elif "Store ID" not in alloc.columns:
        alloc["Store ID"] = ""

    alloc["Supplier_ID"] = alloc["Supplier ID"].astype(str).str.strip()
    
    # Prioritize Store ID for PO grouping if available and not empty, fallback to Warehouse
    store_id_col = alloc["Store ID"].astype(str).str.strip() if "Store ID" in alloc.columns else alloc["Warehouse"]
    store_id_col = store_id_col.replace(["", "NAN", "nan", "None"], pd.NA).fillna(alloc["Warehouse"])
    alloc["Key"] = (store_id_col + alloc["Supplier_ID"]).str.upper()

    # Sequential PO ID per unique Key (Warehouse+SupplierID combo)
    unique_keys = list(dict.fromkeys(alloc["Key"].tolist()))  # preserve order
    key_to_poid = {k: f"{cfg['po_prefix']}{str(i+1).zfill(3)}" for i, k in enumerate(unique_keys)}
    alloc["PO_ID_generated"] = alloc["Key"].map(key_to_poid)

    # Build key reference table
    key_table = (
        alloc[["Key", "Warehouse", "Supplier_ID", "PO_ID_generated", "Store ID"]]
        .drop_duplicates("Key")
        .rename(columns={"PO_ID_generated": "PO ID", "Supplier_ID": "Supplier ID", "Store ID": "Store"})
    )

    # ── Step 2: Update PO Tab & Load E.com SO tab ─────────────────
    if gsheet_url:
        import time
        print(f"► [2/3] Updating {po_sheet_name} tab in Google Sheet...")
        
        # Prepare strictly formatted upload dataframe based on user spec
        upload_df = pd.DataFrame()
        upload_df["FSN/ISBN13"] = alloc["FSN"] if "FSN" in alloc.columns else ""
        
        if "FSN_Title" in alloc.columns:
            upload_df["Title"] = alloc["FSN_Title"]
        elif "Title" in alloc.columns:
            upload_df["Title"] = alloc["Title"]
        elif "NC Name" in alloc.columns:
            upload_df["Title"] = alloc["NC Name"]
        else:
            upload_df["Title"] = ""
            
        if "Final PO" in alloc.columns:
            upload_df["QTY"] = alloc["Final PO"]
        elif "QTY" in alloc.columns:
            upload_df["QTY"] = alloc["QTY"]
        elif "Quantity" in alloc.columns:
            upload_df["QTY"] = alloc["Quantity"]
        elif "Qty" in alloc.columns:
            upload_df["QTY"] = alloc["Qty"]
        elif "PO qty" in alloc.columns:
            upload_df["QTY"] = alloc["PO qty"]
        else:
            upload_df["QTY"] = ""
            
        cust_sheet = cfg.get("cust_sheet", "BLR FK Customers")
        
        # Fetch the customer sheet to get the FK Site Name mapping
        print(f"       Fetching '{cust_sheet}' to map FK Site Name...")
        try:
            cust_sh, _ = get_gsheet_client(gsheet_url)
            cust_ws = get_worksheet_flexible(cust_sh, cust_sheet)
            cust_data = cust_ws.get_all_values()
            
            if len(cust_data) > 1:
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
                        fk_site_map.update({str(k).strip().lower(): v for k, v in raw_map_1.items() if str(v).strip() not in ["", "nan", "None", "NAN"]})
                    if wh_name_col:
                        raw_map_2 = cust_df.set_index(wh_name_col)[fk_site_col].to_dict()
                        fk_site_map.update({str(k).strip().lower(): v for k, v in raw_map_2.items() if str(v).strip() not in ["", "nan", "None", "NAN"]})
            else:
                fk_site_map = {}
        except Exception as e:
            print(f"       [WARN] Failed to fetch customer sheet mapping: {e}")
            fk_site_map = {}

        upload_df["PO Number"] = alloc["PO_ID_generated"]
        _store_fallback = alloc["Store ID"].astype(str).str.strip() if "Store ID" in alloc.columns else alloc["Warehouse"]
        _store_fallback = _store_fallback.replace(["", "NAN", "nan", "None"], pd.NA).fillna(alloc["Warehouse"])
        _wh_code = alloc["Warehouse"].astype(str).str.strip()
        
        _mapped_store = _wh_code.str.lower().map(fk_site_map).replace(["", "nan", "None", "NAN"], pd.NA)
        _mapped_store = _mapped_store.fillna(_store_fallback.str.lower().map(fk_site_map).replace(["", "nan", "None", "NAN"], pd.NA))
        upload_df["Store"] = _mapped_store.fillna(_store_fallback)
        
        # Filter: only upload rows where QTY > 0 (skip 0-qty and blank rows upfront)
        upload_df["QTY_NUM"] = pd.to_numeric(upload_df["QTY"], errors="coerce").fillna(0)
        upload_df = upload_df[upload_df["QTY_NUM"] > 0].copy()
        upload_df.drop(columns=["QTY_NUM"], inplace=True)
        
        num_rows_uploaded = len(upload_df)
        print(f"       {num_rows_uploaded} rows to upload (including missing qty/po ids)")
        upload_df = upload_df.reset_index(drop=True)
        
        # Inject dynamic VLOOKUP formula for the Contact column
        upload_df["Contact"] = [f"=VLOOKUP(E{i},'{cust_sheet}'!F:G,2,0)" for i in range(2, len(upload_df) + 2)]
        
        update_gsheet_po_file(gsheet_url, po_sheet_name, upload_df)
        
        print("       Dragging formulas in SO tab...")
        drag_formulas_in_so(gsheet_url, so_sheet_name, num_rows_uploaded)
        
        print("       Waiting 5 seconds for Google Sheet formulas to evaluate...")
        time.sleep(5)
        
        print("       Fetching updated SO data from Google Sheet...")
        so_df = load_gsheet_so(gsheet_url, so_sheet_name)
    else:
        print("► [2/3] Reading E.com SO Placement data locally...")
        so_df = pd.read_excel(ecom_path, sheet_name=so_sheet_name)

    so_df.columns = so_df.columns.str.strip()
    print(f"       {len(so_df)} total rows in SO tab")


    so_df.replace(["#N/A", "#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#NUM!", "#NULL!"], np.nan, inplace=True)

    # Convert numeric columns from strings back to proper numbers (since gspread returns all strings)
    for col in so_df.columns:
        if col not in ["Date", "NC Name", "ordering_mode(optional)", "purchaseOrder", "sale_order_id(optional- leave empty)", "customer_contact_number(req)", "sub_type (optional- leave empty)"]:
            try:
                # Remove commas from formatted numbers before parsing
                temp = so_df[col].astype(str).str.replace(',', '', regex=False)
                numeric_vals = pd.to_numeric(temp, errors="coerce")
                # Only convert if at least some values are numeric
                if numeric_vals.notna().any():
                    # Convert to object dtype first to avoid Arrow string column type conflict
                    so_df[col] = so_df[col].astype(object)
                    so_df[col] = numeric_vals
            except (ValueError, TypeError):
                pass

    # Fix contact number formatting (prevent scientific notation)
    def parse_contact(x):
        if pd.isna(x): return np.nan
        try:
            return str(int(float(x)))
        except (ValueError, TypeError):
            return x

    if "customer_contact_number(req)" in so_df.columns:
        so_df["customer_contact_number(req)"] = so_df["customer_contact_number(req)"].apply(parse_contact)

    # Ensure date column is formatted correctly
    if "Date" in so_df.columns:
        so_df["Date"] = pd.to_datetime(so_df["Date"], errors="coerce").dt.date
    # If dates are all NaT, use delivery_date
    if so_df["Date"].isna().all():
        from datetime import datetime
        so_df["Date"] = datetime.strptime(delivery_date, "%d-%m-%Y").date()

    # Ensure all output columns exist
    for col in OUTPUT_COLS:
        if col not in so_df.columns:
            so_df[col] = np.nan

    # Filter out completely blank QTY rows from so_df (just in case they are truly blank artifacts)
    # But keep them if they have a Title or FSN (which we want to flag as NA)
    # Wait, we already filtered empty rows before upload, so whatever is here is intended to be here.
    # We will NOT filter QTY here, because we want empty QTY to go to the NA tab!

    print(f"       Total QTY in Google Sheet before NA separation: {pd.to_numeric(so_df.get('QTY'), errors='coerce').sum()}")

    # ── Step 3: Separate valid vs NA rows ────────────────────────
    print("► [3/3] Separating valid and NA rows...")
    
    # Filter out completely blank rows (missing both FSN and contact) from GSheet artifacts
    fsn_col = "FSN" if "FSN" in so_df.columns else "sku_id(req)"
    if fsn_col in so_df.columns and "customer_contact_number(req)" in so_df.columns:
        is_missing_both = (so_df[fsn_col].fillna("").astype(str).str.strip() == "") & (so_df["customer_contact_number(req)"].fillna("").astype(str).str.strip() == "")
        so_df = so_df[~is_missing_both].copy()

    # ── Early filter: drop rows with QTY = 0 or blank immediately ──
    if "QTY" in so_df.columns:
        valid_qty_mask = pd.to_numeric(so_df["QTY"], errors="coerce").fillna(0) > 0
        dropped_zero = (~valid_qty_mask).sum()
        if dropped_zero > 0:
            print(f"       [Filter] Dropped {dropped_zero} rows with zero/blank QTY before NA split.")
        so_df = so_df[valid_qty_mask].copy()

    NA_CHECK_COLS_WITH_PO = NA_CHECK_COLS + ["purchaseOrder"]
    actual_check_cols = [c for c in NA_CHECK_COLS_WITH_PO if c in so_df.columns]
    
    if actual_check_cols:
        is_null = so_df[actual_check_cols].isnull().any(axis=1)
        stripped = so_df[actual_check_cols].fillna("").astype(str).apply(lambda x: x.str.strip())
        is_blank = (stripped == "").any(axis=1)
        is_na_str = stripped.isin(["NA", "#N/A", "nan", "None", "na", "#n/a"]).any(axis=1)
        is_na = is_null | is_blank | is_na_str
    else:
        is_na = pd.Series(False, index=so_df.index)
        
    # Also NA if QTY is invalid
    if "QTY" in so_df.columns:
        is_invalid_qty = so_df["QTY"].isna() | (pd.to_numeric(so_df["QTY"], errors="coerce").fillna(0) <= 0)
        is_na = is_na | is_invalid_qty
        
    df_valid = so_df[~is_na][OUTPUT_COLS].copy()
    
    # Format NA rows to be distinct and contain specific columns
    raw_df_na = so_df[is_na].copy()
    df_na = pd.DataFrame()
    if len(raw_df_na) > 0:
        df_na["FSN"] = raw_df_na.get(fsn_col, pd.Series(dtype=str)).fillna("NA")
        
        title_series = raw_df_na.get("Title") if "Title" in raw_df_na.columns else raw_df_na.get("NC Name", pd.Series(dtype=str))
        df_na["Title"] = title_series.fillna("NA").replace("", "NA")
        
        df_na["Price"] = raw_df_na.get("Sales Price", pd.Series(dtype=str)).fillna("NA")
        df_na["QTY"] = raw_df_na.get("QTY", pd.Series(dtype=str)).fillna("NA")
        if "customer_contact_number(req)" in raw_df_na.columns:
            df_na["Contact"] = raw_df_na["customer_contact_number(req)"].fillna("Missing")
        if "NC ID" in raw_df_na.columns:
            df_na["NC_ID"] = raw_df_na["NC ID"].fillna("Missing")
        
        df_na = df_na.drop_duplicates(subset=["FSN"])

        # ── Pass 1: Fill missing Title from Allocation file (already in memory) ──
        # Build FSN → Title map from alloc
        alloc_fsn_col = "FSN" if "FSN" in alloc.columns else None
        alloc_title_col = next(
            (c for c in ["FSN_Title", "Title", "NC Name"] if c in alloc.columns), None
        )
        if alloc_fsn_col and alloc_title_col:
            alloc_title_map = (
                alloc[[alloc_fsn_col, alloc_title_col]]
                .dropna(subset=[alloc_fsn_col])
                .drop_duplicates(subset=[alloc_fsn_col])
                .set_index(alloc_fsn_col)[alloc_title_col]
                .to_dict()
            )
            def _fill_title_from_alloc(row):
                if str(row["Title"]).strip() in ("", "NA", "#N/A"):
                    return alloc_title_map.get(str(row["FSN"]).strip(), row["Title"])
                return row["Title"]
            df_na["Title"] = df_na.apply(_fill_title_from_alloc, axis=1)
            filled = (df_na["Title"].astype(str).str.strip() != "NA").sum()
            print(f"       [Alloc] Filled Title for {filled} NA rows from Allocation file.")

        # ── Pass 2: Fetch missing Price from DB using SKU Name ──────────
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
                    def _fill_price_from_db(row):
                        if str(row["Price"]).strip() in ("", "NA", "#N/A", "nan", "None", "0", "0.0"):
                            key = str(row["Title"]).strip().lower()
                            return price_map.get(key, row["Price"])
                        return row["Price"]
                    df_na["Price"] = df_na.apply(_fill_price_from_db, axis=1)
            except Exception as db_err:
                print(f"       [DB WARN] Could not fetch price from DB: {db_err}")

        # ── Pass 2.5: Fetch missing Contact from DB using NC Name OR Store Site ID ────────
        if "customer_contact_number(req)" in raw_df_na.columns:
            need_contact_mask = raw_df_na["customer_contact_number(req)"].astype(str).str.strip().isin(["", "NA", "#N/A", "nan", "None"])
            
            # Map purchaseOrder to the original Store Site ID from alloc
            if "purchaseOrder" in raw_df_na.columns and "PO_ID_generated" in alloc.columns:
                store_col = next((c for c in alloc.columns if str(c).strip().lower() in ["store site id", "fk site id"]), None)
                if not store_col:
                    store_col = "Store ID" if "Store ID" in alloc.columns else "Warehouse"
                po_to_store = alloc.set_index("PO_ID_generated")[store_col].to_dict()
                raw_df_na["_fallback_store_id"] = raw_df_na["purchaseOrder"].map(po_to_store)
            else:
                raw_df_na["_fallback_store_id"] = ""

            names_to_fetch = set()
            for idx, row in raw_df_na[need_contact_mask].iterrows():
                nc_name = str(row.get("NC Name", "")).strip()
                fallback = str(row.get("_fallback_store_id", "")).strip()
                if nc_name and nc_name not in ["", "NA", "#N/A", "nan", "None"]:
                    names_to_fetch.add(nc_name)
                if fallback and fallback not in ["", "NA", "#N/A", "nan", "None"]:
                    names_to_fetch.add(fallback)

            names_for_db_contact = list(names_to_fetch)
            
            if names_for_db_contact:
                try:
                    import db_lookup
                    contact_map = db_lookup.fetch_contact_by_name(names_for_db_contact, city)
                    if contact_map:
                        def _fill_contact_from_db(row):
                            if str(row.get("customer_contact_number(req)", "")).strip() in ("", "NA", "#N/A", "nan", "None"):
                                nc_key = str(row.get("NC Name", "")).strip().lower()
                                fb_key = str(row.get("_fallback_store_id", "")).strip().lower()
                                if nc_key in contact_map:
                                    return contact_map[nc_key]
                                if fb_key in contact_map:
                                    return contact_map[fb_key]
                            return row.get("customer_contact_number(req)")
                        raw_df_na["customer_contact_number(req)"] = raw_df_na.apply(_fill_contact_from_db, axis=1)
                        if "Contact" in df_na.columns:
                            df_na["Contact"] = raw_df_na["customer_contact_number(req)"].values
                            df_na["Contact"] = df_na["Contact"].replace(["", "nan", "None", "#N/A"], "Missing").fillna("Missing")
                except Exception as db_err:
                    print(f"       [DB WARN] Could not fetch contact from DB: {db_err}")

        # ── Pass 3: Re-evaluate NA rows after enrichment ────────────────
        # For rows where we now have a Price, update Sales Price in raw_df_na
        # and re-run the NA check — promote newly valid rows to df_valid
        enriched_price_df = df_na[~df_na["Price"].astype(str).str.strip().isin(["", "NA", "#N/A", "nan", "None", "0", "0.0"])]
        if len(enriched_price_df) > 0:
            fsn_to_enriched_price = enriched_price_df.set_index("FSN")["Price"].to_dict()

            raw_df_na["Sales Price"] = raw_df_na.apply(
                lambda r: fsn_to_enriched_price.get(str(r.get(fsn_col, "")).strip(), r.get("Sales Price", np.nan)),
                axis=1
            )

        # Re-run is_na check unconditionally
        recheck_cols = [c for c in NA_CHECK_COLS + ["purchaseOrder"] if c in raw_df_na.columns]
        if recheck_cols:
            is_null_rc   = raw_df_na[recheck_cols].isnull().any(axis=1)
            stripped_rc  = raw_df_na[recheck_cols].fillna("").astype(str).apply(lambda x: x.str.strip())
            is_blank_rc  = (stripped_rc == "").any(axis=1)
            is_na_str_rc = stripped_rc.isin(["NA", "#N/A", "nan", "None", "na", "#n/a"]).any(axis=1)
            is_na_rc     = is_null_rc | is_blank_rc | is_na_str_rc
        else:
            is_na_rc = pd.Series(False, index=raw_df_na.index)
            
        if "QTY" in raw_df_na.columns:
            is_na_rc = is_na_rc | (raw_df_na["QTY"].isna() | (pd.to_numeric(raw_df_na["QTY"], errors="coerce").fillna(0) <= 0))

        newly_valid = raw_df_na[~is_na_rc][OUTPUT_COLS].copy()
        if len(newly_valid) > 0:
            df_valid = pd.concat([df_valid, newly_valid], ignore_index=True)
            print(f"       ✅ {len(newly_valid)} rows promoted: NA → Valid SO after DB enrichment.")

        # Rebuild df_na from still-invalid rows only
        raw_df_na = raw_df_na[is_na_rc].copy()
        df_na = pd.DataFrame()
        if len(raw_df_na) > 0:
                df_na["FSN"]   = raw_df_na.get(fsn_col, pd.Series(dtype=str)).fillna("NA")
                t_rc           = raw_df_na.get("Title") if "Title" in raw_df_na.columns else raw_df_na.get("NC Name", pd.Series(dtype=str))
                df_na["Title"] = t_rc.fillna("NA").replace("", "NA")
                df_na["Price"] = raw_df_na.get("Sales Price", pd.Series(dtype=str)).fillna("NA")
                df_na["QTY"]   = raw_df_na.get("QTY", pd.Series(dtype=str)).fillna("NA")
                if "customer_contact_number(req)" in raw_df_na.columns:
                    df_na["Contact"] = raw_df_na["customer_contact_number(req)"].fillna("Missing")
                if "NC ID" in raw_df_na.columns:
                    df_na["NC_ID"] = raw_df_na["NC ID"].fillna("Missing")
                
                df_na = df_na.drop_duplicates(subset=["FSN"])

    print(f"       ✓ Valid rows : {len(df_valid)}")
    print(f"       ✗ NA rows    : {len(df_na)} (distinct)")
    print(f"       ✓ Valid QTY  : {pd.to_numeric(df_valid.get('QTY'), errors='coerce').sum()}")
    print(f"       ✗ NA QTY     : {pd.to_numeric(raw_df_na.get('QTY'), errors='coerce').sum()}")

    # ── Output ───────────────────────────────────────────────────
    from datetime import datetime
    try:
        dt = datetime.strptime(delivery_date, "%d-%m-%Y")
        date_tag = dt.strftime("%B %d")
    except:
        date_tag = delivery_date.replace("-", " ")

    base_name = f"{city} XD SO {date_tag}"

    csv_path  = os.path.join(output_dir, f"{base_name}.csv")
    xlsx_path = os.path.join(output_dir, f"{base_name}_full.xlsx")
    po_path   = os.path.join(output_dir, f"{city} XD PO Mapping {date_tag}.xlsx")

    # Main CSV — valid rows only
    df_valid.to_csv(csv_path, index=False)

    # Excel — two tabs: valid + NA
    with pd.ExcelWriter(xlsx_path, engine="openpyxl", datetime_format="DD-MM-YYYY") as writer:
        df_valid.to_excel(writer, sheet_name="SO Output", index=False)
        if len(df_na) > 0:
            df_na.to_excel(writer, sheet_name="NA Rows", index=False)
        else:
            pd.DataFrame({"Message": ["No NA rows found"]}).to_excel(
                writer, sheet_name="NA Rows", index=False
            )

    # PO Key mapping reference
    key_table.to_excel(po_path, index=False)

    print(f"\n  ✅ CSV saved      → {csv_path}")
    print(f"  ✅ Excel saved    → {xlsx_path}")
    print(f"  ✅ PO Map saved   → {po_path}\n")

    return csv_path, xlsx_path, po_path, len(df_valid), len(df_na), len(so_df), len(unique_keys)


def run_fnv_automation(
    fnv_alloc_path: str,
    city: str,
    delivery_date: str,
    output_dir: str = ".",
    gsheet_url: str = None,
    so_sheet_override: str = None,
    po_sheet_override: str = None,
    city_col: str = "City",
):
    """
    FnV SO automation.

    Steps:
      1. Read the all-city FnV Excel → filter rows for main city + satellite cities
      2. Build Key & PO IDs
      3. Update FnV PO Tab in GSheet, then fetch FnV SO tab
      4. Separate valid vs NA rows → export CSV + Excel + PO mapping
    """
    if city not in FNV_CITY_CONFIG:
        raise ValueError(f"Unknown city '{city}' for FnV. Options: {list(FNV_CITY_CONFIG.keys())}")

    cfg = FNV_CITY_CONFIG[city]
    satellite_cities = FNV_SATELLITE_CITIES.get(city, [city])
    os.makedirs(output_dir, exist_ok=True)

    so_sheet_name = so_sheet_override.strip() if so_sheet_override and so_sheet_override.strip() else cfg["so_sheet"]
    po_sheet_name = po_sheet_override.strip() if po_sheet_override and po_sheet_override.strip() else cfg["po_sheet"]

    print(f"\n{'='*60}")
    print(f"  FnV | {city}  |  PO Prefix: {cfg['po_prefix']}  |  Date: {delivery_date}")
    print(f"  Satellite cities: {satellite_cities}")
    print(f"{'='*60}\n")

    # ── Step 1: Read all-city FnV Excel & filter ─────────────────
    print("► [1/3] Reading FnV allocation file...")
    alloc = pd.read_excel(fnv_alloc_path)

    # Detect city column (try supplied name first, then common variants)
    city_col_actual = None
    for candidate in [city_col, "City", "city", "Location", "location", "CITY"]:
        if candidate in alloc.columns:
            city_col_actual = candidate
            break

    if city_col_actual:
        # Normalise city values for case-insensitive matching
        satellite_lower = [s.lower().strip() for s in satellite_cities]
        mask = alloc[city_col_actual].astype(str).str.strip().str.lower().isin(satellite_lower)
        alloc = alloc[mask].copy()
        print(f"       Filtered by city column '{city_col_actual}': {satellite_cities}")
    else:
        print(f"       [WARN] City column not found — using all rows. Columns: {list(alloc.columns)}")

    print(f"       {len(alloc)} rows for {city} (including satellite cities)")

    # ── Drop zero-QTY rows from allocation BEFORE anything else ───
    qty_col_alloc = next((c for c in ["Final PO", "final po", "QTY", "Quantity", "Qty", "PO qty"] if c in alloc.columns), None)
    if qty_col_alloc:
        alloc[qty_col_alloc] = pd.to_numeric(alloc[qty_col_alloc], errors="coerce").fillna(0)
        before = len(alloc)
        alloc = alloc[alloc[qty_col_alloc] > 0].copy()
        print(f"       [Filter] Dropped {before - len(alloc)} zero-QTY rows from allocation. Remaining: {len(alloc)}")
    else:
        print("       [WARN] Could not detect QTY column — skipping zero-QTY filter.")

    if alloc.empty:
        raise ValueError(
            f"No rows found for {city} (checked cities: {satellite_cities}). "
            f"Verify the city column name and values in your FnV Excel."
        )

    # ── Normalise columns for FnV sheet format ────────────────────
    # FnV Excel columns: City, WH Code, WH Name, FSN, Title, Final PO
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
        alloc["Store ID"] = alloc["Warehouse"]  # fallback to WH Code

    # FnV has no Supplier ID — key is just the WH Code
    alloc["Supplier_ID"] = alloc["Supplier ID"].astype(str).str.strip() if "Supplier ID" in alloc.columns else ""
    
    store_id_col = alloc["Store ID"].astype(str).str.strip() if "Store ID" in alloc.columns else alloc["Warehouse"]
    store_id_col = store_id_col.replace(["", "NAN", "nan", "None"], pd.NA).fillna(alloc["Warehouse"])
    alloc["Key"] = (store_id_col + alloc["Supplier_ID"]).str.upper()

    # Sequential PO ID per unique Key
    unique_keys = list(dict.fromkeys(alloc["Key"].tolist()))
    key_to_poid = {k: f"{cfg['po_prefix']}{str(i+1).zfill(3)}" for i, k in enumerate(unique_keys)}
    alloc["PO_ID_generated"] = alloc["Key"].map(key_to_poid)

    # Build key reference table
    key_table = (
        alloc[["Key", "Warehouse", "Supplier_ID", "PO_ID_generated", "Store ID"]]
        .drop_duplicates("Key")
        .rename(columns={"PO_ID_generated": "PO ID", "Supplier_ID": "Supplier ID", "Store ID": "Store"})
    )

    # ── Step 2: Update FnV PO Tab & Load SO tab ──────────────────
    if gsheet_url:
        import time
        print(f"► [2/3] Updating '{po_sheet_name}' tab in Google Sheet...")

        # Determine QTY source column
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
            print("       [WARN] Could not find a QTY/Final PO column in FnV Excel!")

        # Determine Title source column
        if "Title" in alloc.columns:
            title_series = alloc["Title"]
        elif "FSN_Title" in alloc.columns:
            title_series = alloc["FSN_Title"]
        elif "NC Name" in alloc.columns:
            title_series = alloc["NC Name"]
        else:
            title_series = pd.Series("", index=alloc.index)

        cust_sheet = cfg.get("cust_sheet", "BLR FK Customers")
        
        # Fetch the customer sheet to get the FK Site Name mapping
        print(f"       Fetching '{cust_sheet}' to map FK Site Name...")
        try:
            cust_sh, _ = get_gsheet_client(gsheet_url)
            cust_ws = get_worksheet_flexible(cust_sh, cust_sheet)
            cust_data = cust_ws.get_all_values()
            
            if len(cust_data) > 1:
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
                        fk_site_map.update({str(k).strip().lower(): v for k, v in raw_map_1.items() if str(v).strip() not in ["", "nan", "None", "NAN"]})
                    if wh_name_col:
                        raw_map_2 = cust_df.set_index(wh_name_col)[fk_site_col].to_dict()
                        fk_site_map.update({str(k).strip().lower(): v for k, v in raw_map_2.items() if str(v).strip() not in ["", "nan", "None", "NAN"]})
            else:
                fk_site_map = {}
        except Exception as e:
            print(f"       [WARN] Failed to fetch customer sheet mapping: {e}")
            fk_site_map = {}

        _store_fallback = alloc["Store ID"].astype(str).str.strip() if "Store ID" in alloc.columns else alloc["Warehouse"]
        _store_fallback = _store_fallback.replace(["", "NAN", "nan", "None"], pd.NA).fillna(alloc["Warehouse"])
        _wh_code = alloc["Warehouse"].astype(str).str.strip()
        
        _mapped_store = _wh_code.str.lower().map(fk_site_map).replace(["", "nan", "None", "NAN"], pd.NA)
        _mapped_store = _mapped_store.fillna(_store_fallback.str.lower().map(fk_site_map).replace(["", "nan", "None", "NAN"], pd.NA))
        _mapped_store = _mapped_store.fillna(_store_fallback)
        
        # Build upload_df with index aligned to alloc, then filter zero-qty rows
        upload_df = pd.DataFrame({
            "FSN/ISBN13": alloc["FSN"] if "FSN" in alloc.columns else pd.Series("", index=alloc.index),
            "Title":      title_series,
            "QTY":        qty_series,
            "PO Number":  alloc["PO_ID_generated"],
            "Store":      _mapped_store,
        }, index=alloc.index)

        # Filter: only upload rows where QTY > 0 (skip 0-qty and blank rows upfront)
        upload_df["QTY_NUM"] = pd.to_numeric(upload_df["QTY"], errors="coerce").fillna(0)
        upload_df = upload_df[upload_df["QTY_NUM"] > 0].copy()
        upload_df.drop(columns=["QTY_NUM"], inplace=True)
        
        num_rows_uploaded = len(upload_df)
        print(f"       {num_rows_uploaded} rows to upload (including missing qty/po ids)")

        # Add VLOOKUP contact formula (row numbers reset after filter)
        upload_df = upload_df.reset_index(drop=True)
        upload_df["Contact"] = [f"=VLOOKUP(E{i},'{cust_sheet}'!F:G,2,0)" for i in range(2, len(upload_df) + 2)]

        update_gsheet_po_file(gsheet_url, po_sheet_name, upload_df)
        
        print("       Dragging formulas in SO tab...")
        drag_formulas_in_so(gsheet_url, so_sheet_name, num_rows_uploaded)

        print("       Waiting 5 seconds for Google Sheet formulas to evaluate...")
        time.sleep(5)

        print(f"       Fetching updated SO data from '{so_sheet_name}'...")
        so_df = load_gsheet_so(gsheet_url, so_sheet_name)
    else:
        raise ValueError("FnV automation requires a Google Sheet URL.")

    so_df.columns = so_df.columns.str.strip()
    
    # Normalize FSN and Title columns to standard names if they differ
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

    # Replace GSheet error values
    so_df.replace(["#N/A", "#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#NUM!", "#NULL!"], np.nan, inplace=True)

    # Filter blank QTY
    # We will NOT drop missing QTY here, because we want it to go to NA tab!
    
    print(f"       Total QTY after fetch (before NA separation): {pd.to_numeric(so_df.get('quantity(req)'), errors='coerce').sum()}")

    print("► [3/3] Separating valid and NA rows...")
    
    # Filter out rows if there is no FSN or no contact number (so they don't appear in NA tab)
    if "sku_id(req)" in so_df.columns and "customer_contact_number(req)" in so_df.columns:
        # Only drop rows where BOTH FSN and contact are blank (artifact rows from GSheet)
        is_completely_empty = (
            (so_df["sku_id(req)"].fillna("").astype(str).str.strip() == "") &
            (so_df["customer_contact_number(req)"].fillna("").astype(str).str.strip() == "")
        )
        so_df = so_df[~is_completely_empty].copy()

    # ── Early filter: drop rows with QTY = 0 or blank immediately ──
    if "quantity(req)" in so_df.columns:
        valid_qty_mask = pd.to_numeric(so_df["quantity(req)"], errors="coerce").fillna(0) > 0
        dropped_zero = (~valid_qty_mask).sum()
        if dropped_zero > 0:
            print(f"       [Filter] Dropped {dropped_zero} rows with zero/blank QTY before NA split.")
        so_df = so_df[valid_qty_mask].copy()

    fnv_check_cols = ["sku_id(req)", "Sales Price", "lot_id(req)", "customer_contact_number(req)", "purchaseOrder"]
    actual_check_cols = [c for c in fnv_check_cols if c in so_df.columns]
    
    if actual_check_cols:
        is_null = so_df[actual_check_cols].isnull().any(axis=1)
        stripped = so_df[actual_check_cols].fillna("").astype(str).apply(lambda x: x.str.strip())
        is_blank = (stripped == "").any(axis=1)
        is_na_str = stripped.isin(["NA", "#N/A", "nan", "None", "na", "#n/a"]).any(axis=1)
        is_na = is_null | is_blank | is_na_str
    else:
        is_na = pd.Series(False, index=so_df.index)
        
    # Also NA if QTY is invalid
    if "quantity(req)" in so_df.columns:
        is_invalid_qty = so_df["quantity(req)"].isna() | (pd.to_numeric(so_df["quantity(req)"], errors="coerce").fillna(0) <= 0)
        is_na = is_na | is_invalid_qty

    # Ensure date column is formatted correctly to dd-mm-yyyy
    if "delivery_date(DD-MM-YYY)" in so_df.columns:
        so_df["delivery_date(DD-MM-YYY)"] = pd.to_datetime(so_df["delivery_date(DD-MM-YYY)"], errors="coerce").dt.date
    if so_df["delivery_date(DD-MM-YYY)"].isna().all():
        from datetime import datetime
        so_df["delivery_date(DD-MM-YYY)"] = datetime.strptime(delivery_date, "%d-%m-%Y").date()

    # ── Output ───────────────────────────────────────────────────
    from datetime import datetime
    try:
        dt = datetime.strptime(delivery_date, "%d-%m-%Y")
        date_tag = dt.strftime("%B_%d")
    except:
        date_tag = delivery_date.replace("-", "")

    base_name = f"{city} FnV CUS SO {date_tag}"
    csv_path  = os.path.join(output_dir, f"{base_name}.csv")
    xlsx_path = os.path.join(output_dir, f"{base_name}_full.xlsx")
    po_path   = os.path.join(output_dir, f"{city} FnV PO Mapping {date_tag}.xlsx")

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

    df_valid = so_df[~is_na][fnv_cols].copy()
    
    # Format NA rows to be distinct and contain specific columns
    raw_df_na = so_df[is_na].copy()
    df_na = pd.DataFrame()
    if len(raw_df_na) > 0:
        fsn_col = next((c for c in ["sku_id(req)", "SKU ID", "sku_id", "FSN", "fsn"] if c in raw_df_na.columns and raw_df_na[c].notna().any()), "sku_id(req)")
        df_na["FSN"] = raw_df_na.get(fsn_col, pd.Series(dtype=str)).fillna("NA").replace("", "NA")
        
        title_col = next((c for c in ["NC NAME", "NC Name", "Title", "title"] if c in raw_df_na.columns and raw_df_na[c].notna().any()), "NC NAME")
        df_na["Title"] = raw_df_na.get(title_col, pd.Series(dtype=str)).fillna("NA").replace("", "NA")
        
        df_na["Price"] = raw_df_na.get("Sales Price", pd.Series(dtype=str)).fillna("NA")
        df_na["QTY"] = raw_df_na.get("quantity(req)", pd.Series(dtype=str)).fillna("NA")
        
        df_na = df_na.drop_duplicates()

        # ── Pass 1: Fill missing Title from Allocation file (already in memory) ──
        alloc_fsn_col = "FSN" if "FSN" in alloc.columns else None
        alloc_title_col = next(
            (c for c in ["FSN_Title", "Title", "NC Name", "NC NAME"] if c in alloc.columns), None
        )
        if alloc_fsn_col and alloc_title_col:
            alloc_title_map = (
                alloc[[alloc_fsn_col, alloc_title_col]]
                .dropna(subset=[alloc_fsn_col])
                .drop_duplicates(subset=[alloc_fsn_col])
                .set_index(alloc_fsn_col)[alloc_title_col]
                .to_dict()
            )
            def _fill_title_from_alloc_fnv(row):
                if str(row["Title"]).strip() in ("", "NA", "#N/A"):
                    return alloc_title_map.get(str(row["FSN"]).strip(), row["Title"])
                return row["Title"]
            df_na["Title"] = df_na.apply(_fill_title_from_alloc_fnv, axis=1)
            filled = (df_na["Title"].astype(str).str.strip() != "NA").sum()
            print(f"       [Alloc] Filled Title for {filled} NA rows from Allocation file.")

        # ── Pass 2: Fetch missing Price from DB using SKU Name ──────────
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
                    def _fill_price_from_db_fnv(row):
                        if str(row["Price"]).strip() in ("", "NA", "#N/A", "nan", "None", "0", "0.0"):
                            key = str(row["Title"]).strip().lower()
                            return price_map.get(key, row["Price"])
                        return row["Price"]
                    df_na["Price"] = df_na.apply(_fill_price_from_db_fnv, axis=1)
            except Exception as db_err:
                print(f"       [DB WARN] Could not fetch price from DB: {db_err}")

        # ── Pass 2.5: Fetch missing Contact from DB using NC Name OR Store Site ID ────────
        if "customer_contact_number(req)" in raw_df_na.columns:
            need_contact_mask = raw_df_na["customer_contact_number(req)"].astype(str).str.strip().isin(["", "NA", "#N/A", "nan", "None"])
            
            # Map purchaseOrder to the original Store Site ID from alloc
            if "purchaseOrder" in raw_df_na.columns and "PO_ID_generated" in alloc.columns:
                store_col = next((c for c in alloc.columns if str(c).strip().lower() in ["store site id", "fk site id"]), None)
                if not store_col:
                    store_col = "Store ID" if "Store ID" in alloc.columns else "Warehouse"
                po_to_store = alloc.set_index("PO_ID_generated")[store_col].to_dict()
                raw_df_na["_fallback_store_id"] = raw_df_na["purchaseOrder"].map(po_to_store)
            else:
                raw_df_na["_fallback_store_id"] = ""

            names_to_fetch = set()
            for idx, row in raw_df_na[need_contact_mask].iterrows():
                nc_name = str(row.get("NC Name", "")).strip()
                fallback = str(row.get("_fallback_store_id", "")).strip()
                if nc_name and nc_name not in ["", "NA", "#N/A", "nan", "None"]:
                    names_to_fetch.add(nc_name)
                if fallback and fallback not in ["", "NA", "#N/A", "nan", "None"]:
                    names_to_fetch.add(fallback)

            names_for_db_contact = list(names_to_fetch)
            
            if names_for_db_contact:
                try:
                    import db_lookup
                    contact_map = db_lookup.fetch_contact_by_name(names_for_db_contact, city)
                    if contact_map:
                        def _fill_contact_from_db(row):
                            if str(row.get("customer_contact_number(req)", "")).strip() in ("", "NA", "#N/A", "nan", "None"):
                                nc_key = str(row.get("NC Name", "")).strip().lower()
                                fb_key = str(row.get("_fallback_store_id", "")).strip().lower()
                                if nc_key in contact_map:
                                    return contact_map[nc_key]
                                if fb_key in contact_map:
                                    return contact_map[fb_key]
                            return row.get("customer_contact_number(req)")
                        raw_df_na["customer_contact_number(req)"] = raw_df_na.apply(_fill_contact_from_db, axis=1)
                        if "Contact" in df_na.columns:
                            df_na["Contact"] = raw_df_na["customer_contact_number(req)"].values
                            df_na["Contact"] = df_na["Contact"].replace(["", "nan", "None", "#N/A"], "Missing").fillna("Missing")
                except Exception as db_err:
                    print(f"       [DB WARN] Could not fetch contact from DB: {db_err}")

        # ── Pass 3: Re-evaluate NA rows after enrichment ────────────────
        enriched_price_df_fnv = df_na[~df_na["Price"].astype(str).str.strip().isin(["", "NA", "#N/A", "nan", "None", "0", "0.0"])]
        if len(enriched_price_df_fnv) > 0:
            fsn_to_enriched_price_fnv = enriched_price_df_fnv.set_index("FSN")["Price"].to_dict()
            raw_df_na["Sales Price"] = raw_df_na.apply(
                lambda r: fsn_to_enriched_price_fnv.get(str(r.get("sku_id(req)", "")).strip(), r.get("Sales Price", np.nan)),
                axis=1
            )

        fnv_recheck_cols = [c for c in ["sku_id(req)", "Sales Price", "lot_id(req)", "customer_contact_number(req)", "purchaseOrder"] if c in raw_df_na.columns]
        if fnv_recheck_cols:
            is_null_rc_fnv  = raw_df_na[fnv_recheck_cols].isnull().any(axis=1)
            stripped_rc_fnv = raw_df_na[fnv_recheck_cols].fillna("").astype(str).apply(lambda x: x.str.strip())
            is_blank_rc_fnv = (stripped_rc_fnv == "").any(axis=1)
            is_na_str_rc_fnv= stripped_rc_fnv.isin(["NA", "#N/A", "nan", "None", "na", "#n/a"]).any(axis=1)
            is_na_rc_fnv    = is_null_rc_fnv | is_blank_rc_fnv | is_na_str_rc_fnv
        else:
            is_na_rc_fnv = pd.Series(False, index=raw_df_na.index)
            
        if "quantity(req)" in raw_df_na.columns:
            is_na_rc_fnv = is_na_rc_fnv | (raw_df_na["quantity(req)"].isna() | (pd.to_numeric(raw_df_na["quantity(req)"], errors="coerce").fillna(0) <= 0))

        newly_valid_fnv = raw_df_na[~is_na_rc_fnv][fnv_cols].copy()
        if len(newly_valid_fnv) > 0:
            df_valid = pd.concat([df_valid, newly_valid_fnv], ignore_index=True)
            print(f"       ✅ {len(newly_valid_fnv)} rows promoted: NA → Valid SO after DB enrichment.")

        raw_df_na = raw_df_na[is_na_rc_fnv].copy()
        df_na = pd.DataFrame()
        if len(raw_df_na) > 0:
            df_na["FSN"]   = raw_df_na.get("sku_id(req)", pd.Series(dtype=str)).fillna("NA")
            t_rc_fnv       = raw_df_na.get("Title") if "Title" in raw_df_na.columns else raw_df_na.get("NC NAME", pd.Series(dtype=str))
            df_na["Title"] = t_rc_fnv.fillna("NA").replace("", "NA")
            df_na["Price"] = raw_df_na.get("Sales Price", pd.Series(dtype=str)).fillna("NA")
            df_na["QTY"] = raw_df_na.get("quantity(req)", pd.Series(dtype=str)).fillna("NA")
            df_na = df_na.drop_duplicates(subset=["FSN"])

    print(f"       ✓ Valid rows : {len(df_valid)}")
    print(f"       ✗ NA rows    : {len(df_na)} (distinct)")
    print(f"       ✓ Valid QTY  : {pd.to_numeric(df_valid.get('quantity(req)'), errors='coerce').sum()}")
    print(f"       ✗ NA QTY     : {pd.to_numeric(raw_df_na.get('quantity(req)'), errors='coerce').sum()}")

    df_valid.to_csv(csv_path, index=False)

    with pd.ExcelWriter(xlsx_path, engine="openpyxl", datetime_format="DD-MM-YYYY", date_format="DD-MM-YYYY") as writer:
        df_valid.to_excel(writer, sheet_name="SO Output", index=False)
        if len(df_na) > 0:
            df_na.to_excel(writer, sheet_name="NA Rows", index=False)
        else:
            pd.DataFrame({"Message": ["No NA rows found"]}).to_excel(writer, sheet_name="NA Rows", index=False)

    key_table.to_excel(po_path, index=False)

    print(f"\n  ✅ CSV saved      → {csv_path}")
    print(f"  ✅ Excel saved    → {xlsx_path}")
    print(f"  ✅ PO Map saved   → {po_path}\n")

    return csv_path, xlsx_path, po_path, len(df_valid), len(df_na), len(so_df), len(unique_keys)


# ── CLI Entry point ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="E-com SO Automation Tool")
    parser.add_argument("--allocation", required=True, help="Allocation Excel path")
    parser.add_argument("--ecom",       required=False, default=None, help="E_COM_SO_Placement.xlsx path (if not using G-sheet)")
    parser.add_argument("--gsheet",     required=False, default=None, help="Public Google Sheet URL (preferred)")
    parser.add_argument("--city",       required=True, choices=list(CITY_CONFIG.keys()))
    parser.add_argument("--date",       required=True, help="Delivery date e.g. 01-07-2026")
    parser.add_argument("--out",        default=".", help="Output directory")
    args = parser.parse_args()

    if not args.ecom and not args.gsheet:
        parser.error("Provide either --ecom (local file) or --gsheet (Google Sheet URL)")

    run_automation(
        allocation_path=args.allocation,
        ecom_path=args.ecom,
        city=args.city,
        delivery_date=args.date,
        output_dir=args.out,
        gsheet_url=args.gsheet,
    )
