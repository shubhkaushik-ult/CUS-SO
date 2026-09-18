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
    s.Name AS skuname,
    ssc.sku_id,
    vssm.reference_id,
    vssm.customer_price AS price
FROM cyclops.sku s
LEFT JOIN cyclops.sku_set_configuration ssc
    ON ssc.sku_id = s.id AND ssc.deleted = 0
LEFT JOIN cyclops.vendor_sku_set_map vssm
    ON vssm.sku_set_config_id = ssc.id AND vssm.deleted = 0
WHERE s.deleted IN (1, 0)
  AND vssm.reference_type = 'FACILITY'
  AND vssm.reference_id in %(facility_id)s
  AND s.name in %(name_list)s
"""

_DB_CONTACT_LOOKUP_QUERY = """
SELECT 
    Id,
    Name, 
    ContactNumber 
FROM asgard.Customer 
WHERE CityId = %(city_id)s
  AND (
    Name IN %(keys)s 
    OR Id IN %(keys)s
  )
"""

_DB_CONTACT_LOOKUP_GLOBAL_QUERY = """
SELECT 
    Id,
    Name, 
    ContactNumber 
FROM asgard.Customer 
WHERE Name IN %(keys)s 
   OR Id IN %(keys)s
"""


CITY_ID_MAP = {
    "Bangalore":  2,
    "Chennai":    3,
    "Mumbai":     14,
    "Hyderabad":  13,
    "Trichy":     102,
    "Coimbatore": 90,
    "Nashik":     8,
}

_DB_SKU_LOOKUP_QUERY = """
SELECT DISTINCT
    peim.fsnCode           AS fsn,
    s.Id                   AS sku_id,
    s.Name                 AS sku_name,
    peim.lotWeightId       AS lot_id,
    peim.cityId            AS city_id
FROM asgard.Sku s
JOIN vormir.ProductExternalInternalMapping peim
    ON peim.skuId = s.Id
WHERE s.Deleted IN (0, 1)
  AND peim.cityId = %(city_id)s
  AND peim.fsnCode IN %(fsn_list)s
"""




def fetch_skus_from_db(fsn_list: list, city: str, credentials_path: str = None) -> dict:
    """
    Query MySQL DB for SKU Id, Sku Name, Lot Weight ID directly using FSN and City.

    Returns dict keyed by FSN:
    {
        'FSN_CODE': {
            'sku_id': int/str,
            'sku_name': str,
            'lot_id': int/str,
            'city_id': int
        }
    }
    """
    if not fsn_list:
        return {}

    city_id = CITY_ID_MAP.get(city)
    if not city_id:
        print(f"       [DB WARN] Unknown city '{city}' for DB lookup.")
        return {}

    clean_fsns = list(set(
        str(f).strip().upper().replace('.0', '') for f in fsn_list
        if f and str(f).strip() not in ("", "NA", "#N/A")
    ))

    if not clean_fsns:
        return {}

    if credentials_path is None:
        credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_credentials.json")

    try:
        creds = _load_credentials(credentials_path)
    except FileNotFoundError as e:
        print(f"       [DB ERROR] Failed to load DB credentials: {e}")
        return {}

    results = {}
    conn = None
    try:
        conn = _get_connection(creds)
        with conn.cursor() as cursor:
            cursor.execute("START TRANSACTION READ ONLY")
            cursor.execute(
                _DB_SKU_LOOKUP_QUERY,
                {"city_id": city_id, "fsn_list": tuple(clean_fsns)},
            )
            rows = cursor.fetchall()
            conn.rollback()

        for row in rows:
            fsn_key = str(row["fsn"]).strip().upper()
            results[fsn_key] = {
                "sku_id": row["sku_id"],
                "sku_name": row["sku_name"],
                "lot_id": row["lot_id"],
                "city_id": row["city_id"]
            }
        print(f"       [DB] Directly fetched {len(results)}/{len(clean_fsns)} SKUs from DB for {city} (CityId {city_id})")
    except Exception as e:
        print(f"       [DB WARN] Error fetching SKUs from DB: {e}")
    finally:
        if conn:
            conn.close()

    return results



def _load_credentials(credentials_path: str = None) -> dict:
    """Load DB credentials from environment variables or a JSON file."""
    # 1. Check environment variables first (ideal for Railway / Cloud deployment)
    if os.getenv("DB_HOST") and os.getenv("DB_USER") and os.getenv("DB_PASSWORD"):
        return {
            "host": os.getenv("DB_HOST"),
            "port": int(os.getenv("DB_PORT", 6033)),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "database": os.getenv("DB_DATABASE", "cyclops")
        }

    # 2. Fall back to JSON file
    if credentials_path is None:
        credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_credentials.json")

    if not os.path.exists(credentials_path):
        raise FileNotFoundError(
            f"DB credentials not found in env vars and file not found at: {credentials_path}\n"
            "Please set DB_HOST, DB_USER, DB_PASSWORD in .env or create 'db_credentials.json'"
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
                {"facility_id": (facility_id,), "name_list": tuple(clean_names)},
            )
            rows = cursor.fetchall()
            conn.rollback()  # Always rollback — we never write anything

        for row in rows:
            name_key = str(row["skuname"]).strip().lower()  # lowercase key for safe matching
            result[name_key] = {
                "price": row["price"] if row["price"] is not None else "NA",
                "sku_id": row["sku_id"]
            }

        print(f"       [DB] Fetched price for {len(result)} SKUs from DB for {city} (facility {facility_id})")

    except Exception as e:
        print(f"       [DB WARN] DB price lookup failed: {e}")
    finally:
        if conn:
            conn.close()

    return result

def fetch_contact_by_name(key_list, city, credentials_path=None):
    """
    Given a list of Customer IDs or Warehouse Names, return a dictionary of {key: contact_number}.
    Queries the asgard.Customer table matching against both Customer.Id and Customer.Name.
    """
    if not key_list:
        return {}

    city_id = CITY_ID_MAP.get(city)
    if not city_id:
        return {}

    results = {}
    valid_keys = [str(k).strip() for k in key_list if k and str(k).strip()]
    if not valid_keys:
        return results

    if credentials_path is None:
        credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_credentials.json")

    try:
        credentials = _load_credentials(credentials_path)
        conn = _get_connection(credentials)
        with conn.cursor() as cursor:
            cursor.execute(
                _DB_CONTACT_LOOKUP_QUERY,
                {"city_id": city_id, "keys": tuple(valid_keys)},
            )
            
            rows = cursor.fetchall()
            for row in rows:
                cust_id = str(row['Id']).strip().lower()
                name = str(row['Name']).strip().lower()
                contact = str(row['ContactNumber']).strip()
                
                if contact and contact.lower() not in ("0", "none", "nan", "null"):
                    results[cust_id] = contact
                    results[name] = contact

            # Pass 1.5: Global fallback across all cities for any missing store keys (e.g. Rta_113_Thanjavur registered under Coimbatore CityId 90)
            missing_keys = [k for k in valid_keys if k.lower() not in results]
            if missing_keys:
                cursor.execute(
                    _DB_CONTACT_LOOKUP_GLOBAL_QUERY,
                    {"keys": tuple(missing_keys)},
                )
                global_rows = cursor.fetchall()
                for row in global_rows:
                    cust_id = str(row['Id']).strip().lower()
                    name = str(row['Name']).strip().lower()
                    contact = str(row['ContactNumber']).strip()
                    if contact and contact.lower() not in ("0", "none", "nan", "null"):
                        results[cust_id] = contact
                        results[name] = contact
                    
            # Second pass: Fuzzy match for WH Codes or Store Site IDs (e.g. 'mum_172_wh_hl_01' -> 'mum_172%')

            for key in valid_keys:
                lower_key = key.lower()
                if lower_key not in results:
                    parts = lower_key.split("_")
                    if len(parts) >= 2:
                        prefix = f"{parts[0]}_{parts[1]}%"
                        fuzzy_query = "SELECT Id, Name, ContactNumber FROM asgard.Customer WHERE CityId = %(city_id)s AND Name LIKE %(prefix)s LIMIT 1"
                        cursor.execute(fuzzy_query, {"city_id": city_id, "prefix": prefix})
                        fuzzy_row = cursor.fetchone()
                        if fuzzy_row:
                            contact = str(fuzzy_row['ContactNumber']).strip()
                            if contact and contact.lower() not in ("0", "none", "nan", "null"):
                                results[lower_key] = contact
                                
    except Exception as e:
        print(f"       [DB WARN] Error fetching contacts from DB: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

    return results
