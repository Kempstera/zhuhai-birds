#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 iNaturalist 抓取开放许可的物种录音，替换缺失或配错的条目。"""
import json, os, subprocess, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_assets as fa

ROOT = fa.ROOT
API = "https://api.inaturalist.org/v1/observations"
FFMPEG, FFPROBE = fa.FFMPEG, fa.FFPROBE

TARGETS = [
    "wu-dong", "an-lu-xiu-yan-niao", "cha-wei-tai-yang-niao", "ba-ge",
    "chi-lu", "hei-lian-pi-lu", "hei-zui-ou", "pu-tong-kuang",
    "xiao-pi-ti", "bai-tou-bei", "hei-shui-ji", "huan-jing-heng",
]

LIC = {
    "cc0": "CC0", "cc-by": "CC BY", "cc-by-nc": "CC BY-NC",
    "cc-by-sa": "CC BY-SA", "cc-by-nc-sa": "CC BY-NC-SA",
    "cc-by-nd": "CC BY-ND", "cc-by-nc-nd": "CC BY-NC-ND",
}


def get(url):
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": fa.UA, "Accept": "application/json"})
    with fa.opener.open(req, timeout=45) as r:
        return json.loads(r.read().decode())


def candidates(sci):
    q = urllib.parse.quote(sci)
    url = (API + "?taxon_name=%s&sounds=true&per_page=30&order_by=votes"
           "&quality_grade=research" % q)
    try:
        d = get(url)
    except Exception as e:
        print("   ! api", e)
        return []
    out = []
    for o in d.get("results", []):
        lic = (o.get("license_code") or "").lower()
        if lic not in LIC:
            continue
        for s in (o.get("sounds") or []):
            u = s.get("file_url")
            if not u:
                continue
            out.append({
                "url": u,
                "license": LIC[lic],
                "user": (o.get("user") or {}).get("login", ""),
                "page": "https://www.inaturalist.org/observations/%s" % o.get("id"),
                "votes": len(o.get("faves") or []) + len(o.get("votes") or []),
                "ext": os.path.splitext(u.split("?")[0])[1].lower(),
            })
    return out


def dur_of(path):
    p = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True)
    try:
        return float(p.stdout.decode().strip())
    except Exception:
        return 0.0


def convert(src, slug):
    out = os.path.join(fa.AUD_DIR, slug + ".mp3")
    if os.path.exists(out):
        os.remove(out)
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", src,
           "-t", "58", "-ac", "1", "-ar", "32000", "-b:a", "72k",
           "-af", "loudnorm=I=-18:TP=-2:LRA=11,afade=t=out:st=55:d=3",
           out]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not os.path.exists(out):
        print("   ! conv", r.stderr.decode()[:160])
        return None
    return {"file": os.path.basename(out), "dur": round(dur_of(out), 1),
            "kb": round(os.path.getsize(out) / 1024)}


def main():
    species = {s["slug"]: s for s in json.load(open(os.path.join(ROOT, "data", "species.json")))}
    meta = json.load(open(os.path.join(ROOT, "data", "assets.json")))
    todo = sys.argv[1:] or TARGETS

    for slug in todo:
        sp = species[slug]
        print(">>", slug, sp["sci"])
        cands = candidates(sp["sci"])
        if not cands:
            print("   - iNat 无候选")
            continue
        # 优先 mp3，其次按票数
        cands.sort(key=lambda c: (c["ext"] != ".mp3", -c["votes"]))
        picked = None
        for c in cands[:8]:
            tmp = "/var/tmp/inat_" + slug + (c["ext"] or ".mp3")
            if not fa.download(c["url"], tmp):
                continue
            d = dur_of(tmp)
            if 4 <= d <= 300:
                picked = (c, tmp, d)
                print("   · 候选 %s %.1fs %s" % (c["ext"], d, c["license"]))
                break
            else:
                print("   · 跳过 %s %.1fs（时长不合适）" % (c["ext"], d))
            try:
                os.remove(tmp)
            except Exception:
                pass
        if not picked:
            print("   - 无合适录音")
            continue
        c, tmp, d = picked
        info = convert(tmp, slug)
        if info:
            info.update({
                "credit": ("iNaturalist 用户 %s" % c["user"]) if c["user"] else "iNaturalist 贡献者",
                "license": c["license"],
                "page": c["page"],
                "title": "%s（iNaturalist 野外录音）" % sp["sci"],
            })
            meta.setdefault(slug, {})["audio"] = info
            json.dump(meta, open(os.path.join(ROOT, "data", "assets.json"), "w"),
                      ensure_ascii=False, indent=1)
            print("   + ok %.1fs %dKB %s" % (info["dur"], info["kb"], c["license"]))
        try:
            os.remove(tmp)
        except Exception:
            pass

    n = sum(1 for v in meta.values() if v.get("audio"))
    print("\n音频合计 %d/%d" % (n, len(species)))


if __name__ == "__main__":
    main()
