"""
Cấu hình tập trung cho toàn bộ dự án Personalized Marketing (bộ dữ liệu H&M).
Mọi hằng số, đường dẫn, siêu tham số và random seed được định nghĩa tại đây.
"""

from pathlib import Path
import os
import sys

# Đảm bảo UTF-8 cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Random seed dùng chung cho toàn bộ dự án
RANDOM_SEED: int = 42

# ---------------------------------------------------------
# ĐƯỜNG DẪN THƯ MỤC & FILE
# ---------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent

# Thêm PROJECT_ROOT vào sys.path để các module import dễ dàng
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
IMAGES_DIR: Path = DATA_DIR / "images"

BACKEND_DIR: Path = PROJECT_ROOT / "backend"
MODELS_DIR: Path = BACKEND_DIR / "models"

# Dữ liệu thô H&M (tải bằng data_processing/download_hm.py, không đưa lên GitHub)
KAGGLE_COMPETITION: str = "h-and-m-personalized-fashion-recommendations"
HM_RAW_DIR: Path = RAW_DATA_DIR / "hm"
TRANSACTIONS_RAW_PATH: Path = HM_RAW_DIR / "transactions_train.csv"
ARTICLES_RAW_PATH: Path = HM_RAW_DIR / "articles.csv"
CUSTOMERS_RAW_PATH: Path = HM_RAW_DIR / "customers.csv"

# Bản Parquet của dữ liệu thô (đọc nhanh hơn CSV hàng chục lần)
TRANSACTIONS_RAW_PARQUET: Path = HM_RAW_DIR / "transactions_train.parquet"

# File dữ liệu sau xử lý
TRANSACTIONS_CLEAN_PATH: Path = PROCESSED_DATA_DIR / "transactions_clean.parquet"
TRAIN_DATA_PATH: Path = PROCESSED_DATA_DIR / "train.parquet"
TEST_DATA_PATH: Path = PROCESSED_DATA_DIR / "test.parquet"
RFM_TRAIN_PATH: Path = PROCESSED_DATA_DIR / "rfm_train.parquet"
INTERACTIONS_TRAIN_PATH: Path = PROCESSED_DATA_DIR / "interactions_train.parquet"
PRODUCTS_PATH: Path = PROCESSED_DATA_DIR / "products.csv"
CUSTOMERS_PATH: Path = PROCESSED_DATA_DIR / "customers.parquet"
TEST_TRUTH_PATH: Path = PROCESSED_DATA_DIR / "test_truth.parquet"

# Bảng đổi customer_id (chuỗi hash 64 ký tự của H&M) sang số nguyên ngắn để API/web dùng
CUSTOMER_ID_MAP_PATH: Path = PROCESSED_DATA_DIR / "customer_id_map.parquet"

# File ảnh placeholder
PLACEHOLDER_IMAGE_PATH: Path = IMAGES_DIR / "placeholder.jpg"

# Artifacts của mô hình
CLUSTERING_MODEL_PATH: Path = MODELS_DIR / "clustering.pkl"
CUSTOMER_CLUSTERS_PATH: Path = MODELS_DIR / "customer_clusters.parquet"
CLUSTER_PROFILES_PATH: Path = MODELS_DIR / "cluster_profiles.json"
CLUSTER_K_SCORES_PATH: Path = MODELS_DIR / "cluster_k_scores.json"
RECOMMENDERS_PATH: Path = MODELS_DIR / "recommenders.pkl"
POPULARITY_GLOBAL_PATH: Path = MODELS_DIR / "popularity_global.json"
METRICS_PATH: Path = MODELS_DIR / "metrics.json"

# ---------------------------------------------------------
# THAM SỐ XỬ LÝ DỮ LIỆU
# ---------------------------------------------------------
# Chỉ dùng dữ liệu từ ngày này trở đi (toàn bộ: 2018-09-20 → 2020-09-22).
# Mặc định lấy 1 năm gần nhất để vừa RAM laptop; đặt None để dùng toàn bộ 2 năm.
DATA_START_DATE: str | None = "2019-09-23"

# Số ngày cuối cùng làm tập test (theo thời gian)
TEST_DAYS: int = 28

# Một "đơn hàng" = toàn bộ món một khách mua trong cùng một ngày
# (H&M không có mã hóa đơn).
MIN_CUSTOMER_ORDERS: int = 2       # khách cần ít nhất N đơn để vào ma trận tương tác
MIN_ARTICLE_PURCHASES: int = 20    # sản phẩm cần ít nhất N lượt mua

# Giới hạn số sản phẩm cho các mô hình gợi ý.
# Item-CF lưu ma trận tương đồng đầy đủ n_items × n_items (float64):
#   10.000 sản phẩm ≈ 0,8 GB RAM; 20.000 sản phẩm ≈ 3,2 GB RAM.
MAX_ITEMS_CF: int = 10_000

# Số khách dùng để huấn luyện mô hình gợi ý (lấy ngẫu nhiên trong số khách có ≥ MIN_CUSTOMER_ORDERS đơn).
# Content-Based lưu 1 vector 1.000 chiều cho mỗi khách: 50.000 khách ≈ 0,4 GB RAM.
# Phân cụm RFM vẫn chạy trên TOÀN BỘ khách.
MAX_CUSTOMERS_RECSYS: int = 50_000

# Số khách lấy mẫu để đánh giá mô hình (đánh giá cả triệu khách sẽ rất lâu)
EVAL_SAMPLE_CUSTOMERS: int = 10_000

# ---------------------------------------------------------
# THAM SỐ ẢNH SẢN PHẨM
# ---------------------------------------------------------
# Ảnh thật của H&M: chỉ tải ảnh của N sản phẩm bán chạy nhất (bộ đầy đủ ~30 GB)
TOP_N_IMAGES: int = 5_000
IMAGE_SIZE: tuple = (400, 400)

# ---------------------------------------------------------
# THAM SỐ PHÂN CỤM (CLUSTERING)
# ---------------------------------------------------------
CLUSTER_K: int = 4
K_EVAL_RANGE: range = range(2, 11)
PCA_SAMPLE_SIZE: int = 2000
# K-Means trên mẫu khách để thử K nhanh; sau đó gán cụm cho toàn bộ khách
CLUSTER_FIT_SAMPLE: int = 200_000

# ---------------------------------------------------------
# THAM SỐ GỢI Ý (RECOMMENDER) & ĐÁNH GIÁ (EVALUATE)
# ---------------------------------------------------------
ALS_FACTORS: int = 64
ALS_ITERATIONS: int = 20
ALS_REGULARIZATION: float = 0.1

HYBRID_WEIGHTS: dict = {
    "als": 0.5,
    "content": 0.2,
    "cluster_pop": 0.3
}

EXCLUDE_SEEN: bool = False
DEFAULT_TOP_K: int = 10
EVAL_K_LIST: list[int] = [5, 10, 20]
