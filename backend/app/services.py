"""
Lớp Service nạp các artifacts và thực hiện các logic truy vấn dữ liệu cho FastAPI (backend/app/services.py).
"""

import sys
import json
from pathlib import Path
import joblib
import pandas as pd
import numpy as np

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


class ModelService:
    _instance = None

    def __init__(self):
        self.loaded = False
        self.customer_clusters: pd.DataFrame | None = None
        self.cluster_profiles: list[dict] = []
        self.cluster_profiles_dict: dict[int, dict] = {}
        self.products_df: pd.DataFrame | None = None
        self.products_dict: dict[str, dict] = {}
        self.popularity_global: list[dict] = []
        self.metrics_data: dict = {}
        self.recommenders: dict = {}
        self.train_recent_purchases: dict[int, list[dict]] = {}
        self.cluster_top_products: dict[int, list[dict]] = {}
        self.customer_map: dict[int, dict] = {}

    @classmethod
    def get_instance(cls) -> "ModelService":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load_artifacts()
        return cls._instance

    def load_artifacts(self):
        if self.loaded:
            return

        print("[API Service] Đang nạp toàn bộ artifacts từ backend/models/ và data/processed/...")

        # 1. Nạp products.csv
        if config.PRODUCTS_PATH.exists():
            self.products_df = pd.read_csv(config.PRODUCTS_PATH, dtype={"stockcode": str})
            self.products_df["image_path"] = self.products_df["image_path"].fillna("/images/placeholder.jpg")
            self.products_dict = self.products_df.set_index("stockcode").to_dict(orient="index")
        else:
            print("Cảnh báo: Không tìm thấy products.csv!")

        # 2. Nạp customer_clusters.parquet
        if config.CUSTOMER_CLUSTERS_PATH.exists():
            self.customer_clusters = pd.read_parquet(config.CUSTOMER_CLUSTERS_PATH)
            for _, r in self.customer_clusters.iterrows():
                cid = int(r["customer_id"])
                self.customer_map[cid] = {
                    "customer_id": cid,
                    "recency": int(r["recency"]),
                    "frequency": int(r["frequency"]),
                    "monetary": float(r["monetary"]),
                    "cluster": int(r["cluster"]),
                    "cluster_name": str(r["cluster_name"]),
                    "pca_x": float(r["pca_x"]),
                    "pca_y": float(r["pca_y"])
                }
        else:
            print("Cảnh báo: Không tìm thấy customer_clusters.parquet!")

        # 3. Nạp cluster_profiles.json
        if config.CLUSTER_PROFILES_PATH.exists():
            with open(config.CLUSTER_PROFILES_PATH, "r", encoding="utf-8") as f:
                self.cluster_profiles = json.load(f)
                self.cluster_profiles_dict = {
                    int(item["id"]): item for item in self.cluster_profiles
                }

        # 4. Nạp popularity_global.json
        if config.POPULARITY_GLOBAL_PATH.exists():
            with open(config.POPULARITY_GLOBAL_PATH, "r", encoding="utf-8") as f:
                self.popularity_global = json.load(f)

        # 5. Nạp metrics.json
        if config.METRICS_PATH.exists():
            with open(config.METRICS_PATH, "r", encoding="utf-8") as f:
                self.metrics_data = json.load(f)

        # 6. Nạp recommenders.pkl
        if config.RECOMMENDERS_PATH.exists():
            self.recommenders = joblib.load(config.RECOMMENDERS_PATH)
            print(f"[API Service] Đã nạp thành công các mô hình: {list(self.recommenders.keys())}")
        else:
            print("Cảnh báo: Không tìm thấy recommenders.pkl!")

        # 7. Nạp train.parquet để tính trước top 10 sản phẩm mua gần nhất của mỗi khách hàng
        if config.TRAIN_DATA_PATH.exists():
            print("[API Service] Đang tiền xử lý lịch sử mua hàng gần nhất từ train.parquet...")
            train_df = pd.read_parquet(config.TRAIN_DATA_PATH)
            train_df["stockcode"] = train_df["stockcode"].astype(str)
            # Sắp xếp theo ngày giảm dần
            train_sorted = train_df.sort_values("invoice_date", ascending=False)
            # Bỏ trùng lặp sản phẩm cho mỗi khách hàng để lấy 10 sản phẩm phân biệt gần nhất
            unique_recent = train_sorted.drop_duplicates(subset=["customer_id", "stockcode"])
            
            for cust_id, grp in unique_recent.groupby("customer_id"):
                recent_list = []
                for _, row in grp.head(10).iterrows():
                    sc = str(row["stockcode"])
                    prod_info = self.products_dict.get(sc, {})
                    recent_list.append({
                        "stockcode": sc,
                        "description": str(row["description"]),
                        "quantity": int(row["quantity"]),
                        "total_price": float(row["total_price"]),
                        "invoice_date": pd.to_datetime(row["invoice_date"]).strftime("%Y-%m-%d %H:%M"),
                        "image": prod_info.get("image_path") or "/images/placeholder.jpg"
                    })
                self.train_recent_purchases[int(cust_id)] = recent_list

            # Tiền xử lý top 10 sản phẩm theo từng cụm
            if self.customer_clusters is not None:
                train_merged = train_df.merge(
                    self.customer_clusters[["customer_id", "cluster"]],
                    on="customer_id",
                    how="inner"
                )
                cluster_prods = (
                    train_merged.groupby(["cluster", "stockcode"])["invoice"]
                    .nunique()
                    .reset_index(name="n_invoices")
                )
                for c_id, grp in cluster_prods.groupby("cluster"):
                    top10 = grp.sort_values("n_invoices", ascending=False).head(10)
                    max_inv = float(top10["n_invoices"].max()) if len(top10) > 0 else 1.0
                    items = []
                    for _, r in top10.iterrows():
                        sc = str(r["stockcode"])
                        prod_info = self.products_dict.get(sc, {})
                        items.append({
                            "stockcode": sc,
                            "description": prod_info.get("description", "unknown product"),
                            "score": round(float(r["n_invoices"]) / max_inv, 4),
                            "image": prod_info.get("image_path") or "/images/placeholder.jpg"
                        })
                    self.cluster_top_products[int(c_id)] = items

        self.loaded = True
        print("[API Service] Sẵn sàng phục vụ yêu cầu!")

    def get_customers(self, search: str = "", limit: int = 50) -> list[dict]:
        """Lấy danh sách khách hàng, hỗ trợ tìm kiếm theo customer_id."""
        if not self.customer_map:
            return []

        search_str = search.strip().lower()
        results = []
        for cid, data in self.customer_map.items():
            if not search_str or search_str in str(cid):
                results.append({
                    "customer_id": cid,
                    "cluster_name": data["cluster_name"],
                    "monetary": round(data["monetary"], 2)
                })
            if len(results) >= limit:
                break

        return results

    def get_customer(self, customer_id: int) -> dict | None:
        """Lấy chi tiết thông tin RFM, cụm và 10 giao dịch gần nhất của khách."""
        cust = self.customer_map.get(customer_id)
        if not cust:
            return None

        recent = self.train_recent_purchases.get(customer_id, [])
        return {
            "customer_id": cust["customer_id"],
            "recency": cust["recency"],
            "frequency": cust["frequency"],
            "monetary": cust["monetary"],
            "cluster_id": cust["cluster"],
            "cluster_name": cust["cluster_name"],
            "recent_purchases": recent
        }

    def get_clusters(self) -> list[dict]:
        """Lấy danh sách thông tin hồ sơ các cụm."""
        return self.cluster_profiles

    def get_cluster(self, cluster_id: int) -> dict | None:
        """Lấy chi tiết một cụm và top 10 sản phẩm bán chạy trong cụm đó."""
        prof = self.cluster_profiles_dict.get(cluster_id)
        if not prof:
            return None
        top_prods = self.cluster_top_products.get(cluster_id, [])
        return {
            "cluster": prof,
            "top_products": top_prods
        }

    def get_cluster_points(self, max_points: int = config.PCA_SAMPLE_SIZE) -> list[dict]:
        """Lấy danh sách tọa độ PCA 2D của khách hàng để vẽ biểu đồ phân tán."""
        if self.customer_clusters is None or self.customer_clusters.empty:
            return []

        df = self.customer_clusters
        if len(df) > max_points:
            # Lấy mẫu ngẫu nhiên đại diện theo tỷ lệ các cụm
            df = df.sample(n=max_points, random_state=config.RANDOM_SEED)

        return [
            {
                "customer_id": int(row["customer_id"]),
                "cluster": int(row["cluster"]),
                "x": round(float(row["pca_x"]), 3),
                "y": round(float(row["pca_y"]), 3)
            }
            for _, row in df.iterrows()
        ]

    def get_recommendations(
        self, customer_id: int, top_k: int = config.DEFAULT_TOP_K, model_name: str = "hybrid"
    ) -> dict:
        """Sinh danh sách sản phẩm gợi ý cho khách hàng."""
        if model_name not in ALLOWED_MODELS:
            raise ValueError(f"Mô hình '{model_name}' không hợp lệ. Phải thuộc: {list(ALLOWED_MODELS)}")

        top_k = max(1, min(50, top_k))
        cust = self.customer_map.get(customer_id)
        
        # Kiểm tra cold-start: Khách hàng không có trong tập huấn luyện
        cold_start = cust is None
        cluster_info = None

        if cold_start:
            # Fallback về popularity
            model = self.recommenders.get("popularity")
            raw_recs = model.recommend(customer_id, k=top_k) if model else []
        else:
            cluster_info = {
                "id": cust["cluster"],
                "name": cust["cluster_name"]
            }
            model = self.recommenders.get(model_name)
            if model is None:
                model = self.recommenders.get("popularity")
            raw_recs = model.recommend(customer_id, k=top_k, exclude_seen=config.EXCLUDE_SEEN) if model else []

        items = []
        for sc, score in raw_recs:
            sc_str = str(sc)
            prod_info = self.products_dict.get(sc_str, {})
            items.append({
                "stockcode": sc_str,
                "description": prod_info.get("description", "unknown product"),
                "score": round(float(score), 4),
                "image": prod_info.get("image_path") or "/images/placeholder.jpg"
            })

        return {
            "customer_id": customer_id,
            "cluster": cluster_info,
            "model": model_name,
            "cold_start": cold_start,
            "items": items
        }

    def get_product(self, stockcode: str) -> dict | None:
        """Lấy thông tin và ảnh của sản phẩm."""
        info = self.products_dict.get(str(stockcode).strip())
        if not info:
            return None
        return {
            "stockcode": str(stockcode).strip(),
            "description": info.get("description", "unknown product"),
            "n_purchases": int(info.get("n_purchases", 0)),
            "image": info.get("image_path") or "/images/placeholder.jpg"
        }

    def get_metrics(self) -> dict:
        """Lấy toàn bộ chỉ số metrics.json."""
        return self.metrics_data
    