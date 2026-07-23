#!/usr/bin/env bash
# Salesforce Connected App for Pardot API — ONE COMMAND
# Prerequisites: sf CLI installed + logged in (sf login)
# Required: Salesforce admin with Pardot provisioned
#
# Usage: bash deploy/automation/salesforce_pardot_setup.sh

set -e

APP_NAME="CampaignOps-Pardot-Integration"

echo "=== Salesforce Connected App for Pardot ==="
echo ""

if ! command -v sf &>/dev/null; then
    echo "ERROR: Salesforce CLI not installed."
    echo "Install: npm install -g @salesforce/cli"
    exit 1
fi

if ! sf org list --json 2>/dev/null | grep -q '"connectedStatus"'; then
    echo "ERROR: Not logged into Salesforce. Run: sf login"
    exit 1
fi

echo "✓ Salesforce CLI authenticated"
echo ""

# Get Pardot Business Unit ID
echo "→ Looking up Pardot Business Unit..."
sf data query --query "SELECT Id, Name FROM BusinessUnit" --json 2>/dev/null > /tmp/bu.json
BU_COUNT=$(grep -c '"Id"' /tmp/bu.json 2>/dev/null || echo "0")

if [ "$BU_COUNT" -gt 0 ]; then
    BU_NAME=$(grep -o '"Name": "[^"]*"' /tmp/bu.json | head -1 | cut -d'"' -f4)
    BU_ID=$(grep -o '"Id": "[^"]*"' /tmp/bu.json | head -1 | cut -d'"' -f4)
    echo "✓ Found Pardot Business Unit: $BU_NAME ($BU_ID)"
else
    echo "⚠  Could not auto-detect Pardot Business Unit."
    echo "   Get it from: Pardot Settings → Business Unit ID"
    echo "   Or run: sf data query --query \"SELECT Id FROM BusinessUnit\""
    BU_ID="YOUR_PARDOT_BUSINESS_UNIT_ID"
fi
echo ""

# Create Connected App via metadata
echo "→ Creating Connected App metadata..."
cat > /tmp/campaignops_pardot_app.xml << EOF
<?xml version="1.0" encoding="UTF-8"?>
<ConnectedApp xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>$APP_NAME</label>
    <description>CampaignOps Kernel — Pardot API integration for lead sync and nurture</description>
    <contactEmail>\${CONTACT_EMAIL}</contactEmail>
    <oauthConfig>
        <callbackUrl>http://localhost:8000/callback</callbackUrl>
        <scopes>api pardot_api refresh_token offline_access</scopes>
        <isAdminApproved>true</isAdminApproved>
    </oauthConfig>
</ConnectedApp>
EOF

echo "✓ Connected App metadata created at /tmp/campaignops_pardot_app.xml"
echo ""
echo "============================================"
echo "  MANUAL STEP REQUIRED"
echo "============================================"
echo ""
echo "Salesforce Connected Apps require UI deployment. The metadata is ready."
echo ""
echo "1. Go to: Setup → App Manager → New Connected App"
echo "2. Name: $APP_NAME"
echo "3. Enable OAuth Settings"
echo "4. Callback URL: http://localhost:8000/callback"
echo "5. Selected OAuth Scopes:"
echo "   - Access Pardot services (pardot_api)"
echo "   - Perform requests on your behalf (api)"
echo "   - Refresh token (refresh_token)"
echo "   - Access data offline (offline_access)"
echo "6. Save → Copy Consumer Key and Consumer Secret"
echo ""
if [ "$BU_ID" != "YOUR_PARDOT_BUSINESS_UNIT_ID" ]; then
    echo "Pardot Business Unit ID: $BU_ID"
fi
echo ""
echo "Then copy to your .env file:"
echo ""
echo "  PARDOT_BUSINESS_UNIT_ID=$BU_ID"
echo "  PARDOT_CLIENT_ID=<Consumer Key from step 6>"
echo "  PARDOT_CLIENT_SECRET=<Consumer Secret from step 6>"
echo "  PARDOT_SF_USERNAME=<your-salesforce-username>"
echo "  PARDOT_SF_PASSWORD=<password+security-token>"
echo ""
echo "After setting .env, test with:"
echo "  python -c \"from integrations.pardot.client import PardotClient; print('Pardot OK')\""
echo ""
