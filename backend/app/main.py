import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (registers all tables)
from app.config import get_settings
from app.demo.router import router as demo_router
from app.identity.router import router as auth_router
from app.market_data.router import router as market_router
from app.planning.router import router as planning_router
from app.portfolio.router import router as portfolio_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

settings = get_settings()
app = FastAPI(
    title="FolioLens API",
    version="1.0.0",
    description="Portfolio analytics for Indian financial advisors. Information and education "
    "only; not investment advice.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

API = "/api/v1"
app.include_router(auth_router, prefix=API)
app.include_router(demo_router, prefix=API)
app.include_router(market_router, prefix=API)
# Planning first: its /portfolios/{id}/plan must win over the report's /portfolios/{id}/{section}.
app.include_router(planning_router, prefix=API)
app.include_router(portfolio_router, prefix=API)


@app.get(f"{API}/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
