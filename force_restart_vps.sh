#!/bin/bash
#
# FORCE RESTART - Kill all Python processes and restart fresh
#

set -e

echo "════════════════════════════════════════════════════════════════"
echo "  FORCE RESTART APPLICATION"
echo "════════════════════════════════════════════════════════════════"
echo ""

cd /var/www/saroyarsir

echo "Step 1: Force sync code..."
git fetch origin main
git reset --hard origin/main
echo "  ✅ Code synchronized"
echo ""

echo "Step 2: Kill ALL Python processes..."
pkill -9 -f "python.*app.py" || echo "  (No processes to kill)"
pkill -9 -f "gunicorn" || echo "  (No gunicorn to kill)"
sleep 2
echo "  ✅ Old processes killed"
echo ""

echo "Step 3: Starting application..."
export FLASK_ENV=production
export PORT=8000

# Try systemd first
if systemctl restart saroyarsir 2>/dev/null; then
    echo "  ✅ Started via systemd"
else
    echo "  ⚠️ systemd failed, starting manually..."
    cd /var/www/saroyarsir
    nohup python3 app.py > logs/app.log 2>&1 &
    echo "  ✅ Started manually"
fi

sleep 3
echo ""

echo "Step 4: Verify process is running..."
if pgrep -f "python.*app.py" > /dev/null; then
    echo "  ✅ Python process is running!"
    pgrep -af "python.*app.py"
else
    echo "  ❌ WARNING: No Python process found!"
    echo "  Check logs/app.log for errors"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ RESTART COMPLETE"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Now refresh your browser (Ctrl+Shift+R) and check if attendance"
echo "column shows '/7' or '/8' instead of '/20'"
echo ""
