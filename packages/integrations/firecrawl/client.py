"""Firecrawl integration — company website enrichment for Phase B.

Turns company domain URLs into structured data for lead scoring and personalization.

Usage:
    client = FirecrawlClient(api_key)
    data = await client.scrape("acme.com")
    # → {markdown, metadata, links, ...}
"""

import os
from typing import Optional

import httpx


class FirecrawlClient:
    """Firecrawl API client for website scraping and enrichment."""

    BASE_URL = "https://api.firecrawl.dev/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY", "")
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0,
        )

    async def scrape(self, domain: str) -> dict:
        """Scrape a company website for enrichment data.
        
        Returns: {markdown, metadata: {title, description, ogImage, ...}, links}
        """
        url = f"https://{domain}" if not domain.startswith("http") else domain
        
        resp = await self.client.post(
            "/scrape",
            json={"url": url, "formats": ["markdown"]},
        )
        resp.raise_for_status()
        return resp.json()

    async def extract_company_signals(self, domain: str) -> dict:
        """Extract quote-relevant signals from a company website.

        Returns structured enrichment data for lead scoring.
        """
        data = await self.scrape(domain)
        markdown = data.get("data", {}).get("markdown", "").lower()
        metadata = data.get("data", {}).get("metadata", {})

        signals = {
            "domain": domain,
            "has_pricing_page": "pricing" in markdown or "/pricing" in markdown,
            "has_quote_form": any(kw in markdown for kw in ["get a quote", "request quote", "quote form", "request pricing"]),
            "has_cpq_mention": "cpq" in markdown or "configure price quote" in markdown,
            "has_crm_mention": any(crm in markdown for crm in ["salesforce", "hubspot", "pipedrive", "dynamics 365", "zoho crm"]),
            "has_sales_team_page": any(kw in markdown for kw in ["sales team", "contact sales", "talk to sales"]),
            "description": metadata.get("description", ""),
            "title": metadata.get("title", ""),
            "scrape_successful": True,
            "source": "firecrawl",
        }
        return signals

    async def batch_enrich(self, domains: list[str]) -> list[dict]:
        """Enrich multiple domains in parallel."""
        import asyncio
        tasks = [self.extract_company_signals(d) for d in domains]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self):
        await self.client.aclose()


# ── Enrichment trigger for n8n ─────────────────────────────────

def build_enrichment_payload(domain: str, company_name: str) -> dict:
    """Build the payload n8n sends to the enrichment endpoint.

    Called from n8n workflow 02 (lead import) after lead creation.
    """
    return {
        "domain": domain,
        "company_name": company_name,
        "action": "enrich",
        "sources": ["firecrawl"],  # Future: firecrawl,apollo,clay
    }
