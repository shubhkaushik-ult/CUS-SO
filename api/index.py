import sys
import os

try:
    from dotenv import load_dotenv
    _root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(_root_env):
        load_dotenv(_root_env)
    else:
        load_dotenv()
except ImportError:
    # Lightweight fallback if python-dotenv is not installed yet
    _root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(_root_env):
        with open(_root_env, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k = _k.strip()
                    _v = _v.strip().strip("'\"")
                    if _k not in os.environ:
                        os.environ[_k] = _v

# Allow importing from root directory when running inside api/ folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

po_dir = r"d:\PO"
if po_dir not in sys.path:
    sys.path.append(po_dir)

from flask import Flask, render_template, request, send_file, jsonify, send_from_directory
import tempfile
import uuid
from werkzeug.utils import secure_filename
import pandas as pd
from automation_script import run_automation
from fnv_automation import process_all_fnv_cities
try:
    from generate_brand_po import process_brand_po
except ImportError:
    process_brand_po = None

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

GENERATED_FILES = {}

@app.route('/')
def index():
    return render_template('index.html')


import base64
import json

RUNS_META_DIR = os.path.join(tempfile.gettempdir(), 'cus_so_meta')
try:
    os.makedirs(RUNS_META_DIR, exist_ok=True)
except Exception:
    pass

def _save_run_meta(run_id, meta):
    GENERATED_FILES[run_id] = meta
    try:
        fpath = os.path.join(RUNS_META_DIR, f"{run_id}.json")
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(meta, f)
    except Exception as e:
        print(f"[WARN] Failed to save run meta to disk: {e}")

def _load_run_meta(run_id):
    if run_id in GENERATED_FILES:
        return GENERATED_FILES[run_id]
    try:
        fpath = os.path.join(RUNS_META_DIR, f"{run_id}.json")
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                meta = json.load(f)
                GENERATED_FILES[run_id] = meta
                return meta
    except Exception as e:
        print(f"[WARN] Failed to load run meta from disk: {e}")
    return None

def _file_to_b64(filepath):
    if not filepath or not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception:
        return None

@app.route('/download_path')
def download_path():
    path_b64 = request.args.get('path')
    if not path_b64:
        return "No path provided", 400
    try:
        file_path = base64.b64decode(path_b64).decode('utf-8')
    except Exception:
        return "Invalid path", 400
        
    if not os.path.exists(file_path):
        return "File not found on disk", 404
        
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    return send_from_directory(directory, filename, as_attachment=True)


@app.route('/download/<run_id>/<file_type>')
def download_file(run_id, file_type):
    meta = _load_run_meta(run_id)
    if not meta or file_type not in meta:
        return "File not found", 404
        
    file_path = meta[file_type]
    if not file_path or not os.path.exists(file_path):
        return "File not found on disk", 404
        
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/download/<run_id>/fnv/<city>/<file_type>')
def download_city_file(run_id, city, file_type):
    meta = _load_run_meta(run_id)
    if not meta or 'city_stats' not in meta:
        return "Run not found", 404
    
    city_stats = meta['city_stats']
    if city not in city_stats:
        return "City not found", 404
        
    path_key = f"{file_type}_path"
    if path_key not in city_stats[city] or not city_stats[city][path_key]:
        return "File not found", 404
        
    file_path = city_stats[city][path_key]
    if not file_path or not os.path.exists(file_path):
        return "File not found on disk", 404
        
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/detect-city', methods=['POST'])
def detect_city():
    alloc_file = request.files.get('file')
    if not alloc_file:
        return jsonify({'error': 'No file'}), 400
        
    filename = alloc_file.filename.lower()
    city = None
    
    if 'blr' in filename or 'bangalore' in filename or 'bengaluru' in filename: city = 'Bangalore'
    elif 'chn' in filename or 'chennai' in filename: city = 'Chennai'
    elif 'mum' in filename or 'mumbai' in filename: city = 'Mumbai'
    elif 'hyd' in filename or 'hyderabad' in filename: city = 'Hyderabad'
    elif 'try' in filename or 'trichy' in filename: city = 'Trichy'
    elif 'cbe' in filename or 'coimbatore' in filename: city = 'Coimbatore'
        
    if not city:
        try:
            df = pd.read_excel(alloc_file, nrows=10)
            city_cols = [c for c in df.columns if 'city' in str(c).lower()]
            if city_cols:
                first_city = str(df[city_cols[0]].dropna().iloc[0]).lower()
                if 'blr' in first_city or 'bangal' in first_city or 'bengal' in first_city: city = 'Bangalore'
                elif 'che' in first_city or 'chn' in first_city: city = 'Chennai'
                elif 'mum' in first_city: city = 'Mumbai'
                elif 'hyd' in first_city: city = 'Hyderabad'
                elif 'tri' in first_city or 'try' in first_city: city = 'Trichy'
                elif 'coim' in first_city or 'cbe' in first_city: city = 'Coimbatore'
        except:
            pass

    return jsonify({'city': city})

@app.route('/process', methods=['POST'])
def process():
    try:
        city = request.form.get('city')
        delivery_date_raw = request.form.get('date')
        if not city or not delivery_date_raw:
            return jsonify({'error': 'City and Delivery Date are required'}), 400

        # Automatically set delivery date to today + 1 day
        from datetime import datetime, timedelta
        delivery_date = (datetime.today() + timedelta(days=1)).strftime("%d-%m-%Y")

        alloc_file = request.files.get('allocation_file')
        if not alloc_file:
            return jsonify({'error': 'Allocation file is required'}), 400
        
        alloc_filename = secure_filename(alloc_file.filename)
        alloc_path = os.path.join(app.config['UPLOAD_FOLDER'], alloc_filename)
        alloc_file.save(alloc_path)

        gsheet_url = request.form.get('gsheet_url', '').strip() or None

        so_sheet = request.form.get('so_sheet')
        po_sheet = request.form.get('po_sheet')

        output_dir = tempfile.mkdtemp()

        csv_path, inst_csv_path, xlsx_path, po_path, valid_len, na_len, total_so, po_generated = run_automation(
            allocation_path=alloc_path,
            ecom_path=None,
            city=city,
            delivery_date=delivery_date,
            output_dir=output_dir,
            gsheet_url=gsheet_url,
            so_sheet_override=so_sheet,
            po_sheet_override=po_sheet
        )

        run_id = str(uuid.uuid4())
        _save_run_meta(run_id, {
            'csv': csv_path,
            'inst_csv': inst_csv_path,
            'xlsx': xlsx_path,
            'po': po_path
        })


        return jsonify({
            'success': True,
            'run_id': run_id,
            'stats': {
                'total': total_so,
                'valid': valid_len,
                'na': na_len,
                'po': po_generated
            },
            'csv_path': csv_path,
            'csv_b64': _file_to_b64(csv_path),
            'inst_csv_path': inst_csv_path,
            'inst_csv_b64': _file_to_b64(inst_csv_path),
            'xlsx_path': xlsx_path,
            'xlsx_b64': _file_to_b64(xlsx_path),
            'po_path': po_path,
            'po_b64': _file_to_b64(po_path)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/process_fnv', methods=['POST'])
def process_fnv():
    try:
        from datetime import datetime, timedelta
        
        # Check if user provided a date from the frontend
        delivery_date_raw = request.form.get('date')
        if delivery_date_raw:
            try:
                dt = datetime.strptime(delivery_date_raw, "%Y-%m-%d")
                delivery_date = dt.strftime("%d-%m-%Y")
            except ValueError:
                delivery_date = (datetime.today() + timedelta(days=1)).strftime("%d-%m-%Y")
        else:
            delivery_date = (datetime.today() + timedelta(days=1)).strftime("%d-%m-%Y")

        alloc_file = request.files.get('allocation_file') or request.files.get('fnv_file')
        if not alloc_file:
            return jsonify({'error': 'Allocation file is required'}), 400
        
        alloc_filename = secure_filename(alloc_file.filename)
        alloc_path = os.path.join(app.config['UPLOAD_FOLDER'], alloc_filename)
        alloc_file.save(alloc_path)

        prev_alloc_file = request.files.get('fnv_prev_file')
        prev_alloc_path = None
        if prev_alloc_file:
            prev_filename = secure_filename(prev_alloc_file.filename)
            prev_alloc_path = os.path.join(app.config['UPLOAD_FOLDER'], f"prev_{prev_filename}")
            prev_alloc_file.save(prev_alloc_path)

        gsheet_url = request.form.get('gsheet_url', '').strip() or None

        output_dir = tempfile.mkdtemp()

        city_stats, grand_totals, zip_path = process_all_fnv_cities(
            allocation_path=alloc_path,
            delivery_date=delivery_date,
            output_dir=output_dir,
            gsheet_url=gsheet_url,
            prev_allocation_path=prev_alloc_path
        )


        run_id = str(uuid.uuid4())
        
        for city, stats in city_stats.items():
            stats['csv_b64'] = _file_to_b64(stats.get('csv_path'))
            stats['inst_csv_b64'] = _file_to_b64(stats.get('inst_csv_path'))
            stats['xlsx_b64'] = _file_to_b64(stats.get('xlsx_path'))

        _save_run_meta(run_id, {
            'zip': zip_path,
            'city_stats': city_stats
        })

        return jsonify({
            'success': True,
            'run_id': run_id,
            'stats': grand_totals,
            'city_stats': city_stats,
            'zip_path': zip_path,
            'zip_b64': _file_to_b64(zip_path)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/process_brand_po', methods=['POST'])
def process_brand_po_route():
    try:
        if process_brand_po is None:
            return jsonify({'error': 'generate_brand_po module could not be imported.'}), 500

        city = request.form.get('city', 'MUM')
        selected_date = request.form.get('date', '')
        if not selected_date:
            from datetime import datetime
            selected_date = datetime.now().strftime("%Y-%m-%d")

        exclude_direct = request.form.get('exclude_direct', 'false').lower() == 'true'
        output_dir = tempfile.mkdtemp()

        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        possible_cred_paths = [
            os.path.join(root_dir, "xd-allocation-9640b0ce66d2.json"),
            os.path.join(os.getcwd(), "xd-allocation-9640b0ce66d2.json"),
            "xd-allocation-9640b0ce66d2.json",
            r"d:\PO\xd-allocation-9640b0ce66d2.json"
        ]
        credentials_path = next((p for p in possible_cred_paths if os.path.exists(p)), None)

        res = process_brand_po(
            city_code=city,
            selected_date=selected_date,
            credentials_path=credentials_path,
            exclude_direct_vendors=exclude_direct,
            output_dir=output_dir,
            wait_time_sec=8
        )

        all_results_simplified = []
        if "all_results" in res and res["all_results"]:
            for r in res["all_results"]:
                out_p = r.get('output_path')
                aud_p = r.get('audit_path')
                na_p = r.get('na_missing_path')
                all_results_simplified.append({
                    'city': r.get('city'),
                    'total_skus': r.get('total_skus', 0),
                    'indent_total_qty': r.get('indent_total_qty', 0),
                    'total_qty': r.get('total_qty', 0),
                    'indent_diff_qty': r.get('indent_diff_qty', 0),
                    'total_val': r.get('total_val', 0),
                    'na_count': r.get('na_count', 0),
                    'na_qty': r.get('na_qty', 0),
                    'na_missing_path': na_p,
                    'na_missing_b64': _file_to_b64(na_p),
                    'na_missing_filename': os.path.basename(na_p) if na_p else None,
                    'discrepancies_count': r.get('discrepancies_count', 0),
                    'qty_discrepancies_count': r.get('qty_discrepancies_count', 0),
                    'output_path': out_p,
                    'output_b64': _file_to_b64(out_p),
                    'output_filename': os.path.basename(out_p) if out_p else None,
                    'audit_path': aud_p,
                    'audit_b64': _file_to_b64(aud_p),
                    'audit_filename': os.path.basename(aud_p) if aud_p else None,
                    'vendor_count': r.get('vendor_count', 0),
                    'date_breakdown_detail': r.get('date_breakdown_detail', {}),
                    'date_vendor_breakdown': r.get('date_vendor_breakdown', {})
                })

        main_out = res.get('output_path')
        main_aud = res.get('audit_path')
        main_na = res.get('na_missing_path')

        return jsonify({
            'success': True,
            'output_path': main_out,
            'output_b64': _file_to_b64(main_out),
            'output_filename': os.path.basename(main_out) if main_out else None,
            'audit_path': main_aud,
            'audit_b64': _file_to_b64(main_aud),
            'audit_filename': os.path.basename(main_aud) if main_aud else None,
            'na_missing_path': main_na,
            'na_missing_b64': _file_to_b64(main_na),
            'na_missing_filename': os.path.basename(main_na) if main_na else None,
            'stats': {
                'total_skus': res.get('total_skus', 0),
                'indent_total_qty': res.get('indent_total_qty', 0),
                'total_qty': res.get('total_qty', 0),
                'indent_diff_qty': res.get('indent_diff_qty', 0),
                'total_val': res.get('total_val', 0),
                'discrepancies': res.get('discrepancies_count', 0),
                'qty_discrepancies': res.get('qty_discrepancies_count', 0),
                'na_count': res.get('na_count', 0),
                'na_qty': res.get('na_qty', 0),
                'vendor_count': res.get('vendor_count', 0),
            },
            'date_breakdown': res.get('date_breakdown_detail', {}),
            'all_results': all_results_simplified
        })


    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
#  REST API  v1  — /api/v1/
#  Every response includes a  so_type  field so the consumer always knows
#  exactly which Sales Order type they are working with:
#
#    so_type = "GRO_SO"    → Grocery Sales Order  (Standard 16-col / Institutional 15-col)
#    so_type = "FNV_SO"    → Fruits & Vegetables Sales Order  (multi-city)
#    so_type = "BRAND_PO"  → Brand Purchase Order (vendor-wise PO generation)
#
#  Route map:
#    GET  /api/v1                         → API discovery
#    GET  /api/v1/so/types                → Explains the 3 SO types
#    GET  /api/v1/so/headers              → Headers for GRO_SO or FNV_SO formats
#    POST /api/v1/gro/process             → Process GRO Grocery SO       [so_type = GRO_SO]
#    POST /api/v1/so/process              → Alias for /api/v1/gro/process (backward compat)
#    POST /api/v1/fnv/process             → Process FnV multi-city SO    [so_type = FNV_SO]
#    POST /api/v1/brand-po/process        → Process Brand PO             [so_type = BRAND_PO]
#    GET  /api/v1/result/<run_id>         → Re-fetch cached run
# ═══════════════════════════════════════════════════════════════════════════════

# ── Column header definitions ─────────────────────────────────────────────────

_STANDARD_HEADERS = [
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

_INSTITUTIONAL_HEADERS = [
    "customer_contact_number(req)",
    "sku_id(req)",
    "NC NAME",
    "quantity(req)",
    "delivery_date(DD-MM-YYYY)",
    "lot_id(req)",
    "ordering_mode(optional)",
    "cancelled(optional)",
    "purchaseOrder",
    "Sales Price",
    "DELIVERY_CHARGE(opt)",
    "sale_order_id(optional)",
    "sub_type(optional)",
    "skuTypeId",
    "CustomerId",
]

_BRAND_PO_HEADERS = [
    "vendor_name",
    "sku_name",
    "fsn",
    "quantity",
    "unit_price",
    "total_value",
    "city",
    "delivery_date",
    "purchase_order_id",
    "indent_qty",
    "indent_diff_qty",
]

# so_type label constants
_SO_TYPE_GRO      = "GRO_SO"
_SO_TYPE_FNV      = "FNV_SO"
_SO_TYPE_BRAND_PO = "BRAND_PO"

# In-memory REST result cache: run_id → result dict
_REST_CACHE = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _csv_to_items(csv_path):
    """Read a generated SO CSV and return list of row dicts."""
    if not csv_path or not os.path.exists(csv_path):
        return []
    try:
        df = pd.read_csv(csv_path, dtype=str).fillna("")
        return df.to_dict(orient="records")
    except Exception:
        return []


def _api_error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def _resolve_format(fmt_str):
    """Return (header_list, format_label) from a format query string."""
    if fmt_str and fmt_str.lower() == "institutional":
        return _INSTITUTIONAL_HEADERS, "institutional"
    return _STANDARD_HEADERS, "standard"


def _parse_date(date_raw):
    """Parse date string (YYYY-MM-DD or DD-MM-YYYY) → DD-MM-YYYY, defaults to tomorrow."""
    from datetime import datetime, timedelta
    if date_raw:
        for pat in ("%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(date_raw, pat).strftime("%d-%m-%Y")
            except (ValueError, TypeError):
                pass
    return (datetime.today() + timedelta(days=1)).strftime("%d-%m-%Y")


# ── GET /api/v1 — Discovery ───────────────────────────────────────────────────

@app.route("/api/v1", methods=["GET"])
def api_v1_index():
    """
    Self-documenting API discovery endpoint.
    Lists all routes, SO types, supported cities and output formats.
    """
    return jsonify({
        "name":    "CUS SO REST API",
        "version": "1.0",
        "description": (
            "Sales Order automation API. Every response includes a 'so_type' field "
            "that identifies whether the data is GRO_SO, FNV_SO, or BRAND_PO."
        ),
        "so_types": {
            "GRO_SO":   "Grocery Sales Order — single city, Standard (16-col) or Institutional (15-col) format",
            "FNV_SO":   "Fruits & Vegetables Sales Order — multi-city processing, per-city breakdown",
            "BRAND_PO": "Brand Purchase Order — vendor-wise PO generation with audit and NA rows"
        },
        "supported_cities": [
            "Bangalore", "Chennai", "Mumbai",
            "Hyderabad", "Trichy", "Coimbatore", "Nashik"
        ],
        "output_formats": {
            "standard":      "16-column GRO SO CSV format",
            "institutional": "15-column Institutional SO CSV format"
        },
        "endpoints": [
            {
                "method":      "GET",
                "path":        "/api/v1/so/types",
                "description": "Returns detailed explanation of all 3 SO types with field descriptions.",
                "example":     "/api/v1/so/types"
            },
            {
                "method":      "GET",
                "path":        "/api/v1/so/headers",
                "so_type":     "GRO_SO / FNV_SO",
                "description": "Returns ordered column headers for standard or institutional SO format.",
                "query_params": {"format": "standard (default) | institutional"},
                "example":     "/api/v1/so/headers?format=institutional"
            },
            {
                "method":      "POST",
                "path":        "/api/v1/gro/process",
                "so_type":     "GRO_SO",
                "description": "Upload a Grocery allocation file and receive SO headers + line items as JSON.",
                "body_type":   "multipart/form-data",
                "fields": {
                    "allocation_file": "(required) .xlsx/.xls/.csv Grocery allocation file",
                    "city":            "(required) City name — Bangalore | Chennai | Mumbai | ...",
                    "date":            "(optional) Delivery date YYYY-MM-DD or DD-MM-YYYY. Default: tomorrow.",
                    "format":          "(optional) standard | institutional. Default: standard.",
                    "gsheet_url":      "(optional) Override the Google Sheet URL."
                }
            },
            {
                "method":      "POST",
                "path":        "/api/v1/fnv/process",
                "so_type":     "FNV_SO",
                "description": "Upload an FnV allocation file and receive per-city SO headers + items.",
                "body_type":   "multipart/form-data",
                "fields": {
                    "allocation_file": "(required) FnV .xlsx allocation file (all cities in one sheet)",
                    "date":            "(optional) Delivery date. Default: tomorrow.",
                    "format":          "(optional) standard | institutional. Default: standard.",
                    "gsheet_url":      "(optional) Override the Google Sheet URL.",
                    "fnv_prev_file":   "(optional) Previous FnV allocation for delta comparison."
                }
            },
            {
                "method":      "POST",
                "path":        "/api/v1/brand-po/process",
                "so_type":     "BRAND_PO",
                "description": "Generate Brand Purchase Orders for a city and date. Returns vendor PO lines + audit rows.",
                "body_type":   "multipart/form-data",
                "fields": {
                    "city":           "(required) City code — MUM | BLR | CHN | HYD | TRICHY | CBE | ALL",
                    "date":           "(required) PO date YYYY-MM-DD.",
                    "exclude_direct": "(optional) true | false — exclude direct vendors. Default: false."
                }
            },
            {
                "method":      "GET",
                "path":        "/api/v1/result/<run_id>",
                "description": "Re-fetch any cached run result by run_id. Works for all 3 SO types.",
                "query_params": {
                    "format": "standard (default) | institutional  (only applies to GRO_SO and FNV_SO)"
                },
                "example":     "/api/v1/result/abc-123?format=institutional"
            }
        ]
    })


# ── GET /api/v1/so/types — Detailed SO type reference ────────────────────────

@app.route("/api/v1/so/types", methods=["GET"])
def api_so_types():
    """
    Returns a detailed explanation of all 3 SO types, their use cases,
    output column headers, and which endpoint to call.
    """
    return jsonify({
        "so_types": [
            {
                "so_type":     _SO_TYPE_GRO,
                "name":        "Grocery Sales Order",
                "description": (
                    "Single-city daily SO for Grocery (GRO) category. "
                    "Processes one city at a time from a store/vendor allocation file. "
                    "Supports both Standard (16-col) and Institutional (15-col) CSV output formats."
                ),
                "endpoint":    "POST /api/v1/gro/process",
                "scope":       "Single city per request",
                "output_formats": {
                    "standard":      {
                        "columns": 16,
                        "use_when": "Uploading to GRO SO sheet via standard pipeline",
                        "key_fields": ["NC ID", "NC Name", "lot weight ID", "CITY_ID(req)", "grocerFlow"]
                    },
                    "institutional": {
                        "columns": 15,
                        "use_when": "Uploading to Institutional SO API pipeline",
                        "key_fields": ["sku_id(req)", "lot_id(req)", "skuTypeId", "CustomerId"]
                    }
                },
                "example_cities": ["Bangalore", "Chennai", "Mumbai", "Hyderabad", "Trichy", "Coimbatore", "Nashik"]
            },
            {
                "so_type":     _SO_TYPE_FNV,
                "name":        "Fruits & Vegetables Sales Order",
                "description": (
                    "Multi-city FnV SO processed in a single run using a combined allocation file. "
                    "Uses a two-phase optimized engine: writes to all city PO tabs in parallel, "
                    "waits for Google Sheets formula evaluation, then reads all SO tabs. "
                    "Response contains a per-city breakdown."
                ),
                "endpoint":    "POST /api/v1/fnv/process",
                "scope":       "All cities in one request (Bangalore, Chennai, Mumbai, Hyderabad, Trichy, Coimbatore, Nashik)",
                "satellite_cities": {
                    "Bangalore":  ["Bangalore", "Bengaluru", "Hosur", "Mandya", "Mysore", "Tumkur"],
                    "Coimbatore": ["Coimbatore", "Erode", "Palakkad", "Salem", "Tirupur"]
                },
                "output_formats": {
                    "standard":      {"columns": 16},
                    "institutional": {"columns": 15}
                }
            },
            {
                "so_type":     _SO_TYPE_BRAND_PO,
                "name":        "Brand Purchase Order",
                "description": (
                    "Generates vendor-wise Brand POs by merging indent plans with costing sheets "
                    "from Google Sheets. Produces a PO output file, a discrepancy audit report, "
                    "and an NA/missing SKU report."
                ),
                "endpoint":    "POST /api/v1/brand-po/process",
                "scope":       "Single city code or ALL",
                "city_codes":  ["MUM", "BLR", "CHN", "HYD", "TRICHY", "CBE", "ALL"],
                "output_fields": [
                    "vendor_name", "sku_name", "fsn", "quantity",
                    "unit_price", "total_value", "city", "delivery_date",
                    "purchase_order_id", "indent_qty", "indent_diff_qty"
                ],
                "extra_outputs": ["audit_rows (discrepancies)", "na_rows (missing SKUs)"]
            }
        ]
    })


# ── GET /api/v1/so/headers ────────────────────────────────────────────────────

@app.route("/api/v1/so/headers", methods=["GET"])
def api_so_headers():
    """
    Return ordered column headers for the given SO format.
    Applies to both GRO_SO and FNV_SO — they share the same column layout.

    Query params:
        format  standard (default) | institutional
    """
    fmt_str = request.args.get("format", "standard")
    headers, fmt_label = _resolve_format(fmt_str)
    return jsonify({
        "success":      True,
        "so_type":      f"{_SO_TYPE_GRO} / {_SO_TYPE_FNV}",
        "format":       fmt_label,
        "column_count": len(headers),
        "headers":      headers
    })


# ── POST /api/v1/gro/process  (+ alias: /api/v1/so/process) ──────────────────

def _handle_gro_process():
    """
    Shared handler for GRO SO processing.
    Called by both /api/v1/gro/process and /api/v1/so/process (backward compat alias).

    so_type = GRO_SO
    """
    city       = (request.form.get("city") or "").strip()
    fmt_str    = (request.form.get("format") or "standard").strip()
    date_raw   = (request.form.get("date") or "").strip()
    gsheet_url = request.form.get("gsheet_url", "").strip() or None
    so_sheet   = request.form.get("so_sheet") or None
    po_sheet   = request.form.get("po_sheet") or None

    if not city:
        return _api_error("'city' is required.")

    alloc_file = request.files.get("allocation_file")
    if not alloc_file:
        return _api_error("'allocation_file' is required.")

    delivery_date  = _parse_date(date_raw)
    alloc_filename = secure_filename(alloc_file.filename)
    alloc_path     = os.path.join(app.config["UPLOAD_FOLDER"], alloc_filename)
    alloc_file.save(alloc_path)

    try:
        output_dir = tempfile.mkdtemp()
        (csv_path, inst_csv_path, xlsx_path, po_path,
         valid_len, na_len, total_so, po_generated) = run_automation(
            allocation_path=alloc_path,
            ecom_path=None,
            city=city,
            delivery_date=delivery_date,
            output_dir=output_dir,
            gsheet_url=gsheet_url,
            so_sheet_override=so_sheet,
            po_sheet_override=po_sheet,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return _api_error(str(e), 500)

    headers, fmt_label = _resolve_format(fmt_str)
    items_path = inst_csv_path if fmt_label == "institutional" else csv_path
    items      = _csv_to_items(items_path)
    run_id     = str(uuid.uuid4())

    stats = {
        "total_rows":   total_so,
        "valid_rows":   valid_len,
        "na_rows":      na_len,
        "po_generated": po_generated,
    }

    _REST_CACHE[run_id] = {
        "so_type":       _SO_TYPE_GRO,
        "city":          city,
        "date":          delivery_date,
        "csv_path":      csv_path,
        "inst_csv_path": inst_csv_path,
        "stats":         stats,
    }
    GENERATED_FILES[run_id] = {
        "csv": csv_path, "inst_csv": inst_csv_path,
        "xlsx": xlsx_path, "po": po_path,
    }

    return jsonify({
        "success": True,
        "so_type": _SO_TYPE_GRO,
        "run_id":  run_id,
        "city":    city,
        "date":    delivery_date,
        "format":  fmt_label,
        "headers": headers,
        "stats":   stats,
        "items":   items,
    })


@app.route("/api/v1/gro/process", methods=["POST"])
def api_gro_process():
    """Process a Grocery (GRO) Sales Order. so_type = GRO_SO"""
    return _handle_gro_process()


@app.route("/api/v1/so/process", methods=["POST"])
def api_so_process():
    """Backward-compatible alias for /api/v1/gro/process. so_type = GRO_SO"""
    return _handle_gro_process()


# ── POST /api/v1/fnv/process ──────────────────────────────────────────────────

@app.route("/api/v1/fnv/process", methods=["POST"])
def api_fnv_process():
    """
    Process a Fruits & Vegetables (FnV) multi-city Sales Order.
    so_type = FNV_SO

    Returns per-city breakdown with headers + items for each city.
    """
    fmt_str    = (request.form.get("format") or "standard").strip()
    date_raw   = (request.form.get("date") or "").strip()
    gsheet_url = request.form.get("gsheet_url", "").strip() or None

    alloc_file = request.files.get("allocation_file") or request.files.get("fnv_file")
    if not alloc_file:
        return _api_error("'allocation_file' is required.")

    delivery_date  = _parse_date(date_raw)
    alloc_filename = secure_filename(alloc_file.filename)
    alloc_path     = os.path.join(app.config["UPLOAD_FOLDER"], alloc_filename)
    alloc_file.save(alloc_path)

    prev_alloc_path = None
    prev_alloc_file = request.files.get("fnv_prev_file")
    if prev_alloc_file:
        prev_filename   = secure_filename(prev_alloc_file.filename)
        prev_alloc_path = os.path.join(app.config["UPLOAD_FOLDER"], f"prev_{prev_filename}")
        prev_alloc_file.save(prev_alloc_path)

    try:
        output_dir = tempfile.mkdtemp()
        city_stats, grand_totals, zip_path = process_all_fnv_cities(
            allocation_path=alloc_path,
            delivery_date=delivery_date,
            output_dir=output_dir,
            gsheet_url=gsheet_url,
            prev_allocation_path=prev_alloc_path,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return _api_error(str(e), 500)

    headers, fmt_label = _resolve_format(fmt_str)

    cities_out = {}
    for city, stats in city_stats.items():
        items_path = stats.get("inst_csv_path") if fmt_label == "institutional" else stats.get("csv_path")
        cities_out[city] = {
            "headers": headers,
            "stats": {
                "total_rows":   stats.get("total",   0),
                "valid_rows":   stats.get("valid",   0),
                "na_rows":      stats.get("na",      0),
                "po_generated": stats.get("po",      0),
            },
            "items": _csv_to_items(items_path),
        }

    run_id = str(uuid.uuid4())
    _REST_CACHE[run_id] = {
        "so_type":      _SO_TYPE_FNV,
        "date":         delivery_date,
        "city_stats":   city_stats,
        "grand_totals": grand_totals,
    }
    GENERATED_FILES[run_id] = {"zip": zip_path, "city_stats": city_stats}

    return jsonify({
        "success":      True,
        "so_type":      _SO_TYPE_FNV,
        "run_id":       run_id,
        "date":         delivery_date,
        "format":       fmt_label,
        "grand_totals": grand_totals,
        "cities":       cities_out,
    })


# ── POST /api/v1/brand-po/process ─────────────────────────────────────────────

@app.route("/api/v1/brand-po/process", methods=["POST"])
def api_brand_po_process():
    """
    Generate Brand Purchase Orders.
    so_type = BRAND_PO

    Returns vendor PO line items, audit rows (discrepancies), and NA/missing SKU rows.
    """
    if process_brand_po is None:
        return _api_error("Brand PO module (generate_brand_po) could not be imported.", 500)

    city_code      = (request.form.get("city") or "MUM").strip().upper()
    date_raw       = (request.form.get("date") or "").strip()
    exclude_direct = request.form.get("exclude_direct", "false").lower() == "true"

    from datetime import datetime
    if date_raw:
        selected_date = date_raw  # keep as-is for brand PO (accepts YYYY-MM-DD)
    else:
        selected_date = datetime.now().strftime("%Y-%m-%d")

    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    possible_cred_paths = [
        os.path.join(root_dir, "xd-allocation-9640b0ce66d2.json"),
        os.path.join(os.getcwd(), "xd-allocation-9640b0ce66d2.json"),
        "xd-allocation-9640b0ce66d2.json",
        r"d:\PO\xd-allocation-9640b0ce66d2.json",
    ]
    credentials_path = next((p for p in possible_cred_paths if os.path.exists(p)), None)

    try:
        output_dir = tempfile.mkdtemp()
        res = process_brand_po(
            city_code=city_code,
            selected_date=selected_date,
            credentials_path=credentials_path,
            exclude_direct_vendors=exclude_direct,
            output_dir=output_dir,
            wait_time_sec=8,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return _api_error(str(e), 500)

    # Build per-city results
    cities_out = []
    for r in (res.get("all_results") or []):
        out_p = r.get("output_path")
        aud_p = r.get("audit_path")
        na_p  = r.get("na_missing_path")

        # Parse output file into items list
        po_items    = _csv_to_items(out_p)  if out_p and out_p.endswith(".csv") else []
        audit_items = _csv_to_items(aud_p)  if aud_p and aud_p.endswith(".csv") else []
        na_items    = _csv_to_items(na_p)   if na_p  and na_p.endswith(".csv")  else []

        cities_out.append({
            "city":        r.get("city"),
            "so_type":     _SO_TYPE_BRAND_PO,
            "headers":     _BRAND_PO_HEADERS,
            "stats": {
                "total_skus":         r.get("total_skus", 0),
                "total_qty":          r.get("total_qty", 0),
                "indent_total_qty":   r.get("indent_total_qty", 0),
                "indent_diff_qty":    r.get("indent_diff_qty", 0),
                "total_value":        r.get("total_val", 0),
                "vendor_count":       r.get("vendor_count", 0),
                "discrepancies":      r.get("discrepancies_count", 0),
                "qty_discrepancies":  r.get("qty_discrepancies_count", 0),
                "na_count":           r.get("na_count", 0),
                "na_qty":             r.get("na_qty", 0),
            },
            "items":       po_items,
            "audit_items": audit_items,
            "na_items":    na_items,
        })

    run_id = str(uuid.uuid4())
    _REST_CACHE[run_id] = {
        "so_type":    _SO_TYPE_BRAND_PO,
        "city_code":  city_code,
        "date":       selected_date,
        "res":        res,
        "cities_out": cities_out,
    }

    return jsonify({
        "success":  True,
        "so_type":  _SO_TYPE_BRAND_PO,
        "run_id":   run_id,
        "city":     city_code,
        "date":     selected_date,
        "headers":  _BRAND_PO_HEADERS,
        "summary_stats": {
            "total_skus":        res.get("total_skus", 0),
            "total_qty":         res.get("total_qty", 0),
            "indent_total_qty":  res.get("indent_total_qty", 0),
            "total_value":       res.get("total_val", 0),
            "vendor_count":      res.get("vendor_count", 0),
            "discrepancies":     res.get("discrepancies_count", 0),
            "na_count":          res.get("na_count", 0),
        },
        "cities": cities_out,
    })


# ── GET /api/v1/result/<run_id> ───────────────────────────────────────────────

@app.route("/api/v1/result/<run_id>", methods=["GET"])
def api_get_result(run_id):
    """
    Re-fetch any previously processed run from in-memory cache.
    Works for GRO_SO, FNV_SO, and BRAND_PO.
    The 'so_type' field in the response always tells you which type this is.

    Query params:
        format   standard (default) | institutional  (only affects GRO_SO and FNV_SO)
    """
    if run_id not in _REST_CACHE:
        return _api_error(
            f"run_id '{run_id}' not found. "
            "Cache is in-memory only — it clears when the server restarts.",
            404
        )

    cached  = _REST_CACHE[run_id]
    so_type = cached.get("so_type", _SO_TYPE_GRO)
    fmt_str = request.args.get("format", "standard")
    headers, fmt_label = _resolve_format(fmt_str)

    # ── BRAND_PO result ───────────────────────────────────────────────────────
    if so_type == _SO_TYPE_BRAND_PO:
        return jsonify({
            "success":       True,
            "so_type":       _SO_TYPE_BRAND_PO,
            "run_id":        run_id,
            "city":          cached.get("city_code"),
            "date":          cached.get("date"),
            "headers":       _BRAND_PO_HEADERS,
            "cities":        cached.get("cities_out", []),
        })

    # ── FNV_SO result ─────────────────────────────────────────────────────────
    if so_type == _SO_TYPE_FNV:
        cities_out = {}
        for city, stats in cached.get("city_stats", {}).items():
            items_path = stats.get("inst_csv_path") if fmt_label == "institutional" else stats.get("csv_path")
            cities_out[city] = {
                "headers": headers,
                "stats": {
                    "total_rows":   stats.get("total",   0),
                    "valid_rows":   stats.get("valid",   0),
                    "na_rows":      stats.get("na",      0),
                    "po_generated": stats.get("po",      0),
                },
                "items": _csv_to_items(items_path),
            }
        return jsonify({
            "success":      True,
            "so_type":      _SO_TYPE_FNV,
            "run_id":       run_id,
            "date":         cached.get("date"),
            "format":       fmt_label,
            "grand_totals": cached.get("grand_totals", {}),
            "cities":       cities_out,
        })

    # ── GRO_SO result (default) ───────────────────────────────────────────────
    items_path = cached.get("inst_csv_path") if fmt_label == "institutional" else cached.get("csv_path")
    return jsonify({
        "success": True,
        "so_type": _SO_TYPE_GRO,
        "run_id":  run_id,
        "city":    cached.get("city"),
        "date":    cached.get("date"),
        "format":  fmt_label,
        "headers": headers,
        "stats":   cached.get("stats", {}),
        "items":   _csv_to_items(items_path),
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  POST /api/v1/combined/process
#  Runs GRO SO + FnV SO simultaneously in background threads.
#  Returns a single merged response so the consumer gets everything in one call.
#
#  so_type = "GRO_FNV_COMBINED"
#
#  Required fields (multipart/form-data):
#    gro_file        — GRO allocation file (.xlsx/.xls/.csv)
#    gro_city        — City name for GRO  (e.g. "Bangalore")
#    fnv_file        — FnV allocation file (.xlsx) covering all cities
#
#  Optional fields:
#    date            — Delivery date YYYY-MM-DD or DD-MM-YYYY (default: tomorrow)
#    format          — standard | institutional  (default: standard)
#    gro_gsheet_url  — Override Google Sheet URL for GRO
#    fnv_gsheet_url  — Override Google Sheet URL for FnV
#    fnv_prev_file   — Previous FnV allocation for delta comparison
# ═══════════════════════════════════════════════════════════════════════════════

_SO_TYPE_COMBINED = "GRO_FNV_COMBINED"


@app.route("/api/v1/combined/process", methods=["POST"])
def api_combined_process():
    """
    Run GRO SO and FnV SO in parallel and return a single merged JSON response.

    so_type = GRO_FNV_COMBINED

    Response shape:
    {
        "success":       true,
        "so_type":       "GRO_FNV_COMBINED",
        "run_id":        "...",
        "date":          "DD-MM-YYYY",
        "format":        "standard" | "institutional",
        "summary": {
            "gro_valid_rows":  int,
            "gro_na_rows":     int,
            "fnv_valid_rows":  int,   (sum across all cities)
            "fnv_na_rows":     int,
            "total_valid_rows": int,
            "total_na_rows":    int
        },
        "gro": {
            "so_type": "GRO_SO",
            "city":    "Bangalore",
            "headers": [...],
            "stats":   {...},
            "items":   [...]
        },
        "fnv": {
            "so_type":      "FNV_SO",
            "grand_totals": {...},
            "cities": {
                "Bangalore": { "headers": [...], "stats": {...}, "items": [...] },
                ...
            }
        },
        "errors": {          // non-empty only if one pipeline failed
            "gro": null | "error message",
            "fnv": null | "error message"
        }
    }
    """
    import threading

    # ── Parse shared inputs ───────────────────────────────────────────────────
    fmt_str        = (request.form.get("format") or "standard").strip()
    date_raw       = (request.form.get("date") or "").strip()
    delivery_date  = _parse_date(date_raw)
    headers, fmt_label = _resolve_format(fmt_str)

    gro_gsheet_url = request.form.get("gro_gsheet_url", "").strip() or None
    fnv_gsheet_url = request.form.get("fnv_gsheet_url", "").strip() or None
    gro_city       = (request.form.get("gro_city") or "").strip()

    # ── Validate required files ───────────────────────────────────────────────
    gro_file = request.files.get("gro_file")
    fnv_file = request.files.get("fnv_file") or request.files.get("allocation_file")

    missing = []
    if not gro_file: missing.append("'gro_file' (GRO allocation file)")
    if not gro_city: missing.append("'gro_city' (city name for GRO, e.g. Bangalore)")
    if not fnv_file: missing.append("'fnv_file' (FnV allocation file)")
    if missing:
        return _api_error("Missing required fields: " + ", ".join(missing))

    # ── Save uploaded files to temp paths ─────────────────────────────────────
    gro_filename = secure_filename(gro_file.filename)
    gro_path     = os.path.join(app.config["UPLOAD_FOLDER"], f"gro_{gro_filename}")
    gro_file.save(gro_path)

    fnv_filename = secure_filename(fnv_file.filename)
    fnv_path     = os.path.join(app.config["UPLOAD_FOLDER"], f"fnv_{fnv_filename}")
    fnv_file.save(fnv_path)

    prev_alloc_path = None
    prev_alloc_file = request.files.get("fnv_prev_file")
    if prev_alloc_file:
        prev_fn         = secure_filename(prev_alloc_file.filename)
        prev_alloc_path = os.path.join(app.config["UPLOAD_FOLDER"], f"prev_{prev_fn}")
        prev_alloc_file.save(prev_alloc_path)

    # ── Thread result containers ──────────────────────────────────────────────
    gro_result = {"data": None, "error": None}
    fnv_result = {"data": None, "error": None}

    # ── GRO worker ────────────────────────────────────────────────────────────
    def run_gro():
        try:
            out_dir = tempfile.mkdtemp()
            (csv_path, inst_csv_path, xlsx_path, po_path,
             valid_len, na_len, total_so, po_generated) = run_automation(
                allocation_path=gro_path,
                ecom_path=None,
                city=gro_city,
                delivery_date=delivery_date,
                output_dir=out_dir,
                gsheet_url=gro_gsheet_url,
                so_sheet_override=None,
                po_sheet_override=None,
            )
            items_path = inst_csv_path if fmt_label == "institutional" else csv_path
            gro_result["data"] = {
                "so_type": _SO_TYPE_GRO,
                "city":    gro_city,
                "headers": headers,
                "stats": {
                    "total_rows":   total_so,
                    "valid_rows":   valid_len,
                    "na_rows":      na_len,
                    "po_generated": po_generated,
                },
                "items":        _csv_to_items(items_path),
                "csv_path":     csv_path,
                "inst_csv_path": inst_csv_path,
            }
        except Exception as exc:
            import traceback
            traceback.print_exc()
            gro_result["error"] = str(exc)

    # ── FnV worker ────────────────────────────────────────────────────────────
    def run_fnv():
        try:
            out_dir = tempfile.mkdtemp()
            city_stats, grand_totals, zip_path = process_all_fnv_cities(
                allocation_path=fnv_path,
                delivery_date=delivery_date,
                output_dir=out_dir,
                gsheet_url=fnv_gsheet_url,
                prev_allocation_path=prev_alloc_path,
            )
            cities_out = {}
            for city, stats in city_stats.items():
                items_path = stats.get("inst_csv_path") if fmt_label == "institutional" else stats.get("csv_path")
                cities_out[city] = {
                    "headers": headers,
                    "stats": {
                        "total_rows":   stats.get("total",   0),
                        "valid_rows":   stats.get("valid",   0),
                        "na_rows":      stats.get("na",      0),
                        "po_generated": stats.get("po",      0),
                    },
                    "items": _csv_to_items(items_path),
                }
            fnv_result["data"] = {
                "so_type":      _SO_TYPE_FNV,
                "grand_totals": grand_totals,
                "cities":       cities_out,
                "city_stats":   city_stats,
                "zip_path":     zip_path,
            }
        except Exception as exc:
            import traceback
            traceback.print_exc()
            fnv_result["error"] = str(exc)

    # ── Run both in parallel ──────────────────────────────────────────────────
    t_gro = threading.Thread(target=run_gro, name="gro_worker", daemon=True)
    t_fnv = threading.Thread(target=run_fnv, name="fnv_worker", daemon=True)

    t_gro.start()
    t_fnv.start()
    t_gro.join()
    t_fnv.join()

    # ── If BOTH failed, return an error ───────────────────────────────────────
    if gro_result["error"] and fnv_result["error"]:
        return _api_error(
            f"Both pipelines failed. GRO: {gro_result['error']} | FnV: {fnv_result['error']}",
            500
        )

    # ── Build merged summary stats ────────────────────────────────────────────
    gro_valid = gro_result["data"]["stats"]["valid_rows"] if gro_result["data"] else 0
    gro_na    = gro_result["data"]["stats"]["na_rows"]    if gro_result["data"] else 0

    fnv_valid = fnv_na = 0
    if fnv_result["data"]:
        for city_data in fnv_result["data"]["cities"].values():
            fnv_valid += city_data["stats"].get("valid_rows", 0)
            fnv_na    += city_data["stats"].get("na_rows",    0)

    summary = {
        "gro_city":         gro_city,
        "gro_valid_rows":   gro_valid,
        "gro_na_rows":      gro_na,
        "fnv_valid_rows":   fnv_valid,
        "fnv_na_rows":      fnv_na,
        "total_valid_rows": gro_valid + fnv_valid,
        "total_na_rows":    gro_na    + fnv_na,
    }

    # ── Cache the combined result ─────────────────────────────────────────────
    run_id = str(uuid.uuid4())
    _REST_CACHE[run_id] = {
        "so_type":  _SO_TYPE_COMBINED,
        "date":     delivery_date,
        "format":   fmt_label,
        "gro":      gro_result["data"],
        "fnv":      fnv_result["data"],
        "summary":  summary,
    }

    # Also register individual file paths for download compatibility
    if gro_result["data"]:
        GENERATED_FILES[run_id] = {
            "csv":      gro_result["data"].get("csv_path"),
            "inst_csv": gro_result["data"].get("inst_csv_path"),
        }
    if fnv_result["data"] and fnv_result["data"].get("zip_path"):
        GENERATED_FILES.setdefault(run_id, {})["zip"] = fnv_result["data"]["zip_path"]

    return jsonify({
        "success": True,
        "so_type": _SO_TYPE_COMBINED,
        "run_id":  run_id,
        "date":    delivery_date,
        "format":  fmt_label,
        "summary": summary,
        "gro":     gro_result["data"],
        "fnv":     {
            "so_type":      fnv_result["data"]["so_type"]      if fnv_result["data"] else None,
            "grand_totals": fnv_result["data"]["grand_totals"] if fnv_result["data"] else {},
            "cities":       fnv_result["data"]["cities"]       if fnv_result["data"] else {},
        } if fnv_result["data"] else None,
        "errors": {
            "gro": gro_result["error"],
            "fnv": fnv_result["error"],
        }
    })

