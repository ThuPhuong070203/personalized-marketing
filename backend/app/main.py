"""
FastAPI ứng dụng chính (backend/app/main.py):
- Định nghĩa các endpoint RESTful theo chuẩn yêu cầu mục 8
- Bật CORS cho mọi origin
- Mount thư mục data/images tại /images
- Nạp toàn bộ artifacts khi khởi động
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Path as FastApiPath
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Đảm bảo import config
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
from backend.app.schemas import (
    HealthResponse,
    CustomerSummary,
    CustomerDetail,
    ClusterItem,
    ClusterDetail,
    ClusterPoint,
    ProductDetail,
    RecommendResponse,
    MetricsResponse
)
from backend.app.services import ModelService, ALLOWED_MODELS


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Nạp toàn bộ dữ liệu và mô hình một lần khi khởi động
    service = ModelService.get_instance()
    yield


app = FastAPI(
    title="Personalized Marketing API",
    description="API phân cụm khách hàng (RFM + K-Means) và gợi ý sản phẩm cá nhân hóa",
    version="1.0.0",
    lifespan=lifespan
)

# Cấu hình CORS cho phép mọi origin truy cập
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount thư mục chứa ảnh sản phẩm
config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(config.IMAGES_DIR)), name="images")


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Kiểm tra trạng thái hoạt động của dịch vụ."""
    return {"status": "ok"}


@app.get("/customers", response_model=list[CustomerSummary], tags=["Customers"])
def get_customers(
    search: str = Query("", description="Chuỗi tìm kiếm theo customer_id"),
    limit: int = Query(50, ge=1, le=500, description="Số lượng khách hàng tối đa trả về")
):
    """Lấy danh sách khách hàng, có hỗ trợ tìm kiếm theo ID."""
    service = ModelService.get_instance()
    return service.get_customers(search=search, limit=limit)


@app.get("/customers/{customer_id}", response_model=CustomerDetail, tags=["Customers"])
def get_customer_detail(
    customer_id: int = FastApiPath(..., description="ID khách hàng cần tra cứu")
):
    """Lấy thông tin chi tiết RFM, cụm và 10 giao dịch gần nhất của khách hàng."""
    service = ModelService.get_instance()
    customer = service.get_customer(customer_id)
    if not customer:
        raise HTTPException(
            status_code=404,
            detail=f"Khách hàng có ID {customer_id} không tồn tại trong hệ thống."
        )
    return customer


@app.get("/clusters", response_model=list[ClusterItem], tags=["Clusters"])
def get_clusters():
    """Lấy danh sách thông tin hồ sơ của các cụm khách hàng."""
    service = ModelService.get_instance()
    return service.get_clusters()


@app.get("/clusters/points", response_model=list[ClusterPoint], tags=["Clusters"])
def get_cluster_points():
    """Lấy tọa độ PCA 2D phục vụ vẽ biểu đồ phân tán cụm khách hàng."""
    service = ModelService.get_instance()
    return service.get_cluster_points(max_points=config.PCA_SAMPLE_SIZE)


@app.get("/clusters/{cluster_id}", response_model=ClusterDetail, tags=["Clusters"])
def get_cluster_detail(
    cluster_id: int = FastApiPath(..., ge=0, description="Mã cụm (0, 1, 2, ...)")
):
    """Lấy chi tiết một cụm kèm top 10 sản phẩm bán chạy nhất trong cụm."""
    service = ModelService.get_instance()
    cluster_detail = service.get_cluster(cluster_id)
    if not cluster_detail:
        raise HTTPException(
            status_code=404,
            detail=f"Cụm {cluster_id} không tồn tại."
        )
    return cluster_detail


@app.get("/recommend/{customer_id}", response_model=RecommendResponse, tags=["Recommendation"])
def get_recommendations(
    customer_id: int = FastApiPath(..., description="ID khách hàng cần nhận gợi ý"),
    top_k: int = Query(10, ge=1, le=50, description="Số sản phẩm gợi ý (1-50)"),
    model: str = Query("hybrid", description="Thuật toán gợi ý")
):
    """
    Sinh danh sách gợi ý sản phẩm cá nhân hóa:
    - Các thuật toán hợp lệ: popularity, cluster_popularity, item_cf, als, content, hybrid
    - Khách hàng cold-start trả về gợi ý Popularity với 'cold_start': true (không trả 404)
    """
    if model not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=422,
            detail=f"Thuật toán '{model}' không hợp lệ. Phải thuộc một trong: {sorted(list(ALLOWED_MODELS))}"
        )

    service = ModelService.get_instance()
    return service.get_recommendations(customer_id=customer_id, top_k=top_k, model_name=model)


@app.get("/products/{stockcode}", response_model=ProductDetail, tags=["Products"])
def get_product_detail(
    stockcode: str = FastApiPath(..., description="Mã sản phẩm (stockcode)")
):
    """Lấy thông tin chi tiết và ảnh của sản phẩm."""
    service = ModelService.get_instance()
    product = service.get_product(stockcode)
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Sản phẩm với mã '{stockcode}' không tồn tại."
        )
    return product


@app.get("/metrics", response_model=MetricsResponse, tags=["Evaluation"])
def get_metrics():
    """Lấy toàn bộ chỉ số đánh giá phân cụm và các mô hình gợi ý."""
    service = ModelService.get_instance()
    return service.get_metrics()
