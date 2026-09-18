"""
so_api_client.py
=================
CUS SO gRPC API Consumer Client
────────────────────────────────
Drop this file and the 3 proto stub files (so_service_pb2.py, so_service_pb2_grpc.py)
in the same folder. Then run:

    pip install grpcio
    python so_api_client.py --host 0.tcp.ngrok.io --port 12345 --city Bangalore

You will receive the Sales Order headers and all line items as JSON.
"""

import sys
import os
import argparse
import json

# ── Detect if running from grpc_service/ or a shared consumer folder ─────────
_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _dir)

try:
    import grpc
    import so_service_pb2 as pb2
    import so_service_pb2_grpc as pb2_grpc
except ImportError as e:
    print(f"\n[ERROR] Missing dependency: {e}")
    print("Run:  pip install grpcio")
    print("Also make sure so_service_pb2.py and so_service_pb2_grpc.py are in the same folder.\n")
    sys.exit(1)


# ── Public API functions ──────────────────────────────────────────────────────

def connect(host: str, port: int) -> pb2_grpc.SalesOrderServiceStub:
    """Create and return a connected gRPC stub."""
    channel = grpc.insecure_channel(f"{host}:{port}")
    return pb2_grpc.SalesOrderServiceStub(channel)


def get_headers(stub, format: str = "standard") -> dict:
    """
    Fetch column headers for the given SO format.

    Parameters
    ----------
    stub   : stub returned by connect()
    format : "standard" (16-column GRO SO) | "institutional" (15-column)

    Returns
    -------
    dict with keys:
        - format  : str
        - headers : list[str]   ordered column names
        - count   : int
    """
    fmt = pb2.SOFormat.INSTITUTIONAL if format.lower() == "institutional" else pb2.SOFormat.STANDARD
    resp = stub.GetSOHeaders(pb2.HeadersRequest(format=fmt))
    return {
        "format":  pb2.SOFormat.Name(resp.format),
        "headers": list(resp.headers),
        "count":   len(resp.headers),
    }


def get_sales_order(stub, city: str, date: str = "", format: str = "standard", run_id: str = "") -> dict:
    """
    Fetch a processed Sales Order for the given city and date.

    Parameters
    ----------
    stub   : stub returned by connect()
    city   : "Bangalore" | "Chennai" | "Mumbai" | "Hyderabad" | "Trichy" | "Coimbatore" | "Nashik"
    date   : delivery date as "DD-MM-YYYY" or "YYYY-MM-DD" (defaults to tomorrow if empty)
    format : "standard" | "institutional"
    run_id : (optional) re-fetch a previously processed run from server cache

    Returns
    -------
    dict with keys:
        - run_id   : str   unique run identifier (save for re-fetching same result)
        - city     : str
        - date     : str   "DD-MM-YYYY"
        - format   : str
        - headers  : list[str]    ordered column names
        - stats    : dict         { total_rows, valid_rows, na_rows, po_generated }
        - items    : list[dict]   each dict maps column name → value
        - error    : str          non-empty only on failure
    """
    fmt = pb2.SOFormat.INSTITUTIONAL if format.lower() == "institutional" else pb2.SOFormat.STANDARD
    request = pb2.SORequest(city=city, date=date, format=fmt, run_id=run_id)

    try:
        resp = stub.GetSalesOrder(request, timeout=120)   # 2-min timeout for processing
    except grpc.RpcError as e:
        return {"error": f"gRPC error: {e.code()} — {e.details()}"}

    if resp.error:
        return {"error": resp.error}

    # Map SOItem proto fields → flat dicts
    items = []
    for item in resp.items:
        row = {}
        for field in [
            "customer_contact_number", "nc_id", "nc_name", "qty", "date",
            "lot_weight_id", "ordering_mode", "cancelled", "purchase_order",
            "sales_price", "delivery_charge", "city_id", "sale_order_id",
            "sub_type", "category_id", "grocer_flow",
            "sku_id", "quantity", "delivery_date", "lot_id", "sku_type_id", "customer_id",
        ]:
            val = getattr(item, field, "")
            if val:
                row[field] = val
        row.update(dict(item.extra))
        items.append(row)

    return {
        "run_id":  resp.run_id,
        "city":    resp.city,
        "date":    resp.date,
        "format":  pb2.SOFormat.Name(resp.format),
        "headers": list(resp.headers),
        "stats": {
            "total_rows":   resp.stats.total_rows,
            "valid_rows":   resp.stats.valid_rows,
            "na_rows":      resp.stats.na_rows,
            "po_generated": resp.stats.po_generated,
        },
        "items": items,
    }


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CUS SO gRPC API Consumer Client",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  # Get column headers
  python so_api_client.py --host 0.tcp.ngrok.io --port 12345 --headers-only

  # Get full SO for Bangalore (standard format)
  python so_api_client.py --host 0.tcp.ngrok.io --port 12345 --city Bangalore --date 19-09-2026

  # Get institutional format
  python so_api_client.py --host 0.tcp.ngrok.io --port 12345 --city Mumbai --format institutional

  # Re-fetch a cached run (instant, no reprocessing)
  python so_api_client.py --host 0.tcp.ngrok.io --port 12345 --city Chennai --run-id <run_id>

  # Save result to JSON file
  python so_api_client.py --host 0.tcp.ngrok.io --port 12345 --city Hyderabad --output result.json
"""
    )
    parser.add_argument("--host",         required=True,       help="Server host (e.g. 0.tcp.ngrok.io or IP address)")
    parser.add_argument("--port",         type=int, required=True, help="Server port (e.g. 12345)")
    parser.add_argument("--city",         default="Bangalore", help="City name")
    parser.add_argument("--date",         default="",          help="Delivery date DD-MM-YYYY (default: tomorrow)")
    parser.add_argument("--format",       default="standard",  choices=["standard", "institutional"])
    parser.add_argument("--run-id",       default="",          help="Re-fetch a cached run by ID")
    parser.add_argument("--headers-only", action="store_true", help="Only fetch column headers, skip items")
    parser.add_argument("--output",       default="",          help="Save JSON result to file path")
    args = parser.parse_args()

    print(f"[Connecting]  {args.host}:{args.port} …")
    stub = connect(args.host, args.port)

    if args.headers_only:
        result = get_headers(stub, args.format)
        print(f"[OK] {len(result['headers'])} headers for '{result['format']}' format:")
    else:
        print(f"[Fetching]  city={args.city}  date={args.date or 'tomorrow'}  format={args.format}")
        result = get_sales_order(stub, args.city, args.date, args.format, args.run_id)
        if "error" in result:
            print(f"[ERROR] {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"[OK] run_id={result['run_id']}  rows={result['stats']['valid_rows']} valid / {result['stats']['na_rows']} NA")

    out = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"[Saved]  {args.output}")
    else:
        print(out)


if __name__ == "__main__":
    main()
