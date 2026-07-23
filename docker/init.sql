-- Auto-applied on first Postgres start
-- Creates the CampaignOps database and applies schema + seed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
ENDENDOFSQL

# Copy migrations into docker context
cp db/migrations/001_initial_schema.sql docker/001_schema.sql
cp db/migrations/002_experiments.sql docker/002_experiments.sql
cp db/seed/001_campaign_data.sql docker/003_seed.sql

echo "Docker SQL files ready"
