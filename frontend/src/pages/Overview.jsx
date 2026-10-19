import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import ClusterScatter, { CLUSTER_COLORS, getClusterColor } from '../components/ClusterScatter';
import LoadingSpinner from '../components/LoadingSpinner';
import StatCard from '../components/StatCard';
import ProductCard from '../components/ProductCard';
import {
  Users,
  PieChart,
  AlertTriangle,
  Crown,
  Sparkles,
  ShoppingBag,
  X,
  TrendingUp,
  Award,
  ArrowRight,
  ShieldAlert,
  Flame,
  UserCheck
} from 'lucide-react';

export default function Overview() {
  const navigate = useNavigate();
  const [clusters, setClusters] = useState([]);
  const [points, setPoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Chi tiết cụm đã chọn (kèm top 10 sản phẩm)
  const [selectedClusterDetail, setSelectedClusterDetail] = useState(null);
  const [loadingClusterDetail, setLoadingClusterDetail] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const [clustersData, pointsData] = await Promise.all([
          api.getClusters(),
          api.getClusterPoints(),
        ]);
        setClusters(clustersData);
        setPoints(pointsData);
      } catch (err) {
        setError(err.message || 'Không thể tải dữ liệu phân cụm.');
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const handleViewClusterDetail = async (clusterId) => {
    try {
      setLoadingClusterDetail(true);
      const detail = await api.getCluster(clusterId);
      setSelectedClusterDetail(detail);
    } catch (err) {
      alert(`Lỗi khi lấy chi tiết cụm: ${err.message}`);
    } finally {
      setLoadingClusterDetail(false);
    }
  };

  if (loading) return <LoadingSpinner text="Đang phân tích đặc trưng RFM và phân cụm K-Means..." />;
  if (error) return <div className="error-banner"><AlertTriangle size={20} /> {error}</div>;

  const totalCustomers = clusters.reduce((acc, c) => acc + c.size, 0);
  const vipCluster = clusters.find((c) => c.name.includes('VIP')) || clusters[1];
  const atRiskCluster = clusters.find((c) => c.name.includes('nguy cơ') || c.name.includes('bỏ')) || clusters[0];
  const loyalCluster = clusters.find((c) => c.name.includes('trung thành')) || clusters[2];

  const getBadgeClass = (name) => {
    if (!name) return 'badge-neutral';
    if (name.includes('nguy cơ') || name.includes('bỏ')) return 'badge-risk';
    if (name.includes('VIP')) return 'badge-vip';
    if (name.includes('trung thành')) return 'badge-loyal';
    if (name.includes('mới')) return 'badge-new';
    return 'badge-neutral';
  };

  const getClusterIcon = (name) => {
    if (name.includes('VIP')) return <Crown size={20} color="#10b981" />;
    if (name.includes('trung thành')) return <Award size={20} color="#818cf8" />;
    if (name.includes('mới')) return <Sparkles size={20} color="#06b6d4" />;
    if (name.includes('nguy cơ') || name.includes('bỏ')) return <ShieldAlert size={20} color="#f43f5e" />;
    return <Users size={20} color="#94a3b8" />;
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-badge">
          <Sparkles size={14} />
          <span>Big Data Analytics • RFM Segmentation</span>
        </div>
        <h1 className="page-title">Phân Cụm Khách Hàng & Chiến Lược Tiếp Thị</h1>
        <p className="page-desc">
          Ứng dụng học máy K-Means trên không gian đặc trưng RFM (Recency, Frequency, Monetary) kết hợp chuẩn hóa phi tuyến log1p, giúp định vị chính xác chân dung và xây dựng chiến dịch cá nhân hóa.
        </p>
      </div>

      {/* 4 Thẻ thống kê tổng quan */}
      <div className="stat-grid">
        <StatCard
          title="Tổng Khách Hàng (Train)"
          value={totalCustomers.toLocaleString()}
          icon={<Users size={26} />}
          color="#818cf8"
          subtitle="Dữ liệu làm sạch Online Retail II"
        />
        <StatCard
          title="Khách Hàng VIP"
          value={`${vipCluster ? vipCluster.size.toLocaleString() : 0}`}
          icon={<Crown size={26} />}
          color="#10b981"
          subtitle={`Chi tiêu TB: £${vipCluster ? Math.round(vipCluster.mean_monetary).toLocaleString() : 0} / khách`}
        />
        <StatCard
          title="Khách Trung Thành"
          value={`${loyalCluster ? loyalCluster.size.toLocaleString() : 0}`}
          icon={<Flame size={26} />}
          color="#06b6d4"
          subtitle={`Tần suất: ${loyalCluster ? loyalCluster.mean_frequency : 0} đơn / khách`}
        />
        <StatCard
          title="Nguy Cơ Rời Bỏ (At-Risk)"
          value={`${atRiskCluster ? atRiskCluster.size.toLocaleString() : 0}`}
          icon={<ShieldAlert size={26} />}
          color="#f43f5e"
          subtitle={`Chưa mua lại TB: ${atRiskCluster ? Math.round(atRiskCluster.mean_recency) : 0} ngày`}
        />
      </div>

      {/* 4 Thẻ hồ sơ phân cụm dạng Grid */}
      <div style={{ marginBottom: '2.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff' }}>
              Chân Dung 4 Phân Khúc Khách Hàng
            </h2>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              Đặc điểm hành vi mua sắm và đề xuất chiến dịch Marketing riêng biệt
            </p>
          </div>
        </div>

        <div className="cluster-card-grid">
          {clusters.map((c) => {
            const color = CLUSTER_COLORS[c.id] || '#94a3b8';
            return (
              <div
                key={c.id}
                className="cluster-card"
                style={{
                  borderTop: `3px solid ${color}`,
                  background: `linear-gradient(180deg, ${color}08 0%, var(--bg-card) 40%)`
                }}
              >
                <div className="cluster-card-header">
                  <div className="cluster-name-title">
                    {getClusterIcon(c.name)}
                    <span>{c.name}</span>
                  </div>
                  <span className={`badge ${getBadgeClass(c.name)}`}>
                    {c.pct}% quy mô
                  </span>
                </div>

                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1rem', minHeight: '40px' }}>
                  {c.description}
                </div>

                <div className="cluster-metrics-row">
                  <div className="cluster-metric-item">
                    <div className="cluster-metric-label">Recency</div>
                    <div className="cluster-metric-val">{Math.round(c.mean_recency)} <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>ngày</span></div>
                  </div>
                  <div className="cluster-metric-item">
                    <div className="cluster-metric-label">Frequency</div>
                    <div className="cluster-metric-val">{c.mean_frequency} <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>đơn</span></div>
                  </div>
                  <div className="cluster-metric-item">
                    <div className="cluster-metric-label">Monetary</div>
                    <div className="cluster-metric-val" style={{ color: '#10b981' }}>£{Math.round(c.mean_monetary).toLocaleString()}</div>
                  </div>
                </div>

                <div className="cluster-campaign-box">
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: color, textTransform: 'uppercase', marginBottom: '4px' }}>
                    Chiến dịch Marketing:
                  </div>
                  <div style={{ color: 'var(--text-main)', lineHeight: 1.4 }}>
                    {c.campaign}
                  </div>
                </div>

                <div style={{ marginTop: '1.25rem', display: 'flex', gap: '0.6rem' }}>
                  <button
                    className="btn btn-secondary"
                    style={{ flex: 1, padding: '0.55rem', fontSize: '0.825rem' }}
                    onClick={() => handleViewClusterDetail(c.id)}
                  >
                    <ShoppingBag size={15} />
                    <span>Top 10 Sản Phẩm</span>
                  </button>
                  <button
                    className="btn btn-primary"
                    style={{ padding: '0.55rem 0.85rem', fontSize: '0.825rem' }}
                    onClick={() => navigate('/customers')}
                    title="Xem danh sách khách hàng"
                  >
                    <Users size={15} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Biểu đồ PCA Scatter 2D cao cấp */}
      <div className="glass-card" style={{ marginBottom: '2.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h3 style={{ fontSize: '1.3rem', fontWeight: 800 }}>Không Gian Phân Cụm 2D (PCA)</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              Phân bố {points.length} khách hàng mẫu từ ma trận đặc trưng RFM đã giảm chiều bằng PCA.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
            {clusters.map((c) => (
              <span key={c.id} className={`badge ${getBadgeClass(c.name)}`}>
                ● {c.name} ({c.pct}%)
              </span>
            ))}
          </div>
        </div>

        <ClusterScatter
          points={points}
          clusterProfiles={clusters}
          onSelectCustomer={(cid) => navigate(`/recommend?customer_id=${cid}`)}
        />
      </div>

      {/* Bảng hồ sơ chi tiết các cụm */}
      <div className="glass-card">
        <h3 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '0.5rem' }}>
          Bảng So Sánh Chỉ Số RFM Giữa Các Phân Khúc
        </h3>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
          Dữ liệu định lượng phục vụ báo cáo đồ án Big Data
        </p>

        <div className="table-wrapper">
          <table className="modern-table">
            <thead>
              <tr>
                <th>Cụm Phân Khúc</th>
                <th>Số Lượng Khách</th>
                <th>Tỷ Lệ</th>
                <th>Recency TB (Ngày)</th>
                <th>Frequency TB (Đơn)</th>
                <th>Monetary TB (£)</th>
                <th>Hành Động Marketing Đề Xuất</th>
                <th>Thao Tác</th>
              </tr>
            </thead>
            <tbody>
              {clusters.map((c) => (
                <tr key={c.id}>
                  <td>
                    <span className={`badge ${getBadgeClass(c.name)}`}>
                      ● {c.name}
                    </span>
                  </td>
                  <td style={{ fontWeight: 700 }}>{c.size.toLocaleString()}</td>
                  <td style={{ fontWeight: 600 }}>{c.pct}%</td>
                  <td>{c.mean_recency}</td>
                  <td>{c.mean_frequency}</td>
                  <td style={{ color: '#10b981', fontWeight: 700 }}>
                    £{c.mean_monetary.toLocaleString()}
                  </td>
                  <td style={{ maxWidth: '340px', fontSize: '0.85rem' }}>
                    <div style={{ color: 'var(--text-main)', fontWeight: 600, marginBottom: '2px' }}>{c.campaign}</div>
                    <div style={{ color: 'var(--text-dim)', fontSize: '0.78rem' }}>{c.description}</div>
                  </td>
                  <td>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '0.45rem 0.85rem', fontSize: '0.8rem' }}
                      onClick={() => handleViewClusterDetail(c.id)}
                    >
                      <ShoppingBag size={14} />
                      Top SP
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal Popup xem Top 10 sản phẩm bán chạy nhất trong cụm */}
      {selectedClusterDetail && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.8)',
            backdropFilter: 'blur(10px)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem',
          }}
          onClick={() => setSelectedClusterDetail(null)}
        >
          <div
            className="glass-card"
            style={{
              maxWidth: '1000px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              background: '#0d1322',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              boxShadow: '0 25px 60px rgba(0,0,0,0.7)'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
              <div>
                <span className={`badge ${getBadgeClass(selectedClusterDetail.cluster.name)}`} style={{ marginBottom: '8px' }}>
                  {selectedClusterDetail.cluster.name}
                </span>
                <h3 style={{ fontSize: '1.45rem', fontWeight: 800 }}>
                  Top 10 Sản Phẩm Bán Chạy Nhất Phân Khúc Này
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
                  {selectedClusterDetail.cluster.campaign}
                </p>
              </div>
              <button
                className="btn btn-secondary"
                style={{ padding: '0.5rem', borderRadius: '50%' }}
                onClick={() => setSelectedClusterDetail(null)}
              >
                <X size={20} />
              </button>
            </div>

            <div className="product-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(185px, 1fr))' }}>
              {selectedClusterDetail.top_products.map((p, idx) => (
                <ProductCard
                  key={p.stockcode}
                  stockcode={p.stockcode}
                  description={p.description}
                  score={p.score}
                  image={p.image}
                  rank={idx + 1}
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
