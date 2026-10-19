import React, { useState } from 'react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  CartesianGrid
} from 'recharts';

// Bảng màu chuẩn đồng bộ tuyệt đối với cụm:
// id 0: Khách có nguy cơ rời bỏ -> Đỏ hồng (#f43f5e)
// id 1: Khách VIP -> Xanh ngọc lục bảo (#10b981)
// id 2: Khách trung thành -> Tím chàm (#818cf8)
// id 3: Khách mới -> Xanh Cyan (#06b6d4)
export const CLUSTER_COLORS = {
  0: '#f43f5e', // Khách có nguy cơ rời bỏ
  1: '#10b981', // Khách VIP
  2: '#818cf8', // Khách trung thành
  3: '#06b6d4', // Khách mới
};

export function getClusterColor(clusterIdOrName, clusterProfiles = []) {
  if (typeof clusterIdOrName === 'number' && CLUSTER_COLORS[clusterIdOrName]) {
    return CLUSTER_COLORS[clusterIdOrName];
  }
  const name = String(clusterIdOrName || '');
  if (name.includes('nguy cơ') || name.includes('bỏ')) return '#f43f5e';
  if (name.includes('VIP')) return '#10b981';
  if (name.includes('trung thành')) return '#818cf8';
  if (name.includes('mới')) return '#06b6d4';
  return '#94a3b8';
}

export default function ClusterScatter({ points, clusterProfiles, onSelectCustomer }) {
  const [activeFilter, setActiveFilter] = useState('all'); // 'all' hoặc clusterId (0, 1, 2, 3)

  // Map tên cụm theo id
  const nameMap = {};
  if (clusterProfiles) {
    clusterProfiles.forEach((p) => {
      nameMap[p.id] = p.name;
    });
  }

  // Lọc điểm hiển thị theo cụm
  const filteredPoints = activeFilter === 'all'
    ? points
    : points.filter((p) => p.cluster === activeFilter);

  // Custom Tooltip trực quan, bắt mắt
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const cId = data.cluster;
      const cName = nameMap[cId] || `Cụm ${cId}`;
      const color = CLUSTER_COLORS[cId] || '#94a3b8';

      return (
        <div
          style={{
            background: 'rgba(11, 15, 25, 0.95)',
            border: `2px solid ${color}`,
            borderRadius: '12px',
            padding: '12px 16px',
            boxShadow: `0 12px 30px rgba(0,0,0,0.6), 0 0 15px ${color}40`,
            backdropFilter: 'blur(12px)',
            fontSize: '0.88rem'
          }}
        >
          <div style={{ fontWeight: 800, color: '#fff', fontSize: '1rem', marginBottom: '6px' }}>
            Khách hàng #{data.customer_id}
          </div>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              color: color,
              fontWeight: 700,
              marginBottom: '6px',
              padding: '2px 8px',
              borderRadius: '6px',
              background: `${color}15`,
              border: `1px solid ${color}35`
            }}
          >
            ● {cName}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '4px' }}>
            Tọa độ PCA 2D: (X: {data.x.toFixed(2)}, Y: {data.y.toFixed(2)})
          </div>
          {onSelectCustomer && (
            <div style={{ fontSize: '0.8rem', color: 'var(--primary-light)', marginTop: '8px', fontWeight: 700 }}>
              ➜ Nhấp để xem hồ sơ và gợi ý sản phẩm
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div>
      {/* Bộ lọc cụm trực quan dạng tab */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1.25rem' }}>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)', fontWeight: 600 }}>
          LỌC NHÓM TRÊN BIỂU ĐỒ:
        </span>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`btn ${activeFilter === 'all' ? 'btn-active' : 'btn-secondary'}`}
            style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem' }}
            onClick={() => setActiveFilter('all')}
          >
            Tất cả ({points.length})
          </button>
          {clusterProfiles && clusterProfiles.map((c) => {
            const isActive = activeFilter === c.id;
            const color = CLUSTER_COLORS[c.id] || '#94a3b8';
            return (
              <button
                key={c.id}
                type="button"
                className="btn"
                style={{
                  padding: '0.4rem 0.85rem',
                  fontSize: '0.8rem',
                  background: isActive ? `${color}25` : 'rgba(255, 255, 255, 0.05)',
                  border: `1px solid ${isActive ? color : 'var(--border-card)'}`,
                  color: isActive ? '#fff' : 'var(--text-muted)',
                  fontWeight: isActive ? 700 : 500,
                  boxShadow: isActive ? `0 0 12px ${color}40` : 'none'
                }}
                onClick={() => setActiveFilter(c.id)}
              >
                <span style={{ color: color }}>●</span> {c.name}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ width: '100%', height: 440 }}>
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 20, right: 25, bottom: 25, left: 15 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.6} />
            <XAxis
              type="number"
              dataKey="x"
              name="PCA 1 (Sức mua & Tần suất)"
              tick={{ fill: '#64748b', fontSize: 12 }}
              axisLine={{ stroke: '#334155' }}
              tickLine={{ stroke: '#334155' }}
              label={{ value: 'PCA 1 (Sức mua & Giá trị đơn hàng)', position: 'insideBottom', offset: -12, fill: '#94a3b8', fontSize: 12 }}
            />
            <YAxis
              type="number"
              dataKey="y"
              name="PCA 2 (Thời gian gần đây)"
              tick={{ fill: '#64748b', fontSize: 12 }}
              axisLine={{ stroke: '#334155' }}
              tickLine={{ stroke: '#334155' }}
              label={{ value: 'PCA 2 (Recency)', angle: -90, position: 'insideLeft', offset: -4, fill: '#94a3b8', fontSize: 12 }}
            />
            <ZAxis range={[32, 32]} />
            <Tooltip content={<CustomTooltip />} />
            <Scatter
              name="Khách hàng"
              data={filteredPoints}
              cursor={onSelectCustomer ? 'pointer' : 'default'}
              onClick={(e) => onSelectCustomer && onSelectCustomer(e.customer_id)}
            >
              {filteredPoints.map((entry, index) => {
                const color = CLUSTER_COLORS[entry.cluster] || '#94a3b8';
                return (
                  <Cell
                    key={`cell-${index}`}
                    fill={color}
                    fillOpacity={0.82}
                    stroke={color}
                    strokeWidth={0.5}
                  />
                );
              })}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
