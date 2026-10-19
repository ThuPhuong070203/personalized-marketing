"""
Module phân cụm khách hàng theo mô hình RFM + K-Means (backend/algorithms/clustering.py):
- prepare_features: log1p + StandardScaler
- evaluate_k: inertia và silhouette score cho các giá trị k
- fit_kmeans: huấn luyện K-Means
- name_clusters: gán tên, mô tả và chiến dịch theo quy tắc RFM
- compute_pca: giảm chiều PCA 2D phục vụ trực quan hóa
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA

# Đảm bảo import config
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config


def prepare_features(rfm: pd.DataFrame) -> tuple[np.ndarray, StandardScaler]:
    """
    Chuẩn bị đặc trưng cho phân cụm:
    1. np.log1p cho recency, frequency, monetary để giảm độ lệch (skewness)
    2. StandardScaler để đưa về phân phối chuẩn hóa
    """
    feature_cols = ["recency", "frequency", "monetary"]
    
    # Đảm bảo các giá trị không âm trước khi log1p
    rfm_clean = rfm[feature_cols].copy()
    rfm_clean["recency"] = np.clip(rfm_clean["recency"], a_min=0, a_max=None)
    rfm_clean["frequency"] = np.clip(rfm_clean["frequency"], a_min=0, a_max=None)
    rfm_clean["monetary"] = np.clip(rfm_clean["monetary"], a_min=0, a_max=None)

    log_features = np.log1p(rfm_clean.values)
    
    scaler = StandardScaler()
    X = scaler.fit_transform(log_features)
    
    return X, scaler


def evaluate_k(X: np.ndarray, k_range=range(2, 11)) -> list[dict]:
    """
    Đánh giá độ phù hợp của các giá trị K trong dải k_range:
    Trả về danh sách các bản ghi gồm k, inertia và silhouette score.
    """
    results = []
    # Lấy mẫu tối đa 5000 điểm khi tính silhouette để tăng tốc độ tính toán
    sample_size = min(len(X), 5000)
    
    for k in k_range:
        kmeans = KMeans(n_clusters=k, random_state=config.RANDOM_SEED, n_init=10)
        labels = kmeans.fit_predict(X)
        
        sil = silhouette_score(
            X, labels, sample_size=sample_size, random_state=config.RANDOM_SEED
        )
        results.append({
            "k": int(k),
            "inertia": round(float(kmeans.inertia_), 2),
            "silhouette": round(float(sil), 4)
        })
        
    return results


def fit_kmeans(X: np.ndarray, k: int = config.CLUSTER_K) -> KMeans:
    """
    Huấn luyện mô hình K-Means với số cụm k và random_state cố định.
    """
    kmeans = KMeans(
        n_clusters=k,
        random_state=config.RANDOM_SEED,
        n_init=10
    )
    kmeans.fit(X)
    return kmeans


def name_clusters(rfm_labeled: pd.DataFrame) -> dict[int, dict]:
    """
    Đặt tên cụm và sinh chiến dịch marketing dựa trên giá trị trung bình RFM của từng cụm:
    - Recency cao nhất -> 'Khách có nguy cơ rời bỏ'
    - Recency thấp, Frequency & Monetary cao nhất -> 'Khách VIP'
    - Frequency cao, Monetary khá -> 'Khách trung thành'
    - Recency thấp, Frequency thấp -> 'Khách mới'
    - Dự phòng: 'Cụm <id>' nếu không khớp
    """
    # Tính trung bình RFM từng cụm
    cluster_stats = (
        rfm_labeled.groupby("cluster")[["recency", "frequency", "monetary"]]
        .mean()
        .to_dict(orient="index")
    )
    
    clusters = list(cluster_stats.keys())
    mapping = {}
    remaining_clusters = set(clusters)

    if len(clusters) == 4:
        # 1. Cụm có Recency cao nhất: Khách có nguy cơ rời bỏ
        at_risk_cluster = max(
            remaining_clusters, key=lambda c: cluster_stats[c]["recency"]
        )
        mapping[at_risk_cluster] = {
            "name": "Khách có nguy cơ rời bỏ",
            "description": "Khách hàng đã lâu không quay lại mua sắm dù từng có lịch sử giao dịch.",
            "campaign": "Chiến dịch Win-Back: gửi email cá nhân hóa kèm mã giảm giá đặc biệt để kích hoạt lại."
        }
        remaining_clusters.remove(at_risk_cluster)

        # 2. Trong các cụm còn lại, cụm có Monetary & Frequency cao nhất: Khách VIP
        vip_cluster = max(
            remaining_clusters,
            key=lambda c: (cluster_stats[c]["monetary"], cluster_stats[c]["frequency"])
        )
        mapping[vip_cluster] = {
            "name": "Khách VIP",
            "description": "Khách hàng có giá trị vòng đời cao nhất, mua sắm định kỳ với giá trị đơn lớn.",
            "campaign": "Đặc quyền VIP: tri ân quà tặng độc quyền, truy cập sớm bộ sưu tập mới và chăm sóc ưu tiên 1-1."
        }
        remaining_clusters.remove(vip_cluster)

        # 3. Trong 2 cụm còn lại, cụm có Frequency / Monetary cao hơn: Khách trung thành
        loyal_cluster = max(
            remaining_clusters,
            key=lambda c: (cluster_stats[c]["frequency"], cluster_stats[c]["monetary"])
        )
        mapping[loyal_cluster] = {
            "name": "Khách trung thành",
            "description": "Khách hàng mua sắm đều đặn, đóng góp doanh thu ổn định cho cửa hàng.",
            "campaign": "Tích điểm đổi quà: nhân đôi điểm thưởng khi mua lại và giới thiệu sản phẩm bổ trợ."
        }
        remaining_clusters.remove(loyal_cluster)

        # 4. Cụm cuối cùng: Khách mới
        new_cluster = remaining_clusters.pop()
        mapping[new_cluster] = {
            "name": "Khách mới",
            "description": "Khách hàng mới phát sinh đơn hàng gần đây nhưng tần suất và giá trị đơn còn khiêm tốn.",
            "campaign": "Chào mừng khách mới: tặng voucher giảm giá cho đơn hàng thứ 2 và gợi ý sản phẩm bán chạy nhất."
        }
    else:
        # Dự phòng cho trường hợp k != 4
        used_names = set()
        for c in clusters:
            name = f"Cụm {c}"
            mapping[c] = {
                "name": name,
                "description": f"Nhóm khách hàng cụm {c} với đặc trưng RFM riêng biệt.",
                "campaign": "Chương trình khuyến mãi cá nhân hóa theo nhóm sản phẩm ưa thích."
            }

    return mapping


def compute_pca(X: np.ndarray) -> tuple[np.ndarray, PCA]:
    """
    Giảm chiều dữ liệu xuống 2D bằng PCA để vẽ biểu đồ phân tán.
    """
    pca = PCA(n_components=2, random_state=config.RANDOM_SEED)
    X_pca = pca.fit_transform(X)
    return X_pca, pca
