#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从维基共享资源采集鸟类图片与鸣声，本地化并压缩。"""
import json, os, re, subprocess, sys, time
import urllib.parse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "assets", "img")
AUD_DIR = os.path.join(ROOT, "assets", "audio")
META_PATH = os.path.join(ROOT, "data", "assets.json")
FFMPEG = "/var/tmp/birdtools/ff"
FFPROBE = "/var/tmp/birdtools/ffprobe"
PROXY = "http://127.0.0.1:9674"
UA = ("BirdGuideZhuhai/1.0 (non-commercial educational field guide; "
      "python-urllib; contact: geoff-birdguide@example.org)")

opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
opener.addheaders = [("User-Agent", UA)]

os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(AUD_DIR, exist_ok=True)


def api(base, params, tries=4):
    url = base + "?" + urllib.parse.urlencode(params)
    for i in range(tries):
        try:
            with opener.open(url, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == tries - 1:
                print("   ! api fail", e)
                return {}
            backoff(i, e)


def clean_url(u):
    u = re.sub(r"[?&]utm_[^&]*", "", u)
    u = u.replace("//thumb.wikimedia.org/", "//upload.wikimedia.org/")
    u = re.sub(r"/thumb/", "/thumb/", u)
    return u


def backoff(i, e):
    code = getattr(e, "code", None)
    if code == 429:
        wait = 12 * (i + 1)
    elif code and code >= 500:
        wait = 5 * (i + 1)
    else:
        wait = 2 * (i + 1)
    print("   . retry in %ds (%s)" % (wait, e))
    time.sleep(wait)


def download(url, path, tries=5):
    url = clean_url(url)
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": "https://commons.wikimedia.org/",
                "Accept": "image/avif,image/webp,image/*,audio/*,*/*"})
            with opener.open(req, timeout=180) as r:
                data = r.read()
            if len(data) < 2000:
                raise ValueError("too small %d" % len(data))
            with open(path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            if i == tries - 1:
                print("   ! dl fail", url[:90], e)
                return False
            backoff(i, e)
    return False


def strip_html(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = s.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    return re.sub(r"\s+", " ", s).strip()


# ---------- 图片 ----------
def wikidata_id(en_name):
    d = api("https://en.wikipedia.org/w/api.php", {
        "action": "query", "format": "json", "redirects": 1,
        "prop": "pageprops", "titles": en_name})
    for p in d.get("query", {}).get("pages", {}).values():
        qid = p.get("pageprops", {}).get("wikibase_item")
        if qid:
            return qid
    return None


def p18_file(qid):
    d = api("https://www.wikidata.org/w/api.php", {
        "action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"})
    try:
        c = d["entities"][qid]["claims"].get("P18")
        if c:
            return c[0]["mainsnak"]["datavalue"]["value"]
    except Exception:
        pass
    return None


def image_info(filename, width=1800):
    d = api("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "titles": "File:" + filename,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": width})
    for p in d.get("query", {}).get("pages", {}).values():
        ii = p.get("imageinfo")
        if not ii:
            continue
        i = ii[0]
        if not i.get("mime", "").startswith("image/"):
            return None
        em = i.get("extmetadata", {})
        return {
            "url": i.get("thumburl") or i.get("url"),
            "w": i.get("thumbwidth") or i.get("width"),
            "h": i.get("thumbheight") or i.get("height"),
            "page": i.get("descriptionurl", ""),
            "artist": strip_html(em.get("Artist", {}).get("value", "")),
            "license": strip_html(em.get("LicenseShortName", {}).get("value", "")),
            "title": filename,
        }
    return None


def search_commons_images(sci, en, limit=14):
    """候选图片，按可信度打分。"""
    out = []
    seen = set()
    queries = ['"%s"' % sci, sci, '"%s"' % en]
    for q in queries:
        d = api("https://commons.wikimedia.org/w/api.php", {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": q + " filetype:bitmap", "gsrnamespace": "6",
            "gsrlimit": str(limit), "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "1800"})
        for p in d.get("query", {}).get("pages", {}).values():
            t = p.get("title", "")
            if t in seen:
                continue
            seen.add(t)
            ii = p.get("imageinfo")
            if not ii:
                continue
            i = ii[0]
            if not i.get("mime", "").startswith("image/"):
                continue
            if (i.get("width") or 0) < 900:
                continue
            em = i.get("extmetadata", {})
            out.append({
                "url": i.get("thumburl") or i.get("url"),
                "w": i.get("width"), "h": i.get("height"),
                "page": i.get("descriptionurl", ""),
                "artist": strip_html(em.get("Artist", {}).get("value", "")),
                "license": strip_html(em.get("LicenseShortName", {}).get("value", "")),
                "title": t,
            })
    return out


def score(img, sci, en):
    s = 0.0
    t = img["title"].lower().replace("_", " ")
    bin_ = sci.lower().split()[1] if len(sci.split()) > 1 else ""
    gen = sci.lower().split()[0]
    if sci.lower() in t:
        s += 60
    if bin_ and bin_ in t:
        s += 25
    if gen in t:
        s += 12
    if en.lower() in t:
        s += 18
    if "map" in t or "range" in t or "distribution" in t or "egg" in t or "skull" in t or "museum" in t:
        s -= 90
    if "juvenile" in t or "subadult" in t:
        s -= 8
    ar = img["w"] / max(img["h"], 1)
    s += min(img["w"], 3000) / 400.0          # 分辨率加分
    if 1.1 <= ar <= 1.9:
        s += 10                                # 横向构图更适合作卡片
    return s


def pick_image(sci, en, qid):
    cands = []
    if qid:
        f = p18_file(qid)
        if f:
            ii = image_info(f)
            if ii:
                ii["title"] = f
                ii["_p18"] = True
                cands.append(ii)
    cands += search_commons_images(sci, en)
    if not cands:
        return None
    for c in cands:
        c["score"] = score(c, sci, en) + (1000 if c.get("_p18") else 0)
    cands.sort(key=lambda c: -c["score"])
    return cands[0]


# ---------- 音频 ----------
BAD_AUDIO = ("call", )  # 不排除，仅记录
def pick_audio(sci, en):
    cands = []
    for q in ['"%s" filetype:audio' % sci, '%s filetype:audio' % sci,
              '"%s" filetype:audio' % en]:
        d = api("https://commons.wikimedia.org/w/api.php", {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": q, "gsrnamespace": "6", "gsrlimit": "20",
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
            dur = 0
            try:
                dur = float(em.get("Length", {}).get("value", 0))
            except Exception:
                pass
            cands.append({
                "url": i.get("url"),
                "mime": mime,
                "title": p.get("title", ""),
                "page": i.get("descriptionurl", ""),
                "artist": strip_html(em.get("Artist", {}).get("value", "")),
                "license": strip_html(em.get("LicenseShortName", {}).get("value", "")),
                "dur": dur,
            })
    if not cands:
        return None, cands

    def sc(a):
        s = 0.0
        t = a["title"].lower()
        bin_ = sci.lower().split()[1] if len(sci.split()) > 1 else ""
        if sci.lower().replace(" ", "_") in t.replace(" ", "_"):
            s += 50
        if bin_ and bin_ in t:
            s += 20
        if a["mime"] == "audio/mpeg":
            s += 40          # 优先 mp3，浏览器兼容性最好
        if "song" in t:
            s += 8
        if a["dur"] and 8 <= a["dur"] <= 90:
            s += 14
        return s

    cands.sort(key=lambda a: -sc(a))
    return cands[0], cands


# ---------- 处理 ----------
def to_webp(src, out_base, widths=(1600, 900)):
    from PIL import Image, ImageOps
    im = Image.open(src)
    im = ImageOps.exif_transpose(im).convert("RGB")
    res = {}
    for w in widths:
        if im.width <= w:
            im2 = im
        else:
            h = round(im.height * w / im.width)
            im2 = im.resize((w, h), Image.LANCZOS)
        path = "%s-%d.webp" % (out_base, w)
        im2.save(path, "WEBP", quality=84, method=6)
        res[w] = os.path.basename(path)
    res["w"] = im2.width
    res["h"] = im2.height
    return res


def process_audio(src, slug):
    """转码一段野外录音。

    踩过的坑（2026-11 修）：
    1. 以前固定 `-ar 32000 -b:a 72k`，鸟鸣的泛音大多在 4–8kHz，等于直接削掉；
       现在统一 44.1kHz / 112k。
    2. 以前用单遍 `loudnorm=I=-18`。对安静的野外录音它会一口气加 20–30dB 增益，
       信噪比不变但底噪被抬到能听见的量级——乌鸫那一段就是这样变成「噪声里有个鸟」
       的（底噪 -18dBFS）。现在改成两遍 loudnorm，并在增益过大时按峰值封顶，
       宁可整体小声，也不要把噪声推上来。
    """
    out = os.path.join(AUD_DIR, slug + ".mp3")
    pre = ("silenceremove=start_periods=1:start_silence=0.25:"
           "start_threshold=-45dB,")

    # 第一遍：只测电平
    probe = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", src, "-af",
         pre + "loudnorm=I=-18:TP=-2:print_format=json", "-f", "null", "-"],
        capture_output=True)
    err = probe.stderr.decode(errors="ignore")
    try:
        import json as _json
        m = _json.loads(err[err.rfind("{"):])
        ln = ("loudnorm=I=-18:TP=-2:LRA=11:linear=true"
              ":measured_I=%s:measured_TP=%s:measured_LRA=%s"
              ":measured_thresh=%s:offset=%s" % (
                  m["input_i"], m["input_tp"], m["input_lra"],
                  m["input_thresh"], m["target_offset"]))
    except Exception:
        ln = "loudnorm=I=-18:TP=-2:LRA=11"   # 测不到就退回单遍

    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", src,
           "-af", pre + ln,
           "-t", "55", "-ac", "1", "-ar", "44100", "-b:a", "112k", out]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not os.path.exists(out):
        print("   ! audio conv fail", r.stderr.decode()[:200])
        return None
    dur = 0
    p = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", out], capture_output=True)
    try:
        dur = float(p.stdout.decode().strip())
    except Exception:
        dur = 0
    return {"file": os.path.basename(out), "dur": round(dur, 1),
            "kb": round(os.path.getsize(out) / 1024)}


def main():
    species = json.load(open(os.path.join(ROOT, "data", "species.json")))
    meta = {}
    if os.path.exists(META_PATH):
        meta = json.load(open(META_PATH))
    only = sys.argv[1:] if len(sys.argv) > 1 else None

    for sp in species:
        slug, sci, en = sp["slug"], sp["sci"], sp["en"]
        if only and slug not in only:
            continue
        if slug in meta and os.path.exists(meta[slug].get("img", {}).get("src", "")):
            print("skip", slug)
            continue
        print(">>", slug, sci)
        rec = {}
        qid = wikidata_id(en)
        img = pick_image(sci, en, qid)
        if img and img.get("url"):
            tmp = os.path.join("/var/tmp", "bi_" + slug + ".jpg")
            if download(img["url"], tmp):
                try:
                    info = to_webp(tmp, os.path.join(IMG_DIR, slug))
                    rec["img"] = {
                        "src": os.path.join(IMG_DIR, slug + "-1600.webp"),
                        "card": slug + "-900.webp",
                        "big": slug + "-1600.webp",
                        "w": info["w"], "h": info["h"],
                        "credit": img["artist"][:120],
                        "license": img["license"],
                        "page": img["page"],
                        "title": img["title"],
                    }
                except Exception as e:
                    print("   ! webp fail", e)
                finally:
                    try: os.remove(tmp)
                    except Exception: pass
        aud, _ = pick_audio(sci, en)
        if aud:
            ext = ".mp3" if aud["mime"] == "audio/mpeg" else ".ogg"
            tmp = os.path.join("/var/tmp", "ba_" + slug + ext)
            if download(aud["url"], tmp):
                a = process_audio(tmp, slug)
                if a:
                    a.update({"credit": aud["artist"][:120], "license": aud["license"],
                              "page": aud["page"], "title": aud["title"]})
                    rec["audio"] = a
                try: os.remove(tmp)
                except Exception: pass
        meta[slug] = rec
        json.dump(meta, open(META_PATH, "w"), ensure_ascii=False, indent=1)
        time.sleep(0.4)

    ok_i = sum(1 for v in meta.values() if v.get("img"))
    ok_a = sum(1 for v in meta.values() if v.get("audio"))
    print("\n== 完成: %d/%d 图片, %d/%d 音频 ==" % (ok_i, len(species), ok_a, len(species)))


if __name__ == "__main__":
    main()
