#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为每个物种采集图集：2 张野外摄影 + 1 张科学绘图 / 博物画。

数据来源：Wikimedia Commons
  - 摄影：Category:<学名>
  - 绘图：Category:<学名> (illustrations)，缺失时按别名 / 书名 / 人工清单回退

用法：
  python3 scripts/fetch_gallery.py            # 只处理还没有 gallery 的物种
  python3 scripts/fetch_gallery.py --force    # 全部重采
  python3 scripts/fetch_gallery.py <slug>...  # 指定物种
"""
import json, os, re, sys, time, urllib.parse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "assets", "img")
META_PATH = os.path.join(ROOT, "data", "assets.json")
OVERRIDE_PATH = os.path.join(ROOT, "data", "gallery_override.json")
PROXY = "http://127.0.0.1:9674"
UA = ("BirdGuideZhuhai/1.0 (non-commercial educational field guide; "
      "python-urllib; contact: geoff-birdguide@example.org)")

op = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
op.addheaders = [("User-Agent", UA), ("Referer", "https://commons.wikimedia.org/")]

# 学名变更后的旧名（Commons 分类多按旧名归档）
ALIAS = {
    "Turdus mandarinus": ["Turdus merula"],
    "Zosterops simplex": ["Zosterops japonicus"],
    "Gracupica nigricollis": ["Sturnus nigricollis"],
    "Charadrius alexandrinus": ["Anarhynchus alexandrinus"],
    "Saundersilarus saundersi": ["Larus saundersi"],
    "Apus nipalensis": ["Apus affinis"],
    "Spodiopsar sericeus": ["Sturnus sericeus"],
    "Bubulcus ibis": ["Ardeola ibis"],
}

PHOTO_BAD = ("map", "range", "distribution", "egg", "skull", "museum", "specimen",
             "skeleton", "nest with", "logo", "chart", "diagram", "graph", "poster",
             "stamp", "sign", "plate", "illustration", "drawing", "lithograph",
             "engraving", "woodcut", "painting", "taxidermy", "mount", "feather",
             "foot", "track", "dropping", "guano", "carcass", "dead", "window",
             "collision", "cage", "aviary", "zoo", "captive")

PLATE_GOOD = ("illustration", "plate", "lithograph", "drawing", "watercolour",
              "watercolor", "engraving", "woodcut", "sketch", "iconograph",
              "gould", "keulemans", "hardwicke", "wolf", "grønvold", "gronvold",
              "naturalis", "bhl", "wellcome", "painting", "art")


def api(base, params, tries=5):
    url = base + "?" + urllib.parse.urlencode(params)
    for i in range(tries):
        try:
            with op.open(url, timeout=50) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            code = getattr(e, "code", None)
            wait = 12 * (i + 1) if code == 429 else 3 * (i + 1)
            if i == tries - 1:
                print("   ! api fail", e)
                return {}
            time.sleep(wait)


def strip_html(s):
    import html as _h
    t = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", _h.unescape(t)).strip(" .;,")


def _collect(pages):
    out = []
    for p in (pages or {}).values():
        ii = p.get("imageinfo")
        if not ii:
            continue
        i = ii[0]
        mime = i.get("mime", "")
        if not mime.startswith("image/"):
            continue                      # 排除 pdf / djvu / 音视频
        if mime in ("image/svg+xml", "image/gif"):
            continue
        em = i.get("extmetadata", {})
        out.append({
            "title": p["title"][5:] if p["title"].startswith("File:") else p["title"],
            "url": i.get("thumburl") or i.get("url"),
            "w": i.get("width") or 0,
            "h": i.get("height") or 0,
            "credit": strip_html(em.get("Artist", {}).get("value", "")),
            "license": strip_html(em.get("LicenseShortName", {}).get("value", "")),
            "page": i.get("descriptionurl", ""),
        })
    return out


def cat_files(cat, limit=200):
    d = api("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "generator": "categorymembers",
        "gcmtitle": "Category:" + cat, "gcmtype": "file", "gcmlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1800"})
    return _collect(d.get("query", {}).get("pages"))


def subcats(cat, limit=60):
    d = api("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "list": "categorymembers",
        "cmtitle": "Category:" + cat, "cmtype": "subcat", "cmlimit": str(limit)})
    return [x["title"][9:] for x in d.get("query", {}).get("categorymembers", [])]


def cat_files_deep(cat, depth=2, cap=400):
    """分类本身常常只有子分类，向下钻一到两层。"""
    seen, out = set(), []
    def walk(c, d):
        if c in seen or len(out) >= cap or d < 0:
            return
        seen.add(c)
        got = cat_files(c, 500)
        out.extend(got)
        if len(out) < cap and d > 0:
            for sc in subcats(c, 40):
                if len(out) >= cap:
                    break
                walk(sc, d - 1)
    walk(cat, depth)
    return out


def search(q, limit=24):
    d = api("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": q, "gsrnamespace": "6", "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1800"})
    return _collect(d.get("query", {}).get("pages"))


def looks_plate(title):
    t = title.lower()
    return any(k in t for k in PLATE_GOOD)


def photo_score(c):
    t = c["title"].lower()
    if any(k in t for k in PHOTO_BAD):
        return -1
    if c["w"] < 1400 or c["h"] < 900:
        return -1
    ar = c["w"] / max(c["h"], 1)
    s = min(c["w"], 4000) / 400.0
    if 1.25 <= ar <= 1.85:
        s += 12
    elif 1.0 <= ar < 1.25 or 1.85 < ar <= 2.4:
        s += 5
    else:
        s -= 6
    return s


def plate_score(c):
    t = c["title"].lower()
    if c["w"] < 700 or c["h"] < 700:
        return -1
    # 明显是照片的排除
    if re.search(r"\.(jpe?g|png)$", t) and any(k in t for k in ("photograph", "photo by")):
        return -1
    s = min(c["w"], 4000) / 500.0
    s += 14 if looks_plate(c["title"]) else 0
    if "map" in t or "range" in t or "distribution" in t:
        s -= 60
    return s


def pick(species):
    """返回 (photos, plates) 两组候选，已排序。"""
    sci, en = species["sci"], species["en"]
    names = [sci] + ALIAS.get(sci, [])

    photos, plates = [], []
    seen = set()

    def add(target, items):
        for c in items:
            key = c["title"]
            if key in seen:
                continue
            seen.add(key)
            target.append(c)

    for n in names:
        add(photos, cat_files_deep(n))
    for n in names:
        add(plates, cat_files_deep(n + " (illustrations)", 0))
    if not plates:
        for n in names:
            add(plates, search('"%s" illustration' % n))
            add(plates, search('"%s" plate' % n))
        add(plates, search('"%s" illustration' % en))
        add(plates, search('"%s" Keulemans' % en))

    # 摄影打分
    ps = [(photo_score(c), c) for c in photos]
    ps = [x for x in ps if x[0] > 0]
    ps.sort(key=lambda x: -x[0])

    # 绘图打分
    qs = [(plate_score(c), c) for c in plates]
    qs = [x for x in qs if x[0] > 0]
    qs.sort(key=lambda x: -x[0])
    return [c for _, c in ps], [c for _, c in qs]


def relaxed_photos(species, need):
    """严格筛选凑不够时，从分类里按分辨率兜底。"""
    sci = species["sci"]
    pool = []
    for n in [sci] + ALIAS.get(sci, []):
        pool += cat_files_deep(n)
    ok = []
    for c in pool:
        t = c["title"].lower()
        if c["w"] < 900 or c["h"] < 600:
            continue
        if any(k in t for k in ("map", "range", "distribution", "egg", "skull",
                                "skeleton", "logo", "chart", "diagram", "stamp",
                                "spectrogram", "drawing", "illustration", "plate")):
            continue
        ar = c["w"] / max(c["h"], 1)
        score = min(c["w"], 5000) / 400.0 - (abs(ar - 1.5) * 8)
        ok.append((score, c))
    ok.sort(key=lambda x: -x[0])
    return [c for _, c in ok[:need]]


def download(url, path, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url)
            with op.open(req, timeout=120) as r, open(path, "wb") as f:
                f.write(r.read())
            return True
        except Exception as e:
            if i == tries - 1:
                print("   ! dl", e, url[:70])
                return False
            time.sleep(3 * (i + 1))


def to_webp(src, out_base, widths=(1600, 900)):
    from PIL import Image, ImageOps
    im = Image.open(src)
    im = ImageOps.exif_transpose(im).convert("RGB")
    res = {}
    for w in widths:
        im2 = im if im.width <= w else im.resize(
            (w, round(im.height * w / im.width)), Image.LANCZOS)
        p = "%s-%d.webp" % (out_base, w)
        im2.save(p, "WEBP", quality=82, method=6)
        res[w] = (os.path.basename(p), im2.width, im2.height)
    return res


def fetch_one(species, meta, overrides, force=False, photos_only=False):
    slug = species["slug"]
    entry = meta.setdefault(slug, {})
    if entry.get("gallery") and not force:
        return "skip"

    photos, plates = pick(species)
    hero_title = (entry.get("img") or {}).get("title", "")

    ov = overrides.get(slug, {})
    want_photos = ov.get("photos") or [c["title"] for c in photos]
    want_plates = ov.get("plates") or [c["title"] for c in plates]

    by_title = {c["title"]: c for c in photos + plates}

    def resolve(t):
        if t in by_title:
            return by_title[t]
        # 人工指定的文件名：直接按标题查
        d = api("https://commons.wikimedia.org/w/api.php", {
            "action": "query", "format": "json",
            "titles": t if t.startswith("File:") else "File:" + t,
            "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": "1800"})
        got = _collect(d.get("query", {}).get("pages"))
        if got:
            return got[0]
        got = search('intitle:"%s"' % t.replace('"', ''), 4)
        for c in got:
            if c["title"] == t:
                return c
        return None

    kept = []
    if photos_only:
        kept = [x for x in (entry.get("gallery") or []) if x["kind"] == "plate"]
        want_plates = []

    chosen = []
    used = {hero_title}
    # 严格筛选不足两张时，放宽条件补足
    if len(want_photos) < 2:
        for c in relaxed_photos(species, 6):
            if c["title"] not in want_photos:
                want_photos.append(c["title"])
                by_title[c["title"]] = c
    for t in want_photos:
        if len([x for x in chosen if x["kind"] == "photo"]) >= 2:
            break
        if t in used:
            continue
        c = resolve(t)
        if not c:
            continue
        used.add(t)
        chosen.append({**c, "kind": "photo"})
    for t in want_plates:
        if len([x for x in chosen if x["kind"] == "plate"]) >= 1:
            break
        c = resolve(t)
        if not c:
            continue
        used.add(t)
        item = {**c, "kind": "plate"}
        if ov.get("note"):
            item["note"] = ov["note"]
        chosen.append(item)

    if not chosen:
        return "empty"

    out = list(kept)
    n_p = 0
    for idx, c in enumerate(chosen, 1):
        tmp = "/var/tmp/g_%s_%d.jpg" % (slug, idx)   # 不删除：沙箱对每轮 unlink 有配额
        if not download(c["url"], tmp):
            continue
        if c["kind"] == "photo":
            n_p += 1
            stem = "%s-ph%d" % (slug, n_p)
        else:
            stem = "%s-plate" % slug
        try:
            res = to_webp(tmp, os.path.join(IMG_DIR, stem))
        except Exception as e:
            print("   ! conv", c["title"][:50], e)
            continue
        out.append({
            "card": res[900][0], "big": res[1600][0],
            "w": res[1600][1], "h": res[1600][2],
            "credit": c["credit"], "license": c["license"],
            "page": c["page"], "title": c["title"], "kind": c["kind"],
        })
    if not out:
        return "empty"
    entry["gallery"] = out
    n_photo = sum(1 for x in out if x["kind"] == "photo")
    n_plate = sum(1 for x in out if x["kind"] == "plate")
    return "ok %dP+%dI" % (n_photo, n_plate)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    force = "--force" in sys.argv
    photos_only = "--photos-only" in sys.argv

    species = json.load(open(os.path.join(ROOT, "data", "species.json")))
    meta = json.load(open(META_PATH))
    overrides = {}
    if os.path.exists(OVERRIDE_PATH):
        overrides = json.load(open(OVERRIDE_PATH))

    todo = [s for s in species if not args or s["slug"] in args]
    bad = []
    for i, sp in enumerate(todo, 1):
        r = fetch_one(sp, meta, overrides, force, photos_only)
        print("[%2d/%2d] %-6s %-24s %s" % (i, len(todo), sp["slug"], sp["sci"], r))
        if not r.startswith("ok"):
            bad.append((sp["slug"], sp["zh"], r))
        json.dump(meta, open(META_PATH, "w"), ensure_ascii=False, indent=1)

    json.dump(meta, open(META_PATH, "w"), ensure_ascii=False, indent=1)
    n_ok = sum(1 for s in species if len((meta.get(s["slug"], {}).get("gallery") or [])) >= 3)
    n_plate = sum(1 for s in species
                  if any(x["kind"] == "plate" for x in (meta.get(s["slug"], {}).get("gallery") or [])))
    print("\n图集齐备(>=3): %d/%d，含绘图: %d/%d" % (n_ok, len(species), n_plate, len(species)))
    if bad:
        print("待补：")
        for b in bad:
            print("   ", b)


if __name__ == "__main__":
    main()
