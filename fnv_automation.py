import os
import tempfile
import zipfile
import traceback
from automation_script import FNV_CITY_CONFIG, run_fnv_automation

def process_all_fnv_cities(fnv_alloc_path, delivery_date, gsheet_url, output_dir=None):
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
        
    zip_path = os.path.join(output_dir, "fnv_all_cities.zip")
    
    total_valid = 0
    total_na = 0
    total_po = 0
    total_so_processed = 0
    city_stats = {}
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for city, cfg in FNV_CITY_CONFIG.items():
            print(f"Processing FnV for {city}...")
            try:
                city_output_dir = os.path.join(output_dir, city)
                os.makedirs(city_output_dir, exist_ok=True)
                
                csv_path, xlsx_path, po_path, valid_len, na_len, total_so, po_generated = run_fnv_automation(
                    fnv_alloc_path=fnv_alloc_path,
                    city=city,
                    delivery_date=delivery_date,
                    output_dir=city_output_dir,
                    gsheet_url=gsheet_url,
                    so_sheet_override=cfg["so_sheet"],
                    po_sheet_override=cfg["po_sheet"],
                    city_col="City"
                )
                
                total_valid += valid_len
                total_na += na_len
                total_po += po_generated
                total_so_processed += total_so
                
                # Add to ZIP
                has_csv = os.path.exists(csv_path)
                has_na = os.path.exists(xlsx_path)
                has_po = os.path.exists(po_path)
                
                if has_csv:
                    zf.write(csv_path, f"{city}/{os.path.basename(csv_path)}")
                if has_na:
                    zf.write(xlsx_path, f"{city}/{os.path.basename(xlsx_path)}")
                if has_po:
                    zf.write(po_path, f"{city}/{os.path.basename(po_path)}")
                    
                city_stats[city] = {
                    'valid': valid_len,
                    'na': na_len,
                    'total_so': total_so,
                    'po': po_generated,
                    'csv_path': csv_path if has_csv else None,
                    'xlsx_path': xlsx_path if has_na else None,
                    'po_path': po_path if has_po else None,
                }
                    
            except Exception as e:
                print(f"Skipped or failed for {city}: {e}")
                # traceback.print_exc()
                
    return zip_path, total_valid, total_na, total_so_processed, total_po, city_stats
