"""
Tải 3 file CSV của bộ dữ liệu H&M về data/raw/hm/ (data_processing/download_hm.py).
Không tải thư mục ảnh (~30 GB). Ảnh sản phẩm đã có sẵn trong repo (data/images/).

Yêu cầu:
  - Đã đồng ý luật cuộc thi trên Kaggle (tab Rules -> I Understand and Accept).
  - Có file C:\\Users\\<tên-máy>\\.kaggle\\kaggle.json (xem README, bước 3.0).

Chạy:
    python data_processing/download_hm.py
"""

import shutil
import sys
import zipfile
from pathlib import Path

import kagglehub

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import config

FILES = ["articles.csv", "customers.csv", "transactions_train.csv"]


def main():
    out_dir = config.HM_RAW_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    for name in FILES:
        target = out_dir / name
        if target.exists():
            print(f"Đã có {name} -> bỏ qua")
            continue

        print(f"Đang tải {name} ...")
        p = Path(kagglehub.competition_download(config.KAGGLE_COMPETITION, path=name, output_dir=str(out_dir)))

        # Kaggle có thể trả về file .zip (với file lớn) -> tự giải nén
        if p.suffix.lower() == ".zip":
            print(f"  Giải nén {p.name} ...")
            with zipfile.ZipFile(p) as z:
                z.extractall(out_dir)
            p.unlink()
        # Nếu file nằm trong thư mục con thì đưa ra đúng chỗ
        if not target.exists():
            found = list(out_dir.rglob(name))
            if found:
                shutil.move(str(found[0]), str(target))

        if target.exists():
            print(f"  -> {target} ({target.stat().st_size / 1e6:,.0f} MB)")
        else:
            print(f"  [LỖI] Không tìm thấy {name} sau khi tải. Kiểm tra thư mục {out_dir}")

    print("\nXong! Dữ liệu nằm trong:", out_dir)
    print("Bước tiếp theo: python data_processing/process.py")


if __name__ == "__main__":
    main()
