"""
Script làm sạch dữ liệu, chia train/test theo thời gian và tạo các tập dữ liệu trung gian:
- transactions_clean.parquet
- train.parquet, test.parquet
- rfm_train.parquet
- interactions_train.parquet
- products.csv
- test_truth.parquet
"""

import sys
import time
from pathlib import Path

# Đảm bảo import được config từ thư mục gốc
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
import pandas as pd
import numpy as np


def find_raw_data_file() -> Path:
    """
    Tìm file dữ liệu thô từ đường dẫn cấu hình hoặc các vị trí dự phòng.
    """
    if config.RAW_DATA_PATH.exists():
        return config.RAW_DATA_PATH
    for fallback in config.FALLBACK_RAW_DATA_PATHS:
        if fallback.exists():
            return fallback
    raise FileNotFoundError(
        f"Không tìm thấy file dữ liệu thô tại '{config.RAW_DATA_PATH}' "
        f"hoặc các vị trí dự phòng. Vui lòng tải file online_retail_cleaned.csv "
        f"vào thư mục data/raw/."
    )


def load_and_standardize_schema(file_path: Path) -> pd.DataFrame:
    """
    Đọc file CSV và chuẩn hóa tên cột (tự động phát hiện cột ngày và cột đơn giá).
    """
    print(f"\n[1/5] Đang đọc dữ liệu từ: {file_path}")
    start_t = time.time()
    
    # Đọc mẫu 1000 dòng để dò tên cột và kiểu dữ liệu
    df_sample = pd.read_csv(file_path, nrows=1000)
    col_mapping = {}
    lower_cols = {col.lower().strip(): col for col in df_sample.columns}
    
    # Tìm cột invoice/hóa đơn
    for candidate in ["invoice", "invoiceno", "invoice_no"]:
        if candidate in lower_cols:
            col_mapping[lower_cols[candidate]] = "invoice"
            break
            
    # Tìm cột stockcode/mã sản phẩm
    for candidate in ["stockcode", "stock_code"]:
        if candidate in lower_cols:
            col_mapping[lower_cols[candidate]] = "stockcode"
            break
            
    # Tìm cột description/mô tả
    for candidate in ["description", "desc"]:
        if candidate in lower_cols:
            col_mapping[lower_cols[candidate]] = "description"
            break
            
    # Tìm cột quantity/số lượng
    for candidate in ["quantity", "qty"]:
        if candidate in lower_cols:
            col_mapping[lower_cols[candidate]] = "quantity"
            break
            
    # Tìm cột chứa 'date'
    for col_lower, original_col in lower_cols.items():
        if "date" in col_lower:
            col_mapping[original_col] = "invoice_date"
            break
            
    # Tìm cột price/đơn giá
    for candidate in ["price", "unitprice", "unit_price"]:
        if candidate in lower_cols:
            col_mapping[lower_cols[candidate]] = "price"
            break
            
    # Tìm cột customer_id/mã khách hàng
    for candidate in ["customer_id", "customerid"]:
        if candidate in lower_cols:
            col_mapping[lower_cols[candidate]] = "customer_id"
            break
            
    # Tìm cột country/quốc gia
    for candidate in ["country"]:
        if candidate in lower_cols:
            col_mapping[lower_cols[candidate]] = "country"
            break
            
    # Tìm cột is_cancelled
    for candidate in ["is_cancelled", "cancelled", "iscancelled"]:
        if candidate in lower_cols:
            col_mapping[lower_cols[candidate]] = "is_cancelled"
            break
            
    # Tìm cột total_price
    for candidate in ["total_price", "totalprice"]:
        if candidate in lower_cols:
            col_mapping[lower_cols[candidate]] = "total_price"
            break

    # Đọc toàn bộ file với kiểu dữ liệu stockcode và invoice là str
    dtype_spec = {
        col_mapping.get(col, col): str
        for col in ["invoice", "stockcode", "invoiceno", "stock_code"]
    }
    df = pd.read_csv(file_path, low_memory=False)
    df.rename(columns=col_mapping, inplace=True)
    
    # In schema thực tế
    print(f"Schema thực tế: {len(df):,} dòng, {len(df.columns)} cột")
    for col in df.columns:
        print(f"  - {col}: {df[col].dtype}")
        
    # Chuẩn hóa invoice_date
    if "invoice_date" in df.columns:
        df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
    else:
        raise ValueError("Không tìm thấy cột chứa thông tin ngày tháng (invoice_date)!")

    # Chuẩn hóa price nếu thiếu
    if "price" not in df.columns or df["price"].isnull().all():
        if "total_price" in df.columns and "quantity" in df.columns:
            print("  -> Tính 'price' từ 'total_price / quantity'")
            df["price"] = df["total_price"] / df["quantity"]
        else:
            raise ValueError("Không xác định được cột đơn giá 'price'!")
            
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    
    print(f"Thời gian đọc và chuẩn hóa schema: {time.time() - start_t:.2f}s")
    return df


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Thực hiện 7 bước làm sạch dữ liệu theo quy định mục 2.1.
    In số dòng sau mỗi bước để dùng cho báo cáo.
    """
    print("\n[2/5] Bắt đầu quá trình làm sạch dữ liệu:")
    initial_rows = len(df)
    print(f"  Số dòng ban đầu: {initial_rows:,}")

    # Bước 1: Bỏ dòng thiếu customer_id, ép customer_id về int
    df = df[df["customer_id"].notnull()].copy()
    df["customer_id"] = df["customer_id"].astype(int)
    print(f"  Bước 1 (Bỏ thiếu customer_id): {len(df):,} dòng (giảm {initial_rows - len(df):,})")
    prev_rows = len(df)

    # Bước 2: Bỏ dòng is_cancelled == True (hoặc invoice bắt đầu bằng 'C')
    is_cancelled_mask = pd.Series(False, index=df.index)
    if "is_cancelled" in df.columns:
        is_cancelled_mask = (
            df["is_cancelled"].astype(str).str.lower().isin(["true", "1", "yes"])
        )
    # Hóa đơn hủy thường có mã bắt đầu bằng chữ C
    invoice_cancel_mask = df["invoice"].astype(str).str.upper().str.startswith("C")
    cancelled = is_cancelled_mask | invoice_cancel_mask
    df = df[~cancelled].copy()
    print(f"  Bước 2 (Bỏ hóa đơn hủy): {len(df):,} dòng (giảm {prev_rows - len(df):,})")
    prev_rows = len(df)

    # Bước 3: Bỏ dòng quantity <= 0 hoặc price <= 0
    df = df[(df["quantity"] > 0) & (df["price"] > 0)].copy()
    print(f"  Bước 3 (Bỏ quantity <= 0 hoặc price <= 0): {len(df):,} dòng (giảm {prev_rows - len(df):,})")
    prev_rows = len(df)

    # Bước 4: Bỏ mã không phải sản phẩm
    df["stockcode"] = df["stockcode"].astype(str).str.strip()
    upper_stock = df["stockcode"].str.upper()
    is_non_prod = upper_stock.isin(config.NON_PRODUCT_CODES)
    for prefix in config.NON_PRODUCT_PREFIXES:
        is_non_prod = is_non_prod | upper_stock.str.startswith(prefix)
    df = df[~is_non_prod].copy()
    print(f"  Bước 4 (Bỏ mã phi sản phẩm): {len(df):,} dòng (giảm {prev_rows - len(df):,})")
    prev_rows = len(df)

    # Bước 5: Bỏ dòng trùng lặp hoàn toàn
    df = df.drop_duplicates().copy()
    print(f"  Bước 5 (Bỏ trùng lặp hoàn toàn): {len(df):,} dòng (giảm {prev_rows - len(df):,})")
    prev_rows = len(df)

    # Bước 6: Chuẩn hóa description: chữ thường, strip khoảng trắng.
    # Mỗi stockcode lấy mô tả xuất hiện nhiều nhất làm mô tả chính.
    df["description"] = df["description"].fillna("").astype(str).str.lower().str.strip()
    
    # Tìm mô tả xuất hiện nhiều nhất cho từng stockcode
    desc_counts = (
        df[df["description"] != ""]
        .groupby(["stockcode", "description"])
        .size()
        .reset_index(name="count")
    )
    # Sắp xếp theo số lần xuất hiện giảm dần và lấy hàng đầu tiên cho mỗi stockcode
    best_descriptions = (
        desc_counts.sort_values(["stockcode", "count"], ascending=[True, False])
        .drop_duplicates(subset=["stockcode"])
        .set_index("stockcode")["description"]
        .to_dict()
    )
    
    # Gán mô tả chuẩn cho các dòng
    df["description"] = df["stockcode"].map(best_descriptions).fillna(df["description"])
    # Nếu vẫn còn chuỗi rỗng thì đặt "unknown product"
    df["description"] = df["description"].replace("", "unknown product")
    print(f"  Bước 6 (Chuẩn hóa description theo stockcode): {len(df):,} dòng")
    prev_rows = len(df)

    # Bước 7: Tính lại total_price = quantity * price
    df["total_price"] = (df["quantity"] * df["price"]).round(2)
    print(f"  Bước 7 (Tính lại total_price): {len(df):,} dòng")

    # Giữ các cột chuẩn
    output_cols = [
        "invoice", "stockcode", "description", "quantity",
        "invoice_date", "price", "customer_id", "country", "total_price"
    ]
    df = df[output_cols].copy()
    print(f"Hoàn thành làm sạch: còn lại {len(df):,} dòng ({len(df)/initial_rows*100:.1f}% ban đầu)")
    return df


def split_train_test(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Chia train/test theo thời gian: TEST_DAYS ngày cuối là test, còn lại là train.
    """
    print(f"\n[3/5] Chia tập Train/Test theo thời gian ({config.TEST_DAYS} ngày cuối làm Test):")
    max_date = df["invoice_date"].max()
    split_date = max_date - pd.Timedelta(days=config.TEST_DAYS)
    
    train_df = df[df["invoice_date"] <= split_date].copy()
    test_df = df[df["invoice_date"] > split_date].copy()
    
    print(f"  Khoảng thời gian toàn bộ: {df['invoice_date'].min().strftime('%Y-%m-%d')} đến {max_date.strftime('%Y-%m-%d')}")
    print(f"  Ngày phân tách (split_date): {split_date.strftime('%Y-%m-%d')}")
    print(f"  Tập Train: {len(train_df):,} dòng ({train_df['invoice_date'].min().strftime('%Y-%m-%d')} đến {train_df['invoice_date'].max().strftime('%Y-%m-%d')}), {train_df['customer_id'].nunique():,} khách hàng")
    print(f"  Tập Test: {len(test_df):,} dòng ({test_df['invoice_date'].min().strftime('%Y-%m-%d')} đến {test_df['invoice_date'].max().strftime('%Y-%m-%d')}), {test_df['customer_id'].nunique():,} khách hàng")
    
    return train_df, test_df


def compute_rfm_train(train_df: pd.DataFrame) -> pd.DataFrame:
    """
    Tính RFM trên tập Train:
    - recency: số ngày từ lần mua cuối đến (ngày lớn nhất của train + 1 ngày)
    - frequency: số invoice khác nhau
    - monetary: tổng total_price
    """
    print("\n[4/5] Tính chỉ số RFM trên tập Train (không data leakage):")
    snapshot_date = train_df["invoice_date"].max() + pd.Timedelta(days=1)
    
    rfm = (
        train_df.groupby("customer_id")
        .agg(
            recency=("invoice_date", lambda dates: (snapshot_date - dates.max()).days),
            frequency=("invoice", "nunique"),
            monetary=("total_price", "sum"),
        )
        .reset_index()
    )
    
    # Đảm bảo monetary không âm (đã lọc ở bước làm sạch) và làm tròn
    rfm["monetary"] = rfm["monetary"].round(2)
    rfm["recency"] = rfm["recency"].astype(int)
    rfm["frequency"] = rfm["frequency"].astype(int)
    
    print(f"  Số khách hàng trong rfm_train: {len(rfm):,}")
    print(f"  Recency: min={rfm['recency'].min()}, mean={rfm['recency'].mean():.1f}, max={rfm['recency'].max()}")
    print(f"  Frequency: min={rfm['frequency'].min()}, mean={rfm['frequency'].mean():.1f}, max={rfm['frequency'].max()}")
    print(f"  Monetary: min={rfm['monetary'].min():.1f}, mean={rfm['monetary'].mean():.1f}, max={rfm['monetary'].max():.1f}")
    
    return rfm


def build_interactions_and_products(
    clean_df: pd.DataFrame, train_df: pd.DataFrame, test_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Tạo:
    - interactions_train: ma trận tương tác khách-sản phẩm từ train_df
    - products.csv: danh mục sản phẩm kèm số lượt mua
    - test_truth: sự thật ngầm định cho tập test
    """
    print("\n[5/5] Xây dựng ma trận tương tác, danh mục sản phẩm và test_truth:")
    
    # 1. interactions_train
    # n_purchases = số hóa đơn khác nhau chứa sản phẩm đó của khách
    interactions = (
        train_df.groupby(["customer_id", "stockcode"])
        .agg(
            n_purchases=("invoice", "nunique"),
            quantity=("quantity", "sum")
        )
        .reset_index()
    )
    
    # Lọc khách hàng có >= MIN_CUSTOMER_INVOICES hóa đơn trong train
    cust_invoices = train_df.groupby("customer_id")["invoice"].nunique()
    valid_customers = cust_invoices[cust_invoices >= config.MIN_CUSTOMER_INVOICES].index
    
    # Lọc sản phẩm có tổng lượt mua n_purchases >= MIN_PRODUCT_PURCHASES trong train
    prod_purchases = interactions.groupby("stockcode")["n_purchases"].sum()
    valid_products = prod_purchases[prod_purchases >= config.MIN_PRODUCT_PURCHASES].index
    
    interactions_filtered = interactions[
        interactions["customer_id"].isin(valid_customers) &
        interactions["stockcode"].isin(valid_products)
    ].copy()
    
    print(f"  Số tương tác ban đầu: {len(interactions):,}")
    print(f"  Sau khi lọc (khách >= {config.MIN_CUSTOMER_INVOICES} đơn, SP >= {config.MIN_PRODUCT_PURCHASES} lượt): {len(interactions_filtered):,} tương tác")
    print(f"  Gồm {interactions_filtered['customer_id'].nunique():,} khách hàng và {interactions_filtered['stockcode'].nunique():,} sản phẩm")

    # 2. products.csv
    # Tổng hợp danh mục sản phẩm từ clean_df (hoặc train_df) để đầy đủ thông tin
    prod_canonical_desc = (
        clean_df.groupby("stockcode")["description"].first().to_dict()
    )
    prod_total_purchases = (
        clean_df.groupby("stockcode")["invoice"].nunique().to_dict()
    )
    
    unique_stockcodes = sorted(clean_df["stockcode"].unique())
    products_df = pd.DataFrame({
        "stockcode": unique_stockcodes,
        "description": [prod_canonical_desc.get(sc, "unknown product") for sc in unique_stockcodes],
        "n_purchases": [prod_total_purchases.get(sc, 0) for sc in unique_stockcodes],
        "image_path": ""  # fetch_images.py sẽ điền
    })
    products_df = products_df.sort_values("n_purchases", ascending=False).reset_index(drop=True)
    print(f"  Tổng số sản phẩm trong products.csv: {len(products_df):,}")

    # 3. test_truth
    # Các cặp khách-sản phẩm mua trong test, chỉ giữ khách xuất hiện trong interactions_train
    active_train_customers = set(interactions_filtered["customer_id"].unique())
    test_truth = (
        test_df[test_df["customer_id"].isin(active_train_customers)][["customer_id", "stockcode"]]
        .drop_duplicates()
        .copy()
    )
    print(f"  Số cặp test_truth (chỉ giữ khách có trong interactions_train): {len(test_truth):,} cặp, từ {test_truth['customer_id'].nunique():,} khách")

    return interactions_filtered, products_df, test_truth


def main():
    total_start_t = time.time()
    print("=" * 60)
    print("BẮT ĐẦU QUÁ TRÌNH TIỀN XỬ LÝ DỮ LIỆU ONLINE RETAIL")
    print("=" * 60)
    
    config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Đọc và chuẩn hóa schema
    raw_path = find_raw_data_file()
    df_raw = load_and_standardize_schema(raw_path)
    
    # 2. Làm sạch
    clean_df = clean_transactions(df_raw)
    clean_df.to_parquet(config.TRANSACTIONS_CLEAN_PATH, index=False)
    print(f"-> Đã lưu: {config.TRANSACTIONS_CLEAN_PATH}")
    
    # 3. Chia train / test
    train_df, test_df = split_train_test(clean_df)
    train_df.to_parquet(config.TRAIN_DATA_PATH, index=False)
    test_df.to_parquet(config.TEST_DATA_PATH, index=False)
    print(f"-> Đã lưu: {config.TRAIN_DATA_PATH}")
    print(f"-> Đã lưu: {config.TEST_DATA_PATH}")
    
    # 4. Tính RFM trên train
    rfm_train = compute_rfm_train(train_df)
    rfm_train.to_parquet(config.RFM_TRAIN_PATH, index=False)
    print(f"-> Đã lưu: {config.RFM_TRAIN_PATH}")
    
    # 5. Xây dựng interactions, products và test_truth
    interactions_train, products_df, test_truth = build_interactions_and_products(
        clean_df, train_df, test_df
    )
    interactions_train.to_parquet(config.INTERACTIONS_TRAIN_PATH, index=False)
    products_df.to_csv(config.PRODUCTS_PATH, index=False)
    test_truth.to_parquet(config.TEST_TRUTH_PATH, index=False)
    
    print(f"-> Đã lưu: {config.INTERACTIONS_TRAIN_PATH}")
    print(f"-> Đã lưu: {config.PRODUCTS_PATH}")
    print(f"-> Đã lưu: {config.TEST_TRUTH_PATH}")
    
    print("=" * 60)
    print(f"TIỀN XỬ LÝ HOÀN THÀNH THÀNH CÔNG trong {time.time() - total_start_t:.2f} giây!")
    print("=" * 60)


if __name__ == "__main__":
    main()
