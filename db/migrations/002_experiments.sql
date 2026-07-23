-- CampaignOps Kernel v1 — Phase E: Experiment & A/B Testing Tables
-- Run after 001_initial_schema.sql

-- ── experiments ─────────────────────────────────────────────────
CREATE TABLE experiments (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  campaign_id     UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  hypothesis      TEXT,                    -- "VP Sales persona responds better to problem-centric openers"
  metric          TEXT NOT NULL DEFAULT 'positive_reply_rate',  -- positive_reply_rate, reply_rate, meeting_rate
  status          TEXT NOT NULL DEFAULT 'draft',  -- draft, active, paused, completed, archived
  started_at      TIMESTAMPTZ,
  ended_at        TIMESTAMPTZ,
  sample_size_target INTEGER DEFAULT 100,
  significance_threshold FLOAT DEFAULT 0.90,  -- Bayesian probability threshold for declaring winner
  winner_variant_id UUID,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_experiments_campaign ON experiments(campaign_id);
CREATE INDEX idx_experiments_status ON experiments(status);

-- ── experiment_variants ─────────────────────────────────────────
CREATE TABLE experiment_variants (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  experiment_id   UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,            -- "Control", "Problem-centric", "Metric-centric"
  template_id     UUID REFERENCES message_templates(id),  -- Which template to use
  description     TEXT,
  is_control      BOOLEAN NOT NULL DEFAULT false,
  traffic_split   FLOAT NOT NULL DEFAULT 0.5,  -- Portion of traffic (must sum to 1.0 across variants)
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_experiment_variants_experiment ON experiment_variants(experiment_id);

-- ── experiment_assignments ──────────────────────────────────────
CREATE TABLE experiment_assignments (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  experiment_id   UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
  lead_id         UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  variant_id      UUID NOT NULL REFERENCES experiment_variants(id),
  assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(experiment_id, lead_id)  -- Each lead gets one variant per experiment
);

CREATE INDEX idx_experiment_assignments_lead ON experiment_assignments(lead_id);
CREATE INDEX idx_experiment_assignments_experiment ON experiment_assignments(experiment_id);

-- ── experiment_results ──────────────────────────────────────────
CREATE TABLE experiment_results (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  experiment_id   UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
  variant_id      UUID NOT NULL REFERENCES experiment_variants(id),
  leads_assigned  INTEGER NOT NULL DEFAULT 0,
  emails_sent     INTEGER NOT NULL DEFAULT 0,
  emails_opened   INTEGER NOT NULL DEFAULT 0,
  emails_clicked  INTEGER NOT NULL DEFAULT 0,
  replies_total   INTEGER NOT NULL DEFAULT 0,
  positive_replies INTEGER NOT NULL DEFAULT 0,
  meetings_booked INTEGER NOT NULL DEFAULT 0,
  unsubscribes    INTEGER NOT NULL DEFAULT 0,
  -- Computed metrics
  reply_rate      FLOAT,
  positive_reply_rate FLOAT,
  meeting_rate    FLOAT,
  -- Bayesian statistics
  win_probability FLOAT,                   -- Probability this variant is best (0-1)
  expected_loss   FLOAT,                   -- Expected loss if wrong (lower = better)
  is_winner       BOOLEAN DEFAULT false,
  computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(experiment_id, variant_id, computed_at)
);

CREATE INDEX idx_experiment_results_experiment ON experiment_results(experiment_id);

-- ── Trigger for updated_at ──────────────────────────────────────
CREATE TRIGGER trg_experiments_updated_at
  BEFORE UPDATE ON experiments
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
