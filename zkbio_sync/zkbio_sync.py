"""
zkbio_sync.py
=============
Reads attendance punch records from ZKBio Time.Net and pushes them
to the school app's biometric-sync API.

Supports ALL ZKBio database types:
  - SQLite   (most common in small installs — a .db file)
  - MySQL    (larger installs with bundled MySQL)
  - SQL Server (enterprise installs)

Run on Windows (where ZKBio Time.Net is installed):
    python zkbio_sync.py              # sync today
    python zkbio_sync.py 2026-02-28  # sync specific date

TIP: Run find_zkbio_db.py FIRST to auto-detect your database.

Requirements:
    pip install requests

Extra (only install what matches your db_type):
    SQLite    : nothing extra — built into Python
    MySQL     : pip install mysql-connector-python
    SQL Server: pip install pyodbc
"""

import sys, json, logging, sqlite3
from datetime import datetime, date
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("ERROR: Run:  pip install requests")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)s  %(message)s',
    handlers=[
        logging.FileHandler('zkbio_sync.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)
CONFIG_FILE = Path(__file__).parent / 'zkbio_config.json'

# ─── SQL that works across ZKBio versions ────────────────────────────────────
# ZKBio stores punches in:
#   att_attlog (att column = punch_time, emp_code = employee code)
#   punch_state: 0=check_in  1=check_out  4=OT_in  5=OT_out
# Some versions use iclock_transaction instead.
QUERIES = [
    # Standard table (most versions)
    "SELECT emp_code, punch_time, punch_state FROM att_attlog WHERE {date_filter} ORDER BY emp_code, punch_time",
    # Fallback table name
    "SELECT emp_code, att_date as punch_time, punch_state FROM att_attrecord WHERE {date_filter} ORDER BY emp_code, att_date",
    # Very old firmware
    "SELECT user_id as emp_code, att_time as punch_time, 0 as punch_state FROM att_log WHERE {date_filter} ORDER BY user_id, att_time",
]

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        log.error(f'Config not found: {CONFIG_FILE}')
        log.error('Run find_zkbio_db.py first, or copy zkbio_config.example.json')
        sys.exit(1)
    with open(CONFIG_FILE, encoding='utf-8') as f:
        return json.load(f)

# ─── Database connectors ──────────────────────────────────────────────────────

def connect_sqlite(cfg: dict):
    db_path = cfg['zkbio_db']['path']
    if not Path(db_path).exists():
        log.error(f'SQLite file not found: {db_path}')
        sys.exit(1)
    log.info(f'SQLite → {db_path}')
    return sqlite3.connect(db_path)

def connect_mysql(cfg: dict):
    try:
        import mysql.connector
    except ImportError:
        sys.exit("ERROR: Run:  pip install mysql-connector-python")
    c = cfg['zkbio_db']
    log.info(f"MySQL → {c.get('host','127.0.0.1')}:{c.get('port',3306)}/{c.get('database','att')}")
    return mysql.connector.connect(
        host=c.get('host','127.0.0.1'), port=int(c.get('port',3306)),
        user=c['user'], password=c['password'],
        database=c.get('database','att'),
    )

def connect_sqlserver(cfg: dict):
    try:
        import pyodbc
    except ImportError:
        sys.exit("ERROR: Run:  pip install pyodbc")
    c = cfg['zkbio_db']
    cs = (f"DRIVER={{ODBC Driver 17 for SQL Server}};"
          f"SERVER={c.get('host','localhost')};"
          f"DATABASE={c.get('database','att')};"
          f"UID={c['user']};PWD={c['password']}")
    log.info(f"SQL Server → {c.get('host')} / {c.get('database')}")
    import pyodbc
    return pyodbc.connect(cs)

def get_connection(cfg: dict):
    db_type = cfg['zkbio_db'].get('type','sqlite').lower()
    if db_type == 'sqlite':    return connect_sqlite(cfg),    'sqlite'
    if db_type == 'mysql':     return connect_mysql(cfg),     'mysql'
    if db_type in ('sqlserver','mssql'): return connect_sqlserver(cfg), 'sqlserver'
    sys.exit(f'Unknown db_type: {db_type}  (must be sqlite / mysql / sqlserver)')

# ─── Read punches ─────────────────────────────────────────────────────────────

def get_zkbio_punches(cfg: dict, sync_date: date) -> list:
    conn, db_type = get_connection(cfg)
    rows = []
    date_str = sync_date.strftime('%Y-%m-%d')

    # SQLite uses DATE(punch_time), MySQL/MSSQL too
    if db_type == 'sqlserver':
        date_filter = "CAST(punch_time AS DATE) = ?"
        param = date_str
    else:
        date_filter = "DATE(punch_time) = ?"
        param = date_str

    for q_template in QUERIES:
        q = q_template.format(date_filter=date_filter)
        try:
            cur = conn.cursor()
            cur.execute(q, (param,))
            rows = cur.fetchall()
            # Convert sqlite3.Row / dict / tuple to plain dicts
            converted = []
            for r in rows:
                if hasattr(r, 'keys'):  # dict-like (mysql)
                    converted.append(dict(r))
                else:                   # tuple (sqlite/sqlserver)
                    converted.append({
                        'emp_code':    str(r[0]),
                        'punch_time':  r[1],
                        'punch_state': r[2] if len(r) > 2 else 0,
                    })
            rows = converted
            log.info(f'Query OK ({len(rows)} rows): {q[:60]}...')
            break
        except Exception as e:
            log.warning(f'Query failed, trying next: {e}')
            continue

    conn.close()
    if not rows:
        log.warning('No punch data found for this date.')
        return []

    # Aggregate: earliest in, latest out per employee
    emp: dict = {}
    for r in rows:
        code  = str(r.get('emp_code','')).strip()
        ptime = r.get('punch_time')
        state = int(r.get('punch_state', 0))
        if isinstance(ptime, str):
            try: ptime = datetime.strptime(ptime, '%Y-%m-%d %H:%M:%S')
            except: ptime = datetime.strptime(ptime[:16], '%Y-%m-%d %H:%M')

        if code not in emp:
            emp[code] = {'check_in': None, 'check_out': None, 'all': []}
        emp[code]['all'].append(ptime)
        if state in (0, 4):
            if emp[code]['check_in'] is None or ptime < emp[code]['check_in']:
                emp[code]['check_in'] = ptime
        elif state in (1, 5):
            if emp[code]['check_out'] is None or ptime > emp[code]['check_out']:
                emp[code]['check_out'] = ptime

    result = []
    for code, d in emp.items():
        ci = d['check_in'] or (d['all'][0] if d['all'] else None)
        co = d['check_out']
        result.append({
            'emp_code':  code,
            'check_in':  ci.strftime('%H:%M') if ci else None,
            'check_out': co.strftime('%H:%M') if co else None,
        })

    log.info(f'Punches: {len(rows)} events → {len(result)} employees')
    return result


def build_records(punches: list, mapping: dict, sync_date: date, late_after='09:00') -> list:
    punched = {p['emp_code'] for p in punches}
    records = []
    for p in punches:
        sid = mapping.get(p['emp_code'])
        if not sid:
            log.warning(f'No mapping for emp_code={p["emp_code"]} — skipping')
            continue
        status = 'late' if (p['check_in'] and p['check_in'] > late_after) else 'present'
        records.append({'student_id': int(sid), 'date': sync_date.strftime('%Y-%m-%d'),
                        'status': status, 'check_in': p['check_in'], 'check_out': p['check_out']})
    for code, sid in mapping.items():
        if code not in punched:
            records.append({'student_id': int(sid), 'date': sync_date.strftime('%Y-%m-%d'), 'status': 'absent'})
    return records


def push_to_school(cfg: dict, records: list):
    sc  = cfg['school_app']
    url = sc['url'].rstrip('/') + '/api/attendance/biometric-sync'
    payload = {'api_key': sc['api_key'], 'batch_id': sc.get('batch_id'), 'records': records}
    log.info(f'Sending {len(records)} records → {url}')
    r = requests.post(url, json=payload, timeout=30)
    if r.status_code == 200:
        d = r.json().get('message', {})
        log.info(f'✅  created={d.get("created")}  updated={d.get("updated")}  skipped={d.get("skipped")}')
        for e in (d.get('errors') or []):
            log.warning(f'Server: {e}')
    else:
        log.error(f'❌  HTTP {r.status_code}: {r.text[:300]}')


def main():
    cfg = load_config()
    sync_date = date.today()
    if len(sys.argv) > 1:
        try:    sync_date = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
        except: sys.exit('Date must be YYYY-MM-DD')

    log.info(f'━━━ ZKBio → School sync  date={sync_date} ━━━')
    punches = get_zkbio_punches(cfg, sync_date)
    records = build_records(punches, cfg.get('student_mapping', {}),
                            sync_date, cfg.get('late_after', '09:00'))
    if records:
        push_to_school(cfg, records)
    else:
        log.info('No records to send.')

if __name__ == '__main__':
    main()
