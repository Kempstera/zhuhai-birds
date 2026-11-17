#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重新为每个物种挑选「科学绘图」：先用缩略图打分，再下载最优者。

打分维度：
  fill   —— 裁掉纸白后，画面内容占整幅的比例（避免「大头留白」的扫描件）
  sat    —— 画面主体平均饱和度（彩版优于单色线描）
  res    —— 分辨率
  aspect —— 构图比例是否适合作竖向图版
标题里出现海报、报纸、地契、插图说明页等字样的直接排除。
"""
import json, os, re, sys, time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_gallery as fg
from trim_plates import trim
from PIL import Image, ImageOps

ROOT = fg.ROOT
IMG_DIR = os.path.join(ROOT, "assets", "img")
META_PATH = os.path.join(ROOT, "data", "assets.json")
THUMB_DIR = "/var/tmp/thumbs"

BAD_TITLE = (
    "cartell", "poster", "avis zona", "notes and news", "gartenlaube",
    "manuscript", "handschrift", "brief", "letter", "documento", "document",
    "bando", "manifesto", "advertisement", "anzeige", "titlepage",
    "title page", "cover", "index", "contents", "errata",
)

os.makedirs(THUMB_DIR, exist_ok=True)


def bad(title):
    t = title.lower()
    if any(k in t for k in BAD_TITLE):
        return True
    if re.search(r"\bpage\s*\d+", t):
        return True
    return False


def fetch_thumb(url, path):
    for i in range(4):
        try:
            with fg.op.open(url, timeout=60) as r, open(path, "wb") as f:
                f.write(r.read())
            return True
        except Exception:
            time.sleep(2 * (i + 1))
    return False


def metrics(path):
    try:
        im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    except Exception:
        return None
    fw, fh = im.size
    out, ok = trim(im)
    fill = (out.width * out.height) / float(fw * fh)
    small = out.copy()
    small.thumbnail((120, 120))
    hsv = small.convert("HSV")
    px = list(hsv.getdata())
    sat = [p[1] for p in px if p[2] > 40]
    mean_sat = sum(sat) / len(sat) if sat else 0
    ar = out.width / float(out.height)
    return {"fill": fill, "sat": mean_sat, "ar": ar,
            "w": fw, "h": fh, "trimmed": ok}


def score(m, w, h):
    if m is None:
        return -1
    s = 46 * min(m["fill"], 1.0)
    s += 26 * (m["sat"] / 110.0)
    s += 14 * min(min(w, 3500), 3500) / 3500.0
    ar = m["ar"]
    if 0.55 <= ar <= 1.05:
        s += 8
    elif 1.05 < ar <= 1.7:
        s += 4
    elif ar < 0.35 or ar > 2.4:
        s -= 12
    return s


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    species = json.load(open(os.path.join(ROOT, "data", "species.json")))
    meta = json.load(open(META_PATH))
    overrides = {}
    p = os.path.join(ROOT, "data", "gallery_override.json")
    if os.path.exists(p):
        overrides = json.load(open(p))

    # 全站已用的图版标题：避免两个物种配到同一张图
    used = {}
    for k, v in meta.items():
        for g in (v.get("gallery") or []):
            if g.get("kind") == "plate":
                used.setdefault(g["title"], k)

    # 人工排除清单
    ban = {}
    bp = os.path.join(ROOT, "data", "plate_exclude.json")
    if os.path.exists(bp):
        ban = json.load(open(bp))

    for i, sp in enumerate(species, 1):
        slug = sp["slug"]
        if only and slug not in only:
            continue

        # 候选池
        pool = []
        for n in [sp["sci"]] + fg.ALIAS.get(sp["sci"], []):
            pool += fg.cat_files_deep(n + " (illustrations)", 0)
        if not pool:
            for n in [sp["sci"]] + fg.ALIAS.get(sp["sci"], []):
                pool += fg.search('"%s" illustration' % n, 20)
        forced = (overrides.get(slug) or {}).get("plates")
        blk = set(ban.get(slug, []))
        pool = [c for c in pool
                if c["w"] >= 700 and c["h"] >= 700
                and not bad(c["title"])
                and c["title"] not in blk
                and used.get(c["title"], slug) == slug]
        # 去重
        seen, cand = set(), []
        for c in pool:
            if c["title"] in seen:
                continue
            seen.add(c["title"])
            cand.append(c)
        if forced:
            got = []
            for t in forced:
                d = fg.api("https://commons.wikimedia.org/w/api.php", {
                    "action": "query", "format": "json", "titles": t,
                    "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
                    "iiurlwidth": "1800"})
                got += fg._collect(d.get("query", {}).get("pages"))
            if got:
                cand = got
            else:
                print("[%2d] %-22s 人工指定文件未找到，改用自动挑选" % (i, slug))
        if not cand:
            print("[%2d] %-22s 无可用候选" % (i, slug))
            continue
        cand.sort(key=lambda c: -(c["w"] * c["h"]))
        cand = cand[:8]

        best, best_s = None, -1e9
        for j, c in enumerate(cand):
            tp = os.path.join(THUMB_DIR, "%s_%d.jpg" % (slug, j))
            if not fetch_thumb(c["url"], tp):
                continue
            m = metrics(tp)
            if m is None or m["fill"] < 0.22:
                continue
            sc = score(m, c["w"], c["h"])
            if sc > best_s:
                best, best_s = (c, m, j), sc
        if not best:
            print("[%2d] %-22s 打分失败，保留原图" % (i, slug))
            continue

        c, m, j = best
        tmp = "/var/tmp/plate_%s.jpg" % slug
        if not fg.download(c["url"], tmp):
            print("[%2d] %-22s 下载失败" % (i, slug))
            continue
        im = ImageOps.exif_transpose(Image.open(tmp)).convert("RGB")
        im, _ = trim(im)
        res = {}
        for w in (1600, 900):
            im2 = im if im.width <= w else im.resize(
                (w, round(im.height * w / im.width)), Image.LANCZOS)
            dst = os.path.join(IMG_DIR, "%s-plate-%d.webp" % (slug, w))
            im2.save(dst, "WEBP", quality=84, method=6)
            res[w] = im2.size
        gal = meta[slug].setdefault("gallery", [])
        # 替换或插入 plate 项（plate 永远排第一）
        item = {
            "card": "%s-plate-900.webp" % slug, "big": "%s-plate-1600.webp" % slug,
            "w": res[1600][0], "h": res[1600][1],
            "credit": c["credit"], "license": c["license"],
            "page": c["page"], "title": c["title"], "kind": "plate",
        }
        if (overrides.get(slug) or {}).get("note"):
            item["note"] = overrides[slug]["note"]
        others = [g for g in gal if g.get("kind") != "plate"]
        meta[slug]["gallery"] = [item] + others
        used[c["title"]] = slug
        json.dump(meta, open(META_PATH, "w"), ensure_ascii=False, indent=1)
        print("[%2d] %-22s fill=%.2f sat=%.0f -> %s" % (i, slug, m["fill"], m["sat"], c["title"][:58]))

    n = sum(1 for s in species if any(g.get("kind") == "plate" for g in (meta.get(s["slug"], {}).get("gallery") or [])))
    print("\n含绘图: %d/%d" % (n, len(species)))


if __name__ == "__main__":
    main()
