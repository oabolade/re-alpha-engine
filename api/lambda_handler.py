"""Mangum adapter to run FastAPI on AWS Lambda."""

from mangum import Mangum
from api.monetization import app

handler = Mangum(app)
