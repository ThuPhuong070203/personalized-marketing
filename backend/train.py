"""
Script huấn luyện toàn diện cho hệ thống Personalized Marketing (backend/train.py):
1. Phân cụm khách hàng (RFM + K-Means, Silhouette cho k=2..10, PCA 2D)
2. Huấn luyện 6 mô hình gợi ý sản phẩm (Popularity, Cluster-Pop, Item-CF, ALS, Content, Hybrid)
3. Đánh giá chất lượng phân cụm và các mô hình gợi ý (Precision@K, Recall@K, MAP@K, NDCG@K, Coverage@K)
4. Lưu toàn bộ artifacts vào backend/models/
"""

import sys
import time
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

# Đảm bảo import config và các module
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
from backend.algorithms.clustering import (
    prepare_features,
    evaluate_k,
    fit_kmeans,
    name_clusters,
    compute_pca
)
from backend.algorithms.recommender import (
    PopularityRecommender,
    ClusterPopularityRecommender,
    ItemCFRecommender,
    ALSRecommender,
    ContentBasedRecommender,
    HybridRecommender
)
from backend.algorithms.evaluate import (
    evaluate_clustering,
    evaluate_recommender
)


def verify_inputs():
    """Kiểm tra các file dữ liệu đầu vào bắt buộc."""
    required_files = [
        config.RFM_TRAIN_PATH,
        config.INTERACTIONS_TRAIN_PATH,
        config.PRODUCTS_PATH,
        config.TEST_TRUTH_PATH
    ]
    missing = [f for f in required_files if not f.exists()]
    if missing:
        msg = "\n".join([f" - {f}" for f in missing])
        raise FileNotFoundError(
            f"Thiếu các file dữ liệu sau:\n{msg}\n"
            f"Vui lòng chạy 'python data_processing/process.py' và 'python data_processing/fetch_images.py' trước!"
        )


def train_clustering(rfm: pd.DataFrame):
    """Huấn luyện mô hình phân cụm và lưu artifacts."""
    print("\n--- [1/3] HUẤN LUYỆN MÔ HÌNH PHÂN CỤM (K-MEANS) ---")
    start_t = time.time()

    # 1. Chuẩn bị đặc trưng
    X, scaler = prepare_features(rfm)
    print(f"Ma trận đặc trưng RFM chuẩn hóa: {X.shape}")

    # 2. Đánh giá các giá trị K từ 2 đến 10
    print("Đang đánh giá các giá trị K (Inertia và Silhouette)...")
    k_eval_scores = evaluate_k(X, config.K_EVAL_RANGE)
    with open(config.CLUSTER_K_SCORES_PATH, "w", encoding="utf-8") as f:
        json.dump(k_eval_scores, f, indent=2, ensure_ascii=False)
    print(f"-> Đã lưu bảng điểm K: {config.CLUSTER_K_SCORES_PATH}")

    # 3. Fit K-Means với K được chọn (mặc định K = 4)
    kmeans = fit_kmeans(X, k=config.CLUSTER_K)
    labels = kmeans.labels_
    rfm_labeled = rfm.copy()
    rfm_labeled["cluster"] = labels

    # 4. Tính PCA 2D cho toàn bộ tập khách hàng
    print("Đang tính toán tọa độ PCA 2D...")
    X_pca, pca = compute_pca(X)
    rfm_labeled["pca_x"] = np.round(X_pca[:, 0], 4)
    rfm_labeled["pca_y"] = np.round(X_pca[:, 1], 4)

    # 5. Đặt tên cụm, mô tả và gợi ý chiến dịch
    cluster_meta = name_clusters(rfm_labeled)
    rfm_labeled["cluster_name"] = rfm_labeled["cluster"].map(
        lambda c: cluster_meta.get(c, {}).get("name", f"Cụm {c}")
    )

    # 6. Tạo hồ sơ cụm (cluster_profiles.json)
    profiles = []
    for c_id in sorted(rfm_labeled["cluster"].unique()):
        grp = rfm_labeled[rfm_labeled["cluster"] == c_id]
        meta = cluster_meta.get(c_id, {})
        profiles.append({
            "id": int(c_id),
            "name": meta.get("name", f"Cụm {c_id}"),
            "size": int(len(grp)),
            "pct": round(float(len(grp) / len(rfm_labeled) * 100), 1),
            "mean_recency": round(float(grp["recency"].mean()), 1),
            "mean_frequency": round(float(grp["frequency"].mean()), 1),
            "mean_monetary": round(float(grp["monetary"].mean()), 1),
            "description": meta.get("description", ""),
            "campaign": meta.get("campaign", "")
        })

    with open(config.CLUSTER_PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)
    print(f"-> Đã lưu hồ sơ các cụm: {config.CLUSTER_PROFILES_PATH}")

    # 7. Lưu DataFrame phân cụm khách hàng
    rfm_labeled.to_parquet(config.CUSTOMER_CLUSTERS_PATH, index=False)
    print(f"-> Đã lưu phân cụm khách hàng: {config.CUSTOMER_CLUSTERS_PATH}")

    # 8. Lưu đối tượng mô hình
    joblib.dump({"scaler": scaler, "kmeans": kmeans, "pca": pca}, config.CLUSTERING_MODEL_PATH)
    print(f"-> Đã lưu model clustering.pkl: {config.CLUSTERING_MODEL_PATH}")

    # 9. Đánh giá phân cụm
    clustering_metrics = evaluate_clustering(X, labels)
    print(f"Chỉ số phân cụm (K={config.CLUSTER_K}):")
    print(f"  Silhouette: {clustering_metrics['silhouette']:.4f}")
    print(f"  Davies-Bouldin: {clustering_metrics['davies_bouldin']:.4f}")
    print(f"  Calinski-Harabasz: {clustering_metrics['calinski_harabasz']:.2f}")
    print(f"Thời gian phân cụm: {time.time() - start_t:.2f}s")

    return rfm_labeled, clustering_metrics


def train_recommenders(
    interactions: pd.DataFrame,
    customer_clusters: pd.DataFrame,
    products_df: pd.DataFrame
) -> dict:
    """Huấn luyện 6 mô hình gợi ý sản phẩm."""
    print("\n--- [2/3] HUẤN LUYỆN 6 MÔ HÌNH GỢI Ý SẢN PHẨM ---")
    start_t = time.time()

    # 1. Popularity
    print("1. Huấn luyện PopularityRecommender...")
    pop_model = PopularityRecommender()
    pop_model.fit(interactions)

    # Lưu danh sách top sản phẩm phổ biến toàn cầu kèm thông tin mô tả và ảnh
    prod_dict = products_df.set_index("stockcode").to_dict(orient="index")
    popularity_global = []
    for sc, score in pop_model.popular_items[:50]:
        info = prod_dict.get(sc, {})
        popularity_global.append({
            "stockcode": sc,
            "description": info.get("description", "unknown product"),
            "score": score,
            "image": info.get("image_path", "/images/placeholder.jpg")
        })
    with open(config.POPULARITY_GLOBAL_PATH, "w", encoding="utf-8") as f:
        json.dump(popularity_global, f, indent=2, ensure_ascii=False)
    print(f"-> Đã lưu: {config.POPULARITY_GLOBAL_PATH}")

    # 2. Cluster Popularity
    print("2. Huấn luyện ClusterPopularityRecommender...")
    cluster_pop_model = ClusterPopularityRecommender(customer_clusters)
    cluster_pop_model.fit(interactions)

    # 3. Item-CF
    print("3. Huấn luyện ItemCFRecommender...")
    item_cf_model = ItemCFRecommender()
    item_cf_model.fit(interactions)

    # 4. ALS
    print("4. Huấn luyện ALSRecommender (implicit library)...")
    als_model = ALSRecommender()
    als_model.fit(interactions)

    # 5. Content-Based
    print("5. Huấn luyện ContentBasedRecommender (TF-IDF)...")
    content_model = ContentBasedRecommender(products_df)
    content_model.fit(interactions)

    # 6. Hybrid
    print("6. Huấn luyện HybridRecommender (ALS + Content + Cluster-Pop)...")
    hybrid_model = HybridRecommender(
        als_model=als_model,
        content_model=content_model,
        cluster_pop_model=cluster_pop_model,
        weights=config.HYBRID_WEIGHTS
    )
    hybrid_model.fit(interactions)

    models_dict = {
        "popularity": pop_model,
        "cluster_popularity": cluster_pop_model,
        "item_cf": item_cf_model,
        "als": als_model,
        "content": content_model,
        "hybrid": hybrid_model
    }

    # Lưu toàn bộ mô hình
    joblib.dump(models_dict, config.RECOMMENDERS_PATH)
    print(f"-> Đã lưu tất cả 6 mô hình: {config.RECOMMENDERS_PATH}")
    print(f"Thời gian huấn luyện gợi ý: {time.time() - start_t:.2f}s")

    return models_dict


def evaluate_all(
    models_dict: dict,
    test_truth: pd.DataFrame,
    interactions: pd.DataFrame,
    clustering_metrics: dict
):
    """Đánh giá toàn bộ 6 mô hình trên tập test_truth và lưu metrics.json."""
    print("\n--- [3/3] ĐÁNH GIÁ CÁC MÔ HÌNH TRÊN TẬP TEST_TRUTH ---")
    start_t = time.time()
    
    all_train_items = list(interactions["stockcode"].astype(str).unique())
    print(f"Số lượng sản phẩm trong tập train: {len(all_train_items):,}")
    print(f"Số khách hàng đánh giá trong test_truth: {test_truth['customer_id'].nunique():,}")

    recommender_metrics = {}

    for name, model in models_dict.items():
        print(f"Đang đánh giá mô hình: {name}...")
        m_start = time.time()
        scores = evaluate_recommender(
            model=model,
            test_truth=test_truth,
            k_list=tuple(config.EVAL_K_LIST),
            all_items=all_train_items
        )
        recommender_metrics[name] = scores
        print(f"  -> {name} xong trong {time.time() - m_start:.2f}s: P@10={scores.get('precision@10', 0):.4f}, R@10={scores.get('recall@10', 0):.4f}, MAP@10={scores.get('map@10', 0):.4f}, NDCG@10={scores.get('ndcg@10', 0):.4f}, Cov@10={scores.get('coverage@10', 0):.4f}")

    metrics_payload = {
        "clustering": clustering_metrics,
        "recommenders": recommender_metrics
    }

    with open(config.METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2, ensure_ascii=False)

    print(f"-> Đã lưu toàn bộ chỉ số đánh giá: {config.METRICS_PATH}")
    print(f"Tổng thời gian đánh giá: {time.time() - start_t:.2f}s")


def main():
    total_start = time.time()
    print("=" * 60)
    print("BẮT ĐẦU QUÁ TRÌNH HUẤN LUYỆN & ĐÁNH GIÁ TOÀN BỘ HỆ THỐNG")
    print("=" * 60)

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    verify_inputs()

    # Nạp dữ liệu
    print("Nạp các file processed...")
    rfm = pd.read_parquet(config.RFM_TRAIN_PATH)
    interactions = pd.read_parquet(config.INTERACTIONS_TRAIN_PATH)
    products_df = pd.read_csv(config.PRODUCTS_PATH, dtype={"stockcode": str})
    test_truth = pd.read_parquet(config.TEST_TRUTH_PATH)

    # 1. Phân cụm
    customer_clusters, clustering_metrics = train_clustering(rfm)

    # 2. Huấn luyện 6 mô hình gợi ý
    models_dict = train_recommenders(interactions, customer_clusters, products_df)

    # 3. Đánh giá
    evaluate_all(models_dict, test_truth, interactions, clustering_metrics)

    print("=" * 60)
    print(f"HOÀN THÀNH TOÀN BỘ QUÁ TRÌNH HUẤN LUYỆN trong {time.time() - total_start:.2f} giây!")
    print("=" * 60)


if __name__ == "__main__":
    main()
