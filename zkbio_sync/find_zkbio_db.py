"""
find_zkbio_db.py
================
Run this FIRST on your Windows PC to auto-detect your ZKBio database.
It will scan common install locations and write zkbio_config.json for you.

Usage:
    python find_zkbio_db.py
"""

import os, sys, json, sqlite3, glob
from pathlib import Path

COMMON_PATHS = [
    r"C:\Program Files\ZKBio Time.Net",
    r"C:\Program Files (x86)\ZKBio Time.Net",
    r"C:\ZKBio Time.Net",
    r"C:\ZKBioTime",
    r"C:\zkbiotime",
    r"C:\Program Files\ZKTime.Net",
    r"D:\ZKBio Time.Net",
    r"D:\Program Files\ZKBio Time.Net",
]

CONFIG_OUT = Path(__file__).parent / 'zkbio_config.json'
EXAMPLE    = Path(__file__).parent / 'zkbio_config.example.json'


def find_sqlite_files():
    """Search for .db files under ZKBio install dirs"""
    found = []
    for base in COMMON_PATHS:
        if not Path(base).exists():
            continue
        for f in Path(base).rglob('*.db'):
            found.append(str(f))
        for f in Path(base).rglob('*.sqlite'):
            found.append(str(f))
        for f in Path(base).rglob('*.sqlite3'):
            found.append(str(f))
    return found


def test_sqlite_db(path: str) -> bool:
    """Check if this SQLite file has ZKBio attendance tables"""
    try:
        conn = sqlite3.connect(path)
        cur  = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0].lower() for r in cur.fetchall()}
        conn.close()
        zkbio_tables = {'att_attlog', 'att_attrecord', 'att_log', 'hr_employee',
                        'iclock_transaction', 'att_payperiod'}
        matched = tables & zkbio_tables
        if matched:
            print(f'  ✅  ZKBio tables found: {matched}')
            return True
        return False
    except Exception as e:
        print(f'  ⚠  Could not read {path}: {e}')
        return False


def find_mysql_config():
    """Look for ZKBio datasource.properties files with MySQL credentials"""
    results = []
    for base in COMMON_PATHS:
        if not Path(base).exists():
            continue
        for f in Path(base).rglob('datasource.properties'):
            results.append(str(f))
        for f in Path(base).rglob('application.properties'):
            results.append(str(f))
        for f in Path(base).rglob('*.properties'):
            results.append(str(f))
    return results


def parse_properties(path: str) -> dict:
    props = {}
    try:
        with open(path, encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, _, v = line.partition('=')
                    props[k.strip()] = v.strip()
    except Exception:
        pass
    return props


def main():
    print("=" * 60)
    print(" ZKBio Time.Net Database Auto-Detector")
    print("=" * 60)

    found_db   = None
    found_type = None
    found_cfg  = {}

    # ── 1. Search for SQLite files ─────────────────────────────
    print("\n[1] Searching for SQLite database files...")
    db_files = find_sqlite_files()
    if db_files:
        for db in db_files:
            print(f'\n  Found: {db}')
            if test_sqlite_db(db):
                found_db   = db
                found_type = 'sqlite'
                found_cfg  = {'type': 'sqlite', 'path': db}
                break
    else:
        print("  No SQLite files found in common ZKBio install locations.")

    # ── 2. Search for MySQL / properties config ────────────────
    if not found_db:
        print("\n[2] Searching for MySQL/database config files...")
        prop_files = find_mysql_config()
        for pf in prop_files:
            props = parse_properties(pf)
            # Check for MySQL JDBC URL
            url = props.get('spring.datasource.url', props.get('jdbc.url', ''))
            user = props.get('spring.datasource.username', props.get('jdbc.username', ''))
            pwd  = props.get('spring.datasource.password', props.get('jdbc.password', ''))
            if 'mysql' in url.lower() and user:
                import re
                m = re.search(r'//([^:/]+):?(\d+)?/(\w+)', url)
                host = m.group(1) if m else '127.0.0.1'
                port = int(m.group(2)) if m and m.group(2) else 3306
                db   = m.group(3) if m else 'att'
                print(f'  ✅  MySQL config found in {pf}')
                print(f'      host={host} port={port} db={db} user={user}')
                found_type = 'mysql'
                found_cfg  = {'type':'mysql','host':host,'port':port,
                              'database':db,'user':user,'password':pwd}
                break
            if 'sqlserver' in url.lower() or 'mssql' in url.lower():
                print(f'  ✅  SQL Server config found in {pf}')
                found_type = 'sqlserver'
                found_cfg  = {'type':'sqlserver','host':'localhost',
                              'database':'att','user':user,'password':pwd}
                break

    # ── 3. Manual fallback ─────────────────────────────────────
    if not found_type:
        print("\n  Could not auto-detect. Let's set it up manually.")
        print("\n  What database does ZKBio use on your PC?")
        print("  [1] SQLite  (most likely for small school)")
        print("  [2] MySQL")
        print("  [3] SQL Server")
        choice = input("  Enter 1, 2 or 3: ").strip()

        if choice == '1':
            path = input("  Full path to the .db file: ").strip()
            found_type = 'sqlite'
            found_cfg  = {'type':'sqlite','path':path}
        elif choice == '2':
            host = input("  MySQL host [127.0.0.1]: ").strip() or '127.0.0.1'
            pwd  = input("  MySQL password: ").strip()
            found_type = 'mysql'
            found_cfg  = {'type':'mysql','host':host,'port':3306,
                          'database':'att','user':'root','password':pwd}
        elif choice == '3':
            host = input("  SQL Server host [localhost]: ").strip() or 'localhost'
            user = input("  Username: ").strip()
            pwd  = input("  Password: ").strip()
            found_type = 'sqlserver'
            found_cfg  = {'type':'sqlserver','host':host,'database':'att',
                          'user':user,'password':pwd}
        else:
            print("  Invalid choice. Exiting.")
            sys.exit(1)

    # ── 4. Load example config and merge ──────────────────────
    if EXAMPLE.exists():
        with open(EXAMPLE, encoding='utf-8') as f:
            cfg = json.load(f)
        # Remove comments
        cfg = {k: v for k, v in cfg.items() if not k.startswith('_')}
        cfg['zkbio_db'] = found_cfg
    else:
        cfg = {
            'zkbio_db': found_cfg,
            'school_app': {
                'url':      'https://opulent-sniffle-5g6jv5vv4xjwfj7v.github.dev',
                'api_key':  'PASTE_YOUR_KEY_HERE',
                'batch_id': 1,
            },
            'late_after': '09:00',
            'student_mapping': {},
        }

    # ── 5. Write config ───────────────────────────────────────
    with open(CONFIG_OUT, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)

    print(f"\n✅  Written: {CONFIG_OUT}")
    print(f"   db_type = {found_type}")
    print("\nNext steps:")
    print("  1. Open zkbio_config.json")
    print("  2. Set school_app.api_key  (get it from your school app admin)")
    print("  3. Fill student_mapping: { \"001\": 2, \"002\": 3, ... }")
    print("  4. Run:  python zkbio_sync.py")


if __name__ == '__main__':
    main()
