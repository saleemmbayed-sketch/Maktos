-- CampaignOps Kernel v1 — Seed Data
-- "Quote Followup - Execution Gap" Campaign

INSERT INTO campaigns (id, name, product, offer, goal, north_star_metric, status)
VALUES (
  'c0000000-0000-0000-0000-000000000001',
  'Quote Followup - Execution Gap',
  'Quote-to-Cash Optimization Platform',
  'Free 15-Minute Quote Followup Gap Audit',
  'Book qualified demos',
  'Demo calls booked per week',
  'active'
);

INSERT INTO campaign_specs (campaign_id, personas_json, channels_json, kpis_json, cta_json, claims_json, compliance_rules_json)
VALUES (
  'c0000000-0000-0000-0000-000000000001',
  '["VP Sales","Head of Sales","RevOps Director","Sales Ops Leader","Inside Sales Manager"]'::jsonb,
  '["cold_email","linkedin_manual","linkedin_lead_forms"]'::jsonb,
  '{"north_star":"demo_calls_booked_per_week","secondary":["emails_sent","reply_rate","positive_reply_rate","meetings_booked","pipeline_generated"]}'::jsonb,
  '{"text":"Book 15-minute audit","action":"schedule_demo","calendly_url":"https://calendly.com/example/quote-gap-audit"}'::jsonb,
  '[{"claim":"Most quotes never get followed up","level":"low","evidence":"industry surveys"},{"claim":"15-minute audit reveals your follow-up gap","level":"low","evidence":"internal methodology"},{"claim":"Companies miss 47% of quote follow-ups","level":"medium","evidence":"Forrester research"}]'::jsonb,
  '{"require_unsubscribe":true,"require_physical_address":true,"require_privacy_policy":true,"require_sender_id":true,"block_auto_linkedin":true,"require_data_source_eu":true}'::jsonb
);

INSERT INTO approved_claims (campaign_id, claim_text, claim_level, reviewed_by)
VALUES
('c0000000-0000-0000-0000-000000000001', 'Most quotes never get followed up', 'low', 'campaign_owner'),
('c0000000-0000-0000-0000-000000000001', '15-minute audit reveals your follow-up gap', 'low', 'campaign_owner');
