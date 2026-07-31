import db_lookup
conn = db_lookup._get_connection(db_lookup._load_credentials('db_credentials.json'))
try:
    with conn.cursor() as cursor:
        for db in ['asgard', 'cyclops']:
            cursor.execute(f"SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '{db}' AND DATA_TYPE IN ('varchar', 'char', 'text')")
            cols = cursor.fetchall()
            for col in cols:
                t = col['TABLE_NAME']
                c = col['COLUMN_NAME']
                try:
                    cursor.execute(f"SELECT {c} FROM {db}.{t} WHERE {c} = %s LIMIT 1", ('mum_172_wh_hl_01',))
                    if cursor.fetchone():
                        print(f"FOUND IN: {db}.{t}.{c}")
                except Exception:
                    pass
        print('Search finished.')
finally:
    conn.close()
