"""
Module chứa các thuật toán gợi ý sản phẩm (backend/algorithms/recommender.py):
1. BaseRecommender: Lớp cơ sở định nghĩa interface chung
2. PopularityRecommender: Gợi ý theo độ phổ biến toàn cục (cold-start)
3. ClusterPopularityRecommender: Gợi ý theo độ phổ biến trong cụm khách hàng
4. ItemCFRecommender: Lọc cộng tác theo sản phẩm (Item-based Collaborative Filtering)
5. ALSRecommender: Phân rã ma trận với Alternating Least Squares (thư viện implicit)
6. ContentBasedRecommender: Gợi ý dựa trên nội dung mô tả sản phẩm (TF-IDF + Cosine)
7. HybridRecommender: Kết hợp trọng số giữa ALS, Content-based và Cluster Popularity
"""

import sys
from pathlib import Path
from abc import ABC, abstractmethod
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import implicit

# Đảm bảo import config
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config


class BaseRecommender(ABC):
    """
    Lớp cơ sở cho mọi thuật toán gợi ý sản phẩm.
    """

    @abstractmethod
    def fit(self, interactions: pd.DataFrame, **kwargs) -> "BaseRecommender":
        """
        Huấn luyện mô hình từ ma trận tương tác khách hàng - sản phẩm.
        """
        pass

    @abstractmethod
    def recommend(
        self, customer_id: int, k: int = config.DEFAULT_TOP_K, exclude_seen: bool = config.EXCLUDE_SEEN
    ) -> list[tuple[str, float]]:
        """
        Trả về danh sách [(stockcode, score), ...] sắp xếp giảm dần theo score.
        """
        pass


class PopularityRecommender(BaseRecommender):
    """
    Mô hình gợi ý sản phẩm bán chạy nhất toàn hệ thống.
    Được dùng làm fallback cho người dùng mới (cold-start).
    """

    def __init__(self):
        self.popular_items: list[tuple[str, float]] = []
        self.user_seen: dict[int, set[str]] = {}

    def fit(self, interactions: pd.DataFrame, **kwargs) -> "PopularityRecommender":
        # interactions có các cột: customer_id, stockcode, n_purchases, quantity
        df = interactions.copy()
        df["stockcode"] = df["stockcode"].astype(str)
        
        # Lưu các sản phẩm từng khách đã mua
        self.user_seen = (
            df.groupby("customer_id")["stockcode"]
            .apply(set)
            .to_dict()
        )

        # Tính tổng số lượt mua theo stockcode
        item_scores = df.groupby("stockcode")["n_purchases"].sum().sort_values(ascending=False)
        max_score = float(item_scores.max()) if len(item_scores) > 0 else 1.0

        self.popular_items = [
            (str(sc), round(float(val) / max_score, 4))
            for sc, val in item_scores.items()
        ]
        return self

    def recommend(
        self, customer_id: int, k: int = config.DEFAULT_TOP_K, exclude_seen: bool = config.EXCLUDE_SEEN
    ) -> list[tuple[str, float]]:
        seen = self.user_seen.get(customer_id, set()) if exclude_seen else set()
        results = []
        for sc, score in self.popular_items:
            if sc not in seen:
                results.append((sc, score))
            if len(results) >= k:
                break
        return results


class ClusterPopularityRecommender(BaseRecommender):
    """
    Mô hình gợi ý sản phẩm bán chạy nhất trong cụm mà khách hàng thuộc về.
    Nếu khách hàng không có cụm -> fallback về PopularityRecommender.
    """

    def __init__(self, customer_clusters: pd.DataFrame = None):
        self.customer_clusters = customer_clusters
        self.cust_to_cluster: dict[int, int] = {}
        self.cluster_popular_items: dict[int, list[tuple[str, float]]] = {}
        self.global_pop = PopularityRecommender()
        self.user_seen: dict[int, set[str]] = {}

    def set_clusters(self, customer_clusters: pd.DataFrame):
        self.customer_clusters = customer_clusters

    def fit(self, interactions: pd.DataFrame, **kwargs) -> "ClusterPopularityRecommender":
        self.global_pop.fit(interactions)
        
        df = interactions.copy()
        df["stockcode"] = df["stockcode"].astype(str)
        self.user_seen = self.global_pop.user_seen

        if self.customer_clusters is not None and not self.customer_clusters.empty:
            cluster_df = self.customer_clusters[["customer_id", "cluster"]].drop_duplicates()
            self.cust_to_cluster = dict(zip(cluster_df["customer_id"], cluster_df["cluster"]))

            merged = df.merge(cluster_df, on="customer_id", how="inner")
            grouped = (
                merged.groupby(["cluster", "stockcode"])["n_purchases"]
                .sum()
                .reset_index()
            )

            for cluster_id, grp in grouped.groupby("cluster"):
                grp_sorted = grp.sort_values("n_purchases", ascending=False)
                max_sc = float(grp_sorted["n_purchases"].max()) if len(grp_sorted) > 0 else 1.0
                self.cluster_popular_items[int(cluster_id)] = [
                    (str(r["stockcode"]), round(float(r["n_purchases"]) / max_sc, 4))
                    for _, r in grp_sorted.iterrows()
                ]

        return self

    def recommend(
        self, customer_id: int, k: int = config.DEFAULT_TOP_K, exclude_seen: bool = config.EXCLUDE_SEEN
    ) -> list[tuple[str, float]]:
        cluster_id = self.cust_to_cluster.get(customer_id)
        if cluster_id is None or cluster_id not in self.cluster_popular_items:
            return self.global_pop.recommend(customer_id, k, exclude_seen)

        seen = self.user_seen.get(customer_id, set()) if exclude_seen else set()
        results = []
        cluster_items = self.cluster_popular_items[cluster_id]

        for sc, score in cluster_items:
            if sc not in seen:
                results.append((sc, score))
            if len(results) >= k:
                break

        # Nếu không đủ k sản phẩm thì bổ sung từ global popularity
        if len(results) < k:
            seen_in_results = seen.union({sc for sc, _ in results})
            for sc, score in self.global_pop.popular_items:
                if sc not in seen_in_results:
                    results.append((sc, score))
                if len(results) >= k:
                    break

        return results[:k]


class ItemCFRecommender(BaseRecommender):
    """
    Lọc cộng tác dựa trên sản phẩm (Item-based Collaborative Filtering):
    - Xây dựng ma trận User-Item
    - Tính ma trận tương đồng Cosine giữa các sản phẩm
    - Điểm dự đoán = tổng độ tương đồng giữa sản phẩm đích với các sản phẩm người dùng đã mua
    """

    def __init__(self):
        self.item_sim: np.ndarray | None = None
        self.stockcode_list: list[str] = []
        self.stockcode_to_idx: dict[str, int] = {}
        self.cust_to_idx: dict[int, int] = {}
        self.user_item_matrix: sparse.csr_matrix | None = None
        self.global_pop = PopularityRecommender()
        self.user_seen: dict[int, set[str]] = {}

    def fit(self, interactions: pd.DataFrame, **kwargs) -> "ItemCFRecommender":
        self.global_pop.fit(interactions)
        self.user_seen = self.global_pop.user_seen

        df = interactions.copy()
        df["stockcode"] = df["stockcode"].astype(str)

        users = sorted(df["customer_id"].unique())
        items = sorted(df["stockcode"].unique())

        self.cust_to_idx = {u: i for i, u in enumerate(users)}
        self.stockcode_list = items
        self.stockcode_to_idx = {it: i for i, it in enumerate(items)}

        row_indices = df["customer_id"].map(self.cust_to_idx).values
        col_indices = df["stockcode"].map(self.stockcode_to_idx).values
        data = df["n_purchases"].values.astype(np.float32)

        self.user_item_matrix = sparse.csr_matrix(
            (data, (row_indices, col_indices)),
            shape=(len(users), len(items))
        )

        # Tính cosine similarity giữa các cột (sản phẩm): item_matrix.T (shape: n_items x n_users)
        item_user = self.user_item_matrix.T.tocsr()
        # float32 thay vì float64: giảm một nửa RAM (10.000 sản phẩm: ~0,4 GB thay vì ~0,8 GB)
        self.item_sim = cosine_similarity(item_user, dense_output=True).astype(np.float32)

        return self

    def recommend(
        self, customer_id: int, k: int = config.DEFAULT_TOP_K, exclude_seen: bool = config.EXCLUDE_SEEN
    ) -> list[tuple[str, float]]:
        if customer_id not in self.cust_to_idx or self.item_sim is None:
            return self.global_pop.recommend(customer_id, k, exclude_seen)

        u_idx = self.cust_to_idx[customer_id]
        # Vector tương tác của người dùng: 1 x n_items
        u_row = self.user_item_matrix[u_idx]

        if u_row.nnz == 0:
            return self.global_pop.recommend(customer_id, k, exclude_seen)

        # Điểm gợi ý = u_vec @ item_sim (1 x n_items).
        # Dùng hàng thưa: chỉ cộng các hàng item_sim của những món khách đã mua,
        # nhanh hơn nhiều so với nhân cả vector dày 10.000 phần tử.
        scores = np.asarray(u_row @ self.item_sim).ravel()

        seen = self.user_seen.get(customer_id, set()) if exclude_seen else set()
        
        # Lấy top k
        top_indices = np.argsort(scores)[::-1]
        results = []
        max_score = float(np.max(scores)) if len(scores) > 0 and np.max(scores) > 0 else 1.0

        for idx in top_indices:
            sc = self.stockcode_list[idx]
            if sc not in seen and scores[idx] > 0:
                results.append((sc, round(float(scores[idx]) / max_score, 4)))
            if len(results) >= k:
                break

        # Nếu không đủ thì bổ sung từ Popularity
        if len(results) < k:
            seen_in_results = seen.union({sc for sc, _ in results})
            for sc, score in self.global_pop.popular_items:
                if sc not in seen_in_results:
                    results.append((sc, score))
                if len(results) >= k:
                    break

        return results[:k]


class ALSRecommender(BaseRecommender):
    """
    Phân rã ma trận ẩn với Alternating Least Squares (implicit feedback):
    - Giá trị tương tác = 1 + 40 * log1p(n_purchases)
    - Siêu tham số từ config (factors, iterations, regularization)
    """

    def __init__(self):
        self.model: implicit.als.AlternatingLeastSquares | None = None
        self.cust_to_idx: dict[int, int] = {}
        self.idx_to_cust: dict[int, int] = {}
        self.stockcode_list: list[str] = []
        self.stockcode_to_idx: dict[str, int] = {}
        self.user_item_matrix: sparse.csr_matrix | None = None
        self.global_pop = PopularityRecommender()
        self.user_seen: dict[int, set[str]] = {}

    def fit(self, interactions: pd.DataFrame, **kwargs) -> "ALSRecommender":
        self.global_pop.fit(interactions)
        self.user_seen = self.global_pop.user_seen

        df = interactions.copy()
        df["stockcode"] = df["stockcode"].astype(str)

        users = sorted(df["customer_id"].unique())
        items = sorted(df["stockcode"].unique())

        self.cust_to_idx = {u: i for i, u in enumerate(users)}
        self.idx_to_cust = {i: u for u, i in self.cust_to_idx.items()}
        self.stockcode_list = items
        self.stockcode_to_idx = {it: i for i, it in enumerate(items)}

        row_indices = df["customer_id"].map(self.cust_to_idx).values
        col_indices = df["stockcode"].map(self.stockcode_to_idx).values
        
        # Giá trị tự tin (confidence) theo quy định mục 6: 1 + 40 * log1p(n_purchases)
        confidence = (1.0 + 40.0 * np.log1p(df["n_purchases"].values)).astype(np.float32)

        self.user_item_matrix = sparse.csr_matrix(
            (confidence, (row_indices, col_indices)),
            shape=(len(users), len(items))
        )

        self.model = implicit.als.AlternatingLeastSquares(
            factors=config.ALS_FACTORS,
            iterations=config.ALS_ITERATIONS,
            regularization=config.ALS_REGULARIZATION,
            random_state=config.RANDOM_SEED
        )

        # Trong implicit >= 0.5.0, fit nhận ma trận user-item dạng csr
        self.model.fit(self.user_item_matrix, show_progress=False)
        return self

    def recommend(
        self, customer_id: int, k: int = config.DEFAULT_TOP_K, exclude_seen: bool = config.EXCLUDE_SEEN
    ) -> list[tuple[str, float]]:
        if customer_id not in self.cust_to_idx or self.model is None:
            return self.global_pop.recommend(customer_id, k, exclude_seen)

        u_idx = self.cust_to_idx[customer_id]
        
        # Sử dụng API recommend của implicit
        ids, scores = self.model.recommend(
            u_idx,
            self.user_item_matrix[u_idx],
            N=min(k * 2, len(self.stockcode_list)),
            filter_already_liked_items=exclude_seen
        )

        results = []
        max_score = float(np.max(scores)) if len(scores) > 0 and np.max(scores) > 0 else 1.0

        for item_idx, score in zip(ids, scores):
            sc = self.stockcode_list[item_idx]
            norm_score = max(0.0, min(1.0, float(score) / max_score))
            results.append((sc, round(norm_score, 4)))
            if len(results) >= k:
                break

        # Nếu không đủ thì bổ sung từ Popularity
        if len(results) < k:
            seen_in_results = {sc for sc, _ in results}
            if exclude_seen:
                seen_in_results = seen_in_results.union(self.user_seen.get(customer_id, set()))
            for sc, score in self.global_pop.popular_items:
                if sc not in seen_in_results:
                    results.append((sc, score))
                if len(results) >= k:
                    break

        return results[:k]


class ContentBasedRecommender(BaseRecommender):
    """
    Gợi ý dựa trên nội dung (Content-Based):
    - TF-IDF trên cột description từ products.csv
    - Vector người dùng = trung bình trọng số các vector TF-IDF của sản phẩm đã mua
    - Điểm tương đồng = Cosine Similarity giữa vector người dùng và các sản phẩm
    """

    def __init__(self, products_df: pd.DataFrame = None):
        self.products_df = products_df
        self.tfidf = TfidfVectorizer(stop_words="english", max_features=1000)
        self.tfidf_matrix: np.ndarray | None = None
        self.stockcode_list: list[str] = []
        self.stockcode_to_idx: dict[str, int] = {}
        self.user_profiles: dict[int, np.ndarray] = {}
        self.global_pop = PopularityRecommender()
        self.user_seen: dict[int, set[str]] = {}

    def set_products(self, products_df: pd.DataFrame):
        self.products_df = products_df

    def fit(self, interactions: pd.DataFrame, **kwargs) -> "ContentBasedRecommender":
        self.global_pop.fit(interactions)
        self.user_seen = self.global_pop.user_seen

        if self.products_df is None or self.products_df.empty:
            if config.PRODUCTS_PATH.exists():
                self.products_df = pd.read_csv(config.PRODUCTS_PATH, dtype={"stockcode": str})
            else:
                return self

        prods = self.products_df.copy()
        prods["stockcode"] = prods["stockcode"].astype(str)
        prods["description"] = prods["description"].fillna("").astype(str)

        self.stockcode_list = prods["stockcode"].tolist()
        self.stockcode_to_idx = {sc: i for i, sc in enumerate(self.stockcode_list)}

        # Tính TF-IDF ma trận sản phẩm.
        # Bộ H&M có cột content_text (tên + loại + nhóm + màu + mô tả chi tiết) -> ưu tiên dùng;
        # nếu không có thì dùng description như cũ.
        text_col = "content_text" if "content_text" in prods.columns else "description"
        tfidf_sparse = self.tfidf.fit_transform(prods[text_col].fillna("").astype(str))
        # TfidfVectorizer đã chuẩn hóa L2 từng dòng -> tích vô hướng = cosine similarity.
        self.tfidf_matrix = tfidf_sparse.toarray().astype(np.float32)

        # Xây dựng vector profile cho từng người dùng
        df = interactions.copy()
        df["stockcode"] = df["stockcode"].astype(str)

        for cust_id, grp in df.groupby("customer_id"):
            valid_indices = []
            weights = []
            for _, r in grp.iterrows():
                sc = r["stockcode"]
                if sc in self.stockcode_to_idx:
                    valid_indices.append(self.stockcode_to_idx[sc])
                    weights.append(r["n_purchases"])

            if valid_indices:
                w = np.array(weights)[:, np.newaxis]
                user_vec = np.sum(self.tfidf_matrix[valid_indices] * w, axis=0)
                norm = np.linalg.norm(user_vec)
                if norm > 0:
                    user_vec = user_vec / norm
                self.user_profiles[cust_id] = user_vec.astype(np.float32)

        return self

    def recommend(
        self, customer_id: int, k: int = config.DEFAULT_TOP_K, exclude_seen: bool = config.EXCLUDE_SEEN
    ) -> list[tuple[str, float]]:
        if customer_id not in self.user_profiles or self.tfidf_matrix is None:
            return self.global_pop.recommend(customer_id, k, exclude_seen)

        user_vec = self.user_profiles[customer_id]
        # Cosine similarity = tích vô hướng, vì cả hồ sơ khách lẫn từng dòng TF-IDF đều đã chuẩn hóa L2.
        # Không gọi cosine_similarity() ở đây: hàm đó chuẩn hóa lại cả ma trận ở MỖI lần gọi
        # (tạo bản sao ~80 MB/lần) -> rất chậm và làm treo máy khi đánh giá 10.000 khách.
        scores = self.tfidf_matrix @ user_vec

        seen = self.user_seen.get(customer_id, set()) if exclude_seen else set()
        top_indices = np.argsort(scores)[::-1]
        results = []

        max_score = float(np.max(scores)) if len(scores) > 0 and np.max(scores) > 0 else 1.0

        for idx in top_indices:
            sc = self.stockcode_list[idx]
            if sc not in seen and scores[idx] > 0:
                results.append((sc, round(float(scores[idx]) / max_score, 4)))
            if len(results) >= k:
                break

        # Bổ sung nếu thiếu
        if len(results) < k:
            seen_in_results = seen.union({sc for sc, _ in results})
            for sc, score in self.global_pop.popular_items:
                if sc not in seen_in_results:
                    results.append((sc, score))
                if len(results) >= k:
                    break

        return results[:k]


class HybridRecommender(BaseRecommender):
    """
    Mô hình gợi ý lai (Hybrid Recommender):
    - Chuẩn hóa Min-Max điểm của ALS, Content-based và Cluster Popularity
    - Kết hợp có trọng số theo HYBRID_WEIGHTS = {"als": 0.5, "content": 0.2, "cluster_pop": 0.3}
    - Khách hàng cold-start fallback về PopularityRecommender.
    """

    def __init__(
        self,
        als_model: ALSRecommender = None,
        content_model: ContentBasedRecommender = None,
        cluster_pop_model: ClusterPopularityRecommender = None,
        weights: dict = config.HYBRID_WEIGHTS
    ):
        self.als_model = als_model or ALSRecommender()
        self.content_model = content_model or ContentBasedRecommender()
        self.cluster_pop_model = cluster_pop_model or ClusterPopularityRecommender()
        self.weights = weights
        self.global_pop = PopularityRecommender()
        self.known_customers: set[int] = set()

    def fit(self, interactions: pd.DataFrame, **kwargs) -> "HybridRecommender":
        self.global_pop.fit(interactions)
        self.known_customers = set(interactions["customer_id"].unique())
        return self

    def recommend(
        self, customer_id: int, k: int = config.DEFAULT_TOP_K, exclude_seen: bool = config.EXCLUDE_SEEN
    ) -> list[tuple[str, float]]:
        # Khách hàng mới (cold-start) fallback Popularity
        if customer_id not in self.known_customers:
            return self.global_pop.recommend(customer_id, k, exclude_seen)

        # Lấy danh sách ứng viên (candidate pool) từ 3 mô hình
        pool_k = max(k * 4, 40)
        recs_als = dict(self.als_model.recommend(customer_id, k=pool_k, exclude_seen=exclude_seen))
        recs_content = dict(self.content_model.recommend(customer_id, k=pool_k, exclude_seen=exclude_seen))
        recs_cluster = dict(self.cluster_pop_model.recommend(customer_id, k=pool_k, exclude_seen=exclude_seen))

        # Tập hợp tất cả các sản phẩm ứng viên
        candidate_items = set(recs_als.keys()).union(recs_content.keys()).union(recs_cluster.keys())

        w_als = self.weights.get("als", 0.5)
        w_content = self.weights.get("content", 0.2)
        w_cluster = self.weights.get("cluster_pop", 0.3)

        combined_scores = {}
        for sc in candidate_items:
            s_als = recs_als.get(sc, 0.0)
            s_cnt = recs_content.get(sc, 0.0)
            s_cls = recs_cluster.get(sc, 0.0)
            combined_scores[sc] = (
                w_als * s_als + w_content * s_cnt + w_cluster * s_cls
            )

        # Sắp xếp giảm dần theo điểm
        sorted_items = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        max_s = sorted_items[0][1] if sorted_items and sorted_items[0][1] > 0 else 1.0

        results = [
            (sc, round(score / max_s, 4))
            for sc, score in sorted_items[:k]
        ]

        # Bổ sung nếu vẫn chưa đủ k
        if len(results) < k:
            seen_set = {sc for sc, _ in results}
            for sc, score in self.global_pop.popular_items:
                if sc not in seen_set:
                    results.append((sc, score))
                if len(results) >= k:
                    break

        return results[:k]
        