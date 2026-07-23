#!/usr/bin/env python3
"""Auto-import CampaignOps workflows into n8n via REST API.

Usage:
  N8N_URL=http://localhost:5678 N8N_API_KEY=n8n_api_... python deploy/import_n8n_workflows.py

Offline export for manual n8n UI import:
  FASTAPI_URL=https://your-api-url N8N_EXPORT_DIR=.n8n-live python deploy/import_n8n_workflows.py

Removes the manual UI import step from the deployment playbook.
Each workflow is imported, nodes updated with the provided FASTAPI_URL,
and optionally activated.
"""

import json
import os
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO / "workflows"

WORKFLOW_NAMES = [
    "01_asset_intake",
    "02_lead_import",
    "03_draft_generation",
    "04_compliance_check",
    "05_email_send",
    "06_reply_classifier",
    "07_sla_monitor",
    "08_daily_summary",
    "09_outlook_bookings",
    "10_experiment_tracker",
    "11_enrichment_pipeline",
]

BOLD = "\033[1m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
RED = "\033[91m"; RESET = "\033[0m"
OK = "OK"
FAIL = "FAIL"


def parse_workflow_json(path: Path) -> dict:
    """Read and normalize an n8n workflow JSON file."""
    with open(path) as f:
        raw = json.load(f)
    
    # n8n API expects a specific format
    workflow = {
        "name": raw.get("name", path.stem),
        "nodes": raw.get("nodes", []),
        "connections": raw.get("connections", {}),
        "settings": raw.get("settings", {}),
        "active": False,  # Never auto-activate
    }
    return workflow


def update_fastapi_url(nodes: list[dict], fastapi_url: str) -> list[dict]:
    """Replace localhost URLs in HTTP Request nodes with the real API URL."""
    for node in nodes:
        if node.get("type") == "n8n-nodes-base.httpRequest":
            params = node.get("parameters", {})
            url = params.get("url", "")
            if "campaignops-api" in url or "localhost:8000" in url:
                params["url"] = url.replace(
                    "http://campaignops-api:8000", fastapi_url
                ).replace(
                    "http://localhost:8000", fastapi_url
                )
                node["parameters"] = params
    return nodes


async def import_all_workflows(
    n8n_url: str,
    api_key: str,
    fastapi_url: str,
    activate: bool = False,
) -> dict:
    """Import all workflows into n8n.

    Returns summary dict with success/failure per workflow.
    """
    results = {}
    
    async with httpx.AsyncClient(
        base_url=n8n_url.rstrip("/"),
        headers={"X-N8N-API-KEY": api_key},
        timeout=30.0,
    ) as client:
        
        # Verify connection
        try:
            resp = await client.get("/api/v1/workflows")
            resp.raise_for_status()
            existing = len(resp.json().get("data", []))
            print(f"  Connected to n8n. {existing} existing workflow(s).")
        except Exception as e:
            print(f"  {RED}Cannot connect to n8n: {e}{RESET}")
            print(f"  Is n8n running at {n8n_url}? Is the API key correct?")
            return {"error": str(e)}
        
        for name in WORKFLOW_NAMES:
            path = WORKFLOW_DIR / f"{name}.json"
            if not path.exists():
                print(f"  {RED}✗{RESET} {name}: file not found")
                results[name] = "missing"
                continue
            
            try:
                wf = parse_workflow_json(path)
                wf["nodes"] = update_fastapi_url(wf["nodes"], fastapi_url)
                
                resp = await client.post("/api/v1/workflows", json=wf)
                
                if resp.status_code in (200, 201):
                    wf_id = resp.json().get("id", "?")
                    results[name] = "imported"

                    # Optionally activate
                    if activate:
                        await client.patch(
                            f"/api/v1/workflows/{wf_id}",
                            json={"active": True},
                        )
                        print(f"  {GREEN}{OK}{RESET} {name} imported + ACTIVE (id={wf_id})")
                    else:
                        print(f"  {GREEN}{OK}{RESET} {name} imported (id={wf_id}, inactive)")
                else:
                    error = resp.text[:100]
                    print(f"  {RED}{FAIL}{RESET} {name}: HTTP {resp.status_code} - {error}")
                    results[name] = f"error_{resp.status_code}"

            except Exception as e:
                print(f"  {RED}{FAIL}{RESET} {name}: {e}")
                results[name] = f"error: {e}"
    
    return results


def print_summary(results: dict):
    """Print import summary."""
    imported = sum(1 for v in results.values() if v == "imported")
    failed = len(results) - imported
    
    print(f"\n{BOLD}{'-'*50}{RESET}")
    print(f"  Imported: {GREEN}{imported}{RESET}")
    if failed:
        print(f"  Failed:   {RED}{failed}{RESET}")
    else:
        print(f"  Failed:   0")
    print(f"{BOLD}{'-'*50}{RESET}")
    
    if imported == len(WORKFLOW_NAMES):
        print(f"\n  {GREEN}All {len(WORKFLOW_NAMES)} workflows imported.{RESET}")
        print(f"  Next: Open n8n UI, configure credentials, then activate workflows.")
        print(f"  Credentials needed: Supabase, OpenAI, Smartlead, Email (SMTP)")
    elif imported > 0:
        print(f"\n  {YELLOW}Partially imported. Check errors above.{RESET}")
    else:
        print(f"\n  {RED}Nothing imported. Check n8n URL, API key, and network.{RESET}")


def export_workflows(fastapi_url: str, export_dir: str) -> dict:
    """Write normalized workflow JSON files for manual n8n UI import."""
    out_dir = Path(export_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for name in WORKFLOW_NAMES:
        path = WORKFLOW_DIR / f"{name}.json"
        if not path.exists():
            print(f"  {RED}{FAIL}{RESET} {name}: file not found")
            results[name] = "missing"
            continue

        workflow = parse_workflow_json(path)
        workflow["nodes"] = update_fastapi_url(workflow["nodes"], fastapi_url)
        workflow["active"] = False

        output_path = out_dir / f"{name}.json"
        output_path.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
        print(f"  {GREEN}{OK}{RESET} {name} -> {output_path}")
        results[name] = "exported"

    return results


async def main():
    n8n_url = os.getenv("N8N_URL", "http://localhost:5678")
    api_key = os.getenv("N8N_API_KEY", "")
    fastapi_url = os.getenv("FASTAPI_URL", "http://localhost:8000")
    activate = os.getenv("N8N_ACTIVATE_WORKFLOWS", "false").lower() == "true"
    export_dir = os.getenv("N8N_EXPORT_DIR", "")

    if export_dir:
        print(f"\n{BOLD}CampaignOps Kernel - n8n Workflow Export{RESET}\n")
        print(f"  Export dir:  {export_dir}")
        print(f"  FastAPI URL: {fastapi_url}")
        print(f"  Active:      False")
        print(f"  Workflows:   {len(WORKFLOW_NAMES)}\n")
        export_workflows(fastapi_url, export_dir)
        print(f"\n  {GREEN}Export complete. Import these JSON files in n8n manually and keep them inactive.{RESET}")
        return

    if not api_key:
        print(f"{RED}ERROR: N8N_API_KEY not set.{RESET}")
        print("Get it from: n8n Settings > API > Create API Key")
        print("Or export files for manual import:")
        print("  FASTAPI_URL=https://your-api-url N8N_EXPORT_DIR=.n8n-live python deploy/import_n8n_workflows.py")
        print("\nUsage:")
        print("  N8N_URL=http://localhost:5678 N8N_API_KEY=n8n_api_... python deploy/import_n8n_workflows.py")
        sys.exit(1)
    
    print(f"\n{BOLD}CampaignOps Kernel - n8n Workflow Import{RESET}\n")
    print(f"  n8n URL:     {n8n_url}")
    print(f"  FastAPI URL: {fastapi_url}")
    print(f"  Activate:    {activate}")
    print(f"  Workflows:   {len(WORKFLOW_NAMES)}\n")
    
    results = await import_all_workflows(n8n_url, api_key, fastapi_url, activate)
    print_summary(results)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
