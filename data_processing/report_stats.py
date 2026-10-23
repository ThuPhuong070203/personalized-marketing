"""
In ra các số liệu để điền vào proposal.md (data_processing/report_stats.py).
Chỉ ĐỌC các file đã có, không ghi đè gì.

Chạy:
    python data_processing/report_stats.py              # số liệu (khoảng 30-60 giây)
    python data_processing/report_stats.py --benchmark  # thêm so sánh tốc độ pandas vs Polars (thêm ~1-2 phút)
"""

import json
import sys
import time
from pathlib import Path

import polars as pl

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import config


def fmt(n) -> str:
    """Định dạng số kiểu Việt Nam: 1.234.567"""
    return f"{int(n):,}".replace(",", ".")


def section(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


# ---------------------------------------------------------------
# 1. Các bước làm sạch (tính lại số dòng từ bản Parquet gốc)
# ---------------------------------------------------------------
section("1. LÀM SẠCH DỮ LIỆU (bảng mục 4.1)")
lf = pl.scan_parquet(config.TRANSACTIONS_RAW_PARQUET)
n0 = lf.select(pl.len()).collect().item()
print(f"Dữ liệu ban đầu                 : {fmt(n0)}")

if config.DATA_START_DATE:
    start = pl.lit(config.DATA_START_DATE).str.strptime(pl.Date, "%Y-%m-%d")
    lf = lf.filter(pl.col("t_dat") >= start)
n1 = lf.select(pl.len()).collect().item()
print(f"Bước 1 (từ {config.DATA_START_DATE})          : {fmt(n1)}  (bỏ {fmt(n0 - n1)})")

lf = lf.filter(pl.col("customer_id").is_not_null() & pl.col("article_id").is_not_null()
               & pl.col("t_dat").is_not_null() & (pl.col("price") > 0))
n2 = lf.select(pl.len()).collect().item()
print(f"Bước 2 (bỏ thiếu mã / giá <= 0) : {fmt(n2)}  (bỏ {fmt(n1 - n2)})")

grouped = lf.group_by(["customer_id", "t_dat", "article_id", "price", "sales_channel_id"]).agg(pl.len())
n3 = grouped.select(pl.len()).collect().item()
print(f"Bước 3 (gộp dòng trùng)         : {fmt(n3)}  (gộp {fmt(n2 - n3)} dòng)")

clean = pl.scan_parquet(config.TRANSACTIONS_CLEAN_PATH)
n4 = clean.select(pl.len()).collect().item()
print(f"Bước 4 (ghép articles.csv)      : {fmt(n4)}  (bỏ {fmt(n3 - n4)})")
n_cust = clean.select(pl.col("customer_id").n_unique()).collect().item()
n_prod = clean.select(pl.col("stockcode").n_unique()).collect().item()
print(f"Bước 5 (đổi mã khách)           : {fmt(n_cust)} khách, {fmt(n_prod)} sản phẩm")
print(f"=> Còn lại {fmt(n4)} dòng = {n4 / n0:.1%} dữ liệu gốc; {n4 / n1:.1%} của 1 năm gần nhất")

# ---------------------------------------------------------------
# 2. Train / test
# ---------------------------------------------------------------
section("2. CHIA TRAIN / TEST (mục 4.2)")
for name, path in [("Train", config.TRAIN_DATA_PATH), ("Test", config.TEST_DATA_PATH)]:
    s = pl.scan_parquet(path).select(
        pl.len().alias("n"), pl.col("customer_id").n_unique().alias("c"),
        pl.col("invoice_date").min().alias("a"), pl.col("invoice_date").max().alias("b"),
    ).collect().row(0, named=True)
    print(f"{name:5s}: {fmt(s['n'])} dòng, {fmt(s['c'])} khách, {str(s['a'])[:10]} -> {str(s['b'])[:10]}")

# ---------------------------------------------------------------
# 3. RFM
# ---------------------------------------------------------------
section("3. THỐNG KÊ RFM TRÊN TẬP TRAIN (bảng mục 4.2)")
rfm = pl.read_parquet(config.RFM_TRAIN_PATH)
print(f"Số khách: {fmt(len(rfm))}")
for c in ["recency", "frequency", "monetary"]:
    print(f"  {c:9s}: min={rfm[c].min():.4g} | trung bình={rfm[c].mean():.4g} | "
          f"trung vị={rfm[c].median():.4g} | max={rfm[c].max():.4g}")

# ---------------------------------------------------------------
# 4. Ma trận tương tác & test_truth
# ---------------------------------------------------------------
section("4. MA TRẬN TƯƠNG TÁC & TEST_TRUTH (mục 4.2)")
inter = pl.read_parquet(config.INTERACTIONS_TRAIN_PATH)
n_u, n_i = inter["customer_id"].n_unique(), inter["stockcode"].n_unique()
print(f"Số cặp (khách, sản phẩm): {fmt(len(inter))}")
print(f"Số khách                : {fmt(n_u)}")
print(f"Số sản phẩm             : {fmt(n_i)}")
print(f"Độ thưa (sparsity)      : {1 - len(inter) / (n_u * n_i):.4%}")
tt = pl.read_parquet(config.TEST_TRUTH_PATH)
print(f"test_truth              : {fmt(len(tt))} cặp, {fmt(tt['customer_id'].n_unique())} khách")

# ---------------------------------------------------------------
# 5. Hồ sơ cụm
# ---------------------------------------------------------------
section("5. HỒ SƠ 4 NHÓM KHÁCH (mục 5.1)")
profiles = json.loads(config.CLUSTER_PROFILES_PATH.read_text(encoding="utf-8"))
for p in sorted(profiles, key=lambda x: -x["size"]):
    print(f"{p['name']:25s}: {fmt(p['size'])} khách ({p['pct']}%) | "
          f"R={p['mean_recency']} ngày | F={p['mean_frequency']} đơn | M={p['mean_monetary']}")

# ---------------------------------------------------------------
# 6. Dung lượng file
# ---------------------------------------------------------------
section("6. DUNG LƯỢNG FILE (phễu dữ liệu)")
for p in [config.TRANSACTIONS_RAW_PATH, config.TRANSACTIONS_RAW_PARQUET, config.TRANSACTIONS_CLEAN_PATH,
          config.TRAIN_DATA_PATH, config.TEST_DATA_PATH, config.INTERACTIONS_TRAIN_PATH,
          config.RECOMMENDERS_PATH]:
    if p.exists():
        print(f"  {p.name:32s}: {p.stat().st_size / 1e6:>9,.1f} MB")
img_mb = sum(f.stat().st_size for f in config.IMAGES_DIR.glob("*.jpg")) / 1e6
print(f"  {'data/images/*.jpg':32s}: {img_mb:>9,.1f} MB")

# ---------------------------------------------------------------
# 7. (Tùy chọn) So sánh pandas + CSV với Polars + Parquet
# ---------------------------------------------------------------
if "--benchmark" in sys.argv:
    import pandas as pd
    section("7. SO SÁNH TỐC ĐỘ (bảng TODO mục 3) - đọc 3 cột, 5 triệu dòng đầu")
    N = 5_000_000
    cols = ["t_dat", "customer_id", "article_id"]

    t = time.time()
    _ = pd.read_csv(config.TRANSACTIONS_RAW_PATH, usecols=cols, nrows=N, dtype={"article_id": str})
    t_pd = time.time() - t
    del _

    t = time.time()
    _ = pl.read_parquet(config.TRANSACTIONS_RAW_PARQUET, columns=cols, n_rows=N)
    t_pl = time.time() - t
    del _

    t = time.time()
    total = pl.scan_parquet(config.TRANSACTIONS_RAW_PARQUET).group_by("article_id").agg(pl.len()).collect()
    t_full = time.time() - t

    print(f"pandas đọc CSV (5 triệu dòng)       : {t_pd:6.2f} s")
    print(f"Polars đọc Parquet (5 triệu dòng)   : {t_pl:6.2f} s  -> nhanh hơn {t_pd / max(t_pl, 1e-6):.0f} lần")
    print(f"Polars đếm lượt mua cho {fmt(len(total))} SP trên TOÀN BỘ 31,8 triệu dòng: {t_full:.2f} s")

print("\nXong. Copy toàn bộ phần in ra ở trên gửi lại để điền vào proposal.md")
