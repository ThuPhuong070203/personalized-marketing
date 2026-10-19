"""
Script gán ảnh sản phẩm (data_processing/fetch_images.py)

1. Tạo ảnh placeholder.jpg.
2. Top N sản phẩm: tìm ẢNH THẬT qua Pixabay API (ưu tiên) / Pexels API (dự phòng).
   - Mô tả được rút gọn thành từ khóa chính để tìm chính xác hơn.
   - Ưu tiên ảnh chưa dùng -> ít trùng ảnh.
3. Sản phẩm còn lại / không tìm được: ảnh minh họa theo danh mục từ Unsplash,
   nếu danh mục không tải được thì tạo thẻ sản phẩm bằng Pillow.
4. Ảnh 400x400 (cắt vuông), lưu data/images/<stockcode>.jpg, cập nhật products.csv.

- _manifest.json: ghi nguồn ảnh từng sản phẩm. Chạy lại sẽ nâng cấp ảnh minh họa thành
  ảnh thật nhưng giữ ảnh thật đã có.
- _query_cache.json: cache kết quả tìm kiếm, dừng giữa chừng chạy lại không tốn quota.

Chạy (PowerShell):
    $env:PIXABAY_API_KEY="..."
    python data_processing/fetch_images.py --top-n 1500
    python data_processing/fetch_images.py --force     # tải lại toàn bộ
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config

PIXABAY_KEY = (getattr(config, "PIXABAY_API_KEY", "") or os.getenv("PIXABAY_API_KEY", "")).strip()
PEXELS_KEY = (getattr(config, "PEXELS_API_KEY", "") or os.getenv("PEXELS_API_KEY", "")).strip()

MANIFEST_PATH = config.IMAGES_DIR / "_manifest.json"
CACHE_PATH = config.IMAGES_DIR / "_query_cache_v2.json"
OVERRIDES_PATH = config.IMAGES_DIR / "_overrides.json"  # {"22423": "cake stand"} sửa tay từ khóa
REAL_SOURCES = {"pixabay", "pexels"}
IMAGE_VERSION = 2  # ảnh thật tải bằng cách tìm cũ (không có v=2) sẽ được tải lại

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "personalized-marketing-demo/1.0"})

# =========================================================
# Kho ảnh minh họa theo danh mục (Unsplash) - dùng làm fallback
# =========================================================
CURATED_CATEGORY_IMAGES = {
    "bag": [
        "https://images.unsplash.com/photo-1544816155-12df9643f363?w=400&q=80",
        "https://images.unsplash.com/photo-1590874103328-eac38a683ce7?w=400&q=80",
        "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=400&q=80",
    ],
    "clock": [
        "https://images.unsplash.com/photo-1563861826100-9cb868fdbe1c?w=400&q=80",
        "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400&q=80",
    ],
    "cake": [
        "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=400&q=80",
        "https://images.unsplash.com/photo-1588195538326-c5b1e9f80a1b?w=400&q=80",
        "https://images.unsplash.com/photo-1535141192574-5d4897c13136?w=400&q=80",
    ],
    "candle": [
        "https://images.unsplash.com/photo-1603006905003-be475563bc59?w=400&q=80",
        "https://images.unsplash.com/photo-1572726729437-3732efed37c1?w=400&q=80",
        "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&q=80",
    ],
    "mirror": [
        "https://images.unsplash.com/photo-1618220179428-22790b461013?w=400&q=80",
        "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?w=400&q=80",
    ],
    "card": [
        "https://images.unsplash.com/photo-1513542789411-b6a5d4f31634?w=400&q=80",
        "https://images.unsplash.com/photo-1586075010923-2dd4570fb338?w=400&q=80",
    ],
    "mug": [
        "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=400&q=80",
        "https://images.unsplash.com/photo-1577937927133-66ef06acdf18?w=400&q=80",
    ],
    "tea": [
        "https://images.unsplash.com/photo-1576092768241-dec231879fc3?w=400&q=80",
        "https://images.unsplash.com/photo-1564890369478-c89ca6d9cde9?w=400&q=80",
    ],
    "box": [
        "https://images.unsplash.com/photo-1549465220-1a8b9238cd48?w=400&q=80",
        "https://images.unsplash.com/photo-1512909006721-3d6018887383?w=400&q=80",
    ],
    "heart": [
        "https://images.unsplash.com/photo-1518199266791-5375a83190b7?w=400&q=80",
        "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?w=400&q=80",
    ],
    "plant": [
        "https://images.unsplash.com/photo-1485955900006-10f4d324d411?w=400&q=80",
        "https://images.unsplash.com/photo-1459411552884-841db9b3cc2a?w=400&q=80",
    ],
    "frame": [
        "https://images.unsplash.com/photo-1583847268964-b28dc8f51f92?w=400&q=80",
        "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?w=400&q=80",
    ],
    "toy": [
        "https://images.unsplash.com/photo-1566576912321-d58ddd7a6088?w=400&q=80",
        "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?w=400&q=80",
    ],
    "decor": [
        "https://images.unsplash.com/photo-1530103862676-de8c9debad1d?w=400&q=80",
        "https://images.unsplash.com/photo-1512496015851-a90fb38ba796?w=400&q=80",
    ],
    "general": [
        "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=400&q=80",
        "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&q=80",
        "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400&q=80",
    ],
}

# Từ gây nhiễu khi tìm ảnh (màu, kích thước, tên dòng sản phẩm của Online Retail...)
STOPWORDS = {
    "red", "white", "pink", "blue", "green", "black", "ivory", "cream", "gold", "silver",
    "purple", "yellow", "orange", "grey", "gray", "brown", "natural", "pastel", "multi",
    "colour", "colours", "assorted", "small", "large", "medium", "mini", "jumbo", "big",
    "set", "pack", "sets", "vintage", "retrospot", "regency", "design", "designs",
    "polkadot", "spotty", "spot", "dots", "stripe", "stripes", "the", "and", "with",
    "for", "piece", "pieces", "asst", "new", "glass", "metal", "wooden", "wood",
    "tier", "tiers", "layer", "dozen", "pcs", "hanging", "retro", "french", "english",
    "victorian", "classic", "antique", "fancy", "lovely", "cute", "of",
}

# Cụm từ đặc thù của Online Retail -> từ khóa dễ tìm ảnh (cụm dài đặt trước)
PHRASE_MAP = {
    "t-light holder": "tealight candle holder",
    "t-lights": "tealight candles",
    "t-light": "tealight candle",
    "tea light": "tealight candle",
    "cakestand": "cake stand",
    "cake cases": "cupcake liners",
    "cake case": "cupcake liners",
    "jumbo bag": "tote bag",
    "jumbo shopper": "tote bag",
    "shopper": "tote bag",
    "night light": "night lamp",
    "hot water bottle": "hot water bottle",
    "bunting": "bunting flags",
    "doormat": "doormat",
    "jam making": "jam jar",
    "trinket box": "jewelry box",
    "lunch box": "lunch box",
    "storage tin": "tin box",
    "tissues": "tissue paper",
    "wrap": "gift wrapping paper",
    "napkins": "paper napkins",
    "chalkboard": "chalkboard",
    "wicker": "wicker basket",
    "fairy cake": "cupcake",
    "bottle opener": "bottle opener",
    "alarm clock": "alarm clock",
    "egg cup": "egg cup",
    "photo frame": "photo frame",
}


# =========================================================
# Ảnh tạo bằng Pillow
# =========================================================
def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _gradient(width: int, height: int, top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / height
        color = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        draw.line([(0, y), (width, y)], fill=color)
    return img


def create_placeholder_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = config.IMAGE_SIZE
    img = _gradient(width, height, (24, 30, 48), (35, 45, 75))
    draw = ImageDraw.Draw(img)
    draw.rectangle([12, 12, width - 12, height - 12], outline=(99, 102, 241), width=2)
    draw.rounded_rectangle([145, 120, 255, 230], radius=16, outline=(129, 140, 248), width=3)
    draw.arc([165, 85, 235, 140], start=180, end=0, fill=(129, 140, 248), width=3)

    font = _font(22)
    for text, y, color in [("Retail Product", 255, (241, 245, 249)),
                           ("Online Retail Collection", 285, (148, 163, 184))]:
        w = draw.textbbox((0, 0), text, font=font)[2]
        draw.text(((width - w) // 2, y), text, fill=color, font=font)

    img.save(path, format="JPEG", quality=90)
    print(f"Đã tạo ảnh placeholder tại: {path}")


def create_product_card_image(desc: str, category: str) -> Image.Image:
    width, height = config.IMAGE_SIZE
    img = _gradient(width, height, (18, 24, 42), (32, 42, 68))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, width - 10, height - 10], outline=(99, 102, 241), width=2)

    draw.rounded_rectangle([25, 25, 200, 55], radius=6, outline=(129, 140, 248), width=1)
    draw.text((35, 32), f"DANH MỤC: {category.upper()}", fill=(224, 231, 255), font=_font(16))

    draw.rounded_rectangle([150, 80, 250, 175], radius=12, outline=(148, 163, 184), width=2)
    draw.line([175, 125, 225, 125], fill=(148, 163, 184), width=2)
    draw.line([200, 100, 200, 150], fill=(148, 163, 184), width=2)

    lines, cur = [], []
    for w in desc.strip().split():
        cur.append(w)
        if len(" ".join(cur)) >= 22:
            lines.append(" ".join(cur))
            cur = []
    if cur:
        lines.append(" ".join(cur))
    y = 210
    for line in lines[:4]:
        draw.text((30, y), line.capitalize(), fill=(248, 250, 252), font=_font(22))
        y += 30
    draw.text((30, height - 38), "Personalized Marketing Product Card",
              fill=(100, 116, 139), font=_font(14))
    return img


# =========================================================
# Ảnh minh họa theo danh mục (fallback)
# =========================================================
def get_category_for_description(desc: str) -> str:
    d = str(desc).lower()
    rules = [
        ("bag", ["bag", "shopper", "tote", "lunch"]),
        ("clock", ["clock", "alarm"]),
        ("cake", ["cake", "baking", "cakestand", "cupcake", "sweet", "fairy"]),
        ("candle", ["candle", "t-light", "light", "lantern", "holder"]),
        ("mirror", ["mirror"]),
        ("card", ["card", "birthday", "paper", "wrap", "invitation"]),
        ("mug", ["mug", "cup"]),
        ("tea", ["tea", "teapot", "ceramic", "trinket", "pot", "bowl"]),
        ("box", ["box", "storage", "case"]),
        ("heart", ["heart", "wicker"]),
        ("plant", ["plant", "flower", "lavender", "garden"]),
        ("frame", ["frame", "picture", "photo"]),
        ("toy", ["toy", "bubble", "game", "spaceboy", "doll", "play"]),
        ("decor", ["bunting", "party", "decoration", "decor", "ornament", "banner"]),
    ]
    for cat, keys in rules:
        if any(k in d for k in keys):
            return cat
    return "general"


def download_category_templates() -> dict[str, list[Image.Image]]:
    print("Đang tải ảnh minh họa theo danh mục từ Unsplash (fallback)...")
    templates = {}
    for cat, urls in CURATED_CATEGORY_IMAGES.items():
        templates[cat] = [img for img in (download_square(u) for u in urls) if img]
        fails = len(urls) - len(templates[cat])
        if fails:
            print(f"  - '{cat}': {fails}/{len(urls)} URL lỗi")
    return templates


# =========================================================
# Tìm & tải ảnh thật
# =========================================================
def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def build_queries(desc: str) -> list[str]:
    """
    Dịch cụm từ đặc thù -> bỏ từ nhiễu -> thử lần lượt 3, 2, 1 từ cuối
    (trong Online Retail, danh từ chính thường đứng cuối mô tả).
    """
    d = str(desc).lower()
    for src, dst in PHRASE_MAP.items():
        d = d.replace(src, dst)
    d = re.sub(r"[^a-z\s]", " ", d)
    words = [w for w in d.split() if len(w) > 2 and w not in STOPWORDS]
    words = list(dict.fromkeys(words))  # bỏ từ lặp, giữ thứ tự
    queries = []
    for n in (3, 2, 1):
        q = " ".join(words[-n:])
        if q and q not in queries:
            queries.append(q)
    return queries


def relevance(query: str, tags: str) -> int:
    """Điểm liên quan = số từ khóa xuất hiện trong tags/alt của ảnh, +1 nếu khớp danh từ chính."""
    toks, tags = query.split(), str(tags).lower()
    score = sum(1 for t in toks if t in tags)
    if toks and toks[-1] in tags:
        score += 1
    return score


def search_pixabay(query: str) -> list[str]:
    params = {"key": PIXABAY_KEY, "q": query[:100], "lang": "en", "image_type": "photo",
              "per_page": 20, "safesearch": "true"}
    for _ in range(3):
        try:
            r = SESSION.get("https://pixabay.com/api/", params=params, timeout=15)
            if r.status_code == 429:
                print("  [Pixabay] chạm giới hạn, chờ 60s...")
                time.sleep(60)
                continue
            if r.status_code != 200:
                print(f"  [Pixabay] lỗi {r.status_code}: {r.text[:120]}")
                return []
            time.sleep(0.65)  # ~90 request/phút, dưới giới hạn 100/phút
            return [(h["webformatURL"], h.get("tags", "")) for h in r.json().get("hits", [])]
        except Exception:
            time.sleep(2)
    return []


def search_pexels(query: str) -> list[str]:
    headers = {"Authorization": PEXELS_KEY}
    params = {"query": query, "per_page": 20, "orientation": "square"}
    for _ in range(3):
        try:
            r = SESSION.get("https://api.pexels.com/v1/search", headers=headers,
                            params=params, timeout=15)
            if r.status_code == 429:
                reset = int(r.headers.get("X-Ratelimit-Reset", time.time() + 60))
                wait = max(5, min(reset - int(time.time()), 3600))
                print(f"  [Pexels] chạm giới hạn, chờ {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                return []
            return [(p["src"]["medium"], p.get("alt") or "") for p in r.json().get("photos", [])]
        except Exception:
            time.sleep(2)
    return []


def search_images(queries: list[str], cache: dict) -> tuple[list[str], str | None, str | None]:
    """Thử lần lượt các truy vấn; chỉ nhận ảnh có tags khớp từ khóa, xếp ảnh khớp nhất lên đầu."""
    for q in queries:
        if q not in cache:
            urls, source = [], None
            for name, fn, key in (("pixabay", search_pixabay, PIXABAY_KEY),
                                  ("pexels", search_pexels, PEXELS_KEY)):
                if not key:
                    continue
                hits = sorted(fn(q), key=lambda h: relevance(q, h[1]), reverse=True)
                urls = [u for u, tags in hits if relevance(q, tags) >= 1][:10]
                if urls:
                    source = name
                    break
            cache[q] = {"urls": urls, "source": source}
        if cache[q]["urls"]:
            return cache[q]["urls"], cache[q]["source"], q
    return [], None, None


def download_square(url: str) -> Image.Image | None:
    try:
        r = SESSION.get(url, timeout=15)
        if r.status_code != 200:
            return None
        img = Image.open(BytesIO(r.content)).convert("RGB")
        return ImageOps.fit(img, config.IMAGE_SIZE, Image.Resampling.LANCZOS)
    except Exception:
        return None


def order_urls(urls: list[str], stockcode: str, used: set[str]) -> list[str]:
    """Giữ thứ tự liên quan, nhưng ưu tiên URL chưa dùng cho sản phẩm khác."""
    return [u for u in urls if u not in used] + [u for u in urls if u in used]


# =========================================================
# MAIN
# =========================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=getattr(config, "TOP_N_IMAGES", 1500),
                        help="Số sản phẩm đầu tiên trong products.csv được tìm ảnh thật")
    parser.add_argument("--force", action="store_true", help="Tải lại cả ảnh thật đã có")
    args = parser.parse_args()

    t0 = time.time()
    print("=" * 60)
    print("BẮT ĐẦU GÁN ẢNH SẢN PHẨM")
    print("=" * 60)
    if not (PIXABAY_KEY or PEXELS_KEY):
        print("[CẢNH BÁO] Chưa có PIXABAY_API_KEY / PEXELS_API_KEY -> chỉ dùng ảnh theo danh mục.")

    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    create_placeholder_image(config.PLACEHOLDER_IMAGE_PATH)

    if not config.PRODUCTS_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy file {config.PRODUCTS_PATH}!")
    df = pd.read_csv(config.PRODUCTS_PATH, dtype={"stockcode": str})
    print(f"Tổng số sản phẩm: {len(df):,} | Tìm ảnh thật cho top {args.top_n:,}")

    manifest, cache = load_json(MANIFEST_PATH), load_json(CACHE_PATH)
    overrides = load_json(OVERRIDES_PATH)
    used = {v["url"] for v in manifest.values()
            if isinstance(v, dict) and v.get("url") and v.get("v") == IMAGE_VERSION}
    templates = None
    stats = {"real_kept": 0, "real_new": 0, "fallback": 0}
    paths = []

    for idx, row in enumerate(df.itertuples(index=False)):
        sc = str(row.stockcode).strip()
        desc = str(row.description).strip()
        target = config.IMAGES_DIR / f"{sc}.jpg"
        info = manifest.get(sc, {})
        paths.append(f"/images/{sc}.jpg")

        # Đã có ảnh thật -> giữ
        if (not args.force and target.exists() and info.get("source") in REAL_SOURCES
                and info.get("v") == IMAGE_VERSION and sc not in overrides):
            stats["real_kept"] += 1
            continue

        # 1) Ảnh thật cho top N (hoặc sản phẩm có từ khóa sửa tay)
        if (PIXABAY_KEY or PEXELS_KEY) and (idx < args.top_n or sc in overrides) \
                and desc and desc != "unknown product":
            queries = [overrides[sc]] if sc in overrides else build_queries(desc)
            urls, source, query = search_images(queries, cache)
            img = chosen = None
            for u in order_urls(urls, sc, used)[:3] if urls else []:
                img = download_square(u)
                if img:
                    chosen = u
                    break
            if img:
                img.save(target, format="JPEG", quality=85)
                used.add(chosen)
                manifest[sc] = {"source": source, "url": chosen, "query": query, "v": IMAGE_VERSION}
                stats["real_new"] += 1
                if stats["real_new"] % 50 == 0:
                    save_json(MANIFEST_PATH, manifest)
                    save_json(CACHE_PATH, cache)
                    print(f"  ... {stats['real_new']} ảnh thật mới ({idx + 1}/{len(df)})")
                continue

        # 2) Fallback: ảnh theo danh mục (giữ ảnh cũ nếu đã có)
        stats["fallback"] += 1
        if target.exists() and not args.force:
            manifest.setdefault(sc, {"source": "category"})
            continue
        if templates is None:
            templates = download_category_templates()
        cat = get_category_for_description(desc)
        cat_imgs = templates.get(cat, [])
        if cat_imgs:
            h = int(hashlib.md5(sc.encode()).hexdigest(), 16)
            cat_imgs[h % len(cat_imgs)].save(target, format="JPEG", quality=85)
            manifest[sc] = {"source": "category"}
        else:
            create_product_card_image(desc, cat).save(target, format="JPEG", quality=85)
            manifest[sc] = {"source": "card"}

    save_json(MANIFEST_PATH, manifest)
    save_json(CACHE_PATH, cache)
    df["image_path"] = paths
    df.to_csv(config.PRODUCTS_PATH, index=False)

    total_real = stats["real_kept"] + stats["real_new"]
    print("=" * 60)
    print(f"Tổng sản phẩm             : {len(df):,}")
    print(f"Ảnh thật (giữ lại / mới)  : {stats['real_kept']:,} / {stats['real_new']:,}")
    print(f"Tỷ lệ có ảnh thật         : {total_real / len(df):.1%}")
    print(f"Ảnh minh họa theo danh mục: {stats['fallback']:,}")
    print(f"Số ảnh thật khác nhau     : {len(used):,}")
    print(f"-> Đã cập nhật: {config.PRODUCTS_PATH}")
    print(f"Thời gian                 : {time.time() - t0:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()