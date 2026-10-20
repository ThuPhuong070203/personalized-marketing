# Personalized Marketing – Phân cụm khách hàng & Gợi ý sản phẩm

Web demo phân cụm khách hàng (RFM + K-Means) và gợi ý sản phẩm (6 thuật toán) trên bộ dữ liệu **Online Retail II**.

📄 Chi tiết về dữ liệu, phương pháp, kết quả và hướng phát triển: xem **[proposal.md](proposal.md)**.

---

## 1. Yêu cầu

| Phần mềm | Phiên bản | Ghi chú |
|---|---|---|
| Python | 3.10 trở lên | |
| Node.js | 18 trở lên | Kèm `npm` |
| Git | bất kỳ | Để tải mã nguồn |
| Pixabay API key | – | Tùy chọn, chỉ cần khi muốn tải lại ảnh sản phẩm |
| Docker | – | Tùy chọn, nếu muốn chạy bằng Docker Compose |

Dữ liệu gốc `online_retail_cleaned.csv` cần được đặt vào `data/raw/` (không có sẵn trong repo vì dung lượng lớn).
## 📥 Dữ liệu đầu vào (Dataset)

Dự án sử dụng bộ dữ liệu **UCI Online Retail II**:
- **Bản CSV sạch trên Kaggle:** [Online Retail II Dataset - Kaggle](https://www.kaggle.com/datasets/mashlyn/online-retail-ii-uci)

### 🛠️ Hướng dẫn thiết lập dữ liệu thô:
1. Tải file dữ liệu CSV `online_retail_cleaned.csv` từ Kaggle
2. Tạo thư mục `data/raw/` ở thư mục gốc của dự án nếu chưa có.
3. Đặt file vừa tải vào thư mục: `data/raw/online_retail_cleaned.csv`.
4. Chạy script tiền xử lý dữ liệu:
   ```bash
   python data_processing/process.py

---

## 2. Cấu trúc thư mục

```
personalized-marketing/
├── config.py              # Đường dẫn, hằng số, siêu tham số dùng chung
├── requirements.txt       # Thư viện Python
├── docker-compose.yml
├── README.md              # Hướng dẫn chạy (file này)
├── proposal.md            # Mô tả chi tiết dự án
├── data/
│   ├── raw/               # Dữ liệu gốc (tự đặt vào)
│   ├── processed/         # Sinh ra từ process.py
│   └── images/            # Ảnh sản phẩm (có sẵn trong repo)
├── data_processing/
│   ├── process.py         # Làm sạch dữ liệu, chia train/test, tính RFM
│   └── fetch_images.py    # Gán ảnh sản phẩm
├── backend/
│   ├── algorithms/        # Phân cụm, gợi ý, đánh giá
│   ├── app/               # FastAPI
│   ├── models/            # Sinh ra từ train.py
│   └── train.py           # Huấn luyện + đánh giá
└── frontend/              # React + Vite
```

Các thư mục `data/processed/` và `backend/models/` **sinh ra khi chạy pipeline** ở bước 3 bên dưới. Ảnh sản phẩm trong `data/images/` đã có sẵn trong repo.

---

## 3. Chạy trực tiếp (Windows / PowerShell)

Mọi lệnh bên dưới chạy tại thư mục `personalized-marketing`, trừ khi có ghi `cd`.

### Bước 1 – Tải mã nguồn

```powershell
git clone https://github.com/<tên-tài-khoản>/personalized-marketing.git
cd personalized-marketing
```

### Bước 2 – Cài thư viện Python

```powershell
# (Tùy chọn) tạo và kích hoạt môi trường ảo
python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

### Bước 3 – Chạy pipeline dữ liệu & huấn luyện

Chạy **đúng thứ tự** sau:

```powershell
# 3.1. Làm sạch dữ liệu (~10 giây)
python data_processing/process.py

# 3.2. Gán ảnh sản phẩm vào products.csv (vài giây, không cần API key)
python data_processing/fetch_images.py --top-n 4624

# 3.3. Huấn luyện và đánh giá mô hình
python backend/train.py
```

**Về bước 3.2 (ảnh sản phẩm):**

- **Ảnh của toàn bộ 4.624 sản phẩm đã có sẵn trong repo** (`data/images/`, kèm `_manifest.json`). Bước này chỉ gán lại đường dẫn ảnh vào `products.csv`, không tải gì thêm.
- **Chỉ khi muốn tải lại ảnh từ đầu** (`--force`) hoặc sửa ảnh sai mới cần API key Pixabay:
  - Lấy key miễn phí: đăng nhập [pixabay.com](https://pixabay.com), mở [pixabay.com/api/docs](https://pixabay.com/api/docs/), copy chuỗi ở dòng `key (required)`.
  - Đặt key trước khi chạy: `$env:PIXABAY_API_KEY="<key của bạn>"`.
  - Tải lại toàn bộ mất khoảng 2,5–3 giờ; có thể dừng bằng `Ctrl + C` và chạy lại, script tự làm tiếp từ chỗ dừng.
- Sản phẩm bị sai ảnh: ghi từ khóa mới vào `data/images/_overrides.json`, ví dụ `{"22423": "cake stand"}`, rồi chạy lại lệnh trên (cần API key).

### Bước 4 – Chạy backend

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

Tài liệu API: http://localhost:8000/docs

### Bước 5 – Chạy frontend (mở terminal mới)

```powershell
cd frontend
npm install
npm run dev
```

Mở trình duyệt: http://localhost:5173

---

## 4. Chạy bằng Docker Compose

Chạy xong **bước 3** ở trên (để có dữ liệu trong `data/` và mô hình trong `backend/models/`), rồi:

```powershell
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000

---

## 5. Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `venv\Scripts\activate : The module 'venv' could not be loaded` | Chưa tạo môi trường ảo | Chạy `python -m venv venv` trước, hoặc bỏ qua bước kích hoạt |
| `npm : File ... cannot be loaded because running scripts is disabled` | PowerShell chặn chạy script | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `ModuleNotFoundError: No module named ...` | Thiếu thư viện Python | `pip install -r requirements.txt` |
| `can't open file ... No such file or directory` | Đứng sai thư mục | `cd` vào thư mục `personalized-marketing` |
| `Chưa có PIXABAY_API_KEY` | Chưa đặt key, hoặc đã mở terminal mới / khởi động lại máy | Chạy lại dòng `$env:PIXABAY_API_KEY="..."` |
| Web hiện ảnh cũ hoặc ảnh placeholder | Trình duyệt lưu ảnh cũ, hoặc đã chạy `process.py` sau `fetch_images.py` | Nhấn `Ctrl + F5`; nếu vẫn sai, chạy lại `fetch_images.py` (vài giây) |

> ⚠️ `process.py` ghi lại `products.csv` từ đầu. Mỗi lần chạy lại `process.py` thì chạy lại `fetch_images.py` để gán lại cột ảnh (chỉ mất vài giây vì ảnh đã có sẵn).

---

## 6. API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/health` | Kiểm tra hệ thống đang chạy |
| `GET` | `/customers?search=&limit=50` | Tìm kiếm danh sách khách hàng |
| `GET` | `/customers/{customer_id}` | Hồ sơ RFM, nhóm và 10 giao dịch gần nhất của khách |
| `GET` | `/clusters` | Thông tin các nhóm: tên, số khách, RFM trung bình, chiến dịch |
| `GET` | `/clusters/{cluster_id}` | Chi tiết một nhóm kèm top 10 sản phẩm bán chạy trong nhóm |
| `GET` | `/clusters/points` | Tọa độ PCA 2D để vẽ biểu đồ phân tán |
| `GET` | `/recommend/{customer_id}?top_k=10&model=hybrid` | Gợi ý sản phẩm cho khách (tự fallback nếu là khách mới) |
| `GET` | `/products/{stockcode}` | Thông tin và ảnh của một sản phẩm |
| `GET` | `/metrics` | Toàn bộ chỉ số đánh giá phân cụm và gợi ý |
