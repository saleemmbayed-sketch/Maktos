#!/bin/sh
# Runs inside the test container after all services are up.
# Validates the full stack end-to-end.

set -e

echo ""
echo "============================================"
echo "  CampaignOps Kernel — Integration Test"
echo "============================================"
echo ""

# 1. API health
echo "--- 1. API Health ---"
curl -sf http://api:8000/health | python3 -m json.tool
echo ""

# 2. Campaign metrics (should have seed data)
echo "--- 2. Campaign Metrics ---"
curl -sf "http://api:8000/campaigns/c0000000-0000-0000-0000-000000000001/metrics" | python3 -m json.tool
echo ""

# 3. Score a lead
echo "--- 3. Score a Lead ---"
curl -sf -X POST http://api:8000/leads/score \
  -H "Content-Type: application/json" \
  -d '{"lead_id":"00000000-0000-0000-0000-000000000001","title":"VP Sales","industry":"SaaS","company_size":"200-500","company_name":"Acme Corp"}' \
  | python3 -m json.tool
echo ""

# 4. Compliance check
echo "--- 4. Compliance Check ---"
curl -sf -X POST http://api:8000/compliance/check \
  -H "Content-Type: application/json" \
  -d '{"channel":"cold_email","message_body":"Hi {{first_name}},\n\nTest.\n\nAlex\n123 Main St, NY\n{{unsubscribe_link}}\nPrivacy policy: https://test.com/privacy","contact_email":"test@test.com","contact_region":"US","contact_data_source":"manual"}' \
  | python3 -m json.tool
echo ""

# 5. Approval stats
echo "--- 5. Approval Queue ---"
curl -sf http://api:8000/approvals/stats | python3 -m json.tool
echo ""

# 6. Experiment recommendations
echo "--- 6. Experiments ---"
curl -sf http://api:8000/experiments/recommendations | python3 -m json.tool
echo ""

# 7. SLA windows
echo "--- 7. SLA Windows ---"
curl -sf http://api:8000/sla/windows | python3 -m json.tool
echo ""

# 8. Run all Python tests
echo "--- 8. Test Suite ---"
python3 tests/test_scoring.py
python3 tests/test_compliance.py
python3 tests/test_reply_classifier.py
python3 tests/test_experiments.py
python3 tests/test_integration.py

echo ""
echo "============================================"
echo "  ALL INTEGRATION CHECKS PASSED"
echo "============================================"
