"""AWS S3 storage for analyses, PDFs, and scraped data."""

import json
from datetime import datetime
from typing import Any

from config import AWS_S3_BUCKET, AWS_REGION

S3_AVAILABLE = False
_s3_client = None

try:
    import boto3
    if AWS_S3_BUCKET:
        S3_AVAILABLE = True
except ImportError:
    pass


def _get_client() -> Any:
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    if not S3_AVAILABLE:
        return None
    _s3_client = boto3.client("s3", region_name=AWS_REGION)
    return _s3_client


def store_analysis(job_id: str, results: dict) -> str | None:
    """Store analysis results to S3.

    Returns the S3 key on success, None if S3 is unavailable.
    """
    if not S3_AVAILABLE:
        return None

    client = _get_client()
    key = f"analyses/{job_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        client.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=key,
            Body=json.dumps(results, default=str),
            ContentType="application/json",
        )
        return key
    except Exception:
        return None


def store_pdf(filename: str, pdf_bytes: bytes) -> str | None:
    """Store a PDF file to S3.

    Returns the S3 key on success, None if S3 is unavailable.
    """
    if not S3_AVAILABLE:
        return None

    client = _get_client()
    key = f"pdfs/{datetime.now().strftime('%Y%m%d')}/{filename}"
    try:
        client.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )
        return key
    except Exception:
        return None


def store_scraped_data(source: str, data: list[dict] | dict) -> str | None:
    """Store scraped deal data to S3.

    Returns the S3 key on success, None if S3 is unavailable.
    """
    if not S3_AVAILABLE:
        return None

    client = _get_client()
    key = f"scraped/{source}/{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        client.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=key,
            Body=json.dumps(data, default=str),
            ContentType="application/json",
        )
        return key
    except Exception:
        return None


def retrieve_analysis(key: str) -> dict | None:
    """Retrieve analysis results from S3.

    Returns the parsed dict on success, None if not found or S3 is unavailable.
    """
    if not S3_AVAILABLE:
        return None

    client = _get_client()
    try:
        response = client.get_object(Bucket=AWS_S3_BUCKET, Key=key)
        body = response["Body"].read().decode("utf-8")
        return json.loads(body)
    except Exception:
        return None
