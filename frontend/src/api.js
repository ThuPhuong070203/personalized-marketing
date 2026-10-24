/**
 * API client giao tiếp với backend FastAPI
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function getImageUrl(path) {
  if (!path) return `${API_BASE_URL}/images/placeholder.jpg`;
  if (path.startsWith('http')) return path;
  if (path.startsWith('/')) return `${API_BASE_URL}${path}`;
  return `${API_BASE_URL}/${path}`;
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMsg = errorData.detail || `Lỗi HTTP ${response.status}: ${response.statusText}`;
      throw new Error(errorMsg);
    }

    return await response.json();
  } catch (err) {
    console.error(`API Error on ${endpoint}:`, err);
    throw err;
  }
}

export const api = {
  // Kiểm tra sức khỏe
  getHealth: () => request('/health'),

  // Danh sách khách hàng
  getCustomers: (search = '', limit = 50, offset = 0) =>
    request(`/customers?search=${encodeURIComponent(search)}&limit=${limit}&offset=${offset}`),

  // Chi tiết 1 khách hàng
  getCustomer: (customerId) => request(`/customers/${customerId}`),

  // Danh sách cụm
  getClusters: () => request('/clusters'),

  // Chi tiết 1 cụm
  getCluster: (clusterId) => request(`/clusters/${clusterId}`),

  // Tọa độ PCA biểu đồ phân tán
  getClusterPoints: () => request('/clusters/points'),

  // Gợi ý sản phẩm
  getRecommendations: (customerId, topK = 10, model = 'hybrid') =>
    request(`/recommend/${customerId}?top_k=${topK}&model=${model}`),

  // Chi tiết sản phẩm
  getProduct: (stockcode) => request(`/products/${stockcode}`),

  // Chỉ số đánh giá
  getMetrics: () => request('/metrics'),
};
