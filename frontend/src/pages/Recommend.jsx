import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api';
import ProductCard from '../components/ProductCard';
import LoadingSpinner from '../components/LoadingSpinner';
import {
  Sparkles,
  AlertTriangle,
  ArrowRightLeft,
  Sliders,
  User,
  Info,
  CheckCircle2,
  Layers,
  Crown,
  Award,
  ShieldAlert
} from 'lucide-react';

const MODEL_OPTIONS = [
  { id: 'hybrid', name: 'Hybrid (Lai ghép: ALS + Content + Cluster-Pop)', desc: 'Mô hình kết hợp tối ưu độ chính xác và độ bao phủ' },
  { id: 'als', name: 'ALS (Matrix Factorization)', desc: 'Phân rã ma trận với thư viện Implicit' },
  { id: 'item_cf', name: 'Item-CF (Lọc cộng tác theo SP)', desc: 'Cosine similarity giữa vector hành vi mua sản phẩm' },
  { id: 'content', name: 'Content-Based (Dựa trên mô tả TF-IDF)', desc: 'Độ tương đồng ngữ nghĩa nội dung sản phẩm' },
  { id: 'cluster_popularity', name: 'Cluster Popularity (Bán chạy theo cụm)', desc: 'Sản phẩm phổ biến nhất trong phân khúc của khách' },
  { id: 'popularity', name: 'Popularity (Bán chạy toàn hệ thống)', desc: 'Dành cho khách hàng mới (Cold-Start baseline)' },
];

export default function Recommend() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialCid = searchParams.get('customer_id') || '12347';

  const [customerId, setCustomerId] = useState(initialCid);
  const [topK, setTopK] = useState(10);
  const [modelA, setModelA] = useState('hybrid');
  const [modelB, setModelB] = useState('item_cf');
  const [isCompareMode, setIsCompareMode] = useState(false);

  const [resultsA, setResultsA] = useState(null);
  const [resultsB, setResultsB] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Danh sách khách hàng mẫu đại diện cho đủ 4 cụm + cold-start
  const sampleCustomers = [
    { id: 12352, label: 'Khách #12352', tag: 'Khách VIP', badgeClass: 'badge-vip' },
    { id: 12347, label: 'Khách #12347', tag: 'Trung thành', badgeClass: 'badge-loyal' },
    { id: 12348, label: 'Khách #12348', tag: 'Khách mới', badgeClass: 'badge-new' },
    { id: 12350, label: 'Khách #12350', tag: 'Nguy cơ rời bỏ', badgeClass: 'badge-risk' },
    { id: 999999, label: 'Khách #999999', tag: 'Cold-Start', badgeClass: 'badge-neutral' },
  ];

  const fetchRecommendations = async (cid, k, mA, mB, compare) => {
    try {
      setLoading(true);
      setError(null);

      const parsedCid = parseInt(cid, 10);
      if (isNaN(parsedCid)) {
        throw new Error('Mã khách hàng phải là số nguyên hợp lệ!');
      }

      if (compare) {
        const [resA, resB] = await Promise.all([
          api.getRecommendations(parsedCid, k, mA),
          api.getRecommendations(parsedCid, k, mB),
        ]);
        setResultsA(resA);
        setResultsB(resB);
      } else {
        const resA = await api.getRecommendations(parsedCid, k, mA);
        setResultsA(resA);
        setResultsB(null);
      }
    } catch (err) {
      setError(err.message || 'Không thể lấy dữ liệu gợi ý sản phẩm.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (customerId) {
      fetchRecommendations(customerId, topK, modelA, modelB, isCompareMode);
    }
  }, [topK, modelA, modelB, isCompareMode]);

  const handleSubmit = (e) => {
    e.preventDefault();
    setSearchParams({ customer_id: customerId });
    fetchRecommendations(customerId, topK, modelA, modelB, isCompareMode);
  };

  const selectSample = (cid) => {
    setCustomerId(String(cid));
    setSearchParams({ customer_id: String(cid) });
    fetchRecommendations(String(cid), topK, modelA, modelB, isCompareMode);
  };

  const getBadgeClass = (name) => {
    if (!name) return 'badge-neutral';
    if (name.includes('nguy cơ') || name.includes('bỏ')) return 'badge-risk';
    if (name.includes('VIP')) return 'badge-vip';
    if (name.includes('trung thành')) return 'badge-loyal';
    if (name.includes('mới')) return 'badge-new';
    return 'badge-neutral';
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-badge">
          <Sparkles size={14} />
          <span>Personalization Engine • Recommender Systems</span>
        </div>
        <h1 className="page-title">Gợi Ý Sản Phẩm Cá Nhân Hóa</h1>
        <p className="page-desc">
          Thử nghiệm và so sánh trực quan hiệu năng 6 thuật toán gợi ý (Popularity, Cluster-Pop, Item-CF, ALS, Content-Based, Hybrid) cho từng khách hàng cụ thể.
        </p>
      </div>

      {/* Bảng điều khiển / Bộ lọc */}
      <div className="glass-card" style={{ marginBottom: '2.2rem' }}>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '1.25rem', alignItems: 'end' }}>
            {/* Input Customer ID */}
            <div>
              <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.5rem', letterSpacing: '0.04em' }}>
                MÃ KHÁCH HÀNG (CUSTOMER ID)
              </label>
              <div className="input-group">
                <User size={18} className="input-icon" />
                <input
                  type="text"
                  className="input-field"
                  placeholder="Nhập ID (ví dụ: 12347)..."
                  value={customerId}
                  onChange={(e) => setCustomerId(e.target.value)}
                />
              </div>
            </div>

            {/* Chọn Thuật toán 1 */}
            <div>
              <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.5rem', letterSpacing: '0.04em' }}>
                {isCompareMode ? 'MÔ HÌNH A' : 'THUẬT TOÁN GỢI Ý'}
              </label>
              <select
                className="select-field"
                style={{ width: '100%' }}
                value={modelA}
                onChange={(e) => setModelA(e.target.value)}
              >
                {MODEL_OPTIONS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Chọn Thuật toán 2 (nếu bật so sánh) */}
            {isCompareMode && (
              <div>
                <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.5rem', letterSpacing: '0.04em' }}>
                  MÔ HÌNH B (SO SÁNH)
                </label>
                <select
                  className="select-field"
                  style={{ width: '100%' }}
                  value={modelB}
                  onChange={(e) => setModelB(e.target.value)}
                >
                  {MODEL_OPTIONS.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Chọn Top K */}
            <div style={{ maxWidth: '140px' }}>
              <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.5rem', letterSpacing: '0.04em' }}>
                SỐ LƯỢNG (TOP-K)
              </label>
              <select
                className="select-field"
                style={{ width: '100%' }}
                value={topK}
                onChange={(e) => setTopK(parseInt(e.target.value, 10))}
              >
                <option value={5}>Top 5</option>
                <option value={10}>Top 10</option>
                <option value={15}>Top 15</option>
                <option value={20}>Top 20</option>
              </select>
            </div>

            {/* Nút hành động */}
            <div style={{ display: 'flex', gap: '0.6rem' }}>
              <button type="submit" className="btn btn-primary" style={{ flex: 1 }}>
                <Sparkles size={16} />
                <span>Gợi Ý</span>
              </button>

              <button
                type="button"
                className={`btn ${isCompareMode ? 'btn-active' : 'btn-secondary'}`}
                onClick={() => setIsCompareMode(!isCompareMode)}
                title="Bật/Tắt chế độ so sánh hai mô hình song song"
              >
                <ArrowRightLeft size={16} />
                <span>{isCompareMode ? 'Tắt' : 'So Sánh'}</span>
              </button>
            </div>
          </div>
        </form>

        {/* Khách hàng mẫu bấm nhanh - Đầy đủ 4 cụm */}
        <div style={{ marginTop: '1.25rem', paddingTop: '1.1rem', borderTop: '1px solid var(--border-card)', display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.825rem', color: 'var(--text-dim)', fontWeight: 600 }}>Thử nhanh khách mẫu:</span>
          {sampleCustomers.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`badge ${s.badgeClass}`}
              style={{
                cursor: 'pointer',
                border: customerId === String(s.id) ? '2px solid #fff' : undefined,
                boxShadow: customerId === String(s.id) ? '0 0 10px rgba(255,255,255,0.4)' : 'none',
                padding: '0.35rem 0.85rem'
              }}
              onClick={() => selectSample(s.id)}
            >
              <strong>{s.label}</strong> ({s.tag})
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={20} />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <LoadingSpinner text="Đang tính toán ma trận tương tác và tạo danh sách gợi ý..." />
      ) : resultsA ? (
        <div>
          {/* Thông tin ngữ cảnh khách hàng */}
          <div
            className="glass-card"
            style={{
              marginBottom: '1.75rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '1rem',
              background: resultsA.cold_start ? 'rgba(245, 158, 11, 0.08)' : 'rgba(99, 102, 241, 0.08)',
              borderColor: resultsA.cold_start ? 'rgba(245, 158, 11, 0.35)' : 'rgba(99, 102, 241, 0.3)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '1.1rem' }}>
              <div
                style={{
                  width: '46px',
                  height: '46px',
                  borderRadius: '12px',
                  background: resultsA.cold_start ? 'rgba(245, 158, 11, 0.2)' : 'rgba(99, 102, 241, 0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: resultsA.cold_start ? '#fbbf24' : '#818cf8',
                }}
              >
                {resultsA.cold_start ? <Info size={24} /> : <CheckCircle2 size={24} />}
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 800 }}>
                    Khách Hàng #{resultsA.customer_id}
                  </h3>
                  {resultsA.cluster ? (
                    <span className={`badge ${getBadgeClass(resultsA.cluster.name)}`}>
                      ● {resultsA.cluster.name}
                    </span>
                  ) : (
                    <span className="badge badge-risk">
                      ● Khách Hàng Mới (Chưa có lịch sử giao dịch)
                    </span>
                  )}
                </div>
                <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {resultsA.cold_start
                    ? 'Chưa từng mua hàng trong tập Train (Cold-Start) -> Tự động chuyển tiếp sang sản phẩm phổ biến toàn cầu (Popularity).'
                    : `Thuộc phân khúc: ${resultsA.cluster?.name}. Các mô hình khai phá hành vi mua sắm để sinh điểm tương thích.`}
                </p>
              </div>
            </div>

            <div style={{ fontSize: '0.88rem', color: 'var(--text-muted)' }}>
              Hiển thị: <strong style={{ color: 'var(--text-main)', fontSize: '1.05rem' }}>Top {topK}</strong> sản phẩm gợi ý
            </div>
          </div>

          {/* Lưới sản phẩm: 1 Mô hình hoặc 2 Mô hình so sánh song song */}
          {!isCompareMode ? (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <Layers size={20} color="var(--primary-light)" />
                  <span>Kết Quả: {MODEL_OPTIONS.find((m) => m.id === modelA)?.name}</span>
                </h3>
              </div>

              <div className="product-grid">
                {resultsA.items.map((item, idx) => (
                  <ProductCard
                    key={item.stockcode}
                    stockcode={item.stockcode}
                    description={item.description}
                    score={item.score}
                    image={item.image}
                    rank={idx + 1}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.75rem' }}>
              {/* Cột Mô hình A */}
              <div className="glass-card">
                <div style={{ marginBottom: '1.25rem', borderBottom: '1px solid var(--border-card)', paddingBottom: '0.85rem' }}>
                  <span className="badge badge-loyal" style={{ marginBottom: '6px' }}>MÔ HÌNH A</span>
                  <h4 style={{ fontSize: '1.2rem', fontWeight: 800 }}>
                    {MODEL_OPTIONS.find((m) => m.id === modelA)?.name}
                  </h4>
                </div>

                <div className="product-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))' }}>
                  {resultsA.items.map((item, idx) => (
                    <ProductCard
                      key={`a-${item.stockcode}`}
                      stockcode={item.stockcode}
                      description={item.description}
                      score={item.score}
                      image={item.image}
                      rank={idx + 1}
                    />
                  ))}
                </div>
              </div>

              {/* Cột Mô hình B */}
              <div className="glass-card">
                <div style={{ marginBottom: '1.25rem', borderBottom: '1px solid var(--border-card)', paddingBottom: '0.85rem' }}>
                  <span className="badge badge-new" style={{ marginBottom: '6px' }}>MÔ HÌNH B</span>
                  <h4 style={{ fontSize: '1.2rem', fontWeight: 800 }}>
                    {MODEL_OPTIONS.find((m) => m.id === modelB)?.name}
                  </h4>
                </div>

                {resultsB && (
                  <div className="product-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))' }}>
                    {resultsB.items.map((item, idx) => (
                      <ProductCard
                        key={item.stockcode}
                        stockcode={item.stockcode}
                        description={item.description}
                        score={item.score}
                        image={item.image}
                        rank={idx + 1}
                        reason={item.reason}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
