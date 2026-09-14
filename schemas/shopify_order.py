from pydantic import BaseModel


class ShopifyCustomer(BaseModel):
    id: int
    email: str


class ShopifyOrderPaid(BaseModel):
    id: int
    email: str
    total_price: str
    subtotal_price: str
    financial_status: str
    customer: ShopifyCustomer