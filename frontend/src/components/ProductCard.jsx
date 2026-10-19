import React, { useState, useEffect } from 'react';
import { getImageUrl } from '../api';

export default function ProductCard({ stockcode, description, score, image, rank }) {
  const [imgSrc, setImgSrc] = useState(getImageUrl(image));
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    setImgSrc(getImageUrl(image));
    setHasError(false);
  }, [image]);

  const handleImageError = () => {
    if (!hasError) {
      setHasError(true);
      setImgSrc(getImageUrl('/images/placeholder.jpg'));
    }
  };

  const percentage = Math.round((score || 0) * 100);

  return (
    <div className="product-card">
      <div className="product-image-container">
        <img
          src={imgSrc}
          alt={description}
          className="product-image"
          onError={handleImageError}
          loading="lazy"
        />
        {score !== undefined && (
          <div className="product-score-badge">
            {rank !== undefined ? `#${rank} • ` : ''}{score.toFixed(2)}
          </div>
        )}
      </div>

      <div className="product-body">
        <div className="product-stockcode">Mã: {stockcode}</div>
        <h4 className="product-title" title={description}>
          {description}
        </h4>

        {score !== undefined && (
          <div className="product-footer">
            <div className="score-bar-bg" title={`Điểm độ tương đồng: ${(score * 100).toFixed(1)}%`}>
              <div
                className="score-bar-fill"
                style={{ width: `${Math.max(5, Math.min(100, percentage))}%` }}
              />
            </div>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>
              {percentage}%
            </span>
          </div>
        )}
      </div>
    </div>
  );
}