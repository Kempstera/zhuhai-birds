#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成珠海观鸟图鉴静态站点。"""
import json, os, shutil, datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")

GROUPS = [
    {"id": "songbird", "zh": "林鸟与城市常客", "en": "Songbirds", "short": "林鸟",
     "intro": "清晨把你叫醒的那些声音，多半来自这一群。它们体型小、嗓门大，把城市绿化带当成了自己的森林。",
     "icon": "songbird", "tags": ["公园","林缘","村落"]},
    {"id": "water", "zh": "湿地与河涌", "en": "Wetland Birds", "short": "湿地",
     "intro": "鹭、秧鸡、鸊鷉——它们的脚趾、喙形和耐心，都为了同一件事：在浅水里抓到下一条鱼。",
     "icon": "heron", "tags": ["河涌","鱼塘","湿地"]},
    {"id": "shore", "zh": "海岸与滩涂", "en": "Shorebirds & Gulls", "short": "海岸",
     "intro": "潮水退去时，滩涂成了一座餐厅。全世界的候鸟沿着这条海岸线南北往返，珠海正好在它们的路上。",
     "icon": "shore", "tags": ["滩涂","沙滩","河口"]},
    {"id": "raptor", "zh": "天空的猎手", "en": "Raptors", "short": "猛禽",
     "intro": "抬头看，永远值得。珠海的风里有上升气流，也有正在盘旋的鹰。",
     "icon": "raptor", "tags": ["海岸","水库","山脊"]},
    {"id": "kingfisher", "zh": "翠鸟家族", "en": "Kingfishers", "short": "翠鸟",
     "intro": "蓝、绿、红、白，颜色浓得不像真的。它们用俯冲的速度，把水与光切开来。",
     "icon": "kingfisher", "tags": ["溪流","水塘","红树林"]},
]

SPOTS = [
    {"no": "01", "name": "淇澳—担杆岛自然保护区", "area": "淇澳岛",
     "desc": "华南少见的连片红树林湿地，也是珠海最重要的候鸟越冬地。退潮时滩涂上挤满鹭类、鸻鹬，冬季有黑脸琵鹭稳定越冬。进入核心区需预约，外围基围与堤岸可自由观察。",
     "birds": ["黑脸琵鹭", "池鹭", "苍鹭", "褐翅鸦鹃", "青脚鹬"],
     "season": "最佳：11 月–次年 3 月"},
    {"no": "02", "name": "横琴芒洲湿地公园", "area": "横琴",
     "desc": "芦苇荡、红树林与鱼塘交织的人工—自然复合湿地，栈道深入水面，是近距离观察水鸟最舒服的地方。清晨与傍晚光线最好。",
     "birds": ["白鹭", "夜鹭", "白胸苦恶鸟", "黑翅长脚鹬", "小鸊鷉"],
     "season": "全年，秋冬水鸟最多"},
    {"no": "03", "name": "金湾海滩与滩涂", "area": "金湾",
     "desc": "珠三角西岸保存较好的开阔沙滩与泥滩，退潮后数公里滩面暴露，是鸻鹬类与鸥类的主战场。需要望远镜，注意潮汐表。",
     "birds": ["环颈鸻", "黑嘴鸥", "红嘴鸥", "青脚鹬", "黑翅长脚鹬"],
     "season": "最佳：10 月–次年 4 月"},
    {"no": "04", "name": "香山湖公园", "area": "香洲",
     "desc": "城市里的综合公园，湖面、湿地与林带俱全。适合初学者：不用走远，一小时能记录十几种鸟，黑水鸡与小鸊鷉几乎必见。",
     "birds": ["小鸊鷉", "黑水鸡", "白鹭", "白头鹎", "红耳鹎", "乌鸫"],
     "season": "全年"},
    {"no": "05", "name": "野狸岛与香炉湾", "area": "香洲",
     "desc": "环岛绿道连着海面与山体，退潮时礁石与沙滩上都有惊喜。冬季海面上有成群红嘴鸥，上空常有黑鸢盘旋。",
     "birds": ["红嘴鸥", "黑鸢", "白头鹎", "叉尾太阳鸟", "暗绿绣眼鸟"],
     "season": "全年，冬季海鸟最盛"},
    {"no": "06", "name": "斗门水稻田与河涌", "area": "斗门",
     "desc": "典型的岭南农业湿地景观。田埂、水渠与鱼塘构成密集的水网，是池鹭、翠鸟与伯劳的猎场，也是观察「人鸟共处」最好的窗口。",
     "birds": ["池鹭", "斑鱼狗", "白胸翡翠", "棕背伯劳", "八哥"],
     "season": "全年，春耕与秋收前后最热闹"},
]

ETHICS = [
    ("01", "远观，不打扰", "用望远镜或长焦，不靠近、不驱赶、不追逐。繁殖期与越冬期（11–3 月）尤其要保持距离，一次惊飞可能耗尽它们一天的能量。"),
    ("02", "不用回放引诱", "播放鸟鸣录音会把鸟从领地、巢区或觅食地引开，长期使用会显著降低繁殖成功率。观察野生行为，比拍到「标准照」重要。"),
    ("03", "不投喂、不放生", "面包会伤害水鸟的消化系统；放生外来物种（如巴西龟、家鸭）会破坏本地生态。让它们自己找吃的。"),
    ("04", "不踩滩涂、不进核心区", "沙滩上的一个小凹坑可能就是一窝卵。保护区的核心区、缓冲区请勿进入，无人机在鸟类栖息地上空属违规行为。"),
    ("05", "记录，而不是收集", "拍照片、记时间地点、上传到公民科学平台，比带走一根羽毛更有价值。所有野生鸟类在中国均受法律保护。"),
    ("06", "带走垃圾，包括看不见的", "鱼线、塑料袋、废弃口罩对水鸟是致命的。滩涂上的垃圾请顺手带走，这比任何口号都实际。"),
]

MONTH_ACT = [
    ("1", 3), ("2", 3), ("3", 2), ("4", 1), ("5", 1), ("6", 0),
    ("7", 0), ("8", 1), ("9", 2), ("10", 3), ("11", 3), ("12", 3),
]

YEAR = datetime.date.today().year


def load():
    species = json.load(open(os.path.join(ROOT, "data", "species.json")))
    assets_path = os.path.join(ROOT, "data", "assets.json")
    assets = json.load(open(assets_path)) if os.path.exists(assets_path) else {}
    for sp in species:
        a = assets.get(sp["slug"], {})
        sp["img"] = a.get("img")
        sp["audio"] = a.get("audio")
    return species, assets


def pclass(p):
    if "一级" in p:
        return "p1"
    if "二级" in p:
        return "p2"
    return "p3"


GROUP_ORDER = {"songbird": 0, "water": 1, "shore": 2, "raptor": 3, "kingfisher": 4}
RARITY_LABEL = {1: "极常见", 2: "常见", 3: "不常见", 4: "局部常见", 5: "罕见"}


def main():
    species, assets = load()
    slugs = {s["slug"] for s in species}
    by_slug = {s["slug"]: s for s in species}

    # 按遇见率排序：极常见 → 罕见；同等级内按类群、名称稳定排列
    species.sort(key=lambda s: (s.get("rank", 2), GROUP_ORDER.get(s["group"], 9), s["zh"]))
    for i, sp in enumerate(species, 1):
        sp["no"] = "%03d" % i
        sp["rlabel"] = RARITY_LABEL.get(sp.get("rank", 2), "常见")

    from collections import Counter
    rank_counts = Counter(s.get("rank", 2) for s in species)

    # 清理无效的相似种引用
    for sp in species:
        sp["similar"] = [x for x in sp.get("similar", []) if x in slugs]
        sp["pclass"] = pclass(sp["protect"])

    counts = {g["id"]: 0 for g in GROUPS}
    for sp in species:
        counts[sp["group"]] = counts.get(sp["group"], 0) + 1
    for g in GROUPS:
        g["count"] = counts.get(g["id"], 0)

    env = Environment(
        loader=FileSystemLoader(os.path.join(ROOT, "templates")),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True, lstrip_blocks=True,
    )
    env.globals.update(GROUPS=GROUPS, SPOTS=SPOTS, ETHICS=ETHICS, YEAR=YEAR)

    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(os.path.join(DIST, "bird"), exist_ok=True)
    os.makedirs(os.path.join(DIST, "assets", "img"), exist_ok=True)
    os.makedirs(os.path.join(DIST, "assets", "audio"), exist_ok=True)
    os.makedirs(os.path.join(DIST, "static"), exist_ok=True)

    # 静态资源
    for f in os.listdir(os.path.join(ROOT, "static")):
        shutil.copy2(os.path.join(ROOT, "static", f), os.path.join(DIST, "static", f))
    for sub in ("img", "audio"):
        src = os.path.join(ROOT, "assets", sub)
        if os.path.isdir(src):
            for f in os.listdir(src):
                if f.startswith("."):
                    continue
                shutil.copy2(os.path.join(src, f), os.path.join(DIST, "assets", sub, f))

    # 首页
    hero = next((s for s in species if s["slug"] == "bai-lu"), species[0])
    hero2 = next((s for s in species if s["slug"] == "hei-lian-pi-lu" and s["img"]), None)
    html = env.get_template("index.html").render(
        species=species, hero=hero, hero2=hero2, nav="home", root="",
        rank_counts=rank_counts, total=len(species))
    open(os.path.join(DIST, "index.html"), "w").write(html)

    # 详情页
    for i, sp in enumerate(species):
        prev = species[(i - 1) % len(species)]
        nxt = species[(i + 1) % len(species)]
        sp["rank"] = sp.get("rank", 2)
        sims = [by_slug[x] for x in sp["similar"]]
        html = env.get_template("detail.html").render(
            sp=sp, prev=prev, next=nxt, sims=sims, nav="species", root="../",
            group=next(g for g in GROUPS if g["id"] == sp["group"]))
        open(os.path.join(DIST, "bird", sp["slug"] + ".html"), "w").write(html)

    # 指南页
    html = env.get_template("guide.html").render(
        species=species, nav="guide", months=MONTH_ACT, root="",
        rank_counts=rank_counts, total=len(species))
    open(os.path.join(DIST, "guide.html"), "w").write(html)

    # 404
    html = env.get_template("404.html").render(nav="", root="")
    open(os.path.join(DIST, "404.html"), "w").write(html)

    # robots / sitemap
    open(os.path.join(DIST, "robots.txt"), "w").write(
        "User-agent: *\nAllow: /\nSitemap: https://birds.signupeverywhere.cc/sitemap.xml\n")
    urls = ["https://birds.signupeverywhere.cc/",
            "https://birds.signupeverywhere.cc/guide.html"]
    urls += ["https://birds.signupeverywhere.cc/bird/%s.html" % s["slug"] for s in species]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append("  <url><loc>%s</loc><changefreq>monthly</changefreq></url>" % u)
    sm.append("</urlset>")
    open(os.path.join(DIST, "sitemap.xml"), "w").write("\n".join(sm))

    n_img = sum(1 for s in species if s["img"])
    n_aud = sum(1 for s in species if s["audio"])
    print("生成完成：%d 个物种，%d 图片，%d 音频" % (len(species), n_img, n_aud))
    if n_img < len(species):
        print("缺图：", [s["zh"] for s in species if not s["img"]])
    if n_aud < len(species):
        print("缺音频：", [s["zh"] for s in species if not s["audio"]])


if __name__ == "__main__":
    main()
