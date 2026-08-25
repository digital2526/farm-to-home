from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import ALLOWED_ORIGINS

from routes.subscription import router as subscription_router
from routes.seeds import router as seeds_router
from routes.webhooks import router as webhook_router

from database import Base, engine
from models.customer import Customer  # noqa: F401
from models.seed_transaction import SeedTransaction  # noqa: F401
from models.reward import Reward  # noqa: F401
from models.redemption import Redemption  # noqa: F401
from models.webhook_delivery import WebhookDelivery  # noqa: F401

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Farm to Home Recharge API",
    version="1.0.0",
)

MAX_REQUEST_BODY_SIZE = 1 * 1024 * 1024  # 1 MB


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BODY_SIZE:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large."},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header."},
                )

        return await call_next(request)


app.add_middleware(RequestSizeLimitMiddleware)

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing Recharge APIs
app.include_router(subscription_router, prefix="/subscription")

# New Seeds APIs
app.include_router(seeds_router)

app.include_router(webhook_router)

@app.get("/")
def health():
    return {
        "status": "running",
        "service": "Farm to Home Recharge API",
        "version": "1.0.0"
    }

# Create database tables
Base.metadata.create_all(bind=engine)