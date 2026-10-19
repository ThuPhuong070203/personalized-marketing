"""
Module tính toán các chỉ số đánh giá cho mô hình phân cụm và hệ thống gợi ý (backend/algorithms/evaluate.py):
- Phân cụm: Silhouette, Davies-Bouldin, Calinski-Harabasz
- Hệ thống gợi ý: Precision@K, Recall@K, MAP@K, NDCG@K, Coverage@K
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import (
    silhouette_score,
    davies_bouldin_score,
    calinski_harabasz_score
)

# Đảm bảo import config
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config


def precision_at_k(actual: list[str], predicted: list[str], k: int) -> float:
    """
    Tính Precision@K: Tỷ lệ các sản phẩm được gợi ý trong top-k mà khách hàng thực sự mua trong test.
    """
    if k <= 0 or not predicted:
        return 0.0
    pred_k = predicted[:k]
    hits = len(set(pred_k) & set(actual))
    return hits / float(k)


def recall_at_k(actual: list[str], predicted: list[str], k: int) -> float:
    """
    Tính Recall@K: Tỷ lệ các sản phẩm khách hàng mua trong test được hệ thống bao phủ trong top-k.
    """
    if not actual or k <= 0 or not predicted:
        return 0.0
    pred_k = predicted[:k]
    hits = len(set(pred_k) & set(actual))
    return hits / float(len(actual))


def map_at_k(actual: list[str], predicted: list[str], k: int) -> float:
    """
    Tính Mean Average Precision (MAP@K) cho một người dùng:
    Trung bình các điểm Precision@i tại mỗi vị trí i mà sản phẩm gợi ý xuất hiện trong actual.
    """
    if not actual or k <= 0 or not predicted:
        return 0.0
    
    actual_set = set(actual)
    score = 0.0
    num_hits = 0.0
    pred_k = predicted[:k]

    for i, p in enumerate(pred_k):
        if p in actual_set:
            num_hits += 1.0
            score += num_hits / (i + 1.0)

    return score / float(min(len(actual), k))


def ndcg_at_k(actual: list[str], predicted: list[str], k: int) -> float:
    """
    Tính Normalized Discounted Cumulative Gain (NDCG@K) cho một người dùng:
    Đánh giá độ chính xác có tính đến vị trí xếp hạng của sản phẩm trong top-k.
    """
    if not actual or k <= 0 or not predicted:
        return 0.0

    actual_set = set(actual)
    pred_k = predicted[:k]
    
    dcg = 0.0
    for i, p in enumerate(pred_k):
        if p in actual_set:
            dcg += 1.0 / np.log2(i + 2.0)  # log2(rank + 1) với rank = i + 1 => i + 2

    # Lý tưởng (IDCG): tất cả các vị trí đầu tiên đều trúng
    idcg_len = min(len(actual), k)
    idcg = sum(1.0 / np.log2(i + 2.0) for i in range(idcg_len))

    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def coverage(
    all_recommended_items: set[str], total_available_items: int
) -> float:
    """
    Tính Coverage@K: Tỷ lệ sản phẩm được hệ thống gợi ý ít nhất 1 lần trên tổng số sản phẩm có thể gợi ý.
    """
    if total_available_items <= 0:
        return 0.0
    return len(all_recommended_items) / float(total_available_items)


def evaluate_recommender(
    model,
    test_truth: pd.DataFrame,
    k_list: tuple[int, ...] = (5, 10, 20),
    all_items: list[str] = None
) -> dict[str, float]:
    """
    Đánh giá một mô hình gợi ý trên tập test_truth:
    - Tính Precision@K, Recall@K, MAP@K, NDCG@K, Coverage@K cho từng k trong k_list
    - Trả về dict kết quả trung bình
    """
    # Nhóm tập test_truth theo customer_id
    truth_dict = (
        test_truth.groupby("customer_id")["stockcode"]
        .apply(lambda s: list(s.astype(str)))
        .to_dict()
    )
    
    customers = list(truth_dict.keys())
    max_k = max(k_list)
    total_available_items = len(all_items) if all_items is not None else 1

    # Khởi tạo các mảng tích lũy
    metrics = {f"precision@{k}": [] for k in k_list}
    metrics.update({f"recall@{k}": [] for k in k_list})
    metrics.update({f"map@{k}": [] for k in k_list})
    metrics.update({f"ndcg@{k}": [] for k in k_list})
    recs_by_k = {k: set() for k in k_list}

    for cust_id in customers:
        actual_items = truth_dict[cust_id]
        # Lấy gợi ý từ mô hình
        recs = model.recommend(cust_id, k=max_k, exclude_seen=config.EXCLUDE_SEEN)
        pred_items = [str(sc) for sc, _ in recs]

        for k in k_list:
            p_k = precision_at_k(actual_items, pred_items, k)
            r_k = recall_at_k(actual_items, pred_items, k)
            m_k = map_at_k(actual_items, pred_items, k)
            n_k = ndcg_at_k(actual_items, pred_items, k)

            metrics[f"precision@{k}"].append(p_k)
            metrics[f"recall@{k}"].append(r_k)
            metrics[f"map@{k}"].append(m_k)
            metrics[f"ndcg@{k}"].append(n_k)
            recs_by_k[k].update(pred_items[:k])

    results = {}
    for k in k_list:
        results[f"precision@{k}"] = round(float(np.mean(metrics[f"precision@{k}"])), 4)
        results[f"recall@{k}"] = round(float(np.mean(metrics[f"recall@{k}"])), 4)
        results[f"map@{k}"] = round(float(np.mean(metrics[f"map@{k}"])), 4)
        results[f"ndcg@{k}"] = round(float(np.mean(metrics[f"ndcg@{k}"])), 4)
        results[f"coverage@{k}"] = round(float(coverage(recs_by_k[k], total_available_items)), 4)

    return results


def evaluate_clustering(X: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    """
    Đánh giá chất lượng phân cụm:
    - Silhouette Score (càng cao càng tốt, dải [-1, 1])
    - Davies-Bouldin Index (càng thấp càng tốt, >= 0)
    - Calinski-Harabasz Index (càng cao càng tốt)
    """
    n_clusters = len(np.unique(labels))
    sample_size = min(len(X), 5000)

    sil = silhouette_score(
        X, labels, sample_size=sample_size, random_state=config.RANDOM_SEED
    )
    db = davies_bouldin_score(X, labels)
    ch = calinski_harabasz_score(X, labels)

    return {
        "k": int(n_clusters),
        "silhouette": round(float(sil), 4),
        "davies_bouldin": round(float(db), 4),
        "calinski_harabasz": round(float(ch), 2)
    }
