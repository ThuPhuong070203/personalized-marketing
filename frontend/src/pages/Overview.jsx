import React, { useState, useEffect } from 'react';
import { api } from '../api';
import LoadingSpinner from '../components/LoadingSpinner';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  CartesianGrid,
} from 'recharts';
import { Award, BarChart2, PieChart, Layers, CheckCircle2, TrendingUp, Info } from 'lucide-react';

const MODEL_LABELS = {
  popularity: 'Popularity',
  cluster_popularity: 'Cluster Popularity',
  item_cf: 'Item-CF',
  als: 'ALS (Implicit)',
  content: 'Content-Based',
  hybrid: 'Hybrid (Đề xuất)',
};

export default function Metrics() {
  const [metrics, setMetrics] = useState(null);
  const [selectedK, setSelectedK] = useState(10);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchMetrics() {
      try {
        setLoading(true);
        const data = await api.getMetrics();
        setMetrics(data);
      } catch (err) {
        setError(err.message || 'Không thể nạp dữ liệu đánh giá mô hình');
      } finally {
        setLoading(false);
      }
    }
    fetchMetrics();
  }, []);

  if (loading) return <LoadingSpinner text="Đang tải dữ liệu đánh giá mô hình..." />;
  if (error) return <div className="error-banner">{error}</div>;
  if (!metrics) return null;

  const clustering = metrics.clustering || {};
  const recommenders = metrics.recommenders || {};

  // Chuẩn bị dữ liệu cho biểu đồ so sánh Recharts
  const chartData = Object.entries(recommenders).map(([key, scores]) => {
    return {
      model: MODEL_LABELS[key] || key,
      precision: Math.round((scores[`precision@${selectedK}`] || 0) * 1000) / 10,
      recall: Math.round((scores[`recall@${selectedK}`] || 0) * 1000) / 10,
      map: Math.round((scores[`map@${selectedK}`] || 0) * 1000) / 10,
      ndcg: Math.round((scores[`ndcg@${selectedK}`] || 0) * 1000) / 10,
      coverage: Math.round((scores[`coverage@${selectedK}`] || 0) * 1000) / 10,
    };
  });

  // Tìm giá trị cao nhất cho từng chỉ số để highlight
  const maxValues = {
    precision: Math.max(...Object.values(recommenders).map((s) => s[`precision@${selectedK}`] || 0)),
    recall: Math.max(...Object.values(recommenders).map((s) => s[`recall@${selectedK}`] || 0)),
    map: Math.max(...Object.values(recommenders).map((s) => s[`map@${selectedK}`] || 0)),
    ndcg: Math.max(...Object.values(recommenders).map((s) => s[`ndcg@${selectedK}`] || 0)),
    coverage: Math.max(...Object.values(recommenders).map((s) => s[`coverage@${selectedK}`] || 0)),
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Đánh Giá & So Sánh Mô Hình</h1>
        <p className="page-desc">
          Bảng chỉ số định lượng đánh giá phân cụm K-Means và hiệu năng thực nghiệm của 6 mô hình gợi ý sản phẩm trên tập Test độc lập (28 ngày cuối của bộ dữ liệu H&M).
        </p>
      </div>

      {/* 1. Phần đánh giá phân cụm */}
      <div className="glass-card" style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
          <PieChart size={22} color="var(--primary-light)" />
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Chỉ Số Đánh Giá Phân Cụm (K-Means)</h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
          <div style={{ background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-card)', padding: '1.25rem', borderRadius: '12px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>SỐ CỤM TỐI ƯU (K)</span>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px' }}>
              {clustering.k || 4}
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>
              Dựa trên phương pháp Elbow và Silhouette
            </p>
          </div>

          <div style={{ background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-card)', padding: '1.25rem', borderRadius: '12px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>SILHOUETTE SCORE</span>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#38bdf8', marginTop: '4px' }}>
              {clustering.silhouette !== undefined ? clustering.silhouette.toFixed(4) : 'N/A'}
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>
              Dải [-1, 1] • Điểm dương cao thể hiện các cụm phân tách rõ ràng
            </p>
          </div>

          <div style={{ background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-card)', padding: '1.25rem', borderRadius: '12px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>DAVIES-BOULDIN INDEX</span>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#10b981', marginTop: '4px' }}>
              {clustering.davies_bouldin !== undefined ? clustering.davies_bouldin.toFixed(4) : 'N/A'}
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>
              Càng nhỏ càng tốt • Thước đo độ tương đồng nội cụm
            </p>
          </div>

          <div style={{ background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--border-card)', padding: '1.25rem', borderRadius: '12px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>CALINSKI-HARABASZ</span>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#a855f7', marginTop: '4px' }}>
              {clustering.calinski_harabasz !== undefined ? clustering.calinski_harabasz.toLocaleString() : 'N/A'}
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>
              Variance Ratio Criterion • Giá trị cao khẳng định cụm chặt chẽ
            </p>
          </div>
        </div>
      </div>

      {/* 2. Phần so sánh hiệu năng Recommenders */}
      <div className="glass-card" style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Award size={22} color="var(--primary-light)" />
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>So Sánh 6 Thuật Toán Gợi Ý Sản Phẩm</h2>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Đánh giá theo Top-K trên 10.000 khách lấy mẫu có mua hàng trong tập Test
              </p>
            </div>
          </div>

          {/* Nút chọn K = 5, 10, 20 */}
          <div style={{ display: 'flex', gap: '0.5rem', background: 'rgba(0,0,0,0.3)', padding: '4px', borderRadius: '8px', border: '1px solid var(--border-card)' }}>
            {[5, 10, 20].map((k) => (
              <button
                key={k}
                type="button"
                className={`btn ${selectedK === k ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '0.4rem 0.9rem', fontSize: '0.85rem' }}
                onClick={() => setSelectedK(k)}
              >
                K = {k}
              </button>
            ))}
          </div>
        </div>

        {/* Bảng so sánh chỉ số */}
        <div className="table-wrapper" style={{ marginBottom: '2rem' }}>
          <table className="modern-table">
            <thead>
              <tr>
                <th>Thuật Toán</th>
                <th>Precision@{selectedK}</th>
                <th>Recall@{selectedK}</th>
                <th>MAP@{selectedK}</th>
                <th>NDCG@{selectedK}</th>
                <th>Coverage@{selectedK}</th>
                <th>Đánh Giá Đặc Trưng</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(recommenders).map(([key, scores]) => {
                const isHybrid = key === 'hybrid';
                const p = scores[`precision@${selectedK}`] || 0;
                const r = scores[`recall@${selectedK}`] || 0;
                const m = scores[`map@${selectedK}`] || 0;
                const n = scores[`ndcg@${selectedK}`] || 0;
                const cov = scores[`coverage@${selectedK}`] || 0;

                return (
                  <tr
                    key={key}
                    style={{
                      background: isHybrid ? 'rgba(99, 102, 241, 0.08)' : undefined,
                      borderLeft: isHybrid ? '3px solid var(--primary)' : '3px solid transparent',
                    }}
                  >
                    <td>
                      <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <span>{MODEL_LABELS[key] || key}</span>
                        {isHybrid && <span className="badge badge-loyal" style={{ fontSize: '0.7rem' }}>Tốt nhất</span>}
                      </div>
                    </td>
                    <td style={{ fontWeight: p === maxValues.precision ? 800 : 500, color: p === maxValues.precision ? '#34d399' : undefined }}>
                      {(p * 100).toFixed(2)}% {p === maxValues.precision && '★'}
                    </td>
                    <td style={{ fontWeight: r === maxValues.recall ? 800 : 500, color: r === maxValues.recall ? '#34d399' : undefined }}>
                      {(r * 100).toFixed(2)}% {r === maxValues.recall && '★'}
                    </td>
                    <td style={{ fontWeight: m === maxValues.map ? 800 : 500, color: m === maxValues.map ? '#34d399' : undefined }}>
                      {(m * 100).toFixed(2)}% {m === maxValues.map && '★'}
                    </td>
                    <td style={{ fontWeight: n === maxValues.ndcg ? 800 : 500, color: n === maxValues.ndcg ? '#34d399' : undefined }}>
                      {(n * 100).toFixed(2)}% {n === maxValues.ndcg && '★'}
                    </td>
                    <td style={{ fontWeight: cov === maxValues.coverage ? 800 : 500, color: cov === maxValues.coverage ? '#38bdf8' : undefined }}>
                      {(cov * 100).toFixed(2)}% {cov === maxValues.coverage && '★'}
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {key === 'hybrid' && 'Cân bằng tốt nhất: MAP & NDCG cao nhất, Coverage rộng hơn ALS.'}
                      {key === 'item_cf' && 'Gợi ý gần như toàn bộ danh mục nhưng kém chính xác hơn ALS.'}
                      {key === 'als' && 'Precision & Recall cao nhất nhờ học sở thích ẩn.'}
                      {key === 'content' && 'Bao phủ rộng nhưng chỉ dựa vào mô tả nên kém chính xác.'}
                      {key === 'cluster_popularity' && 'Bán chạy theo phân khúc RFM, gần như Popularity.'}
                      {key === 'popularity' && 'Baseline cho khách cold-start.'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Biểu đồ Recharts so sánh trực quan */}
        <div>
          <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <BarChart2 size={18} color="var(--primary-light)" />
            <span>Biểu Đồ So Sánh Precision, Recall, NDCG & MAP (%) tại K = {selectedK}</span>
          </h4>

          <div style={{ width: '100%', height: 350 }}>
            <ResponsiveContainer>
              <BarChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="model" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <YAxis unit="%" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    background: '#0f172a',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '8px',
                    fontSize: '0.85rem'
                  }}
                  formatter={(val) => [`${val}%`, '']}
                />
                <Legend wrapperStyle={{ paddingTop: '10px' }} />
                <Bar dataKey="precision" name="Precision" fill="#818cf8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="recall" name="Recall" fill="#34d399" radius={[4, 4, 0, 0]} />
                <Bar dataKey="ndcg" name="NDCG" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="map" name="MAP" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
} 