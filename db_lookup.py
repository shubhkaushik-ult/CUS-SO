import os
import json


CITY_FACILITY_ID = {
    "Bangalore":  9382,
    "Chennai":    9920,
    "Mumbai":     9892,
    "Hyderabad":  9575,
    "Trichy":     10112,
    "Coimbatore": 10071,
    "Nashik":     10078,
}

_DB_PRICE_BY_NAME_QUERY = """
SELECT DISTINCT
    s.Name              AS skuname,
    vssm.customer_price AS price
FROM cyclops.sku s
LEFT JOIN cyclops.sku_set_configuration ssc
    ON ssc.sku_id = s.id AND ssc.deleted = 0
LEFT JOIN cyclops.vendor_sku_set_map vssm
    ON vssm.sku_set_config_id = ssc.id AND vssm.deleted = 0
WHERE s.category_id = 4
  AND s.deleted IN (1, 0)
  AND vssm.reference_type = 'FACILITY'
  AND vssm.reference_id = %(facility_id)s
  AND s.Name IN %(name_list)s
"""

_DB_CONTACT_BY_NAME_QUERY = """
SELECT 
    name, 
    ContactNumber 
FROM asgard.Customer 
WHERE CityId = %(city_id)s
  AND name IN %(name_list)s
"""

CITY_ID_MAP = {
    "Bangalore":  2,
    "Chennai":    3,
    "Mumbai":     14,
    "Hyderabad":  13,
    "Trichy":     102,
    "Coimbatore": 90,
}


def _load_credentials(credentials_path: str) -> dict:
    """Load DB credentials from a JSON file."""
    if not os.path.exists(credentials_path):
        raise FileNotFoundError(
            f"DB credentials file not found at: {credentials_path}\n"
            "Please create 'db_credentials.json' with keys: host, port, user, password, database"
        )
    with open(credentials_path, "r") as f:
        return json.load(f)


def _get_connection(creds: dict):
    """Create a read-only MySQL connection."""
    import pymysql
    return pymysql.connect(
        host=creds.get("host"),
        port=int(creds.get("port", 3306)),
        user=creds.get("user"),
        password=creds.get("password"),
        database=creds.get("database", "cyclops"),
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
        # ── Enforce read-only session ──────────────────────────────
        init_command="SET SESSION TRANSACTION READ ONLY",
        autocommit=False,  # Prevent any accidental writes being auto-committed
    )


def fetch_price_by_name(name_list: list, city: str, credentials_path: str = None) -> dict:
    """
    Query MySQL DB for customer_price using SKU Name as the lookup key.

    Parameters
    ----------
    name_list        : list of SKU names (Titles) to look up — sourced from Allocation file
    city             : city name matching keys in CITY_FACILITY_ID
    credentials_path : path to db_credentials.json

    Returns
    -------
    dict keyed by skuname (str, lowercased for safe matching) → price (float or "NA")
    Returns empty dict on any failure so the caller gracefully falls back to "NA".
    """
    try:
        import pymysql
    except ImportError:
        print("       [DB WARN] pymysql is not installed. Run: pip install pymysql")
        return {}

    # Filter out blank / NA names
    clean_names = [
        str(n).strip() for n in name_list
        if n and str(n).strip() not in ("", "NA", "#N/A")
    ]

    if not clean_names:
        return {}

    facility_id = CITY_FACILITY_ID.get(city)
    if facility_id is None:
        print(f"       [DB WARN] No facility ID configured for city '{city}'. Skipping DB lookup.")
        return {}

    if credentials_path is None:
        credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_credentials.json")

    try:
        creds = _load_credentials(credentials_path)
    except FileNotFoundError as e:
        print(f"       [DB ERROR] Failed to fetch prices from DB: {e}")
        return {}

    result = {}
    conn = None
    try:
        conn = _get_connection(creds)

        with conn.cursor() as cursor:
            cursor.execute("START TRANSACTION READ ONLY")
            cursor.execute(
                _DB_PRICE_BY_NAME_QUERY,
                {"facility_id": facility_id, "name_list": tuple(clean_names)},
            )
            rows = cursor.fetchall()
            conn.rollback()  # Always rollback — we never write anything

        for row in rows:
            name_key = str(row["skuname"]).strip().lower()  # lowercase key for safe matching
            result[name_key] = row["price"] if row["price"] is not None else "NA"

        print(f"       [DB] Fetched price for {len(result)} SKUs from DB for {city} (facility {facility_id})")

    except Exception as e:
        print(f"       [DB WARN] DB price lookup failed: {e}")
    finally:
        if conn:
            conn.close()

    return result

def fetch_contact_by_name(name_list, city, credentials_path=None):
    """
    Given a list of Customer Names (or WH Codes), return a dictionary of {name: contact_number}.
    Queries the asgard.Customer table. Also attempts to fuzzy-match WH codes like 'mum_172_wh_hl_01'.
    """
    if not name_list:
        return {}

    city_id = CITY_ID_MAP.get(city)
    if not city_id:
        return {}
    city_ids = str(city_id)

    results = {}
    valid_names = [str(n).strip() for n in name_list if str(n).strip()]
    if not valid_names:
        return results

    if credentials_path is None:
        credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_credentials.json")

    try:
        credentials = _load_credentials(credentials_path)
        conn = _get_connection(credentials)
        with conn.cursor() as cursor:
            # First pass: Exact match
            cursor.execute(
                _DB_CONTACT_BY_NAME_QUERY,
                {"city_id": city_id, "name_list": tuple(valid_names)},
            )
            
            rows = cursor.fetchall()
            for row in rows:
                name = str(row['name']).strip().lower()
                contact = str(row['ContactNumber']).strip()
                if contact and contact.lower() not in ("0", "none", "nan", "null"):
                    results[name] = contact
                    
            # Second pass: Fuzzy match for WH Codes or Store Site IDs (e.g. 'mum_172_wh_hl_01' or 'mum_172_ulwe' -> 'mum_172%')
            for name in valid_names:
                lower_name = name.lower()
                if lower_name not in results:
                    parts = lower_name.split("_")
                    if len(parts) >= 2:
                        prefix = f"{parts[0]}_{parts[1]}%"
                        fuzzy_query = "SELECT name, ContactNumber FROM asgard.Customer WHERE CityId = %(city_id)s AND Name LIKE %(prefix)s LIMIT 1"
                        cursor.execute(fuzzy_query, {"city_id": city_id, "prefix": prefix})
                        fuzzy_row = cursor.fetchone()
                        if fuzzy_row:
                            contact = str(fuzzy_row['ContactNumber']).strip()
                            if contact and contact.lower() not in ("0", "none", "nan", "null"):
                                results[lower_name] = contact
                                
    except Exception as e:
        print(f"       [DB WARN] Error fetching contacts from DB: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

    return results