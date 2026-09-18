"""
start_grpc_public.py
=====================
One-click script to:
  1. Start the CUS SO gRPC server on port 50051.
  2. Launch an ngrok TCP tunnel on the same port.
  3. Print the public address consumers should use.
  4. Keep everything alive until Ctrl+C.

Requirements:
    pip install ngrok          (official ngrok Python SDK)
    pip install grpcio         (already installed)
    ngrok account + authtoken  (free at https://dashboard.ngrok.com)

Setup (one-time):
    ngrok config add-authtoken <YOUR_AUTHTOKEN>
  OR set env variable:
    $env:NGROK_AUTHTOKEN = "your_token_here"
"""

import os
import sys
import time
import signal
import subprocess
import threading
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("launcher")

GRPC_PORT = int(os.environ.get("GRPC_PORT", 50051))

# ── Ensure parent dir is importable ──────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def start_grpc_server_in_thread():
    """Start the gRPC server in a background thread."""
    # Import here so server starts in background
    grpc_dir = os.path.join(ROOT, "grpc_service")
    sys.path.insert(0, grpc_dir)

    import concurrent.futures
    import grpc
    import so_service_pb2_grpc as pb2_grpc

    # Import the servicer class
    from grpc_service.grpc_server import SalesOrderServicer

    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_SalesOrderServiceServicer_to_server(SalesOrderServicer(), server)
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    server.start()
    log.info("✅ gRPC server started on port %d", GRPC_PORT)
    return server


def start_ngrok_tunnel():
    """Start an ngrok TCP tunnel using the ngrok Python SDK."""
    try:
        import ngrok
    except ImportError:
        log.error("ngrok Python SDK not installed. Run:  pip install ngrok")
        log.error("Then set your authtoken:  ngrok config add-authtoken <TOKEN>")
        sys.exit(1)

    authtoken = os.environ.get("NGROK_AUTHTOKEN", "")
    if authtoken:
        ngrok.set_auth_token(authtoken)

    try:
        tunnel = ngrok.connect(GRPC_PORT, "tcp")
        public_url = tunnel.url()
        return tunnel, public_url
    except Exception as e:
        log.error("Failed to open ngrok tunnel: %s", e)
        log.error(
            "Make sure you've set your authtoken:\n"
            "  ngrok config add-authtoken <YOUR_TOKEN>\n"
            "  OR:  $env:NGROK_AUTHTOKEN = 'your_token_here'"
        )
        sys.exit(1)


def parse_host_port(public_url: str):
    """Parse 'tcp://0.tcp.ngrok.io:12345' into (host, port)."""
    url = public_url.replace("tcp://", "")
    host, port = url.rsplit(":", 1)
    return host.strip(), int(port.strip())


def write_connection_file(host: str, port: int):
    """Write connection details to a shareable JSON file."""
    import json
    info = {
        "grpc_host": host,
        "grpc_port": port,
        "description": "CUS SO gRPC API — Sales Order Service",
        "rpcs": [
            {
                "name": "GetSOHeaders",
                "description": "Returns ordered column headers for Standard (16-col) or Institutional (15-col) SO format.",
                "request_fields": {"format": "0 = STANDARD, 1 = INSTITUTIONAL"}
            },
            {
                "name": "GetSalesOrder",
                "description": "Processes and returns full Sales Order headers + line items as JSON.",
                "request_fields": {
                    "city": "Bangalore | Chennai | Mumbai | Hyderabad | Trichy | Coimbatore | Nashik",
                    "date": "DD-MM-YYYY  (e.g. 19-09-2026)",
                    "format": "0 = STANDARD, 1 = INSTITUTIONAL",
                    "run_id": "(optional) Re-fetch a cached run"
                }
            }
        ],
        "consumer_usage": {
            "step1": "pip install grpcio",
            "step2": f"python grpc_client_test.py --host {host} --port {port} --city Bangalore --format standard",
        }
    }
    out_path = os.path.join(ROOT, "grpc_connection_info.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
    return out_path


def main():
    log.info("=" * 60)
    log.info("  CUS SO  gRPC Public Launcher")
    log.info("=" * 60)

    # 1. Start gRPC server
    server = start_grpc_server_in_thread()

    # 2. Open ngrok tunnel
    log.info("Opening ngrok tunnel …")
    tunnel, public_url = start_ngrok_tunnel()
    host, port = parse_host_port(public_url)

    # 3. Write shareable connection file
    info_path = write_connection_file(host, port)

    # 4. Print consumer instructions
    print()
    print("=" * 60)
    print("  ✅  PUBLIC gRPC API IS LIVE")
    print("=" * 60)
    print(f"  Host  : {host}")
    print(f"  Port  : {port}")
    print(f"  URL   : {public_url}")
    print()
    print("  Share this with consumers:")
    print(f"    python grpc_client_test.py --host {host} --port {port} --city Bangalore")
    print()
    print(f"  Full connection info saved to: {info_path}")
    print("=" * 60)
    print("  Press Ctrl+C to stop the server and close the tunnel.")
    print()

    # 5. Keep alive
    def on_shutdown(sig, frame):
        log.info("Shutting down …")
        try:
            tunnel.close()
        except Exception:
            pass
        server.stop(grace=3)
        sys.exit(0)

    signal.signal(signal.SIGINT, on_shutdown)
    signal.signal(signal.SIGTERM, on_shutdown)

    while True:
        time.sleep(5)


if __name__ == "__main__":
    main()
