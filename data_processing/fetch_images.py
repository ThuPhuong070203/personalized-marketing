"""
Gán ảnh sản phẩm cho bộ dữ liệu H&M (data_processing/fetch_images.py)

Ảnh là ẢNH THẬT của H&M, đúng từng sản phẩm, nằm trong thư mục images/ của cuộc thi Kaggle
theo dạng images/<3 số đầu>/<article_id>.jpg (ví dụ images/010/0108775015.jpg).

Bộ ảnh đầy đủ ~30 GB, nên script chỉ lấy ảnh của TOP_N_IMAGES sản phẩm bán chạy nhất:
  1. Nếu đã có sẵn thư mục data/raw/hm/images/ (tải tay từ Kaggle) -> lấy ảnh từ đó.
  2. Nếu không -> tải từng ảnh từ Kaggle bằng kagglehub (cần kaggle.json như lúc tải CSV).
  3. Ảnh được đặt vào khung vuông 400x400 nền trắng (giữ nguyên dáng quần áo, không cắt mất),
     lưu tại data/images/<article_id>.jpg.
  4. Cập nhật cột image_path trong products.csv. Sản phẩm không có ảnh -> placeholder.jpg.

_manifest.json ghi lại sản phẩm nào đã có ảnh -> chạy lại sẽ bỏ qua ảnh đã tải.

Chạy (PowerShell):
    python data_processing/fetch_images.py --test        # tải thử 1 ảnh để kiểm tra
    python data_processing/fetch_images.py               # tải ảnh cho top 5.000 sản phẩm
    python data_processing/fetch_images.py --top-n 10000 # nhiều hơn
    python data_processing/fetch_images.py --force       # tải lại toàn bộ
"""

import argparse
import json
import shutil
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config

MANIFEST_PATH = config.IMAGES_DIR / "_manifest.json"
LOCAL_IMAGES_DIR = config.HM_RAW_DIR / "images"          # nếu đã tải tay cả thư mục ảnh
TMP_DIR = config.HM_RAW_DIR / "_images_tmp"              # nơi tạm chứa ảnh gốc khi tải từ Kaggle
PLACEHOLDER_URL = "/images/placeholder.jpg"


# =========================================================
# Tiện ích
# =========================================================
def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def kaggle_image_path(article_id: str) -> str:
    """Đường dẫn ảnh trong cuộc thi: images/010/0108775015.jpg"""
    return f"images/{article_id[:3]}/{article_id}.jpg"


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def create_placeholder_image(path: Path) -> None:
    """Ảnh mặc định cho sản phẩm không có ảnh."""
    path.parent.mkdir(parents=True, exist_ok=True)
    w, h = config.IMAGE_SIZE
    img = Image.new("RGB", (w, h), (241, 245, 249))
    draw = ImageDraw.Draw(img)
    # Biểu tượng móc treo quần áo đơn giản
    cx, cy = w // 2, h // 2 - 30
    draw.arc([cx - 18, cy - 60, cx + 18, cy - 24], start=180, end=90, fill=(148, 163, 184), width=4)
    draw.line([cx, cy - 24, cx, cy - 10], fill=(148, 163, 184), width=4)
    draw.polygon([(cx, cy - 10), (cx - 90, cy + 45), (cx + 90, cy + 45)], outline=(148, 163, 184), width=4)
    font = _font(20)
    text = "Chưa có ảnh"
    tw = draw.textbbox((0, 0), text, font=font)[2]
    draw.text(((w - tw) // 2, cy + 75), text, fill=(100, 116, 139), font=font)
    img.save(path, format="JPEG", quality=90)


def to_square(src: Path, dst: Path) -> None:
    """
    Đặt ảnh vào khung vuông nền trắng (không cắt), thu nhỏ về IMAGE_SIZE.
    Ảnh H&M là ảnh dọc (người mẫu / sản phẩm đứng), cắt vuông sẽ mất phần trên/dưới.
    """
    with Image.open(src) as im:
        im = im.convert("RGB")
        out = ImageOps.pad(im, config.IMAGE_SIZE, method=Image.Resampling.LANCZOS, color=(255, 255, 255))
        out.save(dst, format="JPEG", quality=85)


# =========================================================
# Lấy ảnh gốc
# =========================================================
def get_from_local(article_id: str) -> Path | None:
    p = LOCAL_IMAGES_DIR / article_id[:3] / f"{article_id}.jpg"
    return p if p.exists() else None


def get_from_kaggle(article_id: str) -> Path | None:
    """Tải 1 ảnh từ Kaggle vào thư mục tạm; trả về đường dẫn file .jpg hoặc None nếu không có."""
    import kagglehub  # import trễ: chỉ cần khi thật sự tải từ Kaggle

    out_dir = TMP_DIR / article_id
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        p = Path(kagglehub.competition_download(
            config.KAGGLE_COMPETITION, path=kaggle_image_path(article_id), output_dir=str(out_dir)
        ))
    except Exception as e:
        msg = str(e)
        # Lỗi xác thực -> dừng hẳn để người dùng sửa, không cố tải tiếp hàng nghìn ảnh
        if "Unauthenticated" in type(e).__name__ or "401" in msg or "403" in msg:
            raise
        return None  # thường là sản phẩm không có ảnh (404)

    # kagglehub có thể trả về file .jpg, file .zip, hoặc thư mục
    if p.is_dir():
        jpgs = list(p.rglob("*.jpg"))
        return jpgs[0] if jpgs else None
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            z.extractall(out_dir)
        jpgs = list(out_dir.rglob("*.jpg"))
        return jpgs[0] if jpgs else None
    return p if p.exists() else None


def fetch_one(article_id: str, use_local: bool) -> tuple[str, str]:
    """Lấy + chuyển 1 ảnh. Trả về (article_id, trạng thái: ok | missing)."""
    target = config.IMAGES_DIR / f"{article_id}.jpg"
    src = get_from_local(article_id) if use_local else get_from_kaggle(article_id)
    if src is None:
        return article_id, "missing"
    try:
        to_square(src, target)
        return article_id, "ok"
    except Exception:
        return article_id, "missing"
    finally:
        if not use_local:
            shutil.rmtree(TMP_DIR / article_id, ignore_errors=True)  # xóa ảnh gốc (nặng) sau khi đã thu nhỏ


# =========================================================
# MAIN
# =========================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=config.TOP_N_IMAGES,
                        help="Số sản phẩm bán chạy nhất được lấy ảnh")
    parser.add_argument("--force", action="store_true", help="Tải lại cả ảnh đã có")
    parser.add_argument("--test", action="store_true", help="Chỉ tải thử 1 ảnh để kiểm tra kết nối Kaggle")
    parser.add_argument("--workers", type=int, default=4, help="Số luồng tải song song")
    args = parser.parse_args()

    t0 = time.time()
    print("=" * 60)
    print("BẮT ĐẦU GÁN ẢNH SẢN PHẨM H&M")
    print("=" * 60)

    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    create_placeholder_image(config.PLACEHOLDER_IMAGE_PATH)

    if not config.PRODUCTS_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy {config.PRODUCTS_PATH}. Chạy process.py trước!")
    df = pd.read_csv(config.PRODUCTS_PATH, dtype={"stockcode": str}, keep_default_na=False)
    df = df.sort_values("n_purchases", ascending=False).reset_index(drop=True)

    use_local = LOCAL_IMAGES_DIR.exists()
    print(f"Nguồn ảnh: {'thư mục có sẵn ' + str(LOCAL_IMAGES_DIR) if use_local else 'tải từng ảnh từ Kaggle'}")

    # --- Chế độ thử: 1 ảnh ---
    if args.test:
        aid = df["stockcode"].iloc[0]
        print(f"Tải thử ảnh của sản phẩm bán chạy nhất: {aid} ({df['description'].iloc[0]})")
        _, status = fetch_one(aid, use_local)
        if status == "ok":
            print(f"✅ Thành công! Mở thử file: {config.IMAGES_DIR / (aid + '.jpg')}")
            print("   Giờ chạy lại không có --test để tải toàn bộ.")
        else:
            print("❌ Không tải được ảnh. Kiểm tra kaggle.json và việc đã đồng ý luật cuộc thi.")
        return

    manifest = {} if args.force else load_json(MANIFEST_PATH)
    top_ids = df["stockcode"].head(args.top_n).tolist()
    todo = [a for a in top_ids
            if args.force or manifest.get(a) != "ok" or not (config.IMAGES_DIR / f"{a}.jpg").exists()]
    print(f"Tổng sản phẩm: {len(df):,} | Lấy ảnh cho top {len(top_ids):,} | Cần tải: {len(todo):,}")

    stats = {"ok": 0, "missing": 0}
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(fetch_one, a, use_local) for a in todo]
        for fut in as_completed(futures):
            aid, status = fut.result()
            manifest[aid] = status
            stats[status] += 1
            done += 1
            if done % 100 == 0 or done == len(todo):
                save_json(MANIFEST_PATH, manifest)
                rate = done / max(time.time() - t0, 1e-6)
                eta = (len(todo) - done) / max(rate, 1e-6) / 60
                print(f"  ... {done:,}/{len(todo):,} ảnh (thiếu ảnh: {stats['missing']:,}) "
                      f"| ~{rate:.1f} ảnh/giây | còn ~{eta:.0f} phút")
    save_json(MANIFEST_PATH, manifest)
    shutil.rmtree(TMP_DIR, ignore_errors=True)

    # Cập nhật image_path: có file ảnh thì trỏ tới ảnh, không thì placeholder
    has_img = {a for a, s in manifest.items() if s == "ok"}
    df["image_path"] = [
        f"/images/{a}.jpg" if a in has_img and (config.IMAGES_DIR / f"{a}.jpg").exists() else PLACEHOLDER_URL
        for a in df["stockcode"]
    ]
    df.to_csv(config.PRODUCTS_PATH, index=False)

    n_img = (df["image_path"] != PLACEHOLDER_URL).sum()
    share = df.loc[df["image_path"] != PLACEHOLDER_URL, "n_purchases"].sum() / max(df["n_purchases"].sum(), 1)
    size_mb = sum(p.stat().st_size for p in config.IMAGES_DIR.glob("*.jpg")) / 1e6
    print("=" * 60)
    print(f"Sản phẩm có ảnh           : {n_img:,} / {len(df):,}")
    print(f"Tỷ lệ lượt mua có ảnh     : {share:.1%}  (sản phẩm có ảnh chiếm bấy nhiêu % lượt mua)")
    print(f"Không có ảnh trên Kaggle  : {stats['missing']:,}")
    print(f"Dung lượng data/images    : {size_mb:,.0f} MB")
    print(f"-> Đã cập nhật: {config.PRODUCTS_PATH}")
    print(f"Thời gian                 : {time.time() - t0:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
    