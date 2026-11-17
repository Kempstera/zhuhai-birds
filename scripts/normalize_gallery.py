#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把图集图片文件名统一成规范形式，并把不再被引用的旧文件挪走。

规范：
  绘图  <slug>-plate-{1600,900}.webp
  摄影  <slug>-ph1-… / <slug>-ph2-…（按 gallery 中的顺序编号）
  封面  <slug>-{1600,900}.webp

历史遗留的 <slug>-g1/g2/g3-* 会被改名或移出 assets/img。
移出而非删除：沙箱对 unlink 有配额，移到 /var/tmp/orphan_img 更稳。

用法：
  python3 scripts/normalize_gallery.py           # 只看计划
  python3 scripts/normalize_gallery.py --apply   # 真正执行
"""
import json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "assets", "img")
META = os.path.join(ROOT, "data", "assets.json")
PARK = "/var/tmp/orphan_img"


def main():
    apply = "--apply" in sys.argv
    meta = json.load(open(META))
    plan, keep = [], set()

    for slug, v in meta.items():
        gal = v.get("gallery") or []
        n_ph = 0
        for g in gal:
            if g.get("kind") == "plate":
                stems = ["%s-plate" % slug]
            else:
                n_ph += 1
                stems = ["%s-ph%d" % (slug, n_ph)]
            for size in ("1600", "900"):
                cur = g["big"] if size == "1600" else g["card"]
                tgt = "%s-%s.webp" % (stems[0], size)
                if cur == tgt:
                    keep.add(cur)
                    continue
                plan.append((cur, tgt))
                if size == "1600":
                    g["big"] = tgt
                else:
                    g["card"] = tgt
                keep.add(tgt)
        im = v.get("img") or {}
        for k in ("card", "big"):
            if im.get(k):
                keep.add(im[k])
        audio = (v.get("audio") or {})
        for k, val in audio.items():
            if isinstance(val, str) and val.endswith(".mp3"):
                keep.add(val)

    print("需要改名 %d 个文件" % len(plan))
    if not apply:
        for a, b in plan[:12]:
            print("   %s -> %s" % (a, b))
        return

    # 两段式：先挪到临时名，避免目标名已被占用
    stage = []
    for i, (cur, tgt) in enumerate(plan):
        src = os.path.join(IMG, cur)
        if not os.path.exists(src):
            continue
        tmp = os.path.join(IMG, ".n%05d.webp" % i)
        os.rename(src, tmp)
        stage.append((tmp, os.path.join(IMG, tgt)))
    if not os.path.isdir(PARK):
        os.makedirs(PARK)
    for tmp, dst in stage:
        if os.path.exists(dst):          # 目标名上还压着旧文件：先挪走
            shutil.move(dst, os.path.join(PARK, os.path.basename(dst)))
        os.rename(tmp, dst)
    print("改名完成 %d" % len(stage))

    # 清理临时残留 + 未被引用的旧图
    if not os.path.isdir(PARK):
        os.makedirs(PARK)
    moved = 0
    for f in sorted(os.listdir(IMG)):
        if f in keep:
            continue
        if not f.lower().endswith(".webp"):
            continue
        shutil.move(os.path.join(IMG, f), os.path.join(PARK, f))
        moved += 1
    print("移出未引用文件 %d -> %s" % (moved, PARK))
    json.dump(meta, open(META, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
