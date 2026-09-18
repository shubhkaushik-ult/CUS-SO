"""
grpc_client_test.py
===================
Quick test client / CLI tool for the CUS SO gRPC service.

Usage:
    python grpc_service/grpc_client_test.py --city Bangalore --date 19-09-2026
    python grpc_service/grpc_client_test.py --city Mumbai --format institutional
    python grpc_service/grpc_client_test.py --headers-only --format standard
    python grpc_service/grpc_client_test.py --run-id <run_id> --city Chennai --format institutional
"""

import sys
import os
import argparse
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import grpc
import so_service_pb2 as pb2
import so_service_pb2_grpc as pb2_grpc


def get_channel(host: str = "localhost", port: int = 50051) -> grpc.Channel:
    return grpc.insecure_channel(f"{host}:{port}")


def fetch_headers(stub, fmt: int) -> dict:
    """Call GetSOHeaders and pretty-print the result."""
    response = stub.GetSOHeaders(pb2.HeadersRequest(format=fmt))
    return {
        "format": pb2.SOFormat.Name(response.format),
        "headers": list(response.headers),
        "count": len(response.headers),
    }


def fetch_sales_order(stub, city: str, date: str, fmt: int, run_id: str = "") -> dict:
    """Call GetSalesOrder and return a dict with headers + items."""
    request = pb2.SORequest(city=city, date=date, format=fmt, run_id=run_id)
    response = stub.GetSalesOrder(request)

    if response.error:
        return {"error": response.error}

    items = []
    for item in response.items:
        row = {}
        # Core SO fields
        for field in [
            "customer_contact_number", "nc_id", "nc_name", "qty", "date",
            "lot_weight_id", "ordering_mode", "cancelled", "purchase_order",
            "sales_price", "delivery_charge", "city_id", "sale_order_id",
            "sub_type", "category_id", "grocer_flow",
            # Institutional
            "sku_id", "quantity", "delivery_date", "lot_id", "sku_type_id", "customer_id",
        ]:
            val = getattr(item, field, "")
            if val:
                row[field] = val
        # Extra unmapped fields
        row.update(dict(item.extra))
        items.append(row)

    return {
        "run_id":  response.run_id,
        "city":    response.city,
        "date":    response.date,
        "format":  pb2.SOFormat.Name(response.format),
        "headers": list(response.headers),
        "stats": {
            "total_rows":   response.stats.total_rows,
            "valid_rows":   response.stats.valid_rows,
            "na_rows":      response.stats.na_rows,
            "po_generated": response.stats.po_generated,
        },
        "items": items,
    }


def main():
    parser = argparse.ArgumentParser(description="CUS SO gRPC Test Client")
    parser.add_argument("--host",         default="localhost",  help="Server host")
    parser.add_argument("--port",         type=int, default=50051, help="Server port")
    parser.add_argument("--city",         default="Bangalore",  help="City name")
    parser.add_argument("--date",         default="",           help="Delivery date (DD-MM-YYYY or YYYY-MM-DD)")
    parser.add_argument("--format",       default="standard",   choices=["standard", "institutional"], help="SO format")
    parser.add_argument("--run-id",       default="",           help="Re-fetch a cached run by ID")
    parser.add_argument("--headers-only", action="store_true",  help="Only fetch column headers, no items")
    parser.add_argument("--output",       default="",           help="Optional: save JSON result to this file path")
    args = parser.parse_args()

    fmt = pb2.SOFormat.INSTITUTIONAL if args.format == "institutional" else pb2.SOFormat.STANDARD

    channel = get_channel(args.host, args.port)
    stub = pb2_grpc.SalesOrderServiceStub(channel)

    try:
        if args.headers_only:
            result = fetch_headers(stub, fmt)
        else:
            result = fetch_sales_order(stub, args.city, args.date, fmt, args.run_id)
    except grpc.RpcError as e:
        print(f"[gRPC ERROR]  code={e.code()}  details={e.details()}", file=sys.stderr)
        sys.exit(1)

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"[OK] Saved to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
