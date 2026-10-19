"""
Cấu hình tập trung cho toàn bộ dự án Personalized Marketing.
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

# File dữ liệu thô
RAW_DATA_PATH: Path = RAW_DATA_DIR / "online_retail_cleaned.csv"
# Dự phòng nếu file thô ở tên khác
FALLBACK_RAW_DATA_PATHS = [
    RAW_DATA_DIR / "online_retail.csv",
    DATA_DIR / "online_retail_cleaned.csv",
    DATA_DIR / "online_retail.csv",
]

# File dữ liệu sau xử lý
TRANSACTIONS_CLEAN_PATH: Path = PROCESSED_DATA_DIR / "transactions_clean.parquet"
TRAIN_DATA_PATH: Path = PROCESSED_DATA_DIR / "train.parquet"
TEST_DATA_PATH: Path = PROCESSED_DATA_DIR / "test.parquet"
RFM_TRAIN_PATH: Path = PROCESSED_DATA_DIR / "rfm_train.parquet"
INTERACTIONS_TRAIN_PATH: Path = PROCESSED_DATA_DIR / "interactions_train.parquet"
PRODUCTS_PATH: Path = PROCESSED_DATA_DIR / "products.csv"
TEST_TRUTH_PATH: Path = PROCESSED_DATA_DIR / "test_truth.parquet"

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
# Số ngày cuối cùng làm tập test (theo thời gian)
TEST_DAYS: int = 60

# Ngưỡng lọc ma trận tương tác
MIN_CUSTOMER_INVOICES: int = 2
MIN_PRODUCT_PURCHASES: int = 5

# Mã stockcode không phải sản phẩm thông thường
NON_PRODUCT_CODES: set = {
    "POST", "D", "M", "DOT", "CRUK",
    "BANK CHARGES", "AMAZONFEE", "S", "B"
}
NON_PRODUCT_PREFIXES: tuple = ("GIFT_", "TEST")

# ---------------------------------------------------------
# THAM SỐ GÁN ẢNH (FETCH IMAGES)
# ---------------------------------------------------------
TOP_N_IMAGES: int = 500
IMAGE_SIZE: tuple = (400, 400)
PEXELS_API_KEY: str = os.getenv("PEXELS_API_KEY", "")

# ---------------------------------------------------------
# THAM SỐ PHÂN CỤM (CLUSTERING)
# ---------------------------------------------------------
CLUSTER_K: int = 4
K_EVAL_RANGE: range = range(2, 11)
PCA_SAMPLE_SIZE: int = 2000

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
