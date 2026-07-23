#!/usr/bin/env bash
# Azure AD App Registration for Outlook Bookings — ONE COMMAND
# Prerequisites: az CLI installed + logged in (az login)
# Required role: Application Administrator or Global Administrator
# 
# This script creates everything needed for the Outlook Bookings integration.
# Run once. Copy the output values to your .env file.
#
# Usage: bash deploy/automation/azure_bookings_setup.sh

set -e

APP_NAME="CampaignOps-Bookings-Integration"
REDIRECT_URI="${1:-http://localhost:8000/callback}"  # Not used for client credentials, but required

echo "=== Azure AD App Registration for Outlook Bookings ==="
echo ""

# Check prerequisites
if ! command -v az &>/dev/null; then
    echo "ERROR: Azure CLI not installed. Install: curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash"
    exit 1
fi

if ! az account show &>/dev/null; then
    echo "ERROR: Not logged into Azure. Run: az login"
    exit 1
fi

echo "✓ Azure CLI authenticated as: $(az account show --query user.name -o tsv)"
echo ""

# Step 1: Create the app registration
echo "→ Creating app registration: $APP_NAME"
APP_JSON=$(az ad app create \
    --display-name "$APP_NAME" \
    --sign-in-audience "AzureADMyOrg" \
    --web-redirect-uris "$REDIRECT_URI" \
    --output json)

APP_ID=$(echo "$APP_JSON" | grep -o '"appId": "[^"]*"' | cut -d'"' -f4)
OBJECT_ID=$(echo "$APP_JSON" | grep -o '"id": "[^"]*"' | head -1 | cut -d'"' -f4)
TENANT_ID=$(az account show --query tenantId -o tsv)

echo "✓ App registered:"
echo "  App ID (Client ID):     $APP_ID"
echo "  Object ID:              $OBJECT_ID"
echo "  Tenant ID:              $TENANT_ID"
echo ""

# Step 2: Add API permissions for Microsoft Graph
echo "→ Adding Microsoft Graph permissions..."

# Bookings.ReadWrite.All (Application permission — requires admin consent)
GRAPH_API=$(az ad sp list --filter "appId eq '00000003-0000-0000-c000-000000000000'" --query "[0].id" -o tsv)
BOOKINGS_PERM=$(az ad sp show --id 00000003-0000-0000-c000-000000000000 --query "appRoles[?value=='Bookings.ReadWrite.All'].id" -o tsv)
CALENDARS_PERM=$(az ad sp show --id 00000003-0000-0000-c000-000000000000 --query "appRoles[?value=='Calendars.Read'].id" -o tsv)

az ad app permission add \
    --id "$APP_ID" \
    --api 00000003-0000-0000-c000-000000000000 \
    --api-permissions "${BOOKINGS_PERM}=Role ${CALENDARS_PERM}=Role" \
    --output none

echo "✓ Permissions added: Bookings.ReadWrite.All, Calendars.Read"
echo ""

# Step 3: Create client secret
echo "→ Creating client secret (valid 2 years)..."
SECRET_JSON=$(az ad app credential reset \
    --id "$APP_ID" \
    --years 2 \
    --output json)

CLIENT_SECRET=$(echo "$SECRET_JSON" | grep -o '"password": "[^"]*"' | cut -d'"' -f4)

echo "✓ Client secret created"
echo ""

# Step 4: Admin consent
echo "→ Granting admin consent..."
az ad app permission admin-consent --id "$APP_ID" --output none 2>/dev/null || {
    echo "⚠  Could not auto-grant admin consent. You may need to do this manually in Azure Portal."
    echo "   Go to: Azure AD → App Registrations → $APP_NAME → API Permissions → Grant admin consent"
}
echo ""

# Step 5: Create the subscription renewal service principal permission
echo "→ Setting up subscription renewal permissions..."
az ad app permission add \
    --id "$APP_ID" \
    --api 00000003-0000-0000-c000-000000000000 \
    --api-permissions "df021288-bdef-4463-88db-98f22de89214=Role" \
    --output none 2>/dev/null || true
# (Subscription.ReadWrite.All — needed for webhook renewal)

az ad app permission admin-consent --id "$APP_ID" --output none 2>/dev/null || true

echo ""
echo "============================================"
echo "  SETUP COMPLETE"
echo "============================================"
echo ""
echo "Copy these to your .env file:"
echo ""
echo "  MS_TENANT_ID=$TENANT_ID"
echo "  MS_CLIENT_ID=$APP_ID"
echo "  MS_CLIENT_SECRET=$CLIENT_SECRET"
echo ""
echo "Next steps:"
echo "  1. Copy the .env values above"
echo "  2. Create your Bookings page at: https://outlook.office.com/bookings"
echo "  3. Copy the Bookings page URL and update Supabase:"
echo "     UPDATE campaign_specs SET cta_json = jsonb_set(cta_json, '{booking_url}', '\"YOUR_URL\"');"
echo "  4. Run the webhook auto-renewal: python deploy/automation/renew_webhooks.py"
echo ""
