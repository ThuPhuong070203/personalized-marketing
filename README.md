# Personalized Marketing – Phân cụm khách hàng & Gợi ý sản phẩm

Web demo phân cụm khách hàng (RFM + K-Means) và gợi ý sản phẩm (6 thuật toán) trên bộ dữ liệu **H&M Personalized Fashion Recommendations** (~31,8 triệu giao dịch thời trang).

📄 Chi tiết về dữ liệu, phương pháp, kết quả và hướng phát triển: xem **[proposal.md](proposal.md)**.

---

## 1. Yêu cầu

| Phần mềm / Tài khoản | Phiên bản | Ghi chú |
|---|---|---|
| Python | 3.10 trở lên | |
| Node.js | 18 trở lên | Kèm `npm` |
| Git | bất kỳ | Để tải mã nguồn |
| Tài khoản Kaggle | – | Bắt buộc, để tải dữ liệu (miễn phí) |
| RAM | 16 GB (khuyến nghị) | Máy 8 GB vẫn chạy được nếu giảm khoảng thời gian dữ liệu, xem mục 5 |
| Ổ đĩa trống | ≥ 10 GB | 3 file CSV ~4 GB + bản Parquet + dữ liệu sau xử lý |
| Docker | – | Tùy chọn, nếu muốn chạy bằng Docker Compose |

Dữ liệu H&M **không có sẵn trong repo** (file giao dịch ~3,5 GB). Bước 3.1 bên dưới hướng dẫn tải về. Ảnh sản phẩm thì **có sẵn trong repo** (`data/images/`).

---

## 2. Cấu trúc thư mục

```
personalized-marketing/
├── config.py                    # Đường dẫn, hằng số, siêu tham số dùng chung
├── requirements.txt             # Thư viện Python
├── docker-compose.yml
├── README.md                    # Hướng dẫn chạy (file này)
├── proposal.md                  # Mô tả chi tiết dự án
├── data/
│   ├── raw/hm/                  # Dữ liệu gốc H&M (tải bằng download_hm.py)
│   ├── processed/               # Sinh ra từ process.py
│   └── images/                  # Ảnh thật của 15.000 sản phẩm bán chạy (có sẵn trong repo)
├── data_processing/
│   ├── download_hm.py           # Tải 3 file CSV từ Kaggle
│   ├── process.py               # Làm sạch dữ liệu, chia train/test, tính RFM (Polars)
│   ├── fetch_images.py          # Gán đường dẫn ảnh vào products.csv (hoặc tải ảnh qua Kaggle API)
│   └── kaggle_export_images.py  # Chạy trên Kaggle Notebook: xuất ảnh 15.000 sản phẩm thành file zip
├── backend/
│   ├── algorithms/              # Phân cụm, gợi ý, đánh giá
│   ├── app/                     # FastAPI
│   ├── models/                  # Sinh ra từ train.py
│   └── train.py                 # Huấn luyện + đánh giá
└── frontend/                    # React + Vite
```

Các thư mục `data/raw/hm/`, `data/processed/` và `backend/models/` **sinh ra khi chạy pipeline** ở bước 3.

---

## 3. Chạy trực tiếp (Windows / PowerShell)

Mọi lệnh bên dưới chạy tại thư mục `personalized-marketing`, trừ khi có ghi `cd`.

### Bước 1 – Tải mã nguồn

```powershell
git clone https://github.com/ThuPhuong070203/personalized-marketing.git
cd personalized-marketing
```

### Bước 2 – Cài thư viện Python

```powershell
# (Tùy chọn) tạo và kích hoạt môi trường ảo
python -m venv venv
venv\Scripts\activate

python -m pip install -r requirements.txt
```

### Bước 3 – Tải dữ liệu, xử lý & huấn luyện

**3.0. Chuẩn bị tài khoản Kaggle** (làm 1 lần):

1. Vào [trang cuộc thi H&M](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations), đăng nhập, mở tab **Rules** và bấm **I Understand and Accept**. Không đồng ý luật thì sẽ không tải được.
2. Lấy API key: kaggle.com → ảnh đại diện → **Settings** → **API Tokens** → **Create Legacy API Key**, máy sẽ tải về file `kaggle.json`.
3. Đặt file vào `C:\Users\<tên-máy>\.kaggle\kaggle.json`:
   ```powershell
   mkdir $env:USERPROFILE\.kaggle
   Move-Item $env:USERPROFILE\Downloads\kaggle.json $env:USERPROFILE\.kaggle\ -Force
   ```

**3.1 → 3.4. Chạy pipeline theo đúng thứ tự:**

```powershell
# 3.1. Tải 3 file CSV (~4 GB, vài phút đến vài chục phút tùy mạng)
python data_processing/download_hm.py

# 3.2. Làm sạch dữ liệu, chia train/test, tính RFM (~1 phút)
python data_processing/process.py

# 3.3. Gán đường dẫn ảnh vào products.csv (vài giây, ảnh đã có sẵn trong repo)
python data_processing/fetch_images.py --top-n 0

# 3.4. Huấn luyện và đánh giá mô hình (~6 phút)
python backend/train.py
```

> Thời gian đo trên laptop RAM 16 GB: `process.py` ~59 giây (lần đầu cộng thêm vài phút để chuyển CSV sang Parquet), `train.py` ~350 giây.

**Về bước 3.3 (ảnh sản phẩm):**

- Ảnh là **ảnh thật của H&M** cho 15.000 sản phẩm bán chạy nhất (~190 MB, 14.978 sản phẩm có ảnh), lưu ở `data/images/` kèm `_manifest.json`.
- Ảnh **đã có sẵn trong repo**, nên bước này chỉ gán đường dẫn ảnh vào `products.csv`, không tải gì.
- Nếu **muốn tạo lại ảnh từ đầu**: không nên tải từng ảnh qua Kaggle API vì sẽ bị giới hạn tốc độ (lỗi 429). Cách khuyên dùng:
  1. Trên trang cuộc thi H&M → tab **Code** → **New Notebook** (dữ liệu cuộc thi được gắn sẵn).
  2. Dán toàn bộ nội dung `data_processing/kaggle_export_images.py` vào một ô và chạy (~17 phút). Muốn tắt máy trong lúc chờ thì dùng **Save Version → Save & Run All (Commit)** để chạy ngầm.
  3. Tải file `hm_images.zip` ở tab **Output** của notebook.
  4. Giải nén vào dự án:
     ```powershell
     Expand-Archive -Path $env:USERPROFILE\Downloads\hm_images.zip -DestinationPath data -Force
     ```
  5. Chạy `python data_processing/fetch_images.py --top-n 0`.
- Sản phẩm không có ảnh dùng `placeholder.jpg`.

### Bước 4 – Chạy backend

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

- Lần khởi động đầu mất ~40 giây (nạp mô hình + tạo cache lịch sử mua hàng); các lần sau ~30 giây.
- Chờ tới dòng `[API Service] Sẵn sàng phục vụ yêu cầu!`. Log sẽ in kèm **mã khách mẫu cho từng nhóm** để dùng khi demo.
- Tài liệu API: http://localhost:8000/docs

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

> Cách chạy bằng Docker chưa được kiểm thử đầy đủ; nếu gặp lỗi, dùng cách chạy trực tiếp ở mục 3.

---

## 5. Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `429 Client Error: Too Many Requests` khi tải ảnh | Kaggle giới hạn tốc độ tải từng file | Dừng lại; dùng cách lấy ảnh qua Kaggle Notebook ở bước 3.3 |
| `UnauthenticatedError: User is not authenticated` | Chưa có hoặc đặt sai `kaggle.json` | Kiểm tra lại bước 3.0, file phải nằm ở `C:\Users\<tên-máy>\.kaggle\kaggle.json` |
| Lỗi `403 Forbidden` khi tải | Chưa đồng ý luật cuộc thi | Vào tab **Rules** trên Kaggle, bấm **I Understand and Accept** |
| `FileNotFoundError: ...data\raw\hm\transactions_train.csv` | Dữ liệu chưa nằm đúng chỗ | Đặt 3 file CSV vào `data/raw/hm/` (không phải `data/raw/` hay `data/`) |
| `MemoryError` hoặc máy treo khi chạy `process.py` / `train.py` | Không đủ RAM | Tắt bớt ứng dụng; hoặc trong `config.py` đặt `DATA_START_DATE` gần hơn (ví dụ `"2020-03-23"` = 6 tháng) và giảm `MAX_ITEMS_CF`, `MAX_CUSTOMERS_RECSYS` |
| `venv\Scripts\activate : The module 'venv' could not be loaded` | Chưa tạo môi trường ảo | Chạy `python -m venv venv` trước, hoặc bỏ qua bước kích hoạt |
| `npm : File ... cannot be loaded because running scripts is disabled` | PowerShell chặn chạy script | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `ModuleNotFoundError: No module named ...` | Thiếu thư viện, hoặc cài vào một bản Python khác | `python -m pip install -r requirements.txt` |
| `can't open file ... No such file or directory` | Đứng sai thư mục | `cd` vào thư mục `personalized-marketing` |
| `docker : The term 'docker' is not recognized` | Máy chưa cài Docker | Cài [Docker Desktop](https://www.docker.com/products/docker-desktop/) (cần WSL 2, khởi động lại máy), hoặc chạy trực tiếp theo mục 3 |
| Web báo `Failed to fetch` | Backend chưa chạy hoặc đang khởi động | Bật backend (bước 4), chờ dòng "Sẵn sàng phục vụ yêu cầu!" |
| Web hiện ảnh "Chưa có ảnh" hàng loạt | Đã chạy `process.py` sau khi gán ảnh | Chạy lại `python data_processing/fetch_images.py --top-n 0`, rồi khởi động lại backend và nhấn `Ctrl + F5` |

> ⚠️ `process.py` ghi lại `products.csv` từ đầu. Mỗi lần chạy lại `process.py` thì chạy lại `fetch_images.py --top-n 0` để gán lại cột ảnh.

---

## 6. API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/health` | Kiểm tra hệ thống đang chạy |
| `GET` | `/customers?search=&limit=50&offset=0` | Danh sách khách hàng (tìm theo mã, phân trang); khách có gợi ý cá nhân hóa được xếp trước |
| `GET` | `/customers/{customer_id}` | Hồ sơ RFM, nhóm và 10 sản phẩm mua gần nhất của khách |
| `GET` | `/clusters` | Thông tin các nhóm: tên, số khách, RFM trung bình, chiến dịch |
| `GET` | `/clusters/{cluster_id}` | Chi tiết một nhóm kèm top 10 sản phẩm bán chạy trong nhóm |
| `GET` | `/clusters/points` | Tọa độ PCA 2D (mẫu 2.000 khách) để vẽ biểu đồ phân tán |
| `GET` | `/recommend/{customer_id}?top_k=10&model=hybrid` | Gợi ý sản phẩm cho khách (tự fallback nếu là khách mới) |
| `GET` | `/products/{article_id}` | Thông tin và ảnh của một sản phẩm |
| `GET` | `/metrics` | Toàn bộ chỉ số đánh giá phân cụm và gợi ý |

> `customer_id` trong API là **số nguyên ngắn** do hệ thống tự đánh (H&M dùng chuỗi mã hóa 64 ký tự, quá dài để gõ). Bảng đối chiếu lưu ở `data/processed/customer_id_map.parquet`.
>
> Giá trong dữ liệu H&M **đã được chuẩn hóa** (không phải tiền thật), nên web hiển thị giá trị dạng số thập phân, không kèm đơn vị tiền tệ.
