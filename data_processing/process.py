"""
Tiền xử lý bộ dữ liệu H&M Personalized Fashion Recommendations (data_processing/process.py).

Dùng Polars (xử lý lười - lazy) + Parquet để xử lý ~31,8 triệu giao dịch trên laptop.
Đầu ra GIỮ NGUYÊN định dạng cột như pipeline cũ, để train.py / recommender.py / backend
chạy được mà không phải sửa:

  - transactions_clean.parquet, train.parquet, test.parquet
        customer_id (int), invoice, invoice_date, stockcode, description,
        quantity, price, total_price, sales_channel_id
  - rfm_train.parquet          customer_id, recency, frequency, monetary
  - interactions_train.parquet customer_id, stockcode, n_purchases, quantity
  - products.csv               stockcode, description, n_purchases, image_path, ... , content_text
  - test_truth.parquet         customer_id, stockcode
  - customers.parquet          customer_id, age, club_member_status, fashion_news_frequency
  - customer_id_map.parquet    customer_hash (mã gốc H&M) <-> customer_id (số nguyên)

Quy ước ánh xạ H&M -> cột cũ:
  article_id -> stockcode, prod_name -> description, t_dat -> invoice_date,
  (khách, ngày mua) -> invoice, số dòng trùng -> quantity, price × quantity -> total_price
"""

import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config


def log_rows(step: str, n: int, before: int | None = None) -> None:
    if before is None:
        print(f"  {step}: {n:,} dòng")
    else:
        print(f"  {step}: {n:,} dòng (giảm {before - n:,})")


# =========================================================
# [1/6] CSV -> PARQUET
# =========================================================
def convert_transactions_to_parquet() -> None:
    """Chuyển transactions_train.csv (~3,5 GB) sang Parquet theo kiểu streaming (không nạp hết vào RAM)."""
    print("\n[1/6] Chuyển transactions_train.csv sang Parquet:")
    if config.TRANSACTIONS_RAW_PARQUET.exists():
        print(f"  Đã có sẵn: {config.TRANSACTIONS_RAW_PARQUET} -> bỏ qua")
        return
    if not config.TRANSACTIONS_RAW_PATH.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {config.TRANSACTIONS_RAW_PATH}. "
            "Chạy 'python data_processing/download_hm.py' và giải nén vào data/raw/hm/ trước."
        )

    t0 = time.time()
    (
        pl.scan_csv(
            config.TRANSACTIONS_RAW_PATH,
            schema_overrides={
                "t_dat": pl.Utf8,
                "customer_id": pl.Utf8,
                "article_id": pl.Utf8,
                "price": pl.Float64,
                "sales_channel_id": pl.Int8,
            },
        )
        .with_columns(
            pl.col("t_dat").str.strptime(pl.Date, "%Y-%m-%d"),
            pl.col("article_id").str.zfill(10),
        )
        .sink_parquet(config.TRANSACTIONS_RAW_PARQUET)
    )
    csv_mb = config.TRANSACTIONS_RAW_PATH.stat().st_size / 1e6
    pq_mb = config.TRANSACTIONS_RAW_PARQUET.stat().st_size / 1e6
    print(f"  CSV: {csv_mb:,.0f} MB -> Parquet: {pq_mb:,.0f} MB (nhỏ hơn {csv_mb / pq_mb:.1f} lần)")
    print(f"  Thời gian chuyển đổi: {time.time() - t0:.1f}s")


def load_articles() -> pl.DataFrame:
    df = pl.read_csv(config.ARTICLES_RAW_PATH, schema_overrides={"article_id": pl.Utf8}, infer_schema_length=0)
    keep = [
        "article_id", "prod_name", "product_type_name", "product_group_name",
        "colour_group_name", "department_name", "index_name", "garment_group_name", "detail_desc",
    ]
    df = df.select([c for c in keep if c in df.columns]).with_columns(pl.col("article_id").str.zfill(10))
    return df


# =========================================================
# [2/6] LÀM SẠCH
# =========================================================
def clean_transactions(articles: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Trả về (clean_df, customer_id_map)."""
    print("\n[2/6] Làm sạch dữ liệu giao dịch:")
    lf = pl.scan_parquet(config.TRANSACTIONS_RAW_PARQUET)

    n0 = lf.select(pl.len()).collect().item()
    log_rows("Dữ liệu ban đầu", n0)

    # Bước 1: lọc theo khoảng thời gian
    if config.DATA_START_DATE:
        start = pl.lit(config.DATA_START_DATE).str.strptime(pl.Date, "%Y-%m-%d")
        lf = lf.filter(pl.col("t_dat") >= start)
    n1 = lf.select(pl.len()).collect().item()
    log_rows(f"Bước 1 (Chỉ giữ từ {config.DATA_START_DATE or 'đầu'})", n1, n0)

    # Bước 2: bỏ dòng thiếu mã / giá <= 0
    lf = lf.filter(
        pl.col("customer_id").is_not_null()
        & pl.col("article_id").is_not_null()
        & pl.col("t_dat").is_not_null()
        & (pl.col("price") > 0)
    )
    n2 = lf.select(pl.len()).collect().item()
    log_rows("Bước 2 (Bỏ thiếu mã khách/sản phẩm, giá <= 0)", n2, n1)

    # Bước 3: gộp các dòng trùng (cùng khách, ngày, sản phẩm, giá, kênh) thành 1 dòng có quantity
    # Ở H&M, mua 2 món giống hệt nhau = 2 dòng y hệt -> KHÔNG được xóa, mà phải đếm số lượng.
    lf = lf.group_by(["customer_id", "t_dat", "article_id", "price", "sales_channel_id"]).agg(
        pl.len().cast(pl.Int32).alias("quantity")
    )
    df = lf.collect()
    log_rows("Bước 3 (Gộp dòng trùng thành số lượng)", len(df), n2)

    # Bước 4: chỉ giữ sản phẩm có trong articles.csv
    before = len(df)
    df = df.join(articles.select("article_id", "prod_name"), on="article_id", how="inner")
    log_rows("Bước 4 (Ghép tên sản phẩm từ articles.csv)", len(df), before)

    # Bước 5: đổi mã khách (hash 64 ký tự) -> số nguyên ngắn
    id_map = (
        df.select(pl.col("customer_id").unique().sort())
        .with_row_index("new_id", offset=1)
        .select(
            pl.col("customer_id").alias("customer_hash"),
            pl.col("new_id").cast(pl.Int64).alias("customer_id"),
        )
    )
    df = (
        df.join(id_map, left_on="customer_id", right_on="customer_hash", how="left")
        .drop("customer_id")
        .rename({"customer_id_right": "customer_id"})
    )
    print(f"  Bước 5 (Đổi mã khách sang số nguyên): {len(id_map):,} khách")

    # Đưa về đúng tên cột của pipeline cũ
    df = df.select(
        pl.col("customer_id"),
        (pl.col("customer_id").cast(pl.Utf8) + "_" + pl.col("t_dat").cast(pl.Utf8)).alias("invoice"),
        pl.col("t_dat").cast(pl.Datetime("us")).alias("invoice_date"),
        pl.col("article_id").alias("stockcode"),
        pl.col("prod_name").str.to_lowercase().alias("description"),
        pl.col("quantity"),
        pl.col("price"),
        (pl.col("price") * pl.col("quantity")).alias("total_price"),
        pl.col("sales_channel_id"),
    )
    print(f"  Hoàn thành làm sạch: còn {len(df):,} dòng ({len(df) / n0:.1%} so với ban đầu)")
    return df, id_map


# =========================================================
# [3/6] CHIA TRAIN / TEST
# =========================================================
def split_train_test(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    print(f"\n[3/6] Chia tập Train/Test theo thời gian ({config.TEST_DAYS} ngày cuối làm Test):")
    max_date = df["invoice_date"].max()
    split_date = max_date - np.timedelta64(config.TEST_DAYS, "D")
    train_df = df.filter(pl.col("invoice_date") <= split_date)
    test_df = df.filter(pl.col("invoice_date") > split_date)

    fmt = lambda d: str(d)[:10]
    print(f"  Khoảng thời gian toàn bộ: {fmt(df['invoice_date'].min())} đến {fmt(max_date)}")
    print(f"  Ngày phân tách (split_date): {fmt(split_date)}")
    print(f"  Tập Train: {len(train_df):,} dòng, {train_df['customer_id'].n_unique():,} khách hàng")
    print(f"  Tập Test: {len(test_df):,} dòng, {test_df['customer_id'].n_unique():,} khách hàng")
    return train_df, test_df


# =========================================================
# [4/6] RFM
# =========================================================
def compute_rfm_train(train_df: pl.DataFrame) -> pl.DataFrame:
    """
    recency  = số ngày từ lần mua cuối đến (ngày lớn nhất của train + 1)
    frequency = số đơn hàng (số ngày khác nhau có mua)
    monetary  = tổng total_price (giá đã được H&M chuẩn hóa)
    """
    print("\n[4/6] Tính chỉ số RFM trên tập Train (không data leakage):")
    snapshot = train_df["invoice_date"].max() + np.timedelta64(1, "D")
    rfm = (
        train_df.group_by("customer_id")
        .agg(
            pl.col("invoice_date").max().alias("last_date"),
            pl.col("invoice").n_unique().cast(pl.Int32).alias("frequency"),
            pl.col("total_price").sum().round(4).alias("monetary"),
        )
        .with_columns(
            (pl.lit(snapshot) - pl.col("last_date")).dt.total_days().cast(pl.Int32).alias("recency")
        )
        .select("customer_id", "recency", "frequency", "monetary")
        .sort("customer_id")
    )
    print(f"  Số khách hàng trong rfm_train: {len(rfm):,}")
    for c in ["recency", "frequency", "monetary"]:
        print(f"  {c.capitalize()}: min={rfm[c].min():.4g}, mean={rfm[c].mean():.4g}, max={rfm[c].max():.4g}")
    return rfm


# =========================================================
# [5/6] INTERACTIONS, PRODUCTS, TEST_TRUTH
# =========================================================
def build_interactions_and_products(
    clean_df: pl.DataFrame, train_df: pl.DataFrame, test_df: pl.DataFrame, articles: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    print("\n[5/6] Xây dựng ma trận tương tác, danh mục sản phẩm và test_truth:")
    rng = np.random.default_rng(config.RANDOM_SEED)

    # 1. interactions: n_purchases = số đơn hàng khác nhau có sản phẩm đó
    interactions = train_df.group_by(["customer_id", "stockcode"]).agg(
        pl.col("invoice").n_unique().cast(pl.Int32).alias("n_purchases"),
        pl.col("quantity").sum().cast(pl.Int32).alias("quantity"),
    )
    print(f"  Số tương tác ban đầu: {len(interactions):,}")

    # Khách đủ số đơn
    cust_orders = train_df.group_by("customer_id").agg(pl.col("invoice").n_unique().alias("n_orders"))
    valid_customers = cust_orders.filter(pl.col("n_orders") >= config.MIN_CUSTOMER_ORDERS)["customer_id"].to_numpy()
    print(f"  Khách có >= {config.MIN_CUSTOMER_ORDERS} đơn: {len(valid_customers):,}")

    # Lấy ngẫu nhiên MAX_CUSTOMERS_RECSYS khách để huấn luyện mô hình gợi ý (giới hạn RAM)
    if len(valid_customers) > config.MAX_CUSTOMERS_RECSYS:
        valid_customers = rng.choice(valid_customers, size=config.MAX_CUSTOMERS_RECSYS, replace=False)
        print(f"  Lấy ngẫu nhiên {config.MAX_CUSTOMERS_RECSYS:,} khách cho mô hình gợi ý")

    # Sản phẩm phổ biến: đủ lượt mua và nằm trong top MAX_ITEMS_CF
    prod_pop = (
        interactions.group_by("stockcode")
        .agg(pl.col("n_purchases").sum().alias("total"))
        .filter(pl.col("total") >= config.MIN_ARTICLE_PURCHASES)
        .sort("total", descending=True)
        .head(config.MAX_ITEMS_CF)
    )
    valid_products = prod_pop["stockcode"].to_list()
    print(f"  Sản phẩm giữ lại (>= {config.MIN_ARTICLE_PURCHASES} lượt, top {config.MAX_ITEMS_CF:,}): {len(valid_products):,}")

    interactions_filtered = interactions.filter(
        pl.col("customer_id").is_in(valid_customers) & pl.col("stockcode").is_in(valid_products)
    )
    print(f"  Sau khi lọc: {len(interactions_filtered):,} tương tác, "
          f"{interactions_filtered['customer_id'].n_unique():,} khách, "
          f"{interactions_filtered['stockcode'].n_unique():,} sản phẩm")

    # 2. products.csv: mọi sản phẩm xuất hiện trong dữ liệu đã làm sạch
    prod_counts = clean_df.group_by("stockcode").agg(pl.col("invoice").n_unique().cast(pl.Int32).alias("n_purchases"))
    text_cols = [c for c in ["prod_name", "product_type_name", "product_group_name",
                             "colour_group_name", "index_name", "garment_group_name", "detail_desc"]
                 if c in articles.columns]
    products = (
        prod_counts.join(articles.rename({"article_id": "stockcode"}), on="stockcode", how="left")
        .with_columns(
            pl.col("prod_name").str.to_lowercase().alias("description"),
            pl.concat_str([pl.col(c).fill_null("") for c in text_cols], separator=" ")
              .str.to_lowercase().alias("content_text"),
            pl.lit("").alias("image_path"),
        )
        .select(
            "stockcode", "description", "n_purchases", "image_path",
            *[c for c in ["product_type_name", "product_group_name", "colour_group_name"] if c in articles.columns],
            "content_text",
        )
        .sort("n_purchases", descending=True)
    )
    print(f"  Tổng số sản phẩm trong products.csv: {len(products):,}")

    # 3. test_truth: lấy mẫu EVAL_SAMPLE_CUSTOMERS khách (có trong interactions và có mua trong test)
    train_custs = interactions_filtered["customer_id"].unique().to_list()
    test_pairs = (
        test_df.filter(pl.col("customer_id").is_in(train_custs))
        .select("customer_id", "stockcode")
        .unique()
    )
    test_custs = test_pairs["customer_id"].unique().to_numpy()
    if len(test_custs) > config.EVAL_SAMPLE_CUSTOMERS:
        test_custs = rng.choice(test_custs, size=config.EVAL_SAMPLE_CUSTOMERS, replace=False)
    test_truth = test_pairs.filter(pl.col("customer_id").is_in(test_custs)).sort("customer_id")
    print(f"  Số cặp test_truth: {len(test_truth):,} cặp, từ {test_truth['customer_id'].n_unique():,} khách (lấy mẫu)")

    return interactions_filtered.sort(["customer_id", "stockcode"]), products, test_truth


# =========================================================
# [6/6] HỒ SƠ KHÁCH HÀNG
# =========================================================
def build_customers(id_map: pl.DataFrame) -> pl.DataFrame:
    print("\n[6/6] Chuẩn bị hồ sơ khách hàng (tuổi, hạng thành viên):")
    if not config.CUSTOMERS_RAW_PATH.exists():
        print("  Không có customers.csv -> bỏ qua")
        return pl.DataFrame()
    cust = pl.read_csv(config.CUSTOMERS_RAW_PATH, infer_schema_length=10_000)
    keep = [c for c in ["customer_id", "age", "club_member_status", "fashion_news_frequency"] if c in cust.columns]
    cust = (
        cust.select(keep)
        .join(id_map, left_on="customer_id", right_on="customer_hash", how="inner")
        .drop("customer_id")
        .rename({"customer_id_right": "customer_id"})
        .select("customer_id", *[c for c in keep if c != "customer_id"])
        .sort("customer_id")
    )
    print(f"  Số khách có hồ sơ: {len(cust):,}")
    return cust


def main():
    t0 = time.time()
    print("=" * 60)
    print("BẮT ĐẦU TIỀN XỬ LÝ DỮ LIỆU H&M")
    print("=" * 60)
    config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    convert_transactions_to_parquet()
    articles = load_articles()
    print(f"  articles.csv: {len(articles):,} sản phẩm")

    clean_df, id_map = clean_transactions(articles)
    clean_df.write_parquet(config.TRANSACTIONS_CLEAN_PATH)
    id_map.write_parquet(config.CUSTOMER_ID_MAP_PATH)
    print(f"-> Đã lưu: {config.TRANSACTIONS_CLEAN_PATH}")

    train_df, test_df = split_train_test(clean_df)
    train_df.write_parquet(config.TRAIN_DATA_PATH)
    test_df.write_parquet(config.TEST_DATA_PATH)
    print(f"-> Đã lưu: {config.TRAIN_DATA_PATH}")
    print(f"-> Đã lưu: {config.TEST_DATA_PATH}")

    rfm = compute_rfm_train(train_df)
    rfm.write_parquet(config.RFM_TRAIN_PATH)
    print(f"-> Đã lưu: {config.RFM_TRAIN_PATH}")

    interactions, products, test_truth = build_interactions_and_products(clean_df, train_df, test_df, articles)
    interactions.write_parquet(config.INTERACTIONS_TRAIN_PATH)
    products.write_csv(config.PRODUCTS_PATH)
    test_truth.write_parquet(config.TEST_TRUTH_PATH)
    print(f"-> Đã lưu: {config.INTERACTIONS_TRAIN_PATH}")
    print(f"-> Đã lưu: {config.PRODUCTS_PATH}")
    print(f"-> Đã lưu: {config.TEST_TRUTH_PATH}")

    customers = build_customers(id_map)
    if len(customers):
        customers.write_parquet(config.CUSTOMERS_PATH)
        print(f"-> Đã lưu: {config.CUSTOMERS_PATH}")

    print("=" * 60)
    print(f"TIỀN XỬ LÝ HOÀN THÀNH trong {time.time() - t0:.1f} giây!")
    print("=" * 60)


if __name__ == "__main__":
    main()
    