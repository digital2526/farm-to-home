from fastapi import APIRouter, Depends, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from shopify_auth import verify_shopify_proxy

from sqlalchemy.orm import Session
from config import SYNC_API_KEY

from database import get_db
from services.seeds import get_customer_balance, get_or_create_customer, award_seeds

from services.rewards import list_rewards

from schemas.redeem import RedeemRewardRequest
from services.redemption import redeem_reward
from services.history import get_history
from services.dashboard import get_dashboard
from services.recharge_rewards import sync_recharge_rewards


router = APIRouter(
    prefix="/seeds",
    tags=["Terramay Seeds"]
)

limiter = Limiter(key_func=get_remote_address)

@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "Terramay Seeds API"
    }

@router.get("/balance")
@limiter.limit("60/minute")
async def balance(
    request: Request,
    db: Session = Depends(get_db),
):
    shopify_customer_id = await verify_shopify_proxy(request)

    balance = get_customer_balance(
        db,
        shopify_customer_id,
    )

    return {
        "shopify_customer_id": shopify_customer_id,
        "balance": balance,
    }
    
@router.get("/rewards")
@limiter.limit("60/minute")
async def rewards(
    request: Request,
    db: Session = Depends(get_db),
):
    # Authenticate the Shopify customer before returning
    # customer-facing reward data.
    await verify_shopify_proxy(request)

    rewards = list_rewards(db)

    return rewards

@router.post("/redeem")
@limiter.limit("5/minute")
async def redeem(
    request: RedeemRewardRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    shopify_customer_id = await verify_shopify_proxy(http_request)

    customer = redeem_reward(
        db=db,
        shopify_customer_id=shopify_customer_id,
        reward_id=request.reward_id,
    )

    return {
        "status": "success",
        "customer_id": customer.id,
        "balance": customer.current_balance,
    }
    
@router.get("/history")
@limiter.limit("60/minute")
async def history(
    request: Request,
    db: Session = Depends(get_db),
):
    shopify_customer_id = await verify_shopify_proxy(request)

    history = get_history(
        db,
        shopify_customer_id,
    )

    return history

@router.get("/dashboard")
@limiter.limit("60/minute")
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
):
    shopify_customer_id = await verify_shopify_proxy(request)

    dashboard = get_dashboard(
        db,
        shopify_customer_id,
    )

    if dashboard is None:
        return {
            "balance": 0,
            "rewards": list_rewards(db),
            "history": [],
        }

    return {
        "balance": dashboard["customer"].current_balance,
        "rewards": dashboard["rewards"],
        "history": dashboard["history"],
    }
    
@router.post("/sync-recharge")
@limiter.limit("5/minute")
def sync_recharge(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str = Header(None),
):

    if x_api_key != SYNC_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )

    return sync_recharge_rewards(db)