#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""裁掉图版扫描件的空白边距，重新导出 1600 / 900 两档。

古登堡/博物馆扫描的图版常带大片纸白，直接放进网格会显得图很小。
这里以四角颜色估计纸张底色，取与之差异明显的包围盒，留一点安全边。
"""
import json, os, sys
from PIL import Image, ImageChops, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "assets", "img")
META_PATH = os.path.join(ROOT, "data", "assets.json")

PAD_RATIO = 0.012      # 保留一点呼吸空间
BG_TOL = 16            # 与纸张底色的最小差异
MIN_KEEP = 0.15        # 裁得比这更狠就认为判断失误，放弃
MAX_KEEP = 0.985       # 几乎没裁到就不动


def paper_color(im):
    """取四角小块的中位色，作为纸张底色估计。"""
    w, h = im.size
    s = max(8, int(min(w, h) * 0.06))
    px = []
    for box in [(0, 0, s, s), (w - s, 0, w, s), (0, h - s, s, h), (w - s, h - s, w, h)]:
        px.append(im.crop(box).resize((1, 1), Image.BOX).getpixel((0, 0)))
    px.sort(key=lambda c: sum(c))
    return px[len(px) // 2]


def trim(im):
    bg = paper_color(im)
    diff = ImageChops.difference(im, Image.new("RGB", im.size, bg))
    mask = diff.convert("L").point(lambda p: 255 if p > BG_TOL else 0)
    # 轻微膨胀，避免把画框边裁掉
    try:
        from PIL import ImageFilter
        mask = mask.filter(ImageFilter.MaxFilter(9))
    except Exception:
        pass
    bbox = mask.getbbox()
    if not bbox:
        return im, False
    w, h = im.size
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if bw * bh < MIN_KEEP * w * h or bw * bh > MAX_KEEP * w * h:
        return im, False
    pad = int(min(bw, bh) * PAD_RATIO)
    box = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
           min(w, bbox[2] + pad), min(h, bbox[3] + pad))
    return im.crop(box), True


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    meta = json.load(open(META_PATH))
    done = changed = 0
    for slug, entry in meta.items():
        if only and slug not in only:
            continue
        gal = entry.get("gallery") or []
        for i, g in enumerate(gal):
            if g.get("kind") != "plate":
                continue
            p = os.path.join(IMG_DIR, g["big"])
            if not os.path.exists(p):
                print("  miss", p)
                continue
            im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
            out, ok = trim(im)
            done += 1
            if not ok:
                print("  - %-22s 保留原样 %dx%d" % (slug, im.width, im.height))
                continue
            changed += 1
            for w in (1600, 900):
                im2 = out if out.width <= w else out.resize(
                    (w, round(out.height * w / out.width)), Image.LANCZOS)
                dst = os.path.join(IMG_DIR, "%s-g%d-%d.webp" % (slug, i + 1, w))
                im2.save(dst, "WEBP", quality=84, method=6)
                if w == 1600:
                    g["w"], g["h"] = im2.width, im2.height
            print("  + %-22s %dx%d -> %dx%d" % (slug, im.width, im.height, out.width, out.height))
    json.dump(meta, open(META_PATH, "w"), ensure_ascii=False, indent=1)
    print("\n处理 %d 张，裁边 %d 张" % (done, changed))


if __name__ == "__main__":
    main()
