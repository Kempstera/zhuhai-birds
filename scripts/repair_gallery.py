#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复图版与照片共用文件名的问题。

pick_plates 早期把图版写到 <slug>-g1-*.webp，而该位置原本是第一张照片，
导致详情页出现「同一张图重复两次」。这里：
  1. 把图版文件改名为 <slug>-plate-*
  2. 按记录的标题重新下载被覆盖的第一张照片，存为 <slug>-ph1-*
"""
import json, os, sys, time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_gallery as fg
from PIL import Image, ImageOps

ROOT = fg.ROOT
IMG_DIR = os.path.join(ROOT, "assets", "img")
META_PATH = os.path.join(ROOT, "data", "assets.json")


def big_by_title(title):
    d = fg.api("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json",
        "titles": title if title.startswith("File:") else "File:" + title,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1800"})
    got = fg._collect(d.get("query", {}).get("pages"))
    return got[0] if got else None


def export(im, base):
    res = {}
    for w in (1600, 900):
        im2 = im if im.width <= w else im.resize(
            (w, round(im.height * w / im.width)), Image.LANCZOS)
        p = "%s-%d.webp" % (base, w)
        im2.save(p, "WEBP", quality=82, method=6)
        res[w] = (os.path.basename(p), im2.width, im2.height)
    return res


def main():
    meta = json.load(open(META_PATH))
    fixed = 0
    for slug, entry in meta.items():
        gal = entry.get("gallery") or []
        if not gal:
            continue
        plate = next((g for g in gal if g.get("kind") == "plate"), None)
        if not plate:
            continue

        old_card = plate["card"]          # 改名前的文件名，用来识别冲突
        # 1) 图版改名，避开 g1..g3 的命名空间
        src = os.path.join(IMG_DIR, plate["big"])
        if os.path.exists(src) and not plate["big"].startswith("%s-plate" % slug):
            im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
            res = export(im, os.path.join(IMG_DIR, "%s-plate" % slug))
            plate["card"] = res[900][0]
            plate["big"] = res[1600][0]
            plate["w"], plate["h"] = res[1600][1], res[1600][2]

        # 2) 重下被覆盖的照片（card 与原图版相同）
        for idx, g in enumerate(gal):
            if g.get("kind") != "photo" or g["card"] != old_card:
                continue
            c = big_by_title(g["title"])
            if not c:
                print("  ! %-22s 找不到 %s" % (slug, g["title"][:40]))
                continue
            tmp = "/var/tmp/rp_%s.jpg" % slug
            if not fg.download(c["url"], tmp):
                continue
            im = ImageOps.exif_transpose(Image.open(tmp)).convert("RGB")
            res = export(im, os.path.join(IMG_DIR, "%s-ph%d" % (slug, idx + 1)))
            g["card"] = res[900][0]
            g["big"] = res[1600][0]
            g["w"], g["h"] = res[1600][1], res[1600][2]
            g["credit"] = c["credit"] or g.get("credit")
            g["license"] = c["license"] or g.get("license")
            fixed += 1
            print("  + %-22s 重下照片 %s" % (slug, g["title"][:44]))
        json.dump(meta, open(META_PATH, "w"), ensure_ascii=False, indent=1)
    print("\n修复 %d 张照片" % fixed)


if __name__ == "__main__":
    main()
