#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按月自动更新：到了新的月份，重新构建并发布。

设计上的几个取舍：
- **不存状态文件**。判断「要不要重建」的依据是构建产物本身：
  如果 dist/zh/index.html 里已经是「M 月先认这 12 种」，说明本月已经更新过。
  这样重启、换机器、手工跑过构建都不会互相打架。
- **幂等**。内容没变就不提交、部署还是照发（Cloudflare 按文件去重，很快）。
- **先验证再发布**。构建完先检查月份、卡片数、内部链接，任一项不过就不发布，
  免得把坏页面推上线——这是无人值守脚本唯一不能省的一步。
- **不碰 git 历史**。只在有 diff 时新提交一条，绝不 amend / reset。

用法:
  python3 scripts/auto_update.py            # 该更新就更新，否则静默跳过
  python3 scripts/auto_update.py --dry      # 只构建和校验，不提交不发布
  python3 scripts/auto_update.py --force    # 无视月份判断，强制重建
"""
import argparse
import datetime
import os
import posixpath
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
WRANGLER = os.path.expanduser(
    "~/.npm/_npx/d77349f55c2be1c0/node_modules/wrangler/bin/wrangler.js")
SITE = "https://birds.signupeverywhere.cc"
PROJECT = "zhuhai-birds"
LOG = "/var/tmp/zhuhai-birds-auto-update.log"

MONTHS_EN = ["", "January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]


def log(msg):
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def sh(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def already_current(month):
    """产物里已经是本月名单，就不用重建。"""
    zh = read(os.path.join(DIST, "zh", "index.html"))
    en = read(os.path.join(DIST, "index.html"))
    if not zh or not en:
        return False
    title_ok = ("%d 月先认这 12 种" % month) in zh
    en_ok = ("in %s" % MONTHS_EN[month]) in en
    return title_ok and en_ok


def cards_of(path, anchor):
    """取出「本月名录」区块里的物种 slug，顺便确认有多少张卡。"""
    s = read(path)
    i = s.find(anchor)
    if i < 0:
        return []
    seg = s[i:i + 40000]
    end = seg.find("</section>")
    if end > 0:
        seg = seg[:end]
    out = []
    for m in re.finditer(r'href="(?:\.\./)?bird/([a-z0-9-]+)\.html"', seg):
        if m.group(1) not in out:
            out.append(m.group(1))
    return out


def check_links():
    bad = []
    total = 0
    for dp, _, fs in os.walk(DIST):
        for f in fs:
            if not f.endswith(".html"):
                continue
            p = os.path.join(dp, f)
            url_dir = posixpath.dirname(os.path.relpath(p, DIST))
            s = read(p)
            for m in re.finditer(r'(?:href|src)="([^"]+)"', s):
                u = m.group(1)
                if u.startswith(("http://", "https://", "mailto:", "#",
                                 "data:", "javascript:")):
                    continue
                base = u.split("#")[0].split("?")[0]
                if not base:
                    continue
                total += 1
                t = base if base.startswith("/") else posixpath.normpath(
                    posixpath.join("/" + url_dir if url_dir != "." else "/", base))
                t = re.sub(r"^(\.\./)+", "/", t)
                tgt = os.path.join(DIST, t.lstrip("/"))
                if base.endswith("/"):
                    tgt = os.path.join(tgt, "index.html")
                if not os.path.exists(tgt):
                    bad.append(u)
    return total, bad


def validate(month):
    errs = []
    zh = os.path.join(DIST, "zh", "index.html")
    en = os.path.join(DIST, "index.html")
    for p in (zh, en):
        if not os.path.exists(p):
            errs.append("缺页面：%s" % p)
    if errs:
        return errs

    if ("%d 月先认这 12 种" % month) not in read(zh):
        errs.append("中文首页标题不是 %d 月" % month)
    if ("in %s" % MONTHS_EN[month]) not in read(en):
        errs.append("英文首页标题不是 %s" % MONTHS_EN[month])

    zc = cards_of(zh, "过了季节就看不到了")
    if len(zc) != 12:
        errs.append("中文名录卡片 %d 张（应为 12）" % len(zc))
    ec = cards_of(en, "migrants that only turn up")
    if len(ec) != 12:
        errs.append("英文名录卡片 %d 张（应为 12）" % len(ec))
    if zc and ec and zc != ec:
        errs.append("中英文名录不一致")

    total, bad = check_links()
    if bad:
        errs.append("内部链接缺失 %d 条，例如 %s" % (len(bad), bad[:3]))

    # 封面池里的鸟必须都在名录里，否则「听到哪只、低头找不到」
    hero_pool = re.search(r'id="heroPool">(.*?)</script>', read(zh), re.S)
    if hero_pool:
        import json as _json
        try:
            pool = {e["slug"] for e in _json.loads(hero_pool.group(1))}
            missing = pool - set(zc)
            if missing:
                errs.append("封面池有 %d 只不在名录里：%s" % (len(missing), sorted(missing)))
        except ValueError:
            errs.append("heroPool JSON 解析失败")

    log("  校验：链接 %d 条，名录 12 张，中英文一致" % total)
    return errs


def now():
    """当前日期。和 build.py 共用 ZHUHAI_TODAY 覆盖，用来预演别的月份。"""
    raw = os.environ.get("ZHUHAI_TODAY")
    if raw:
        y, m, d = (int(x) for x in raw.split("-"))
        return datetime.date(y, m, d)
    return datetime.date.today()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()

    today = now()
    month = today.month
    log("=== 自动更新检查（%s）===" % today.strftime("%Y-%m-%d"))

    if not a.force and already_current(month):
        log("产物已是 %d 月内容，跳过。" % month)
        return 0

    log("开始构建…")
    r = sh([sys.executable, "build.py"])
    if r.returncode != 0:
        log("构建失败：\n" + (r.stderr or r.stdout)[-1500:])
        return 1
    tail = [l for l in (r.stdout or "").splitlines() if l.strip()][-3:]
    for l in tail:
        log("  " + l)

    errs = validate(month)
    if errs:
        log("校验不通过，已中止（未提交、未发布）：")
        for e in errs:
            log("  · " + e)
        return 2
    log("校验通过。")

    if a.dry:
        log("--dry：到此为止，不提交也不发布。")
        return 0

    st = sh(["git", "status", "--porcelain"])
    if st.stdout.strip():
        msg = "月度自动重建：%d 年 %d 月" % (today.year, month)
        sh(["git", "add", "-A"])
        c = sh(["git", "commit", "-m", msg])
        log("已提交：%s" % msg if c.returncode == 0 else "提交失败：" + c.stderr[-300:])
    else:
        log("产物无变化，跳过提交。")

    log("发布到 Cloudflare Pages…")
    d = sh(["node", WRANGLER, "pages", "deploy", "dist",
            "--project-name=" + PROJECT, "--branch=main", "--commit-dirty=true"])
    if d.returncode != 0:
        log("发布失败：\n" + (d.stderr or d.stdout)[-1200:])
        return 3
    url = ""
    for line in (d.stdout or "").splitlines():
        if "pages.dev" in line:
            url = line.strip()
    log("发布完成。" + (" " + url if url else ""))

    # 线上回读一次，确认真的换月了（CDN 有缓存，给它几秒）
    log("线上回读校验…")
    ok = False
    for i in range(6):
        time.sleep(5)
        p = sh(["curl", "-s", "--max-time", "20", "%s/zh/?v=%d" % (SITE, int(time.time()))])
        if ("%d 月先认这 12 种" % month) in (p.stdout or ""):
            ok = True
            break
    log("线上已是 %d 月内容。" % month if ok else "线上回读未确认（可能 CDN 未刷新），请稍后手工看一眼。")

    if not a.no_push:
        # 推到 GitHub 只是同步源码，失败不影响线上
        pr = sh(["git", "-c", "http.proxy=http://127.0.0.1:9674",
                 "-c", "https.proxy=http://127.0.0.1:9674", "push", "origin", "HEAD"])
        log("已推送到 GitHub。" if pr.returncode == 0
            else "推送失败（不影响线上）：" + (pr.stderr or "").strip()[-200:])

    log("=== 完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
