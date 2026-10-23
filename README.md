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
