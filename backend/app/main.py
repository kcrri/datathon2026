import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.chat import router as chat_router
from app.api.features import router as features_router
from app.api.mcp import router as mcp_router
from app.api.portfolio import router as portfolio_router
from app.services.errors import ExternalServiceError, ServiceConfigurationError

load_dotenv()

app = FastAPI(title="PortfolioGuard AI")
frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(ServiceConfigurationError)
async def _configuration_error(_: Request, exc: ServiceConfigurationError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(ExternalServiceError)
async def _external_error(_: Request, exc: ExternalServiceError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


app.include_router(chat_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(features_router, prefix="/api")
app.include_router(mcp_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "portfolioguard-api"}
