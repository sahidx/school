#!/bin/bash
#
# Deploy phoneNumber constraint fix to VPS
# This removes the UNIQUE constraint allowing siblings to share phone numbers
#

set -e

echo "════════════════════════════════════════════════════════════════"
echo "  Deploy phoneNumber Sibling Fix to VPS"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Configuration
VPS_USER="root"
VPS_HOST="103.145.51.132"
VPS_DIR="/var/www/saroyarsir"
DB_PATH="$VPS_DIR/smartgardenhub.db"

echo "📋 Pre-deployment checklist:"
echo "  • Remove UNIQUE constraint from phoneNumber column"
echo "  • Allow multiple students (siblings) to share one phone number"
echo "  • Backup production database before migration"
echo ""

# Step 1: Commit and push migration script
echo "Step 1: Committing migration script..."
git add fix_phone_unique_constraint.py check_phone_indexes.py
git commit -m "Add migration to remove phoneNumber UNIQUE constraint for sibling support" || echo "  No changes to commit"
git push origin main
echo "  ✅ Code pushed to repository"
echo ""

# Step 2: Pull changes on VPS
echo "Step 2: Pulling latest code on VPS..."
ssh ${VPS_USER}@${VPS_HOST} "cd ${VPS_DIR} && git pull origin main"
echo "  ✅ Code updated on VPS"
echo ""

# Step 3: Backup production database
echo "Step 3: Backing up production database..."
BACKUP_NAME="smartgardenhub_before_phone_fix_$(date +%Y%m%d_%H%M%S).db"
ssh ${VPS_USER}@${VPS_HOST} "cd ${VPS_DIR} && cp smartgardenhub.db backups/${BACKUP_NAME}" || {
    echo "  ⚠️  Backup directory might not exist, creating it..."
    ssh ${VPS_USER}@${VPS_HOST} "cd ${VPS_DIR} && mkdir -p backups && cp smartgardenhub.db backups/${BACKUP_NAME}"
}
echo "  ✅ Database backed up as: backups/${BACKUP_NAME}"
echo ""

# Step 4: Check current constraint status
echo "Step 4: Checking current constraint status on VPS..."
ssh ${VPS_USER}@${VPS_HOST} "cd ${VPS_DIR} && python3 check_phone_indexes.py"
echo ""

# Step 5: Run migration
echo "Step 5: Running migration to remove UNIQUE constraint..."
echo "  ⚠️  This will modify the production database!"
read -p "  Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "  ❌ Migration cancelled by user"
    exit 1
fi

ssh ${VPS_USER}@${VPS_HOST} "cd ${VPS_DIR} && python3 fix_phone_unique_constraint.py"
echo "  ✅ Migration completed"
echo ""

# Step 6: Verify fix
echo "Step 6: Verifying constraint removal..."
ssh ${VPS_USER}@${VPS_HOST} "cd ${VPS_DIR} && python3 check_phone_indexes.py"
echo ""

# Step 7: Restart application
echo "Step 7: Restarting application..."

# Try systemd first
if ssh ${VPS_USER}@${VPS_HOST} "systemctl restart saroyarsir 2>/dev/null"; then
    echo "  ✅ Application restarted via systemd"
else
    echo "  ⚠️  systemd restart failed, trying manual restart..."
    
    # Kill existing process and restart
    ssh ${VPS_USER}@${VPS_HOST} "cd ${VPS_DIR} && pkill -f 'python.*app.py' || true && nohup python3 app.py > logs/app.log 2>&1 &"
    sleep 3
    echo "  ✅ Application restarted manually"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ Deployment Complete!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📝 Summary:"
echo "  • phoneNumber UNIQUE constraint removed from production database"
echo "  • Multiple students can now share the same phone number (siblings)"
echo "  • Database backup saved: $BACKUP_NAME"
echo ""
echo "🧪 Test Instructions:"
echo "  1. Try adding a student with an existing phone number"
echo "  2. The system should allow it (for siblings sharing a guardian phone)"
echo "  3. Search/filter should show all students with that phone number"
echo ""
echo "💡 Next steps:"
echo "  • Add UI indicator when a phone number is shared by siblings"
echo "  • Consider adding 'sibling_group' column to link related students"
echo ""
