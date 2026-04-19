"""
Run once to register school_logo in the database.
Usage:
    python3 set_logo.py path/to/logo.png
    python3 set_logo.py              # looks for logo.png in current directory
"""
import sys, os, shutil, base64, sqlite3

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
STATIC_DEST = os.path.join(SCRIPT_DIR, 'static', 'static', 'images', 'school_logo.png')
DB_PATH     = os.path.join(SCRIPT_DIR, 'school.db')
LOGO_URL    = '/static/images/school_logo.png'   # URL served by Flask

# ── find source image ──────────────────────────────────────
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SCRIPT_DIR, 'logo.png')
if not os.path.exists(src):
    print(f"ERROR: Logo file not found at: {src}")
    print("  1. Save the logo image to: /workspaces/school/logo.png")
    print("  2. Re-run:  python3 set_logo.py")
    sys.exit(1)

# ── copy to static ─────────────────────────────────────────
os.makedirs(os.path.dirname(STATIC_DEST), exist_ok=True)
shutil.copy2(src, STATIC_DEST)
print(f"✓ Logo copied → {STATIC_DEST}")

# ── encode as base64 data-URI (used everywhere in DB) ──────
with open(STATIC_DEST, 'rb') as f:
    logo_b64 = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()

# ── update school_info table ───────────────────────────────
conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()
cur.execute("SELECT id FROM school_info WHERE key='school_logo'")
row = cur.fetchone()
if row:
    cur.execute("UPDATE school_info SET value=? WHERE key='school_logo'", (logo_b64,))
else:
    cur.execute("INSERT INTO school_info (key, value) VALUES ('school_logo', ?)", (logo_b64,))
conn.commit()
conn.close()

print(f"✓ school_logo saved to database ({len(logo_b64)//1024} KB)")
print("✓ Done! Restart Flask to see the logo everywhere.")
