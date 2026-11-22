#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成分享卡片 assets/og/<slug>.jpg（1080×1080）。

为什么是正方形：
  - 微信转发卡片里的缩略图是**居中裁成 1:1** 的。给一张 1.9:1 的横图，
    两侧会被切掉，很多鸟（尤其站在画面边上的）直接被裁掉一半。
  - 1080×1080 在群里显示完整，X / Facebook 会自己裁成 1.91:1，损失可接受。

为什么不直接裁：原图比例各异，硬裁到 1:1 会切主体。这里用
「同图模糊铺底 + 原图完整居中」，任何一张都不会裁坏，底色的氛围仍是该物种本身。

可重复运行：已存在且比源图新的会跳过，`--force` 强制重做。
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "assets", "img")
OUT = os.path.join(ROOT, "assets", "og")

S = 1080
FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"
BRAND = "珠海观鸟图鉴 · BIRDS OF ZHUHAI"

INK = (247, 244, 236)
DIM = (216, 208, 192)


def font(size):
    return ImageFont.truetype(FONT, size, index=0)


def cover(im, size):
    w, h = im.size
    r = max(size / w, size / h)
    im = im.resize((max(size, round(w * r)), max(size, round(h * r))), Image.LANCZOS)
    left, top = (im.width - size) // 2, (im.height - size) // 2
    return im.crop((left, top, left + size, top + size))


def shade(im, frac=0.46, strength=230):
    """底部渐变：白字压在任何照片上都读得清。"""
    mask = Image.new("L", (1, S), 0)
    px = mask.load()
    start = int(S * (1 - frac))
    for y in range(S):
        if y >= start:
            t = (y - start) / max(1, S - start)
            px[0, y] = int(strength * (t ** 1.6))
    mask = mask.resize((S, S))
    im.paste(Image.new("RGB", (S, S), (10, 16, 12)), (0, 0), mask)
    return im


def wrap_cjk(text, f, maxw, draw):
    out, line = [], ""
    for ch in text:
        if draw.textlength(line + ch, font=f) <= maxw:
            line += ch
        else:
            out.append(line)
            line = ch
    if line:
        out.append(line)
    return out


def render(src, dst, name_zh, sci):
    base = Image.open(src).convert("RGB")

    # 1) 模糊铺底：既补齐画布，又不引入第二种颜色
    bg = cover(base, S).filter(ImageFilter.GaussianBlur(52))
    bg = Image.eval(bg, lambda v: int(v * 0.66))

    # 2) 前景完整居中，略微上移给文字留位置
    r = min(S / base.width, S / base.height)
    fg = base.resize((max(1, round(base.width * r)), max(1, round(base.height * r))),
                     Image.LANCZOS)
    canvas = bg.copy()
    canvas.paste(fg, ((S - fg.width) // 2, max(0, (S - fg.height) // 2 - 46)))

    canvas = shade(canvas)
    d = ImageDraw.Draw(canvas)

    f_name, f_sci, f_brand = font(78), font(31), font(21)

    if sci:
        d.text((72, S - 78), sci, font=f_sci, fill=DIM, anchor="ls")
    if name_zh:
        lines = wrap_cjk(name_zh, f_name, S - 148, d)
        for i, line in enumerate(reversed(lines)):
            d.text((70, S - 132 - i * 88), line, font=f_name, fill=INK, anchor="ls")

    bw = d.textlength(BRAND, font=f_brand)
    d.text((S - 72 - bw, 62), BRAND, font=f_brand, fill=(238, 232, 219))
    d.line([(S - 72 - bw, 94), (S - 72, 94)], fill=(168, 178, 164), width=1)

    canvas.save(dst, "JPEG", quality=84, optimize=True, progressive=True)


def main():
    force = "--force" in sys.argv
    os.makedirs(OUT, exist_ok=True)

    assets = json.load(open(os.path.join(ROOT, "data", "assets.json")))
    species = json.load(open(os.path.join(ROOT, "data", "species.json")))
    meta = {s["slug"]: {"zh": s["zh"], "sci": s["sci"]} for s in species}

    made = skipped = failed = 0
    for slug, a in assets.items():
        m = meta.get(slug)
        big = ((a or {}).get("img") or {}).get("big")
        if not m or not big:
            continue
        src = os.path.join(IMG, big)
        dst = os.path.join(OUT, "%s.jpg" % slug)
        if not os.path.exists(src):
            continue
        if not force and os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
            skipped += 1
            continue
        try:
            render(src, dst, m["zh"], m["sci"])
            made += 1
        except Exception as ex:
            failed += 1
            print("  ! %s: %s" % (slug, ex))
    print("分享图：新建 %d，跳过 %d，失败 %d" % (made, skipped, failed))


if __name__ == "__main__":
    main()
