-- CampaignOps Kernel v1 — Initial Database Schema
-- Week 1 Foundation: all core tables, triggers, and indexes
-- Run against Supabase/Postgres

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Enums ───────────────────────────────────────────────────────
CREATE TYPE campaign_status AS ENUM (
  'draft', 'active', 'paused', 'completed', 'archived'
);

CREATE TYPE asset_type AS ENUM (
  'cold_email', 'linkedin_dm', 'linkedin_connection_note',
  'ad_copy', 'objection_response', 'landing_page_copy',
  'brand_framework', 'content_calendar', 'operator_pack',
  'compliance_report', 'measurement_framework', 'outreach_template'
);

CREATE TYPE channel_type AS ENUM (
  'cold_email', 'linkedin_manual', 'linkedin_lead_forms'
);

CREATE TYPE claim_level AS ENUM ('low', 'medium', 'high');

CREATE TYPE compliance_status AS ENUM (
  'approved', 'needs_review', 'blocked'
);

CREATE TYPE lead_tier AS ENUM ('tier_1', 'tier_2', 'nurture', 'excluded');

CREATE TYPE lead_status AS ENUM (
  'imported', 'scored', 'draft_ready', 'needs_review',
  'approved', 'rejected', 'revise', 'in_sequence',
  'replied', 'booked', 'disqualified', 'nurturing', 'completed'
);

CREATE TYPE event_type AS ENUM (
  'sent', 'delivered', 'opened', 'clicked', 'bounced',
  'unsubscribed', 'complained', 'replied', 'sequence_stopped'
);

CREATE TYPE reply_type AS ENUM (
  'interested', 'needs_more_info', 'pricing_question',
  'competitor', 'not_now', 'wrong_person', 'referral',
  'unsubscribe', 'negative', 'legal_privacy', 'spam', 'other'
);

CREATE TYPE approval_status AS ENUM (
  'pending', 'approved', 'rejected', 'revise'
);

CREATE TYPE approval_entity_type AS ENUM (
  'campaign', 'sequence', 'message', 'ad_copy', 'budget_action'
);

CREATE TYPE sla_status AS ENUM (
  'active', 'due_soon', 'overdue', 'resolved', 'escalated'
);

CREATE TYPE actor_type AS ENUM (
  'human', 'system', 'ai', 'n8n_workflow'
);

CREATE TYPE research_status AS ENUM (
  'pending', 'in_progress', 'enriched', 'failed'
);

-- ── campaigns ───────────────────────────────────────────────────
CREATE TABLE campaigns (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name            TEXT NOT NULL,
  product         TEXT,
  offer           TEXT,
  goal            TEXT,
  north_star_metric TEXT,
  status          campaign_status NOT NULL DEFAULT 'draft',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── campaign_specs ──────────────────────────────────────────────
CREATE TABLE campaign_specs (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id       UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  personas_json     JSONB NOT NULL DEFAULT '[]',
  channels_json     JSONB NOT NULL DEFAULT '[]',
  kpis_json         JSONB NOT NULL DEFAULT '{}',
  cta_json          JSONB NOT NULL DEFAULT '{}',
  claims_json       JSONB NOT NULL DEFAULT '[]',
  compliance_rules_json JSONB NOT NULL DEFAULT '{}',
  source_assets     JSONB NOT NULL DEFAULT '[]',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_campaign_specs_campaign ON campaign_specs(campaign_id);

-- ── campaign_assets ─────────────────────────────────────────────
CREATE TABLE campaign_assets (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id     UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  asset_type      asset_type NOT NULL,
  channel         channel_type,
  persona         TEXT,
  funnel_stage    TEXT,
  content         TEXT NOT NULL,
  source_file     TEXT,
  approval_status compliance_status NOT NULL DEFAULT 'needs_review',
  risk_level      claim_level NOT NULL DEFAULT 'low',
  version         INTEGER NOT NULL DEFAULT 1,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_campaign_assets_campaign ON campaign_assets(campaign_id);
CREATE INDEX idx_campaign_assets_status ON campaign_assets(approval_status);

-- ── asset_versions ──────────────────────────────────────────────
CREATE TABLE asset_versions (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  asset_id    UUID NOT NULL REFERENCES campaign_assets(id) ON DELETE CASCADE,
  version     INTEGER NOT NULL,
  content     TEXT NOT NULL,
  changed_by  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_asset_versions_asset ON asset_versions(asset_id);

-- ── approved_claims ─────────────────────────────────────────────
CREATE TABLE approved_claims (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  claim_text  TEXT NOT NULL,
  claim_level claim_level NOT NULL DEFAULT 'low',
  reviewed_by TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── risky_claims ────────────────────────────────────────────────
CREATE TABLE risky_claims (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  claim_text  TEXT NOT NULL,
  risk_reason TEXT,
  flagged_by  actor_type NOT NULL DEFAULT 'ai',
  resolved    BOOLEAN NOT NULL DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── message_templates ───────────────────────────────────────────
CREATE TABLE message_templates (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id     UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  template_type   asset_type NOT NULL,
  channel         channel_type NOT NULL,
  persona         TEXT NOT NULL,
  funnel_stage    TEXT NOT NULL,
  subject         TEXT,
  body            TEXT NOT NULL,
  version         INTEGER NOT NULL DEFAULT 1,
  is_active       BOOLEAN NOT NULL DEFAULT true,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_message_templates_campaign ON message_templates(campaign_id);

-- ── accounts ───────────────────────────────────────────────────
CREATE TABLE accounts (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  company_name    TEXT NOT NULL,
  domain          TEXT,
  industry        TEXT,
  country         TEXT,
  company_size    TEXT,
  fit_score       INTEGER DEFAULT 0,
  research_status research_status NOT NULL DEFAULT 'pending',
  enrichment_data JSONB DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_accounts_domain ON accounts(domain) WHERE domain IS NOT NULL;

-- ── contacts ───────────────────────────────────────────────────
CREATE TABLE contacts (
  id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  account_id          UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  first_name          TEXT,
  last_name           TEXT,
  title               TEXT,
  email               TEXT,
  linkedin_url        TEXT,
  region              TEXT,
  data_source         TEXT,
  source_date         DATE,
  suppression_status  BOOLEAN NOT NULL DEFAULT false,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_contacts_account ON contacts(account_id);
CREATE INDEX idx_contacts_email ON contacts(email) WHERE email IS NOT NULL;
CREATE INDEX idx_contacts_suppression ON contacts(suppression_status);

-- ── leads ──────────────────────────────────────────────────────
CREATE TABLE leads (
  id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id         UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  account_id          UUID NOT NULL REFERENCES accounts(id),
  contact_id          UUID NOT NULL REFERENCES contacts(id),
  lead_score          INTEGER DEFAULT 0,
  tier                lead_tier,
  status              lead_status NOT NULL DEFAULT 'imported',
  next_action         TEXT,
  next_action_due_at  TIMESTAMPTZ,
  owner               TEXT,
  scoring_reasons     JSONB DEFAULT '[]',
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_leads_campaign ON leads(campaign_id);
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_tier ON leads(tier);
CREATE INDEX idx_leads_score ON leads(lead_score DESC);
CREATE INDEX idx_leads_next_action ON leads(next_action_due_at) WHERE next_action_due_at IS NOT NULL;

-- ── outreach_events ────────────────────────────────────────────
CREATE TABLE outreach_events (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id         UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  channel         channel_type NOT NULL,
  message_id      TEXT,
  event_type      event_type NOT NULL,
  sent_at         TIMESTAMPTZ,
  opened_at       TIMESTAMPTZ,
  clicked_at      TIMESTAMPTZ,
  replied_at      TIMESTAMPTZ,
  external_id     TEXT,
  metadata        JSONB DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_outreach_events_lead ON outreach_events(lead_id);
CREATE INDEX idx_outreach_events_type ON outreach_events(event_type);
CREATE INDEX idx_outreach_events_sent ON outreach_events(sent_at);

-- ── reply_events ───────────────────────────────────────────────
CREATE TABLE reply_events (
  id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id             UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  channel             channel_type NOT NULL,
  reply_text          TEXT NOT NULL,
  reply_type          reply_type,
  confidence          FLOAT CHECK (confidence >= 0 AND confidence <= 1),
  recommended_action  TEXT,
  draft_response      TEXT,
  status              TEXT NOT NULL DEFAULT 'unprocessed',
  processed_by        actor_type,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_reply_events_lead ON reply_events(lead_id);
CREATE INDEX idx_reply_events_status ON reply_events(status);
CREATE INDEX idx_reply_events_confidence ON reply_events(confidence);

-- ── compliance_checks ──────────────────────────────────────────
CREATE TABLE compliance_checks (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id           UUID REFERENCES leads(id),
  asset_id          UUID REFERENCES campaign_assets(id),
  channel           channel_type NOT NULL,
  status            compliance_status NOT NULL,
  blocked_reasons   JSONB DEFAULT '[]',
  review_required   BOOLEAN NOT NULL DEFAULT false,
  checked_by        actor_type NOT NULL DEFAULT 'system',
  checked_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_compliance_checks_lead ON compliance_checks(lead_id);

-- ── approvals ──────────────────────────────────────────────────
CREATE TABLE approvals (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  entity_type     approval_entity_type NOT NULL,
  entity_id       UUID NOT NULL,
  status          approval_status NOT NULL DEFAULT 'pending',
  reviewer        TEXT,
  comments        TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  approved_at     TIMESTAMPTZ
);

CREATE INDEX idx_approvals_entity ON approvals(entity_type, entity_id);
CREATE INDEX idx_approvals_status ON approvals(status);

-- ── sla_events ─────────────────────────────────────────────────
CREATE TABLE sla_events (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id           UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  channel           channel_type NOT NULL,
  triggered_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  due_at            TIMESTAMPTZ NOT NULL,
  status            sla_status NOT NULL DEFAULT 'active',
  escalation_level  INTEGER NOT NULL DEFAULT 0,
  resolved_at       TIMESTAMPTZ
);

CREATE INDEX idx_sla_events_status ON sla_events(status);
CREATE INDEX idx_sla_events_due ON sla_events(due_at) WHERE status IN ('active', 'due_soon');

-- ── suppression_list ───────────────────────────────────────────
CREATE TABLE suppression_list (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email       TEXT NOT NULL UNIQUE,
  reason      TEXT,
  source      TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── audit_log ──────────────────────────────────────────────────
CREATE TABLE audit_log (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  actor_type  actor_type NOT NULL,
  actor_id    TEXT,
  action      TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id   UUID,
  before_json JSONB,
  after_json  JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);

-- ── Update triggers ────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_campaigns_updated_at BEFORE UPDATE ON campaigns FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_campaign_specs_updated_at BEFORE UPDATE ON campaign_specs FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_campaign_assets_updated_at BEFORE UPDATE ON campaign_assets FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_message_templates_updated_at BEFORE UPDATE ON message_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_accounts_updated_at BEFORE UPDATE ON accounts FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_contacts_updated_at BEFORE UPDATE ON contacts FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_leads_updated_at BEFORE UPDATE ON leads FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Audit logging trigger ──────────────────────────────────────
CREATE OR REPLACE FUNCTION audit_lead_changes()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, before_json, after_json)
  VALUES ('system', 'lead_state_machine', TG_OP, 'lead', NEW.id,
          to_jsonb(OLD), to_jsonb(NEW));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_leads
  AFTER UPDATE ON leads
  FOR EACH ROW
  WHEN (OLD.status IS DISTINCT FROM NEW.status OR OLD.tier IS DISTINCT FROM NEW.tier)
  EXECUTE FUNCTION audit_lead_changes();

-- ── View: lead_current_state ───────────────────────────────────
CREATE VIEW lead_current_state AS
SELECT
  l.id AS lead_id,
  l.status,
  l.tier,
  l.lead_score,
  l.next_action,
  l.next_action_due_at,
  c.first_name || ' ' || c.last_name AS contact_name,
  c.email,
  c.title,
  a.company_name,
  a.domain,
  a.industry,
  cam.name AS campaign_name,
  cam.offer AS campaign_offer,
  oe_last.sent_at AS last_outreach_at,
  re_last.created_at AS last_reply_at,
  sla.due_at AS sla_due_at,
  sla.status AS sla_status
FROM leads l
JOIN contacts c ON l.contact_id = c.id
JOIN accounts a ON l.account_id = a.id
JOIN campaigns cam ON l.campaign_id = cam.id
LEFT JOIN LATERAL (
  SELECT sent_at FROM outreach_events
  WHERE lead_id = l.id AND event_type = 'sent'
  ORDER BY sent_at DESC LIMIT 1
) oe_last ON true
LEFT JOIN LATERAL (
  SELECT created_at FROM reply_events
  WHERE lead_id = l.id
  ORDER BY created_at DESC LIMIT 1
) re_last ON true
LEFT JOIN LATERAL (
  SELECT due_at, status FROM sla_events
  WHERE lead_id = l.id AND status IN ('active', 'due_soon', 'overdue')
  ORDER BY due_at ASC LIMIT 1
) sla ON true;
