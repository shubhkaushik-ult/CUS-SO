"""
grpc_server.py
==============
gRPC Server for Sales Order (SO) Service.

Exposes two RPCs:
  - GetSalesOrder  : Given city + date + format, returns SO headers + all line items as JSON-compatible SOItem messages.
  - GetSOHeaders   : Returns just the ordered column headers for the given format.

Usage:
    python grpc_service/grpc_server.py           # Starts server on port 50051
    python grpc_service/grpc_server.py --port 50052
"""

import sys
import os
import argparse
import time
import logging
import json
import concurrent.futures
from datetime import datetime, timedelta

# ── Ensure parent dir is on path (so we can import automation_script, db_lookup, etc.)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import grpc
import so_service_pb2 as pb2
import so_service_pb2_grpc as pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("so_grpc_server")

# ── Column definitions (mirrors automation_script.py) ─────────────────────────

STANDARD_HEADERS = [
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

INSTITUTIONAL_HEADERS = [
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

# Mapping from SO format enum → ordered headers list
FORMAT_HEADERS = {
    pb2.SOFormat.STANDARD:      STANDARD_HEADERS,
    pb2.SOFormat.INSTITUTIONAL: INSTITUTIONAL_HEADERS,
}

# ── Standard column name → SOItem field mapping ──────────────────────────────

_STD_COL_MAP = {
    "customer_contact_number(req)":              "customer_contact_number",
    "nc id":                                     "nc_id",
    "nc name":                                   "nc_name",
    "qty":                                       "qty",
    "date":                                      "date",
    "lot weight id":                             "lot_weight_id",
    "ordering_mode(optional)":                   "ordering_mode",
    "cancelled (optional)by default should be 0": "cancelled",
    "purchaseorder":                             "purchase_order",
    "sales price":                               "sales_price",
    "delivery_charge(opt)":                      "delivery_charge",
    "city_id(req)":                              "city_id",
    "sale_order_id(optional- leave empty)":      "sale_order_id",
    "sub_type (optional- leave empty)":          "sub_type",
    "categoryid (if empty then default is 1)":   "category_id",
    "grocerflow":                                "grocer_flow",
}

_INST_COL_MAP = {
    "customer_contact_number(req)":  "customer_contact_number",
    "sku_id(req)":                   "sku_id",
    "nc name":                       "nc_name",
    "quantity(req)":                 "quantity",
    "delivery_date(dd-mm-yyyy)":     "delivery_date",
    "lot_id(req)":                   "lot_id",
    "ordering_mode(optional)":       "ordering_mode",
    "cancelled(optional)":           "cancelled",
    "purchaseorder":                 "purchase_order",
    "sales price":                   "sales_price",
    "delivery_charge(opt)":          "delivery_charge",
    "sale_order_id(optional)":       "sale_order_id",
    "sub_type(optional)":            "sub_type",
    "skutypeid":                     "sku_type_id",
    "customerid":                    "customer_id",
}


def _row_to_so_item(row: dict, format_type: int) -> pb2.SOItem:
    """Convert a flat row dict (column → value) to an SOItem proto message."""
    col_map = _INST_COL_MAP if format_type == pb2.SOFormat.INSTITUTIONAL else _STD_COL_MAP

    item_kwargs = {}
    extra = {}

    for col, val in row.items():
        normalized = col.strip().lower()
        field_name = col_map.get(normalized)
        if field_name:
            item_kwargs[field_name] = str(val) if val is not None else ""
        else:
            extra[col] = str(val) if val is not None else ""

    item = pb2.SOItem(**item_kwargs)
    item.extra.update(extra)
    return item


# ── In-memory run cache: run_id → {format → [row_dicts]} ────────────────────
_RUN_CACHE: dict[str, dict] = {}


def _load_csv_as_rows(csv_path: str) -> list[dict]:
    """Read a CSV file and return list of row dicts."""
    import pandas as pd
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    return df.to_dict(orient="records")


# ── gRPC Servicer Implementation ─────────────────────────────────────────────

class SalesOrderServicer(pb2_grpc.SalesOrderServiceServicer):

    def GetSOHeaders(self, request: pb2.HeadersRequest, context) -> pb2.HeadersResponse:
        """Return ordered column headers for the requested SO format."""
        headers = FORMAT_HEADERS.get(request.format, STANDARD_HEADERS)
        logger.info("GetSOHeaders  format=%s  → %d headers", pb2.SOFormat.Name(request.format), len(headers))
        return pb2.HeadersResponse(format=request.format, headers=headers)

    def GetSalesOrder(self, request: pb2.SORequest, context) -> pb2.SOResponse:
        """
        Process or retrieve a Sales Order for the given city + date.

        Lookup order:
        1.  If run_id is provided and cached → return cached data directly.
        2.  Otherwise call run_automation() to process and generate outputs.
        3.  Read the generated CSV, parse rows, cache, and return.
        """
        city = request.city.strip()
        date = request.date.strip()
        fmt  = request.format
        run_id = request.run_id.strip() if request.run_id else ""

        logger.info("GetSalesOrder  city=%s  date=%s  format=%s  run_id=%r", city, date, pb2.SOFormat.Name(fmt), run_id)

        headers = FORMAT_HEADERS.get(fmt, STANDARD_HEADERS)

        # ── Try cache hit ────────────────────────────────────────────────────
        if run_id and run_id in _RUN_CACHE:
            cached = _RUN_CACHE[run_id]
            rows = cached.get(fmt, [])
            items = [_row_to_so_item(r, fmt) for r in rows]
            stats = cached.get("stats", {})
            logger.info("  Cache HIT  run_id=%s  rows=%d", run_id, len(items))
            return pb2.SOResponse(
                run_id=run_id,
                city=city,
                date=date,
                format=fmt,
                headers=headers,
                items=items,
                stats=pb2.SOStats(
                    total_rows=stats.get("total", 0),
                    valid_rows=stats.get("valid", 0),
                    na_rows=stats.get("na", 0),
                    po_generated=stats.get("po", 0),
                ),
            )

        # ── Validate inputs ──────────────────────────────────────────────────
        if not city:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("'city' is required.")
            return pb2.SOResponse(error="'city' is required.")

        # Normalize and default delivery date to today + 1 if not supplied
        if not date:
            date = (datetime.today() + timedelta(days=1)).strftime("%d-%m-%Y")
        else:
            # Accept YYYY-MM-DD or DD-MM-YYYY
            for fmt_str in ("%Y-%m-%d", "%d-%m-%Y"):
                try:
                    date = datetime.strptime(date, fmt_str).strftime("%d-%m-%Y")
                    break
                except ValueError:
                    pass

        # ── Trigger automation pipeline ──────────────────────────────────────
        try:
            import tempfile
            import uuid
            from automation_script import run_automation

            output_dir = tempfile.mkdtemp(prefix="grpc_so_")
            new_run_id = str(uuid.uuid4())

            logger.info("  Running automation: city=%s date=%s output_dir=%s", city, date, output_dir)

            (csv_path, inst_csv_path, xlsx_path, po_path,
             valid_len, na_len, total_so, po_generated) = run_automation(
                allocation_path=None,     # No upload file — DB-direct mode
                ecom_path=None,
                city=city,
                delivery_date=date,
                output_dir=output_dir,
                gsheet_url=None,
                so_sheet_override=None,
                po_sheet_override=None,
            )

        except Exception as exc:
            logger.error("  Automation error: %s", exc, exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return pb2.SOResponse(error=str(exc))

        # ── Parse generated CSVs ─────────────────────────────────────────────
        def safe_rows(path):
            if path and os.path.exists(path):
                return _load_csv_as_rows(path)
            return []

        std_rows  = safe_rows(csv_path)
        inst_rows = safe_rows(inst_csv_path)

        stats_dict = {
            "total":  total_so,
            "valid":  valid_len,
            "na":     na_len,
            "po":     po_generated,
        }

        # ── Cache the results ────────────────────────────────────────────────
        _RUN_CACHE[new_run_id] = {
            pb2.SOFormat.STANDARD:      std_rows,
            pb2.SOFormat.INSTITUTIONAL: inst_rows,
            "stats": stats_dict,
        }

        rows = inst_rows if fmt == pb2.SOFormat.INSTITUTIONAL else std_rows
        items = [_row_to_so_item(r, fmt) for r in rows]

        logger.info("  Done  run_id=%s  rows=%d  valid=%d  na=%d", new_run_id, len(items), valid_len, na_len)

        return pb2.SOResponse(
            run_id=new_run_id,
            city=city,
            date=date,
            format=fmt,
            headers=headers,
            items=items,
            stats=pb2.SOStats(
                total_rows=total_so,
                valid_rows=valid_len,
                na_rows=na_len,
                po_generated=po_generated,
            ),
        )


# ── Server Bootstrap ──────────────────────────────────────────────────────────

def serve(port: int = 50051, max_workers: int = 10):
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=max_workers))
    pb2_grpc.add_SalesOrderServiceServicer_to_server(SalesOrderServicer(), server)
    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)
    server.start()
    logger.info("─" * 60)
    logger.info("  CUS SO  gRPC Server  listening on  %s", listen_addr)
    logger.info("  RPCs available:")
    logger.info("    • SalesOrderService.GetSOHeaders")
    logger.info("    • SalesOrderService.GetSalesOrder")
    logger.info("─" * 60)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down gRPC server …")
        server.stop(grace=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CUS SO gRPC Server")
    parser.add_argument("--port", type=int, default=50051, help="Port to listen on (default: 50051)")
    parser.add_argument("--workers", type=int, default=10, help="Thread pool size (default: 10)")
    args = parser.parse_args()
    serve(port=args.port, max_workers=args.workers)
