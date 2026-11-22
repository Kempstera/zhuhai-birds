#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量重制鸟鸣录音：先在原来源里找高清版，找不到就换一段更好的。

判据是信噪比（50ms 分帧，p90-p10 帧能量差），不是「听起来还行」。

每条的处理：
  1. 用 assets.json 里记的 page 找回原始文件（iNat 走 observations API，
     Commons 走 imageinfo），下载到 /var/tmp/audio_src 缓存
  2. 原件重制一版（两遍 loudnorm + 高通），量 SNR
  3. 若原件版没有提升（iNat 的手机录音本身就是 64k，换来换去一样烂），
     就按学名搜同物种的其他录音，挑 SNR 最高的候选再试
  4. 只有新版本比线上那份好 3dB 以上才替换，否则原样不动

用法:
  python3 scripts/remaster_batch.py --below 8          # 体检分低于 8dB 的全做
  python3 scripts/remaster_batch.py --slugs a,b,c      # 指定几条
  python3 scripts/remaster_batch.py --below 8 --dry    # 只报告不写入
"""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import urllib.parse
import wave
from array import array

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_assets as fa

ROOT = fa.ROOT
FF = fa.FFMPEG
FFPROBE = fa.FFPROBE
AUD = os.path.join(ROOT, "assets", "audio")
SRC = "/var/tmp/audio_src"
TMP = "/var/tmp/batch_tmp"
ASSETS = os.path.join(ROOT, "data", "assets.json")

# 高通按类群给：鹬鸻类在海边录，低频全是浪和风，叫声在 2kHz 以上，
# 130Hz 的高通根本挡不住；鸣禽 250 足够；涉禽/鸭类叫声本来就低，别切狠了。
# 第二个数字是高通级数：海岸录音的低频能压过叫声本身，一级 12dB/oct 压不住，
# 鹬鸻类用两级（24dB/oct）才把浪声甩到叫声下面。
HP_BY_GROUP = {"shore": (700, 2), "kingfisher": (500, 1), "raptor": (300, 1),
               "songbird": (250, 1), "water": (150, 1)}
HP_DEFAULT = (250, 1)
TARGET_I = -16.0
TARGET_TP = -1.5
MAX_SEC = 55
MIN_GAIN_DB = 3.0         # 至少要好 3dB 才替换
MIN_NEW_SNR = 8.0         # 新版本至少要过这条线


# ---------- 测量 ----------


def metrics(path):
    """返回 (SNR dB, 峰值 dBFS, 时长 s)。

    用 ffmpeg 把音频解成裸 PCM 走 stdout，不落临时文件——
    早先版本用 afconvert 写 wav 再删，循环几十次会撞上沙箱的批量删除确认。
    """
    r = subprocess.run([FF, "-v", "error", "-i", path, "-f", "s16le",
                        "-ac", "1", "-ar", "16000", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    a = array("h")
    a.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    if not len(a):
        return None
    sr = 16000
    step = int(sr * 0.05)
    fr = []
    for i in range(0, len(a) - step + 1, step):
        s = 0
        for v in a[i:i + step]:
            s += v * v
        fr.append(math.sqrt(s / step) / 32768.0)
    if len(fr) < 4:
        return None
    fr.sort()
    db = lambda x: 20 * math.log10(max(x, 1e-9))
    peak = max(max(a), -min(a)) / 32768.0
    snr = db(fr[min(len(fr) - 1, int(len(fr) * 0.90))]) - db(fr[int(len(fr) * 0.10)])
    return snr, db(peak), len(a) / sr


# ---------- 取源 ----------


def cached(url):
    ext = os.path.splitext(url.split("?")[0])[1].lower() or ".mp3"
    key = hashlib.md5(url.encode()).hexdigest()[:10]
    dst = os.path.join(SRC, key + ext)
    if os.path.exists(dst) and os.path.getsize(dst) > 2048:
        return dst
    with fa.opener.open(url, timeout=180) as r, open(dst, "wb") as f:
        f.write(r.read())
    return dst


def from_inat(page):
    m = re.search(r"observations/(\d+)", page)
    if not m:
        return []
    d = fa.api("https://api.inaturalist.org/v1/observations/" + m.group(1), {})
    out = []
    for o in d.get("results", []):
        for s in o.get("sounds", []):
            if s.get("file_url"):
                out.append({"url": s["file_url"], "keep": True})
    return out


def from_commons(page):
    title = urllib.parse.unquote(page.split("/wiki/")[-1])
    d = fa.api("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "titles": title,
        "prop": "imageinfo", "iiprop": "url|size"})
    out = []
    for p in (d.get("query") or {}).get("pages", {}).values():
        for ii in p.get("imageinfo", []):
            if ii.get("url"):
                out.append({"url": ii["url"], "keep": True})
    return out


def search_inat(sci, limit=8):
    # 注意 fa.api(base, params) 会自己拼 "?"+urlencode，base 不能再带查询串
    d = fa.api("https://api.inaturalist.org/v1/observations", {
        "taxon_name": sci, "sounds": "true", "per_page": str(limit),
        "order_by": "votes", "quality_grade": "research"})
    out = []
    for o in d.get("results", []):
        for s in o.get("sounds", []):
            if not s.get("file_url"):
                continue
            out.append({
                "url": s["file_url"],
                "keep": False,
                "license": s.get("license_code") or "",
                "credit": "iNaturalist 用户 " + (o.get("user") or {}).get("login", ""),
                "page": "https://www.inaturalist.org/observations/%s" % o["id"],
                "title": "%s（iNaturalist 野外录音）"
                         % (o.get("taxon") or {}).get("name", sci),
            })
    return out


AUDIO_EXT = (".mp3", ".ogg", ".oga", ".wav", ".flac", ".m4a", ".mpga")


def search_commons(sci, limit=8):
    # 学名加引号会跟 filetype: 打架（实测 0 结果），这里不加引号
    d = fa.api("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": '%s filetype:audio' % sci, "gsrnamespace": "6",
        "gsrlimit": str(limit), "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata"})
    out = []
    for p in (d.get("query") or {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        u = str(ii.get("url", ""))
        if not u.lower().endswith(AUDIO_EXT):
            continue
        em = ii.get("extmetadata", {})
        out.append({
            "url": u,
            "keep": False,
            "license": em.get("LicenseShortName", {}).get("value", ""),
            "credit": re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", "")),
            "page": "https://commons.wikimedia.org/wiki/"
                    + urllib.parse.quote(p["title"].replace(" ", "_")),
            "title": p["title"].replace("File:", ""),
        })
    return out


# ---------- 重制 ----------


def remaster(src, dst, hp=HP_DEFAULT):
    pre = "silenceremove=start_periods=1:start_silence=0.25:start_threshold=-45dB,"
    freq, stages = hp if isinstance(hp, tuple) else (hp, 1)
    if freq:
        pre += ("highpass=f=%d:poles=2," % freq) * stages
    r = subprocess.run([FF, "-hide_banner", "-i", src, "-af",
                        pre + "loudnorm=I=%s:TP=%s:print_format=json" % (TARGET_I, TARGET_TP),
                        "-f", "null", "-"], capture_output=True, text=True)
    err = r.stderr
    try:
        m = json.loads(err[err.rfind("{"):])
        ln = ("loudnorm=I=%s:TP=%s:LRA=11:linear=true"
              ":measured_I=%s:measured_TP=%s:measured_LRA=%s"
              ":measured_thresh=%s:offset=%s" % (
                  TARGET_I, TARGET_TP, m["input_i"], m["input_tp"],
                  m["input_lra"], m["input_thresh"], m["target_offset"]))
    except Exception:
        ln = "loudnorm=I=%s:TP=%s:LRA=11" % (TARGET_I, TARGET_TP)
    r = subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", src,
                        "-af", pre + ln, "-t", str(MAX_SEC), "-vn",
                        "-ac", "1", "-ar", "44100", "-b:a", "112k", dst], capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(dst)


SNR_CAP = 22.0          # 超过这个就没有听感意义了，转而优先时长
PREFER_SEC = 6.0        # 低于这个长度的片段只在别无选择时才用


def score(snr_new, dur):
    return (min(snr_new, SNR_CAP), min(dur, 30.0) / 30.0)


def better(new, old, margin=0.0):
    """new/old 都是 try_source 的返回值；比 SNR（封顶）+ 时长。"""
    if new is None:
        return False
    if old is None:
        return True
    dn = new[4] >= PREFER_SEC
    do = old[4] >= PREFER_SEC
    if dn != do:
        return dn                      # 够长的优先
    sn, so = min(new[1], SNR_CAP), min(old[1], SNR_CAP)
    if abs(sn - so) >= margin:
        return sn > so
    return new[4] > old[4] + 1.0       # SNR 打平时，谁长用谁


def try_source(c, slug, hp=HP_DEFAULT):
    """下载 + 重制一个候选，返回 (新SNR, 路径) 或 None。"""
    try:
        raw = cached(c["url"])
    except Exception:
        return None
    m0 = metrics(raw)
    if not m0 or m0[2] < 3:
        return None
    # 每次尝试必须用独立文件名：早先所有候选都写 TMP/<slug>.mp3，
    # 结果 best 存的路径被后一个候选覆盖，报告分数和实际落盘根本不是一段。
    key = hashlib.md5(c["url"].encode()).hexdigest()[:8]
    out = os.path.join(TMP, "%s-%s.mp3" % (slug, key))
    if not remaster(raw, out, hp):
        return None
    m1 = metrics(out)
    if not m1:
        return None
    return m0[0], m1[0], m1[1], out, m1[2]   # 源SNR, 新SNR, 峰值, 路径, 时长


# ---------- 主流程 ----------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--below", type=float, default=0)
    ap.add_argument("--slugs", default="")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="不看相对提升，只按绝对标准挑最好的（改了高通等参数后重跑用）")
    a = ap.parse_args()

    for d in (SRC, TMP):
        if not os.path.isdir(d):
            os.makedirs(d)

    data = json.load(open(ASSETS, encoding="utf-8"))
    species = {s["slug"]: s for s in json.load(
        open(os.path.join(ROOT, "data", "species.json"), encoding="utf-8"))}

    todo = [s.strip() for s in a.slugs.split(",") if s.strip()]
    if not todo:
        for slug in sorted(data):
            p = os.path.join(AUD, slug + ".mp3")
            if not os.path.exists(p):
                continue
            m = metrics(p)
            if m and m[0] < a.below:
                todo.append(slug)

    print("待处理 %d 条（判据：新版本 SNR 至少提升 %.0f dB 且 ≥ %.0f dB）\n"
          % (len(todo), MIN_GAIN_DB, MIN_NEW_SNR))

    accepted = []
    for slug in todo:
        cur = os.path.join(AUD, slug + ".mp3")
        curm = metrics(cur)
        if not curm:
            print("%-22s 跳过（现有文件读不了）" % slug)
            continue
        aud = data[slug]["audio"]
        sci = species.get(slug, {}).get("sci", "")
        hp = HP_BY_GROUP.get(species.get(slug, {}).get("group", ""), HP_DEFAULT)

        # 1) 原来源的高清版
        cands = []
        page = aud.get("page", "")
        try:
            if "inaturalist" in page:
                cands += from_inat(page)
            elif "wikimedia" in page:
                cands += from_commons(page)
        except Exception as e:
            print("  %s 原来源解析失败 %s" % (slug, e))

        best = None
        for c in cands:
            r = try_source(c, slug, hp)
            if r and better(r, best[1] if best else None):
                best = (c, r)

        # 2) 原件不够好 → 换一段
        if a.force or best is None or best[1][1] < curm[0] + MIN_GAIN_DB:
            pool = []
            if sci:
                for fn in (search_inat, search_commons):
                    try:
                        pool += fn(sci)
                    except Exception:
                        pass
            for c in pool:
                r = try_source(c, slug, hp)
                if not r:
                    continue
                if better(r, best[1] if best else None, margin=1.0):
                    best = (c, r)
                    if r[1] >= 20 and r[4] >= 10:
                        break   # 又干净又够长，不用再试了

        if best is None:
            print("%-22s 现 %4.1f dB  找不到可用源，保持原样" % (slug, curm[0]))
            continue

        c, (snr_src, snr_new, peak_new, out, dur_new) = best
        gain = snr_new - curm[0]
        if snr_new < MIN_NEW_SNR or (gain < MIN_GAIN_DB and not a.force):
            print("%-22s 现 %4.1f dB  最佳候选 %4.1f dB（%+.1f）不够，跳过"
                  % (slug, curm[0], snr_new, gain))
            continue

        kb = os.path.getsize(out) // 1024
        tag = "原件重制" if c.get("keep") else "换源"
        print("%-22s 现 %4.1f → %4.1f dB（%+.1f）%s %dKB  %s"
              % (slug, curm[0], snr_new, gain, tag, kb, c["url"].split("/")[-1][:28]))

        if a.dry:
            continue

        bak = "/var/tmp/audio_old"
        if not os.path.isdir(bak):
            os.makedirs(bak)
        if not os.path.exists(os.path.join(bak, slug + ".mp3")):
            with open(cur, "rb") as f, open(os.path.join(bak, slug + ".mp3"), "wb") as g:
                g.write(f.read())
        with open(out, "rb") as f, open(cur, "wb") as g:
            g.write(f.read())

        aud["kb"] = kb
        dur = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", out],
                             capture_output=True, text=True).stdout.strip()
        try:
            aud["dur"] = round(float(dur), 1)
        except ValueError:
            pass
        freq, stages = hp if isinstance(hp, tuple) else (hp, 1)
        aud["note"] = ("2026-11 批量重制：两遍 loudnorm + %dHz 高通×%d，SNR %.1f→%.1f dB"
                       % (freq, stages, curm[0], snr_new))
        if not c.get("keep"):
            aud["credit"] = c.get("credit") or aud.get("credit")
            aud["license"] = c.get("license") or aud.get("license")
            aud["page"] = c.get("page") or aud.get("page")
            aud["title"] = c.get("title") or aud.get("title")
        accepted.append(slug)

    json.dump(data, open(ASSETS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n已替换 %d 条%s" % (len(accepted), "（dry-run，未写入）" if a.dry else ""))


if __name__ == "__main__":
    main()
