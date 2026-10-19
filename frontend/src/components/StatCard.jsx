import React from 'react';

export default function StatCard({ title, value, icon, color = 'var(--primary)', subtitle }) {
  return (
    <div className="stat-card">
      <div
        className="stat-icon"
        style={{
          background: `rgba(${color.startsWith('#') ? hexToRgb(color) : '99, 102, 241'}, 0.15)`,
          color: color
        }}
      >
        {icon}
      </div>
      <div className="stat-info">
        <h4>{title}</h4>
        <p>{value}</p>
        {subtitle && (
          <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
            {subtitle}
          </span>
        )}
      </div>
    </div>
  );
}

function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`
    : '99, 102, 241';
}
