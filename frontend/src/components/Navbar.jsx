import React from 'react';
import { NavLink } from 'react-router-dom';
import { PieChart, Users, Sparkles, BarChart3, ShoppingBag } from 'lucide-react';

export default function Navbar() {
  return (
    <header className="navbar">
      <div className="nav-inner">
        <NavLink to="/" className="nav-brand">
          <div className="brand-icon">
            <Sparkles size={20} />
          </div>
          <div>
            <span>Personalized</span>
            <span style={{ color: 'var(--primary-light)', marginLeft: '4px' }}>Marketing</span>
          </div>
        </NavLink>

        <nav className="nav-links">
          <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} end>
            <PieChart size={18} />
            <span>Phân Cụm</span>
          </NavLink>
          <NavLink to="/customers" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Users size={18} />
            <span>Khách Hàng</span>
          </NavLink>
          <NavLink to="/recommend" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <ShoppingBag size={18} />
            <span>Gợi Ý Sản Phẩm</span>
          </NavLink>
          <NavLink to="/metrics" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <BarChart3 size={18} />
            <span>Đánh Giá Mô Hình</span>
          </NavLink>
        </nav>
      </div>
    </header>
  );
}
