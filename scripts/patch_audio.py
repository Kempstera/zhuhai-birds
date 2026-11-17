#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为缺失鸣声的物种用异名/别名补抓录音。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_assets as fa

ROOT = fa.ROOT

ALIASES = {
    "wu-dong": ["Turdus merula", "Turdus mandarinus"],
    "an-lu-xiu-yan-niao": ["Zosterops japonicus", "Zosterops simplex"],
    "ba-ge": ["Acridotheres cristatellus"],
    "cha-wei-tai-yang-niao": ["Aethopyga christinae", "Aethopyga"],
    "chi-lu": ["Ardeola bacchus"],
    "hei-lian-pi-lu": ["Platalea minor"],
    "hei-zui-ou": ["Larus saundersi", "Saundersilarus saundersi", "Chroicocephalus saundersi"],
    "he-chi-ya-juan": ["Centropus sinensis"],
    "zao-juan": ["Eudynamys scolopaceus"],
}


def try_audio(queries):
    cands = []
    for q in queries:
        for mode in ('"%s" filetype:audio' % q, '%s filetype:audio' % q):
            d = fa.api("https://commons.wikimedia.org/w/api.php", {
                "action": "query", "format": "json", "generator": "search",
                "gsrsearch": mode, "gsrnamespace": "6", "gsrlimit": "25",
                "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata"})
            for p in d.get("query", {}).get("pages", {}).values():
                ii = p.get("imageinfo")
                if not ii:
                    continue
                i = ii[0]
                mime = i.get("mime", "")
                if not (mime.startswith("audio/") or mime == "application/ogg"):
                    continue
                em = i.get("extmetadata", {})
                try:
                    dur = float(em.get("Length", {}).get("value", 0))
                except Exception:
                    dur = 0
                cands.append({
                    "url": i.get("url"), "mime": mime,
                    "title": p.get("title", ""),
                    "page": i.get("descriptionurl", ""),
                    "artist": fa.strip_html(em.get("Artist", {}).get("value", "")),
                    "license": fa.strip_html(em.get("LicenseShortName", {}).get("value", "")),
                    "dur": dur,
                })

    # 去重
    seen, uniq = set(), []
    for c in cands:
        if c["url"] in seen:
            continue
        seen.add(c["url"])
        uniq.append(c)
    if not uniq:
        return None

    def sc(a):
        s = 0.0
        t = a["title"].lower()
        if a["mime"] == "audio/mpeg":
            s += 45
        if "song" in t:
            s += 10
        if a["dur"] and 8 <= a["dur"] <= 90:
            s += 15
        if "xeno" in t or "xc" in t:
            s += 8
        return s

    uniq.sort(key=lambda a: -sc(a))
    return uniq[0]


def main():
    species = json.load(open(os.path.join(ROOT, "data", "species.json")))
    meta = json.load(open(os.path.join(ROOT, "data", "assets.json")))
    todo = [s for s in species if not meta.get(s["slug"], {}).get("audio")]
    print("待补:", [s["zh"] for s in todo])

    for sp in todo:
        slug = sp["slug"]
        qs = ALIASES.get(slug) or [sp["sci"], sp["en"]]
        print(">>", slug, qs)
        a = try_audio(qs)
        if not a:
            print("   - 无结果")
            continue
        ext = ".mp3" if a["mime"] == "audio/mpeg" else ".ogg"
        tmp = "/var/tmp/bx_" + slug + ext
        if not fa.download(a["url"], tmp):
            continue
        info = fa.process_audio(tmp, slug)
        if info:
            info.update({"credit": a["artist"][:120], "license": a["license"],
                         "page": a["page"], "title": a["title"]})
            meta[slug]["audio"] = info
            json.dump(meta, open(os.path.join(ROOT, "data", "assets.json"), "w"),
                      ensure_ascii=False, indent=1)
            print("   + ok", a["title"][:70], info["dur"], "s")
        try:
            os.remove(tmp)
        except Exception:
            pass

    n = sum(1 for v in meta.values() if v.get("audio"))
    print("\n音频合计 %d/%d" % (n, len(species)))


if __name__ == "__main__":
    main()
