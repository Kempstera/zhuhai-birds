#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为指定物种抓一批候选照片，渲染成对照表（contact sheet）供人工挑选。

用法：
  python3 scripts/probe_photos.py <slug> [<slug> ...]
  python3 scripts/probe_photos.py --query "Amaurornis phoenicurus"   # 临时查询

输出：/var/tmp/cand/<slug>/000.jpg ... 以及 /var/tmp/cand/sheet<N>.html
随后用 node /var/tmp/shot/cand.js 截图。
"""
import json, os, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = "/var/tmp/cand"
PROXY = "http://127.0.0.1:9674"
UA = ("BirdGuideZhuhai/1.0 (non-commercial educational field guide; "
      "python-urllib; contact: geoff-birdguide@example.org)")

op = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
op.addheaders = [("User-Agent", UA), ("Referer", "https://commons.wikimedia.org/")]

BAD = ("map", "range", "distribution", "egg", "skull", "museum", "specimen",
       "skeleton", "logo", "chart", "diagram", "graph", "poster", "stamp",
       "sign", "plate", "illustration", "drawing", "lithograph", "engraving",
       "woodcut", "painting", "taxidermy", "feather", "track", "carcass",
       "dead", "cage", "aviary", "zoo", "captive", "nest", "chick", "habitat",
       "biotope", "landscape", "forest", "panorama", "skyline")

PER = 8          # 每个物种展示的候选数


def api(params, tries=4):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    for i in range(tries):
        try:
            with op.open(url, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == tries - 1:
                print("  ! api", e)
                return {}
            time.sleep(6 * (i + 1))


def candidates(q, limit=40):
    d = api({"action": "query", "format": "json", "generator": "search",
             "gsrsearch": q + " filetype:bitmap", "gsrnamespace": "6",
             "gsrlimit": str(limit), "prop": "imageinfo",
             "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "520"})
    out = []
    for p in (d.get("query", {}).get("pages") or {}).values():
        ii = p.get("imageinfo")
        if not ii:
            continue
        i = ii[0]
        if not i.get("mime", "").startswith("image/"):
            continue
        t = p["title"][5:] if p["title"].startswith("File:") else p["title"]
        tl = t.lower()
        if any(k in tl for k in BAD):
            continue
        if i.get("width", 0) < 1000 or i.get("height", 0) < 700:
            continue
        em = i.get("extmetadata", {})
        out.append({
            "title": t, "thumb": i.get("thumburl"),
            "w": i["width"], "h": i["height"],
            "page": i.get("descriptionurl", ""),
            "credit": (em.get("Artist", {}).get("value", "") or ""),
            "license": (em.get("LicenseShortName", {}).get("value", "") or ""),
        })
    # 分辨率高的排前面
    out.sort(key=lambda c: -min(c["w"], 5000))
    return out[:limit]


def grab(url, path, tries=3):
    for i in range(tries):
        try:
            with op.open(url, timeout=60) as r, open(path, "wb") as f:
                f.write(r.read())
            return True
        except Exception:
            time.sleep(2 * (i + 1))
    return False


def main():
    slugs = [a for a in sys.argv[1:] if not a.startswith("-")]
    tag = ""
    for a in sys.argv[1:]:
        if a.startswith("--tag="):
            tag = "_" + a.split("=", 1)[1]
    species = json.load(open(os.path.join(ROOT, "data", "species.json")))
    by_slug = {s["slug"]: s for s in species}
    os.makedirs(OUT, exist_ok=True)

    rows = []
    for slug in slugs:
        q_override = None
        if "::" in slug:
            slug, q_override = slug.split("::", 1)
        s = by_slug.get(slug)
        if not s:
            print("未知 slug", slug)
            continue
        q = q_override or ('"%s"' % s["sci"])
        cands = candidates(q, PER * 3)
        # 里氏替换：标题里出现别的鸟种名（且不是本种）的剔除
        d = os.path.join(OUT, slug)
        if not os.path.isdir(d):
            os.makedirs(d)
        picked = []
        for c in cands:
            if len(picked) >= PER:
                break
            p = os.path.join(d, "%03d.jpg" % len(picked))
            if grab(c["thumb"], p):
                picked.append(c)
        json.dump(picked, open(os.path.join(d, "cands.json"), "w"),
                  ensure_ascii=False, indent=1)
        rows.append((s, picked))
        print("%-24s %d 候选" % (slug, len(picked)))

    # 每 6 个物种一页
    for page in range(0, len(rows), 6):
        chunk = rows[page:page + 6]
        html = ['<html><head><meta charset="utf-8"><style>',
                'body{background:#fff;font:12px -apple-system,"PingFang SC",sans-serif;margin:0;padding:10px}',
                'table{border-collapse:collapse}',
                'td{padding:3px;border:1px solid #ddd;text-align:center;vertical-align:top;width:150px}',
                'img{height:130px;max-width:146px;object-fit:contain;display:block;margin:0 auto}',
                '.n{font-weight:700;color:#b3261e}',
                '.t{color:#666;font-size:9px;line-height:1.15;word-break:break-all;height:22px;overflow:hidden}',
                'th{text-align:left;font-size:13px;padding:4px;background:#f4f4f4}',
                '</style></head><body><table>']
        for s, picked in chunk:
            html.append('<tr><th colspan="%d">%s &nbsp;%s &nbsp;<span style="color:#888">%s</span></th></tr>'
                        % (PER, s["zh"], s["slug"], s["sci"]))
            html.append('<tr>')
            for k, c in enumerate(picked):
                html.append('<td><div class="n">#%d</div>'
                            '<img src="%s/%s/%03d.jpg"><div class="t">%s</div></td>'
                            % (k, OUT, s["slug"], k, c["title"][:52]))
            for _ in range(PER - len(picked)):
                html.append('<td>—</td>')
            html.append('</tr>')
        html.append('</table></body></html>')
        p = os.path.join(OUT, "sheet%s%d.html" % (tag, page // 6))
        open(p, "w").write("".join(html))
        print("->", p)


if __name__ == "__main__":
    main()
