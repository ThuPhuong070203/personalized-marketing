"""
Pydantic schemas định nghĩa dữ liệu đầu vào và đầu ra cho API (backend/app/schemas.py).
"""

from pydantic import BaseModel, Field
from typing import Any


class HealthResponse(BaseModel):
    status: str = "ok"


class RecentPurchase(BaseModel):
    stockcode: str
    description: str
    quantity: int
    total_price: float
    invoice_date: str
    image: str


class CustomerSummary(BaseModel):
    customer_id: int
    cluster_name: str
    monetary: float


class CustomerDetail(BaseModel):
    customer_id: int
    recency: int
    frequency: int
    monetary: float
    cluster_id: int
    cluster_name: str
    recent_purchases: list[RecentPurchase]


class ClusterItem(BaseModel):
    id: int
    name: str
    size: int
    pct: float
    mean_recency: float
    mean_frequency: float
    mean_monetary: float
    description: str
    campaign: str


class ProductRecommendItem(BaseModel):
    stockcode: str
    description: str
    score: float
    image: str


class ClusterDetail(BaseModel):
    cluster: ClusterItem
    top_products: list[ProductRecommendItem]


class ClusterPoint(BaseModel):
    customer_id: int
    cluster: int
    x: float
    y: float


class ProductDetail(BaseModel):
    stockcode: str
    description: str
    n_purchases: int
    image: str


class ClusterBrief(BaseModel):
    id: int | None = None
    name: str | None = None


class RecommendResponse(BaseModel):
    customer_id: int
    cluster: ClusterBrief | None = None
    model: str
    cold_start: bool
    items: list[ProductRecommendItem]


class MetricsResponse(BaseModel):
    clustering: dict[str, Any]
    recommenders: dict[str, Any]