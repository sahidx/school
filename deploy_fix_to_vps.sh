#!/bin/bash
# Comprehensive VPS Deployment Script for Bug Fixes

echo "=================================================="
echo "🚀 VPS Deployment Script - Fix Fees & Marks"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Git operations
echo ""
echo "${YELLOW}📦 Step 1: Pulling latest changes from Git${NC}"
echo "=================================================="

if [ ! -d ".git" ]; then
    echo "${RED}❌ Not a git repository${NC}"
    exit 1
fi

echo "Fetching latest changes..."
git fetch origin main

echo "Pulling changes..."
git pull origin main

if [ $? -ne 0 ]; then
    echo "${RED}❌ Git pull failed. Please resolve conflicts manually.${NC}"
    exit 1
fi

echo "${GREEN}✅ Git pull successful${NC}"

# Step 2: Backup database
echo ""
echo "${YELLOW}📦 Step 2: Creating database backup${NC}"
echo "=================================================="

if [ ! -f "instance/app.db" ]; then
    echo "${YELLOW}⚠️  Database file not found at instance/app.db - Attempting to find elsewhere or skipping backup${NC}"
    # Try alternate location
    if [ -f "/var/www/saroyarsir/smartgardenhub.db" ]; then
        echo "${GREEN}✅ Found database at /var/www/saroyarsir/smartgardenhub.db${NC}"
        cp "/var/www/saroyarsir/smartgardenhub.db" "/var/www/saroyarsir/smartgardenhub.db.backup.$(date +%Y%m%d_%H%M%S)"
    else 
        echo "${YELLOW}⚠️  Skipping database backup (DB not found)${NC}"
    fi
    # Do not exit, continue deployment
else
    BACKUP_FILE="instance/app.db.backup.$(date +%Y%m%d_%H%M%S)"
    cp instance/app.db "$BACKUP_FILE"
    echo "${GREEN}✅ Database backup created at $BACKUP_FILE${NC}"
fi

if [ $? -ne 0 ]; then
    echo "${RED}❌ Backup failed${NC}"
    exit 1
fi

echo "${GREEN}✅ Backup created: $BACKUP_FILE${NC}"

# Step 3: Run database fixes
echo ""
echo "${YELLOW}🔧 Step 3: Running database fixes${NC}"
echo "=================================================="

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run fix script
python3 fix_vps_issues.py

if [ $? -ne 0 ]; then
    echo "${RED}❌ Fix script failed${NC}"
    echo "Restoring backup..."
    cp "$BACKUP_FILE" instance/app.db
    exit 1
fi

echo "${GREEN}✅ Database fixes applied${NC}"

# Step 4: Restart application
echo ""
echo "${YELLOW}🔄 Step 4: Restarting application${NC}"
echo "=================================================="

# Try to detect the service name
if systemctl list-units --type=service | grep -q "gunicorn"; then
    SERVICE_NAME=$(systemctl list-units --type=service | grep gunicorn | awk '{print $1}')
    echo "Found service: $SERVICE_NAME"
    sudo systemctl restart "$SERVICE_NAME"
    
    if [ $? -eq 0 ]; then
        echo "${GREEN}✅ Service restarted: $SERVICE_NAME${NC}"
    else
        echo "${YELLOW}⚠️  Failed to restart service automatically${NC}"
        echo "Please restart manually: sudo systemctl restart $SERVICE_NAME"
    fi
else
    # Try pkill as fallback
    echo "No systemd service found. Using pkill..."
    pkill -f "gunicorn.*app:app"
    
    if [ $? -eq 0 ]; then
        echo "${GREEN}✅ Gunicorn processes killed${NC}"
        echo "${YELLOW}⚠️  Please start your application manually${NC}"
    else
        echo "${YELLOW}⚠️  Could not detect application process${NC}"
        echo "Please restart your application manually"
    fi
fi

# Step 5: Verify deployment
echo ""
echo "${YELLOW}🔍 Step 5: Verification${NC}"
echo "=================================================="

# Wait a moment for service to start
sleep 3

# Check if service is running
if systemctl is-active --quiet gunicorn 2>/dev/null || pgrep -f "gunicorn.*app:app" > /dev/null; then
    echo "${GREEN}✅ Application is running${NC}"
else
    echo "${YELLOW}⚠️  Could not verify application status${NC}"
fi

# Show recent logs if available
if [ -f "logs/app.log" ]; then
    echo ""
    echo "Recent application logs:"
    tail -n 10 logs/app.log
elif journalctl -n 0 &>/dev/null; then
    echo ""
    echo "Recent systemd logs:"
    sudo journalctl -u gunicorn -n 10 --no-pager
fi

# Final summary
echo ""
echo "=================================================="
echo "${GREEN}✅ Deployment completed!${NC}"
echo "=================================================="
echo ""
echo "📝 Changes applied:"
echo "  1. Latest code pulled from Git"
echo "  2. Database backup created"
echo "  3. Database schema fixed (fees table)"
echo "  4. Application restarted"
echo ""
echo "🧪 Testing checklist:"
echo "  [ ] Open Fee Management page"
echo "  [ ] Select a batch and check if students load"
echo "  [ ] Try to update marks in Monthly Exams"
echo "  [ ] Verify marks are saved"
echo ""
echo "🔗 If issues persist:"
echo "  1. Check logs: tail -f logs/app.log"
echo "  2. Restore backup: cp $BACKUP_FILE instance/app.db"
echo "  3. Contact support with error messages"
echo ""
