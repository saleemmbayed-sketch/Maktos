"""Enrichment pipeline regression tests."""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "packages"))

from enrichment.engine import EnrichmentPipeline


def test_personalization_brief_uses_profile_name_without_error():
    pipeline = EnrichmentPipeline()
    profile = pipeline.enrich_company(
        domain="example-industrial.test",
        company_name="Example Industrial",
        known_industry="Manufacturing",
        known_size="500-1000",
    )

    brief = pipeline.generate_personalization_brief(profile, lead_title="Sales Operations Director")

    assert brief.company_name == "Example Industrial"
    assert "Example Industrial" in brief.one_line_observation
    assert brief.icebreaker
    assert brief.confidence > 0


def test_enrichment_infers_industrial_crm_and_cpq_signals():
    pipeline = EnrichmentPipeline()
    profile = pipeline.enrich_company(
        domain="example-manufacturing.test",
        company_name="Example Manufacturing",
        known_industry="Manufacturing",
        known_size="1000+",
    )

    assert profile.likely_uses_crm == "Salesforce"
    assert profile.likely_uses_cpq is True
    assert "ERP" in profile.tech_stack
