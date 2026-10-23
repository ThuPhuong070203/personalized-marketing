"""
Lớp Service nạp các artifacts và thực hiện các logic truy vấn dữ liệu cho FastAPI (backend/app/services.py).

Tối ưu cho bộ dữ liệu lớn H&M (~1 triệu khách, hàng chục triệu giao dịch):
- Thông tin khách lưu trong DataFrame có index theo customer_id (tra cứu O(1)),
  không dựng dict Python cho từng khách.
- 10 món mua gần nhất của khách KHÔNG tính sẵn cho mọi khách lúc khởi động. Thay vào đó,
  lần khởi động đầu tạo file recent_purchases.parquet (sắp xếp theo customer_id), sau đó mỗi
  yêu cầu chỉ đọc đúng phần của một khách bằng Polars (nhờ thống kê row group trong Parquet).
- Top sản phẩm theo cụm được tính bằng Polars và lưu cache ra JSON.
"""

import sys
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import polars as pl

# Đảm bảo import config
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config

ALLOWED_MODELS = {
    "popularity",
    "cluster_popularity",
    "item_cf",
    "als",
    "content",
    "hybrid"
}

PLACEHOLDER = "/images/placeholder.jpg"
RECENT_PURCHASES_PATH: Path = config.PROCESSED_DATA_DIR / "recent_purchases.parquet"
CLUSTER_TOP_PATH: Path = config.MODELS_DIR / "cluster_top_products.json"


def _is_stale(target: Path, *sources: Path) -> bool:
    """File đích chưa có hoặc cũ hơn một trong các file nguồn -> cần tạo lại."""
    if not target.exists():
        return True
    t = target.stat().st_mtime
    return any(s.exists() and s.stat().st_mtime > t for s in sources)


class ModelService:
    _instance = None

    def __init__(self):
        self.loaded = False
        self.customers: pd.DataFrame | None = None        # index = customer_id
        self._customer_id_str: pd.Series | None = None    # để tìm kiếm theo chuỗi
        self.cluster_profiles: list[dict] = []
        self.cluster_profiles_dict: dict[int, dict] = {}
        self.products_dict: dict[str, dict] = {}
        self.popularity_global: list[dict] = []
        self.metrics_data: dict = {}
        self.recommenders: dict = {}
        self.cluster_top_products: dict[int, list[dict]] = {}
        self.recsys_customers: set[int] = set()            # khách có trong mô hình gợi ý cá nhân
        self._recsys_sorted: list[int] = []
        self._browse_order: np.ndarray | None = None       # thứ tự hiển thị danh sách khách (có gợi ý trước)

    @classmethod
    def get_instance(cls) -> "ModelService":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load_artifacts()
        return cls._instance

    # =========================================================
    # NẠP DỮ LIỆU
    # =========================================================
    def load_artifacts(self):
        if self.loaded:
            return
        t0 = time.time()
        print("[API Service] Đang nạp artifacts từ backend/models/ và data/processed/...")

        # 1. products.csv -> dict (bỏ cột content_text dài, chỉ dùng cho TF-IDF)
        if config.PRODUCTS_PATH.exists():
            prods = pd.read_csv(config.PRODUCTS_PATH, dtype={"stockcode": str}, keep_default_na=False)
            prods = prods.drop(columns=[c for c in ["content_text"] if c in prods.columns])
            prods["image_path"] = prods["image_path"].replace("", PLACEHOLDER)
            self.products_dict = prods.set_index("stockcode").to_dict(orient="index")
            print(f"  - Sản phẩm: {len(self.products_dict):,}")
        else:
            print("Cảnh báo: Không tìm thấy products.csv!")

        # 2. customer_clusters.parquet -> DataFrame có index (không duyệt từng dòng)
        if config.CUSTOMER_CLUSTERS_PATH.exists():
            cc = pd.read_parquet(config.CUSTOMER_CLUSTERS_PATH)
            cc["customer_id"] = cc["customer_id"].astype("int64")
            cc["cluster_name"] = cc["cluster_name"].astype("category")
            self.customers = cc.set_index("customer_id").sort_index()
            self._customer_id_str = pd.Series(self.customers.index.astype(str), index=self.customers.index)
            print(f"  - Khách hàng đã phân cụm: {len(self.customers):,}")
        else:
            print("Cảnh báo: Không tìm thấy customer_clusters.parquet!")

        # 3. cluster_profiles.json
        if config.CLUSTER_PROFILES_PATH.exists():
            with open(config.CLUSTER_PROFILES_PATH, "r", encoding="utf-8") as f:
                self.cluster_profiles = json.load(f)
            self.cluster_profiles_dict = {int(item["id"]): item for item in self.cluster_profiles}

        # 4. popularity_global.json
        if config.POPULARITY_GLOBAL_PATH.exists():
            with open(config.POPULARITY_GLOBAL_PATH, "r", encoding="utf-8") as f:
                self.popularity_global = json.load(f)
            for item in self.popularity_global:  # cập nhật ảnh nếu fetch_images chạy sau train
                info = self.products_dict.get(str(item.get("stockcode")), {})
                item["image"] = info.get("image_path") or PLACEHOLDER

        # 5. metrics.json
        if config.METRICS_PATH.exists():
            with open(config.METRICS_PATH, "r", encoding="utf-8") as f:
                self.metrics_data = json.load(f)

        # 6. recommenders.pkl
        if config.RECOMMENDERS_PATH.exists():
            t = time.time()
            self.recommenders = joblib.load(config.RECOMMENDERS_PATH)
            hybrid = self.recommenders.get("hybrid")
            self.recsys_customers = set(int(c) for c in getattr(hybrid, "known_customers", set()))
            self._recsys_sorted = sorted(self.recsys_customers)
            print(f"  - Mô hình: {list(self.recommenders.keys())} ({time.time() - t:.1f}s)")
            print(f"  - Khách có gợi ý cá nhân hóa: {len(self.recsys_customers):,}")
        else:
            print("Cảnh báo: Không tìm thấy recommenders.pkl!")

        # 7. Lịch sử mua gần nhất & top sản phẩm theo cụm (tính bằng Polars, có cache)
        if config.TRAIN_DATA_PATH.exists():
            self._prepare_recent_purchases()
            self._prepare_cluster_top_products()

        # Thứ tự duyệt danh sách khách: khách có gợi ý cá nhân hóa trước, rồi tới các khách còn lại
        if self.customers is not None:
            all_ids = self.customers.index.to_numpy()
            rec = np.array(self._recsys_sorted, dtype=all_ids.dtype)
            rest = all_ids[~np.isin(all_ids, rec)]
            self._browse_order = np.concatenate([rec[np.isin(rec, all_ids)], rest])

        self._print_demo_customers()
        self.loaded = True
        print(f"[API Service] Sẵn sàng phục vụ yêu cầu! (khởi động {time.time() - t0:.1f}s)")

    def _prepare_recent_purchases(self):
        """Tạo recent_purchases.parquet: tối đa 10 món khác nhau mua gần nhất của mỗi khách."""
        if not _is_stale(RECENT_PURCHASES_PATH, config.TRAIN_DATA_PATH):
            return
        t = time.time()
        print("  - Đang tạo recent_purchases.parquet (chỉ lần đầu)...")
        df = (
            pl.scan_parquet(config.TRAIN_DATA_PATH)
            .select("customer_id", "stockcode", "description", "quantity", "total_price", "invoice_date")
            .sort(["customer_id", "invoice_date"], descending=[False, True])
            .unique(subset=["customer_id", "stockcode"], keep="first", maintain_order=True)
            .group_by("customer_id", maintain_order=True)
            .head(10)
            .collect()
        )
        df.write_parquet(RECENT_PURCHASES_PATH, row_group_size=20_000, statistics=True)
        print(f"    xong: {len(df):,} dòng ({time.time() - t:.1f}s)")

    def _prepare_cluster_top_products(self):
        """Top 10 sản phẩm bán chạy nhất trong từng cụm (cache ra JSON)."""
        if not _is_stale(CLUSTER_TOP_PATH, config.TRAIN_DATA_PATH, config.CUSTOMER_CLUSTERS_PATH):
            with open(CLUSTER_TOP_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
        else:
            t = time.time()
            print("  - Đang tính top sản phẩm theo cụm (chỉ lần đầu)...")
            clusters = pl.read_parquet(config.CUSTOMER_CLUSTERS_PATH, columns=["customer_id", "cluster"])
            top = (
                pl.scan_parquet(config.TRAIN_DATA_PATH)
                .select("customer_id", "stockcode", "invoice")
                .join(clusters.lazy(), on="customer_id", how="inner")
                .group_by(["cluster", "stockcode"])
                .agg(pl.col("invoice").n_unique().alias("n_invoices"))
                .sort(["cluster", "n_invoices"], descending=[False, True])
                .group_by("cluster", maintain_order=True)
                .head(10)
                .collect()
            )
            raw = {}
            for c_id in top["cluster"].unique().to_list():
                grp = top.filter(pl.col("cluster") == c_id)
                raw[str(int(c_id))] = list(zip(grp["stockcode"].to_list(), grp["n_invoices"].to_list()))
            CLUSTER_TOP_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CLUSTER_TOP_PATH, "w", encoding="utf-8") as f:
                json.dump(raw, f)
            print(f"    xong ({time.time() - t:.1f}s)")

        for c_id, pairs in raw.items():
            max_inv = float(max((n for _, n in pairs), default=1)) or 1.0
            self.cluster_top_products[int(c_id)] = [
                {
                    "stockcode": str(sc),
                    "description": self.products_dict.get(str(sc), {}).get("description", "unknown product"),
                    "score": round(float(n) / max_inv, 4),
                    "image": self.products_dict.get(str(sc), {}).get("image_path") or PLACEHOLDER,
                }
                for sc, n in pairs
            ]

    def _print_demo_customers(self):
        """In ra vài khách mẫu (mỗi cụm 1 khách, có gợi ý cá nhân hóa) để dùng khi demo trên web."""
        if self.customers is None or not self.recsys_customers:
            return
        df = self.customers[self.customers.index.isin(self.recsys_customers)]
        print("  - Khách mẫu gợi ý cho demo (mỗi cụm khách mua nhiều đơn nhất):")
        for name, grp in df.groupby("cluster_name", observed=True):
            cid = int(grp["frequency"].idxmax())
            print(f"      {name}: {cid}")

    # =========================================================
    # TRA CỨU
    # =========================================================
    def _get_customer_row(self, customer_id: int):
        if self.customers is None:
            return None
        try:
            return self.customers.loc[int(customer_id)]
        except KeyError:
            return None

    def _recent_purchases(self, customer_id: int) -> list[dict]:
        if not RECENT_PURCHASES_PATH.exists():
            return []
        df = (
            pl.scan_parquet(RECENT_PURCHASES_PATH)
            .filter(pl.col("customer_id") == int(customer_id))
            .collect()
        )
        out = []
        for r in df.iter_rows(named=True):
            sc = str(r["stockcode"])
            info = self.products_dict.get(sc, {})
            out.append({
                "stockcode": sc,
                "description": str(r["description"]),
                "quantity": int(r["quantity"]),
                "total_price": float(r["total_price"]),
                "invoice_date": pd.Timestamp(r["invoice_date"]).strftime("%Y-%m-%d"),  # H&M chỉ có ngày, không có giờ
                "image": info.get("image_path") or PLACEHOLDER,
            })
        return out

    def get_customers(self, search: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
        """Lấy danh sách khách hàng (có phân trang), hỗ trợ tìm kiếm theo customer_id.
        Khi không tìm kiếm, khách có gợi ý cá nhân hóa được xếp trước (để demo có kết quả rõ ràng)."""
        if self.customers is None:
            return []
        offset = max(0, int(offset))
        search_str = search.strip()
        if search_str:
            matched = self._customer_id_str[self._customer_id_str.str.contains(search_str, regex=False)].index
            ids = matched[offset:offset + limit]
        elif self._browse_order is not None:
            ids = self._browse_order[offset:offset + limit]
        else:
            ids = self.customers.index[offset:offset + limit]
        rows = self.customers.loc[list(ids)]
        return [
            {"customer_id": int(cid), "cluster_name": str(r["cluster_name"]), "monetary": round(float(r["monetary"]), 4)}
            for cid, r in rows.iterrows()
        ]

    def get_customer(self, customer_id: int) -> dict | None:
        """Lấy chi tiết thông tin RFM, cụm và 10 giao dịch gần nhất của khách."""
        r = self._get_customer_row(customer_id)
        if r is None:
            return None
        return {
            "customer_id": int(customer_id),
            "recency": int(r["recency"]),
            "frequency": int(r["frequency"]),
            "monetary": float(r["monetary"]),
            "cluster_id": int(r["cluster"]),
            "cluster_name": str(r["cluster_name"]),
            "recent_purchases": self._recent_purchases(customer_id),
        }

    def get_clusters(self) -> list[dict]:
        """Lấy danh sách thông tin hồ sơ các cụm."""
        return self.cluster_profiles

    def get_cluster(self, cluster_id: int) -> dict | None:
        """Lấy chi tiết một cụm và top 10 sản phẩm bán chạy trong cụm đó."""
        prof = self.cluster_profiles_dict.get(cluster_id)
        if not prof:
            return None
        return {"cluster": prof, "top_products": self.cluster_top_products.get(cluster_id, [])}

    def get_cluster_points(self, max_points: int = config.PCA_SAMPLE_SIZE) -> list[dict]:
        """Lấy danh sách tọa độ PCA 2D của khách hàng để vẽ biểu đồ phân tán."""
        if self.customers is None or self.customers.empty:
            return []
        df = self.customers
        if len(df) > max_points:
            df = df.sample(n=max_points, random_state=config.RANDOM_SEED)
        return [
            {"customer_id": int(cid), "cluster": int(r["cluster"]),
             "x": round(float(r["pca_x"]), 3), "y": round(float(r["pca_y"]), 3)}
            for cid, r in df.iterrows()
        ]

    def get_recommendations(
        self, customer_id: int, top_k: int = config.DEFAULT_TOP_K, model_name: str = "hybrid"
    ) -> dict:
        """Sinh danh sách sản phẩm gợi ý cho khách hàng."""
        if model_name not in ALLOWED_MODELS:
            raise ValueError(f"Mô hình '{model_name}' không hợp lệ. Phải thuộc: {list(ALLOWED_MODELS)}")

        top_k = max(1, min(50, top_k))
        r = self._get_customer_row(customer_id)

        # Cold-start: khách không có trong tập huấn luyện
        cold_start = r is None
        cluster_info = None

        if cold_start:
            model = self.recommenders.get("popularity")
            raw_recs = model.recommend(customer_id, k=top_k) if model else []
        else:
            cluster_info = {"id": int(r["cluster"]), "name": str(r["cluster_name"])}
            model = self.recommenders.get(model_name) or self.recommenders.get("popularity")
            raw_recs = model.recommend(int(customer_id), k=top_k, exclude_seen=config.EXCLUDE_SEEN) if model else []

        items = []
        for sc, score in raw_recs:
            sc_str = str(sc)
            info = self.products_dict.get(sc_str, {})
            items.append({
                "stockcode": sc_str,
                "description": info.get("description", "unknown product"),
                "score": round(float(score), 4),
                "image": info.get("image_path") or PLACEHOLDER,
            })

        return {
            "customer_id": int(customer_id),
            "cluster": cluster_info,
            "model": model_name,
            "cold_start": cold_start,
            "items": items,
        }

    def get_product(self, stockcode: str) -> dict | None:
        """Lấy thông tin và ảnh của sản phẩm."""
        sc = str(stockcode).strip()
        info = self.products_dict.get(sc)
        if not info:
            return None
        return {
            "stockcode": sc,
            "description": info.get("description", "unknown product"),
            "n_purchases": int(info.get("n_purchases", 0) or 0),
            "image": info.get("image_path") or PLACEHOLDER,
        }

    def get_metrics(self) -> dict:
        """Lấy toàn bộ chỉ số metrics.json."""
        return self.metrics_data
        