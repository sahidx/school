#!/bin/bash
# Fix SMS balance - Deploy and restart Gunicorn to load /api/sms/personal-balance endpoint

echo "=== Step 1: Verify endpoint exists in code ==="
cd /var/www/saroyarsir
grep -n "personal-balance" routes/sms.py | head -3

echo ""
echo "=== Step 2: Hard stop Gunicorn and clean PID file ==="
sudo systemctl stop saroyarsir
sudo pkill -9 -f "gunicorn.*saroyarsir"
sudo rm -f /tmp/smartgarden-hub.pid
sleep 2

echo ""
echo "=== Step 3: Start service ==="
sudo systemctl start saroyarsir
sleep 3

echo ""
echo "=== Step 4: Check service status ==="
sudo systemctl status saroyarsir --no-pager -l | head -15

echo ""
echo "=== Step 5: Test endpoint (expect 401/302, NOT 404) ==="
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/api/sms/personal-balance)
echo "HTTP Status: $HTTP_CODE"

if [ "$HTTP_CODE" = "404" ]; then
    echo "❌ ERROR: Still getting 404 - endpoint not loaded"
    exit 1
elif [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "302" ]; then
    echo "✅ SUCCESS: Endpoint exists (needs authentication)"
    echo ""
    echo "Now refresh your teacher dashboard (Ctrl+Shift+R) and SMS balance should show 1000"
    exit 0
else
    echo "⚠️  Got unexpected status: $HTTP_CODE"
    exit 1
fi
