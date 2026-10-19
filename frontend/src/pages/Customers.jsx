import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, getImageUrl } from '../api';
import LoadingSpinner from '../components/LoadingSpinner';
import { Search, Users, AlertTriangle, ArrowRight, Clock, ShoppingCart, DollarSign, ChevronRight } from 'lucide-react';

export default function Customers() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Khách hàng đang được chọn xem chi tiết
  const [selectedCustomerId, setSelectedCustomerId] = useState(null);
  const [customerDetail, setCustomerDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Load danh sách khách hàng (có debounce cho ô tìm kiếm)
  useEffect(() => {
    const delayDebounce = setTimeout(async () => {
      try {
        setLoading(true);
        const data = await api.getCustomers(searchTerm, 50);
        setCustomers(data);
        // Tự động chọn khách hàng đầu tiên nếu chưa chọn ai
        if (data.length > 0 && !selectedCustomerId) {
          loadCustomerDetail(data[0].customer_id);
        }
      } catch (err) {
        setError(err.message || 'Không thể tải danh sách khách hàng');
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(delayDebounce);
  }, [searchTerm]);

  const loadCustomerDetail = async (cid) => {
    try {
      setSelectedCustomerId(cid);
      setDetailLoading(true);
      const detail = await api.getCustomer(cid);
      setCustomerDetail(detail);
    } catch (err) {
      console.error(err);
    } finally {
      setDetailLoading(false);
    }
  };

  const getBadgeClass = (name) => {
    if (!name) return 'badge-neutral';
    if (name.includes('VIP')) return 'badge-vip';
    if (name.includes('trung thành')) return 'badge-loyal';
    if (name.includes('mới')) return 'badge-new';
    if (name.includes('nguy cơ') || name.includes('bỏ')) return 'badge-risk';
    return 'badge-neutral';
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Quản Lý & Phân Tích Khách Hàng</h1>
        <p className="page-desc">
          Tra cứu thông tin hồ sơ RFM, phân nhóm khách hàng và lịch sử các mặt hàng đã mua sắm trong tập dữ liệu.
        </p>
      </div>

      {/* Thanh tìm kiếm */}
      <div style={{ marginBottom: '1.5rem', maxWidth: '480px' }}>
        <div className="input-group">
          <Search size={18} className="input-icon" />
          <input
            type="text"
            className="input-field"
            placeholder="Tìm theo Mã Khách Hàng (Customer ID)..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {error && <div className="error-banner"><AlertTriangle size={20} /> {error}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: '1.5rem' }}>
        {/* Bảng danh sách khách hàng */}
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Users size={18} color="var(--primary-light)" />
              Danh Sách Khách Hàng ({customers.length})
            </h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Tối đa 50 kết quả</span>
          </div>

          {loading ? (
            <LoadingSpinner text="Đang tìm kiếm..." />
          ) : customers.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
              Không tìm thấy khách hàng nào khớp với từ khóa "{searchTerm}".
            </div>
          ) : (
            <div className="table-wrapper" style={{ maxHeight: '600px', overflowY: 'auto' }}>
              <table className="modern-table">
                <thead>
                  <tr>
                    <th>Mã KH</th>
                    <th>Nhóm Cụm</th>
                    <th>Tổng Chi Tiêu</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map((c) => {
                    const isSelected = c.customer_id === selectedCustomerId;
                    return (
                      <tr
                        key={c.customer_id}
                        onClick={() => loadCustomerDetail(c.customer_id)}
                        style={{
                          background: isSelected ? 'rgba(99, 102, 241, 0.15)' : undefined,
                          borderLeft: isSelected ? '3px solid var(--primary)' : '3px solid transparent',
                        }}
                      >
                        <td style={{ fontWeight: 700 }}>#{c.customer_id}</td>
                        <td>
                          <span className={`badge ${getBadgeClass(c.cluster_name)}`}>
                            {c.cluster_name}
                          </span>
                        </td>
                        <td style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>
                          £{c.monetary.toLocaleString()}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <ChevronRight size={16} color={isSelected ? 'var(--primary-light)' : '#64748b'} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Khung chi tiết khách hàng và lịch sử mua gần nhất */}
        <div className="glass-card">
          {detailLoading ? (
            <LoadingSpinner text="Đang tải thông tin chi tiết khách hàng..." />
          ) : !customerDetail ? (
            <div style={{ textAlign: 'center', padding: '4rem 1rem', color: 'var(--text-muted)' }}>
              Chọn một khách hàng ở danh sách bên trái để xem hồ sơ RFM và lịch sử mua hàng.
            </div>
          ) : (
            <div>
              {/* Header chi tiết khách hàng */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '4px' }}>
                    <h2 style={{ fontSize: '1.6rem', fontWeight: 800 }}>
                      Khách Hàng #{customerDetail.customer_id}
                    </h2>
                    <span className={`badge ${getBadgeClass(customerDetail.cluster_name)}`}>
                      {customerDetail.cluster_name}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                    Cụm {customerDetail.cluster_id} • Dữ liệu ghi nhận trong tập Train
                  </p>
                </div>

                <button
                  className="btn btn-primary"
                  onClick={() => navigate(`/recommend?customer_id=${customerDetail.customer_id}`)}
                >
                  <span>Gợi Ý Sản Phẩm</span>
                  <ArrowRight size={16} />
                </button>
              </div>

              {/* 3 Thẻ RFM Mini */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.75rem' }}>
                <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-card)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.78rem', marginBottom: '4px' }}>
                    <Clock size={14} color="#38bdf8" />
                    <span>RECENCY (GẦN ĐÂY)</span>
                  </div>
                  <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>
                    {customerDetail.recency} <span style={{ fontSize: '0.8rem', fontWeight: 400, color: 'var(--text-dim)' }}>ngày</span>
                  </div>
                </div>

                <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-card)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.78rem', marginBottom: '4px' }}>
                    <ShoppingCart size={14} color="#a855f7" />
                    <span>FREQUENCY (TẦN SUẤT)</span>
                  </div>
                  <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>
                    {customerDetail.frequency} <span style={{ fontSize: '0.8rem', fontWeight: 400, color: 'var(--text-dim)' }}>đơn</span>
                  </div>
                </div>

                <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-card)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.78rem', marginBottom: '4px' }}>
                    <DollarSign size={14} color="#10b981" />
                    <span>MONETARY (GIÁ TRỊ)</span>
                  </div>
                  <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--accent-emerald)' }}>
                    £{customerDetail.monetary.toLocaleString()}
                  </div>
                </div>
              </div>

              {/* Danh sách 10 sản phẩm mua gần nhất */}
              <div>
                <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span>10 Sản Phẩm Mua Gần Nhất (Tập Train)</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 400 }}>
                    ({customerDetail.recent_purchases.length} sản phẩm)
                  </span>
                </h4>

                {customerDetail.recent_purchases.length === 0 ? (
                  <p style={{ color: 'var(--text-dim)', fontSize: '0.875rem' }}>Chưa có lịch sử giao dịch.</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', maxHeight: '340px', overflowY: 'auto' }}>
                    {customerDetail.recent_purchases.map((item, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.85rem',
                          padding: '0.6rem 0.8rem',
                          background: 'rgba(255, 255, 255, 0.02)',
                          border: '1px solid var(--border-card)',
                          borderRadius: '8px',
                        }}
                      >
                        <img
                          src={getImageUrl(item.image)}
                          alt={item.description}
                          onError={(e) => { e.target.src = getImageUrl('/images/placeholder.jpg'); }}
                          style={{ width: '42px', height: '42px', borderRadius: '6px', objectFit: 'cover' }}
                        />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: '0.85rem', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textTransform: 'capitalize' }}>
                            {item.description}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                            Mã: {item.stockcode} • Ngày: {item.invoice_date}
                          </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)' }}>
                            £{item.total_price.toFixed(2)}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                            SL: {item.quantity}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
