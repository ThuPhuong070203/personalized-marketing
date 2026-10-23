"""
Xuất ảnh sản phẩm H&M - chạy trên KAGGLE NOTEBOOK (data_processing/kaggle_export_images.py)

Vì sao chạy trên Kaggle: bộ ảnh đầy đủ ~30 GB, còn tải từng ảnh qua Kaggle API thì bị giới hạn
tốc độ (lỗi 429). Trên Kaggle Notebook, dữ liệu cuộc thi có sẵn nên chỉ cần đọc, thu nhỏ và nén lại.

Cách dùng:
  1. Trang cuộc thi H&M -> tab Code -> New Notebook (dữ liệu cuộc thi được gắn sẵn).
  2. Dán toàn bộ file này vào một ô và chạy (~17 phút). Muốn tắt máy trong lúc chờ thì dùng
     Save Version -> Save & Run All (Commit) để chạy ngầm.
  3. Tải /kaggle/working/hm_images.zip ở tab Output.
  4. Trên máy, tại thư mục personalized-marketing:
       Expand-Archive -Path <đường-dẫn>\\hm_images.zip -DestinationPath data -Force
       python data_processing/fetch_images.py --top-n 0
"""

import json, time, zipfile
from pathlib import Path
import pandas as pd
from PIL import Image, ImageOps

TOP_N = 15_000                 # số sản phẩm bán chạy nhất cần ảnh
START_DATE = "2019-09-23"      # giống DATA_START_DATE trong config.py
IMAGE_SIZE = (400, 400)

t0 = time.time()
BASE = Path("/kaggle/input/competitions/h-and-m-personalized-fashion-recommendations")
if not BASE.exists():  # đường dẫn cũ của Kaggle
    BASE = Path("/kaggle/input/h-and-m-personalized-fashion-recommendations")
img_root = BASE / "images"

# 1. Top N sản phẩm bán chạy nhất trong khoảng thời gian dùng cho đồ án
print("Đang đọc transactions_train.csv...", flush=True)
tx = pd.read_csv(BASE / "transactions_train.csv", engine="pyarrow",
                 usecols=["t_dat", "customer_id", "article_id"], dtype={"article_id": str})
print(f"  đọc xong {len(tx):,} dòng ({time.time()-t0:.0f}s)", flush=True)
tx["t_dat"] = pd.to_datetime(tx["t_dat"])
tx = tx[tx["t_dat"] >= START_DATE]
tx["article_id"] = tx["article_id"].astype(str).str.zfill(10)
counts = tx.drop_duplicates(["customer_id", "t_dat", "article_id"])["article_id"].value_counts()
ids = counts.head(TOP_N).index.tolist()
del tx
print(f"Số sản phẩm cần ảnh: {len(ids)} ({time.time()-t0:.0f}s)", flush=True)

# 2. Đặt ảnh vào khung vuông nền trắng (không cắt), thu nhỏ
out = Path("/kaggle/working/images"); out.mkdir(parents=True, exist_ok=True)
manifest = {}
for i, a in enumerate(ids):
    p = img_root / a[:3] / f"{a}.jpg"
    if p.exists():
        im = Image.open(p).convert("RGB")
        ImageOps.pad(im, IMAGE_SIZE, method=Image.Resampling.LANCZOS,
                     color=(255, 255, 255)).save(out / f"{a}.jpg", "JPEG", quality=85)
        manifest[a] = "ok"
    else:
        manifest[a] = "missing"
    if i % 1000 == 0:
        print(f"  {i}/{len(ids)} ({time.time()-t0:.0f}s)", flush=True)
json.dump(manifest, open(out / "_manifest.json", "w"))
print("Có ảnh:", sum(v == "ok" for v in manifest.values()), "/", len(ids), flush=True)

# 3. Nén lại (ảnh JPEG đã nén sẵn nên dùng ZIP_STORED cho nhanh)
with zipfile.ZipFile("/kaggle/working/hm_images.zip", "w", zipfile.ZIP_STORED) as z:
    for f in out.iterdir():
        z.write(f, f"images/{f.name}")
print(f"Xong! ({time.time()-t0:.0f}s)", flush=True)
