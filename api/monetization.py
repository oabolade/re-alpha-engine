"""FastAPI service — exposes deal analysis to external agents via Nevermined payment verification."""

import json
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, Field

from config import NEVERMINED_API_KEY
from tools.rent_roll_normalizer import normalize_rent_roll
from tools.financial_engine import run_financial_model, run_scenarios
from tools.memo_generator import generate_memo, generate_negotiation_leverage
from tools.market_intelligence import research_market, format_market_context
from tools.s3_storage import store_analysis

app = FastAPI(
    title="RE Alpha Engine API",
    description="Institutional multifamily underwriting intelligence — accessible via Nevermined payments",
    version="2.0.0",
)

# In-memory job store (use DynamoDB/Redis in production)
_jobs: dict[str, dict] = {}


# --- Pydantic Models ---

class DealAnalysisRequest(BaseModel):
    raw_extraction: dict = Field(..., description="Raw JSON from offering memorandum extraction")
    assumptions: dict | None = Field(None, description="Optional assumption overrides")
    include_market_intel: bool = Field(True, description="Whether to include market intelligence research")


class DealAnalysisStatus(BaseModel):
    job_id: str
    status: str  # "pending", "processing", "completed", "failed"
    message: str = ""


class DealAnalysisResult(BaseModel):
    job_id: str
    status: str
    normalized_data: dict | None = None
    financial_results: dict | None = None
    scenario_results: dict | None = None
    negotiation_points: list[str] | None = None
    market_data: dict | None = None
    memo: str | None = None


# --- Payment Verification ---

async def verify_nevermined_payment(
    x_nevermined_agreement_id: str | None = Header(None),
) -> str:
    """Verify Nevermined payment via agreement ID header.

    In production, this validates the agreement against the Nevermined node.
    For now, it checks the header is present when NEVERMINED_API_KEY is set.
    """
    if not NEVERMINED_API_KEY:
        # No payment required if Nevermined is not configured
        return "no-payment-required"

    if not x_nevermined_agreement_id:
        raise HTTPException(
            status_code=402,
            detail="Payment required — include x-nevermined-agreement-id header",
        )

    # TODO: Validate agreement against Nevermined node
    # client = get_client()
    # valid = client.verify_agreement(x_nevermined_agreement_id)
    # if not valid: raise HTTPException(402, "Invalid or expired payment agreement")

    return x_nevermined_agreement_id


# --- Endpoints ---

@app.post("/api/v1/analyze", response_model=DealAnalysisStatus)
async def submit_analysis(
    request: DealAnalysisRequest,
    agreement_id: str = Depends(verify_nevermined_payment),
):
    """Submit a deal for analysis. Requires Nevermined payment verification."""
    job_id = str(uuid.uuid4())

    _jobs[job_id] = {"status": "processing", "agreement_id": agreement_id}

    try:
        normalized = normalize_rent_roll(request.raw_extraction)
        financials = run_financial_model(normalized, request.assumptions)
        scenarios = run_scenarios(normalized)
        leverage = generate_negotiation_leverage(normalized, financials)

        market_data = None
        market_context = ""
        if request.include_market_intel:
            try:
                market_data = research_market(normalized.get("address", ""))
                market_context = format_market_context(market_data)
            except Exception:
                pass

        memo = generate_memo(normalized, financials, scenarios, leverage, market_context)

        result = {
            "normalized_data": normalized,
            "financial_results": financials,
            "scenario_results": scenarios,
            "negotiation_points": leverage,
            "market_data": market_data,
            "memo": memo,
        }

        # Persist to S3 if available
        store_analysis(job_id, result)

        _jobs[job_id] = {"status": "completed", "result": result, "agreement_id": agreement_id}

    except Exception as e:
        _jobs[job_id] = {"status": "failed", "error": str(e), "agreement_id": agreement_id}
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    return DealAnalysisStatus(job_id=job_id, status="completed", message="Analysis complete")


@app.get("/api/v1/status/{job_id}", response_model=DealAnalysisStatus)
async def get_status(job_id: str):
    """Check the status of a submitted analysis job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return DealAnalysisStatus(
        job_id=job_id,
        status=job["status"],
        message=job.get("error", ""),
    )


@app.get("/api/v1/result/{job_id}", response_model=DealAnalysisResult)
async def get_result(
    job_id: str,
    agreement_id: str = Depends(verify_nevermined_payment),
):
    """Retrieve analysis results. Requires payment verification."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail=f"Job status: {job['status']}")

    result = job.get("result", {})
    return DealAnalysisResult(
        job_id=job_id,
        status="completed",
        **result,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "re-alpha-engine", "version": "2.0.0"}
