import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Overview from './pages/Overview';
import Customers from './pages/Customers';
import Recommend from './pages/Recommend';
import Metrics from './pages/Metrics';

export default function App() {
  return (
    <div className="app-container">
      <Navbar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/customers" element={<Customers />} />
          <Route path="/recommend" element={<Recommend />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <footer
        style={{
          borderTop: '1px solid var(--border-card)',
          padding: '1.5rem',
          textAlign: 'center',
          color: 'var(--text-dim)',
          fontSize: '0.85rem',
        }}
      >
        <p>
          Đồ án Big Data: Personalized Marketing – Phân Cụm Khách Hàng (RFM + K-Means) & Gợi Ý Sản Phẩm
        </p>
      </footer>
    </div>
  );
}
