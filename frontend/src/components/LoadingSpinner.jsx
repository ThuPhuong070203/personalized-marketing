import React from 'react';

export default function LoadingSpinner({ text = 'Đang tải dữ liệu...' }) {
  return (
    <div className="spinner-container">
      <div className="spinner" />
      <p style={{ fontSize: '0.95rem' }}>{text}</p>
    </div>
  );
}
