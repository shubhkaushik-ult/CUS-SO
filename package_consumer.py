"""
package_consumer.py
====================
Bundles everything a consumer needs into a single zip file:
  - so_api_client.py           (main client — all logic in one file)
  - so_service_pb2.py          (auto-generated proto messages)
  - so_service_pb2_grpc.py     (auto-generated gRPC stub)
  - consumer_README.txt        (instructions for the recipient)

Run: python package_consumer.py
Output: dist/CUS_SO_gRPC_Client.zip
"""

import os
import zipfile
import json

ROOT        = os.path.dirname(os.path.abspath(__file__))
GRPC_DIR    = os.path.join(ROOT, "grpc_service")
DIST_DIR    = os.path.join(ROOT, "dist")
ZIP_OUTPUT  = os.path.join(DIST_DIR, "CUS_SO_gRPC_Client.zip")

FILES_TO_BUNDLE = [
    os.path.join(GRPC_DIR, "so_api_client.py"),
    os.path.join(GRPC_DIR, "so_service_pb2.py"),
    os.path.join(GRPC_DIR, "so_service_pb2_grpc.py"),
]

README_CONTENT = """
CUS SO gRPC API — Consumer Package
====================================

Contents of this package:
  - so_api_client.py          ← Main client you run
  - so_service_pb2.py         ← Auto-generated (do not edit)
  - so_service_pb2_grpc.py    ← Auto-generated (do not edit)

STEP 1 — Install dependency (one-time)
----------------------------------------
  pip install grpcio

STEP 2 — Get the connection details
--------------------------------------
  Ask the API owner for:
    HOST  =  e.g. 0.tcp.ngrok.io  (or an IP address)
    PORT  =  e.g. 12345

STEP 3 — Run the client
--------------------------

  # A) Get column headers only (no data processed)
  python so_api_client.py --host <HOST> --port <PORT> --headers-only

  # B) Fetch Standard SO for Bangalore (today's date)
  python so_api_client.py --host <HOST> --port <PORT> --city Bangalore

  # C) Fetch Institutional SO for Mumbai on a specific date
  python so_api_client.py --host <HOST> --port <PORT> --city Mumbai --date 19-09-2026 --format institutional

  # D) Save the result to a JSON file
  python so_api_client.py --host <HOST> --port <PORT> --city Chennai --output result.json

  # E) Re-fetch a previous result using its run_id (instant, no reprocessing)
  python so_api_client.py --host <HOST> --port <PORT> --city Hyderabad --run-id <run_id>

SUPPORTED CITIES
-----------------
  Bangalore | Chennai | Mumbai | Hyderabad | Trichy | Coimbatore | Nashik

OUTPUT FORMAT
--------------
  Returns JSON with:
    {
      "run_id": "...",
      "city": "Bangalore",
      "date": "19-09-2026",
      "format": "STANDARD",
      "headers": ["customer_contact_number(req)", "NC ID", ...],
      "stats": {"total_rows": 150, "valid_rows": 140, "na_rows": 10, "po_generated": 140},
      "items": [
        {"customer_contact_number": "9876543210", "nc_id": "1234", "nc_name": "...", "qty": "5", ...},
        ...
      ]
    }

USING AS A PYTHON LIBRARY
---------------------------
  from so_api_client import connect, get_headers, get_sales_order

  stub = connect("0.tcp.ngrok.io", 12345)

  # Just headers
  headers = get_headers(stub, format="institutional")
  print(headers["headers"])

  # Full SO data
  result = get_sales_order(stub, city="Bangalore", date="19-09-2026", format="standard")
  for item in result["items"]:
      print(item["nc_name"], item["qty"])
"""

def package():
    os.makedirs(DIST_DIR, exist_ok=True)

    missing = [f for f in FILES_TO_BUNDLE if not os.path.exists(f)]
    if missing:
        print("[ERROR] Missing files to bundle:")
        for m in missing:
            print(f"  {m}")
        return

    with zipfile.ZipFile(ZIP_OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in FILES_TO_BUNDLE:
            arcname = os.path.basename(file_path)
            zf.write(file_path, arcname)
            print(f"  + {arcname}")
        
        # Write README
        zf.writestr("README.txt", README_CONTENT.strip())
        print("  + README.txt")

    print(f"\n[DONE] Consumer package created:\n   {ZIP_OUTPUT}\n")
    print("Share this ZIP file with your consumers.")
    print("They only need to: pip install grpcio  and then run so_api_client.py")

if __name__ == "__main__":
    package()
