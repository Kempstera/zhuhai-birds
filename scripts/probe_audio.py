#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测指定物种在 Commons 上的全部音频候选。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_assets as fa

TARGETS = {
    "wu-dong": ["Turdus mandarinus", "Chinese Blackbird", "Turdus merula"],
    "an-lu-xiu-yan-niao": ["Zosterops simplex", "Zosterops japonicus", "Japanese White-eye"],
    "cha-wei-tai-yang-niao": ["Aethopyga christinae", "Fork-tailed Sunbird"],
    "ba-ge": ["Acridotheres cristatellus", "Crested Myna"],
    "chi-lu": ["Ardeola bacchus", "Chinese Pond Heron"],
    "hei-lian-pi-lu": ["Platalea minor", "Black-faced Spoonbill"],
    "hei-zui-ou": ["Saundersilarus saundersi", "Larus saundersi", "Saunders's Gull"],
    "pu-tong-kuang": ["Buteo japonicus", "Eastern Buzzard", "Buteo buteo"],
    "xiao-pi-ti": ["Tachybaptus ruficollis", "Little Grebe"],
    "bai-tou-bei": ["Pycnonotus sinensis", "Light-vented Bulbul"],
    "hei-shui-ji": ["Gallinula chloropus", "Common Moorhen"],
    "huan-jing-heng": ["Charadrius alexandrinus", "Kentish Plover"],
}


def search(q, extra=""):
    out = []
    for mode in ('"%s" filetype:audio' % q, q + " filetype:audio", 'incategory:"%s" filetype:audio' % q):
        d = fa.api("https://commons.wikimedia.org/w/api.php", {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": mode, "gsrnamespace": "6", "gsrlimit": "30",
            "prop": "imageinfo", "iiprop": "url|mime|extmetadata"})
        for p in d.get("query", {}).get("pages", {}).values():
            ii = p.get("imageinfo")
            if not ii:
                continue
            i = ii[0]
            if not (i.get("mime", "").startswith("audio/") or i.get("mime") == "application/ogg"):
                continue
            em = i.get("extmetadata", {})
            try:
                dur = float(em.get("Length", {}).get("value", 0))
            except Exception:
                dur = 0
            out.append((p.get("title", ""), i.get("mime"), round(dur, 1),
                        fa.strip_html(em.get("LicenseShortName", {}).get("value", ""))))
    seen, uniq = set(), []
    for t in out:
        if t[0] in seen:
            continue
        seen.add(t[0])
        uniq.append(t)
    return uniq


for slug, qs in TARGETS.items():
    print("\n=== %s ===" % slug)
    allr = []
    for q in qs:
        allr += search(q)
    seen = set()
    for t in allr:
        if t[0] in seen:
            continue
        seen.add(t[0])
        print("  %6.1fs %-22s %s" % (t[2], t[1], t[0][:80]))
