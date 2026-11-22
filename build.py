#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成珠海观鸟图鉴静态站点。"""
import json, os, re, shutil, datetime, hashlib
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def clean_dist():
    """清空 dist。删不干净也不许崩。

    无人值守的月度构建最怕「因为一个删不掉的条目整个流程静默停止」——那意味着
    站点永远停在上个月。所以这里先整棵删，失败了再逐个删，剩下的记一笔警告让
    后面的校验去判断，而不是抛异常把本次更新废掉。
    """
    if not os.path.isdir(DIST):
        return
    try:
        shutil.rmtree(DIST)
        return
    except OSError:
        pass
    left = []
    for dp, dns, fns in os.walk(DIST, topdown=False):
        for name in fns:
            try:
                os.unlink(os.path.join(dp, name))
            except OSError:
                left.append(os.path.join(dp, name))
        for name in dns:
            try:
                os.rmdir(os.path.join(dp, name))
            except OSError:
                left.append(os.path.join(dp, name))
    try:
        os.rmdir(DIST)
    except OSError:
        left.append(DIST)
    if left:
        print("  警告：dist 有 %d 项没能清除，产物里可能残留旧文件：%s"
              % (len(left), left[:5]))



def ruby(zh, py=""):
    """把拼音逐音节标到对应汉字的头顶（HTML ruby 注音）。

    例：ruby("白头鹎", "bái tóu bēi")
        → <ruby class="rb">白<rt>bái</rt></ruby><ruby ...>头<rt>tóu</rt></ruby>...

    65 个中文名的汉字数与拼音音节数刚好一一对应；如果将来新增的名字对不上
    （比如带儿化音、或多字音节），就退回「汉字 + 并排拼音」的老写法，避免错位。
    """
    zh = zh or ""
    py = (py or "").strip()
    syl = py.split()
    chars = list(zh)
    if not py:
        return Markup(escape(zh))
    if not syl or sum(1 for c in chars if CJK_RE.match(c)) != len(syl):
        return Markup("%s<em class=\"py\">%s</em>" % (escape(zh), escape(py)))
    out, i = [], 0
    for c in chars:
        if CJK_RE.match(c):
            out.append('<ruby class="rb">%s<rt>%s</rt></ruby>' % (escape(c), escape(syl[i])))
            i += 1
        else:
            out.append(str(escape(c)))
    return Markup("".join(out))


def asset_ver(name):
    """静态资源的短哈希，用来打破 CDN / 浏览器缓存。

    Cloudflare Pages 对 *.css / *.js 设的是 max-age=14400，文件名不带版本号时，
    部署新版本后浏览器最多还会用 4 小时的旧样式表 —— 新 HTML + 旧 CSS 会让
    依赖样式定尺寸的图片被 width/height 属性撑变形。加 ?v= 哈希可以彻底避免。
    """
    p = os.path.join(ROOT, "static", name)
    if not os.path.exists(p):
        return "0"
    with open(p, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

GROUPS = [
    {"id": "songbird", "zh": "林鸟与城市常客", "en": "Songbirds", "short": "林鸟",
     "intro": "清晨把你叫醒的那些声音，多半来自这一群。它们体型小、嗓门大，把城市绿化带当成了自己的森林。", "tags": ["公园","林缘","村落"]},
    {"id": "water", "zh": "湿地与河涌", "en": "Wetland Birds", "short": "湿地",
     "intro": "鹭、秧鸡、鸊鷉——它们的脚趾、喙形和耐心，都为了同一件事：在浅水里抓到下一条鱼。", "tags": ["河涌","鱼塘","湿地"]},
    {"id": "shore", "zh": "海岸与滩涂", "en": "Shorebirds & Gulls", "short": "海岸",
     "intro": "潮水退去时，滩涂成了一座餐厅。全世界的候鸟沿着这条海岸线南北往返，珠海正好在它们的路上。", "tags": ["滩涂","沙滩","河口"]},
    {"id": "raptor", "zh": "天空的猎手", "en": "Raptors", "short": "猛禽",
     "intro": "抬头看，永远值得。珠海的风里有上升气流，也有正在盘旋的鹰。", "tags": ["海岸","水库","山脊"]},
    {"id": "kingfisher", "zh": "翠鸟家族", "en": "Kingfishers", "short": "翠鸟",
     "intro": "蓝、绿、红、白，颜色浓得不像真的。它们用俯冲的速度，把水与光切开来。", "tags": ["溪流","水塘","红树林"]},
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

GROUPS_EN = [
    {"id": "songbird", "zh": "Songbirds & City Birds", "en": "", "short": "Songbirds",
     "intro": "Most of the voices that wake a southern city belong to this group. Small, loud, and entirely at home in the greenery we plant.",
     "tags": ["Park", "Forest edge", "Village"]},
    {"id": "water", "zh": "Wetlands & Waterways", "en": "", "short": "Wetland",
     "intro": "Herons, rails, grebes — their toes, their bills and their patience are all built for one thing: the next fish in shallow water.",
     "tags": ["Creek", "Fish pond", "Wetland"]},
    {"id": "shore", "zh": "Coast & Tidal Flats", "en": "", "short": "Shore",
     "intro": "When the tide falls, the flats become a restaurant. Migrants shuttle along this coast twice a year, and Zhuhai is directly on the route.",
     "tags": ["Tidal flat", "Beach", "Estuary"]},
    {"id": "raptor", "zh": "Hunters of the Sky", "en": "", "short": "Raptors",
     "intro": "It always pays to look up. Zhuhai's air carries thermals, and thermals carry circling hawks.",
     "tags": ["Coast", "Reservoir", "Ridge"]},
    {"id": "kingfisher", "zh": "The Kingfishers", "en": "", "short": "Kingfisher",
     "intro": "Blue, green, red, white — colours too saturated to look real. They cut water and light apart at diving speed.",
     "tags": ["Stream", "Pond", "Mangrove"]},
]

SPOTS_EN = [
    {"no": "01", "name": "Qi'ao–Dangan Island Nature Reserve", "area": "Qi'ao Island",
     "desc": "One of the few large, continuous mangrove wetlands in southern China, and Zhuhai's most important wintering ground. At low tide the flats fill with herons, plovers and sandpipers; Black-faced Spoonbills winter here reliably. The core zone needs a booking — the outer gei wai and seawalls are open for watching.",
     "birds": ["黑脸琵鹭", "池鹭", "苍鹭", "褐翅鸦鹃", "青脚鹬"],
     "season": "Best: November – March"},
    {"no": "02", "name": "Hengqin Mangzhou Wetland Park", "area": "Hengqin",
     "desc": "A hybrid wetland of reedbeds, mangroves and fish ponds, with boardwalks reaching out over the water — the most comfortable place in the city to watch waterbirds at close range. Light is best at dawn and dusk.",
     "birds": ["白鹭", "夜鹭", "白胸苦恶鸟", "黑翅长脚鹬", "小鸊鷉"],
     "season": "All year; most waterbirds in autumn and winter"},
    {"no": "03", "name": "Jinwan Beaches & Tidal Flats", "area": "Jinwan",
     "desc": "Some of the best-preserved open sand and mudflat on the western shore of the Pearl River Delta. At low tide kilometres of flat are exposed — prime ground for waders and gulls. Bring a scope, and check the tide table first.",
     "birds": ["环颈鸻", "黑嘴鸥", "红嘴鸥", "青脚鹬", "黑翅长脚鹬"],
     "season": "Best: October – April"},
    {"no": "04", "name": "Xiangshan Lake Park", "area": "Xiangzhou",
     "desc": "A general-purpose city park with a lake, wetlands and belts of trees. Ideal for beginners: no travelling required, a dozen species in an hour, and Moorhens and Little Grebes almost guaranteed.",
     "birds": ["小鸊鷉", "黑水鸡", "白鹭", "白头鹎", "红耳鹎", "乌鸫"],
     "season": "All year"},
    {"no": "05", "name": "Yeli Island & Xianglu Bay", "area": "Xiangzhou",
     "desc": "A coastal path linking open sea to the hillside; at low tide the rocks and the sand both hold surprises. In winter Black-headed Gulls gather offshore and Black Kites often circle overhead.",
     "birds": ["红嘴鸥", "黑鸢", "白头鹎", "叉尾太阳鸟", "暗绿绣眼鸟"],
     "season": "All year; best seabirds in winter"},
    {"no": "06", "name": "Doumen Rice Fields & Creeks", "area": "Doumen",
     "desc": "Classic Lingnan agricultural wetland. Bunds, channels and fish ponds form a dense water network — hunting ground for pond herons, kingfishers and shrikes, and the best place to watch people and birds sharing the same landscape.",
     "birds": ["池鹭", "斑鱼狗", "白胸翡翠", "棕背伯劳", "八哥"],
     "season": "All year; busiest around spring ploughing and the autumn harvest"},
]

ETHICS_EN = [
    ("01", "Watch from a distance",
     "Use binoculars or a long lens. Don't approach, flush or chase. Keep even more distance in the breeding season and in winter (Nov–Mar): one flush can cost a bird a day's energy."),
    ("02", "Never use playback",
     "Playing a recording pulls a bird off its territory, its nest or its feeding grounds, and repeated use measurably lowers breeding success. Watching natural behaviour matters more than getting the standard shot."),
    ("03", "Don't feed, don't release",
     "Bread damages waterbirds' digestion, and releasing non-native species — red-eared sliders, domestic ducks — damages the local ecology. Let them find their own food."),
    ("04", "Stay off the flats, out of core zones",
     "A small depression in the sand may be a clutch of eggs. Keep out of core and buffer zones; flying a drone over a roost is an offence."),
    ("05", "Record, don't collect",
     "A photograph, a date, a place, an upload to a citizen-science platform, is worth more than a feather. All wild birds are protected by law in China."),
    ("06", "Take your litter, including the litter you can't see",
     "Fishing line, plastic bags and discarded masks are lethal to waterbirds. Carry out what you find on the flats — it does more than any slogan."),
]

MONTH_ACT = [
    ("1", 3), ("2", 3), ("3", 2), ("4", 1), ("5", 1), ("6", 0),
    ("7", 0), ("8", 1), ("9", 2), ("10", 3), ("11", 3), ("12", 3),
]

def today():
    """当前日期。可用 ZHUHAI_TODAY=2026-12-01 覆盖，用来预演别的月份。

    构建脚本里所有「今天」都必须走这里：如果一处用 date.today()、一处用这个
    覆盖值，产物会自相矛盾（比如标题写 12 月、封面池按 11 月选）。
    """
    raw = os.environ.get("ZHUHAI_TODAY")
    if raw:
        y, m, d = (int(x) for x in raw.split("-"))
        return datetime.date(y, m, d)
    return datetime.date.today()


YEAR = today().year


def sb_configured():
    """留言板是否已接通 Supabase。

    配置写在 static/supabase-config.js 里（前端公开信息）。构建时读一眼：
    两项都填了，导航栏和页脚才出现「留言」入口、页面才进 sitemap；
    没填时页面照样生成，但只显示一句「还没接通」的说明。
    """
    p = os.path.join(ROOT, "static", "supabase-config.js")
    try:
        s = open(p, encoding="utf-8").read()
    except OSError:
        return False
    m = re.search(r"url:\s*['\"](https?://[^'\"]+)['\"]", s)
    k = re.search(r"anon:\s*['\"]([A-Za-z0-9._\-]{20,})['\"]", s)
    return bool(m and k)


def load():
    species = json.load(open(os.path.join(ROOT, "data", "species.json")))
    assets_path = os.path.join(ROOT, "data", "assets.json")
    assets = json.load(open(assets_path)) if os.path.exists(assets_path) else {}
    for sp in species:
        a = assets.get(sp["slug"], {})
        sp["img"] = a.get("img")
        sp["audio"] = a.get("audio")
        gal = a.get("gallery") or []
        # 绘图排在前面：这是本页最有信息量的一张
        sp["gallery"] = sorted(gal, key=lambda g: 0 if g.get("kind") == "plate" else 1)
    return species, assets


def pclass(p):
    if "一级" in p:
        return "p1"
    if "二级" in p:
        return "p2"
    return "p3"


GROUP_ORDER = {"songbird": 0, "water": 1, "shore": 2, "raptor": 3, "kingfisher": 4}
RARITY_LABEL = {1: "极常见", 2: "常见", 3: "不常见", 4: "局部常见", 5: "罕见"}

I18N_DIR = os.path.join(ROOT, "data", "i18n")
SITE = "https://birds.signupeverywhere.cc"
# IndexNow 密钥：放在站点根目录的 <key>.txt 里，Bing / Yandex / Seznam / Naver
# 先来取这个文件确认域名归属，之后就能用一次 POST 通知它们 URL 变了。
INDEXNOW_KEY = "3898acb4267601cdbe79afa64928d45a"
LANGS = ("zh", "en")

# 分享卡片统一尺寸（1080×1080：微信缩略图是 1:1，横图会被裁掉两侧）
OG_W, OG_H = 1080, 1080


def og_url(slug):
    """每个物种一张 1200×630 的分享图（scripts/make_og.py 生成）。
    退回原图是为了兜底：万一某张没生成，至少还有图，不会是光秃秃的灰卡。"""
    return "%s/assets/og/%s.jpg" % (SITE, slug)


def page_url(path):
    """Pages 会把 /x.html 以 308 跳到 /x，canonical / sitemap 必须写最终地址，
    否则等于把搜索引擎指向一个重定向。"""
    return SITE + re.sub(r"\.html$", "", path)


HERO_SLUG = "zhu-jing-ban-jiu"
DEFAULT_OG = og_url(HERO_SLUG)

# 首页封面每天换一只：按日期取模，选中的鸟连同它的鸣声一起换。
# 池子里只放「鸣声好听 + 图清楚 + 全年可见」的常见种——封面是引导用户往下看的，
# 放一只难得一见或叫声难听的，等于第一眼就把人劝走。
# 顺序固定，不能随手调：日期取模依赖下标，改顺序等于打乱已经排好的日历。
HERO_POOL = [
    "zhu-jing-ban-jiu",       # 珠颈斑鸠：咕—咕—咕，最容易被认出的城市声音
    "wu-dong",                # 乌鸫：百舌，会学别的鸟叫
    "bai-tou-bei",            # 白头鹎：清晨最吵的那只
    "hong-er-bei",            # 红耳鹎：哨音上扬，脸上有红点
    "an-lu-xiu-yan-niao",     # 暗绿绣眼鸟：细碎的铃声
    "ba-ge",                  # 八哥：会模仿，学得还挺像
    "pu-tong-cui-niao",       # 普通翠鸟：一道蓝影 + 尖细哨声
    "chun-se-shan-jiao-ying", # 纯色山鹪莺：草丛里连续冒泡的叫声
]
HERO_WINDOW = (0, 14)         # 默认只试听前 14 秒


def jld(obj):
    """结构化数据。ensure_ascii=False 让中文原样输出；
    </ 转义避免提前闭合 script。"""
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return Markup('<script type="application/ld+json">%s</script>'
                  % s.replace("</", "<\\/"))


def load_i18n():
    ui = json.load(open(os.path.join(I18N_DIR, "ui.json")))
    vocab = json.load(open(os.path.join(I18N_DIR, "vocab.json")))
    p = os.path.join(ROOT, "data", "species_en.json")
    sen = json.load(open(p)) if os.path.exists(p) else {}
    return ui, vocab, sen


def clean_credit(s):
    """署名里少数几条中文前缀，英文版统一成英文。"""
    return (s or "").replace("iNaturalist 用户 ", "iNaturalist user ")


def make_view(sp, lang, sen, vocab):
    """把一条物种数据整理成某个语言下可直接渲染的视图。"""
    v = dict(sp)
    v["is_en"] = lang == "en"
    v["og_image"] = og_url(sp["slug"])
    v["og_w"], v["og_h"] = OG_W, OG_H
    if lang == "zh":
        v["name"] = sp["zh"]
        return v

    t = sen.get(sp["slug"]) or {}
    E = vocab["enum"]
    v["name"] = sp["en"]
    v["family"] = vocab["family"].get(sp["family"], sp["family"])
    for k in ("residency", "common", "protect"):
        v[k] = E[k].get(sp[k], sp[k])
    v["iucn"] = E["iucn"].get(sp["iucn"], sp["iucn"])
    v["rlabel"] = E["rarity"].get(str(sp.get("rank", 2)), "Common")
    v["habitat"] = [vocab["habitat"].get(h, h) for h in sp["habitat"]]
    v["where"] = [vocab["where"].get(w, w) for w in sp["where"]]

    fz = t.get("features") or []
    if len(fz) == len(sp["features"]):
        v["features"] = fz
    else:  # 还没翻译的物种，先退到「特征键英文 + 中文正文」
        v["features"] = [{"k": vocab["feature_k"].get(f["k"], f["k"]), "v": f["v"]}
                         for f in sp["features"]]
    for k in ("tagline", "summary", "behavior", "voice", "tip"):
        if t.get(k):
            v[k] = t[k]

    gal = []
    for g in sp.get("gallery") or []:
        gg = dict(g)
        if gg.get("note"):
            gg["note"] = vocab["gallery_note"].get(gg["note"], gg["note"])
        if gg.get("credit"):
            gg["credit"] = clean_credit(gg["credit"])
        gal.append(gg)
    v["gallery"] = gal
    if v.get("audio"):
        au = dict(v["audio"])
        au["credit"] = clean_credit(au.get("credit"))
        v["audio"] = au
    return v


def nm(x):
    """名字渲染：中文走逐字注音（ruby），英文直接输出。"""
    if x.get("is_en"):
        return Markup(escape(x["name"]))
    return ruby(x.get("zh") or x["name"], x.get("py", ""))


def main():
    species, assets = load()
    slugs = {s["slug"] for s in species}

    # 按遇见率排序：极常见 → 罕见；同等级内按类群、名称稳定排列
    species.sort(key=lambda s: (s.get("rank", 2), GROUP_ORDER.get(s["group"], 9), s["zh"]))
    for i, sp in enumerate(species, 1):
        sp["no"] = "%03d" % i
        sp["rlabel"] = RARITY_LABEL.get(sp.get("rank", 2), "常见")

    from collections import Counter
    rank_counts = Counter(s.get("rank", 2) for s in species)

    for sp in species:
        sp["similar"] = [x for x in sp.get("similar", []) if x in slugs]
        sp["pclass"] = pclass(sp["protect"])

    ui, vocab, sen = load_i18n()
    zh2en = {s["zh"]: s["en"] for s in species}
    PY = {s["zh"]: s.get("py", "") for s in species}

    env = Environment(
        loader=FileSystemLoader(os.path.join(ROOT, "templates")),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True, lstrip_blocks=True,
    )
    env.globals.update(YEAR=YEAR, CSSV=asset_ver("style.css"), JSV=asset_ver("app.js"),
                       BV=asset_ver("beacon.js"),
                       SBV=asset_ver("supabase-config.js"), BOV=asset_ver("board.js"),
                       SUV=asset_ver("vendor/supabase.js"), VSV=asset_ver("visits.js"),
                       ruby=ruby, nm=nm)

    sb_on = sb_configured()

    clean_dist()
    for d in ("bird", "zh/bird", "assets/img", "assets/audio", "assets/og", "static",
              "board", "zh/board", "visits"):
        p = os.path.join(DIST, d)
        if not os.path.isdir(p):
            os.makedirs(p)

    for f in os.listdir(os.path.join(ROOT, "static")):
        src_p = os.path.join(ROOT, "static", f)
        dst_p = os.path.join(DIST, "static", f)
        if os.path.isdir(src_p):          # static/vendor 这类子目录（Supabase SDK）
            shutil.copytree(src_p, dst_p, dirs_exist_ok=True)
        else:
            shutil.copy2(src_p, dst_p)
    for sub in ("img", "audio", "og"):
        src = os.path.join(ROOT, "assets", sub)
        if os.path.isdir(src):
            for f in os.listdir(src):
                if f.startswith("."):
                    continue
                shutil.copy2(os.path.join(src, f), os.path.join(DIST, "assets", sub, f))

    totals = {}
    for lang in LANGS:
        en = lang == "en"
        # 英文是站点默认语言，放在根目录；中文镜像到 /zh/ 下
        sub = "" if en else "zh"
        base = os.path.join(DIST, sub) if sub else DIST
        root_i = "" if en else "../"          # 首页所在层级的资源前缀
        root_d = "../" if en else "../../"    # 详情页所在层级的资源前缀
        pr_i = ""                             # 同语言内的页面链接（首页与 404 都在本语言根目录）
        T = ui[lang]
        hl = "en" if en else "zh-CN"
        groups = GROUPS_EN if en else GROUPS
        spots_src = SPOTS_EN if en else SPOTS
        ethics = ETHICS_EN if en else ETHICS
        views = [make_view(s, lang, sen, vocab) for s in species]
        by = {v["slug"]: v for v in views}

        counts = {g["id"]: 0 for g in groups}
        for v in views:
            counts[v["group"]] = counts.get(v["group"], 0) + 1
        for g in groups:
            g["count"] = counts.get(g["id"], 0)

        spots = []
        for s in spots_src:
            items = []
            for b in s["birds"]:
                if en:
                    items.append({"name": zh2en.get(b, b), "is_en": True})
                else:
                    items.append({"name": b, "zh": b, "py": PY.get(b, ""), "is_en": False})
            spots.append(dict(s, bird_items=items))

        common = dict(T=T, hl=hl, lang=lang, total=len(views),
                      GROUPS=groups, SPOTS=spots, ETHICS=ethics,
                      rank_counts=rank_counts, SB=sb_on)

        # ---- 首页 ----
        # 封面鸟每天换：池子里的 8 只都是「鸣声好听 + 图清楚 + 全年可见」的常见种。
        # 静态页渲染的是「今天」那一只（爬虫和禁 JS 的用户看到的就是它），
        # 页面里再带一份候选表，浏览器按本地日期重算一次——
        # 这样既不用每天重新构建，跨过零点也会自动换。
        sp_path = "/species.html" if en else "/zh/species.html"
        sp_canon = page_url(sp_path)

        pool_views = [by[s] for s in HERO_POOL if s in by]
        today_ = today()
        eligible = [v for v in pool_views
                    if today_.month in (v.get("months") or range(1, 13))] or pool_views
        hero = eligible[today_.toordinal() % len(eligible)]

        def hero_entry(v):
            img = v.get("img") or {}
            au = v.get("audio") or {}
            w_in, w_out = HERO_WINDOW
            return {
                "slug": v["slug"],
                "name": v.get("name") or v["zh"],
                "sci": v.get("sci", ""),
                "img": root_i + "assets/img/" + img.get("big", ""),
                "w": img.get("w", 0),
                "h": img.get("h", 0),
                "credit": img.get("credit", ""),
                "license": img.get("license", ""),
                "audio": root_i + "assets/audio/" + au.get("file", ""),
                "in": au.get("hero_in", w_in),
                "out": au.get("hero_out", w_out),
                "months": v.get("months") or list(range(1, 13)),
                "href": pr_i + "bird/" + v["slug"] + ".html#voice",
            }

        hero_json = json.dumps([hero_entry(v) for v in pool_views],
                               ensure_ascii=False, separators=(",", ":"))

        # 首页名录：8 只「全年都在」的常见种 + 4 只「本月才到」的候鸟。
        # 为什么不全按 rank 排：留鸟每个月的 rank 都一样，排出来 12 个月长得完全相同，
        # 「这个月」就成了空话。真正随月变化的是候鸟——11 月是红嘴鸥、白鹡鸰，
        # 7 月换成家燕、噪鹃。这样这块内容每个月都真的不一样，而且都看得到。
        # 注意：v["residency"] 是本地化之后的值（英文页是 "Winter visitor"），
        # 判断候鸟必须回到 species.json 里的中文原文，否则英文页会全部判成留鸟。
        raw_res = {sp["slug"]: (sp.get("residency") or "") for sp in species}

        def is_seasonal(v):
            r = raw_res.get(v["slug"], "")
            return ("候鸟" in r or "过境" in r) and "留鸟" not in r

        order = {v["slug"]: i for i, v in enumerate(views)}
        here = [v for v in views
                if today_.month in (v.get("months") or range(1, 13))]

        picked = [v for v in pool_views if v["slug"] in {x["slug"] for x in here}]
        seasonal = [v for v in here
                    if v["slug"] not in HERO_POOL and is_seasonal(v)]
        seasonal.sort(key=lambda v: (v.get("rank", 9), order[v["slug"]]))
        picked += seasonal[:4]

        if len(picked) < 12:
            chosen = {v["slug"] for v in picked}
            filler = [v for v in here if v["slug"] not in chosen]
            filler.sort(key=lambda v: (v.get("rank", 9), order[v["slug"]]))
            picked += filler[:12 - len(picked)]
        picked = picked[:12]
        n_seasonal = sum(1 for v in picked if is_seasonal(v))
        home_canon = SITE + ("/" if en else "/zh/")
        home_jld = jld({
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "WebSite", "@id": SITE + "/#website", "url": SITE + "/",
                 "name": T["brand"], "inLanguage": hl,
                 "description": (T["idx"]["desc"] % len(views))},
                {"@type": "CollectionPage", "@id": home_canon,
                 "url": home_canon, "name": T["idx"]["title"] % len(views),
                 "isPartOf": {"@id": SITE + "/#website"}, "inLanguage": hl},
            ],
        })
        html = env.get_template("index.html").render(
            **common, root=root_i, pr=pr_i, hero=hero, nav="home", species=picked,
            hero_pool=Markup(hero_json), hero_day=today_.toordinal(),
            mon=(datetime.date(2000, today_.month, 1).strftime('%B') if en else today_.month),
            n_seasonal=n_seasonal,
            hero_in=hero["audio"].get("hero_in", HERO_WINDOW[0]) if hero.get("audio") else 0,
            hero_out=hero["audio"].get("hero_out", HERO_WINDOW[1]) if hero.get("audio") else 0,
            all_total=len(views), species_href=pr_i + "species.html",
            page_title=T["idx"]["title"] % len(views),
            page_desc=T["idx"]["desc"] % len(views),
            canon=SITE + ("/" if en else "/zh/"),
            zh_url=SITE + "/zh/", en_url=SITE + "/",
            alt_url=("../zh/index.html" if en else "../index.html"),
            jsonld=home_jld)
        open(os.path.join(base, "index.html"), "w").write(html)

        # ---- 完整名录（首页瘦身后，65 种搬到这里）----
        idx_jld = jld({
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "url": sp_canon, "name": T["idx"]["index_title"].replace("<em>", "").replace("</em>", ""),
            "inLanguage": hl, "isPartOf": {"@id": SITE + "/#website"},
            "mainEntity": {
                "@type": "ItemList", "numberOfItems": len(views),
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1, "name": v["name"],
                     "url": page_url("/bird/%s.html" % v["slug"] if en
                                     else "/zh/bird/%s.html" % v["slug"])}
                    for i, v in enumerate(views)],
            },
        })
        html = env.get_template("species.html").render(
            **common, root=root_i, pr=pr_i, nav="species", species=views,
            page_title=(T["idx"]["index_title"].replace("<em>", "").replace("</em>", "")
                        + " · " + T["brand"]),
            page_desc=T["idx"]["desc"] % len(views),
            canon=sp_canon,
            zh_url=page_url("/zh/species.html"), en_url=page_url("/species.html"),
            alt_url=("../zh/species.html" if en else "../species.html"),
            og=DEFAULT_OG, ogw=OG_W, ogh=OG_H, jsonld=idx_jld)
        open(os.path.join(base, "species.html"), "w").write(html)

        # ---- 详情页 ----
        for i, v in enumerate(views):
            prev = views[(i - 1) % len(views)]
            nxt = views[(i + 1) % len(views)]
            sims = [by[x] for x in v["similar"]]
            zh_path = "/zh/bird/%s.html" % v["slug"]
            en_path = "/bird/%s.html" % v["slug"]
            path = en_path if en else zh_path
            title = (T["d"]["title"] % (v["name"], v["sci"]))
            desc = (T["d"]["desc"] % (v["name"], v["sci"], v["tagline"]))
            d_jld = jld({
                "@context": "https://schema.org",
                "@graph": [
                    {"@type": "Taxon", "@id": page_url(path) + "#taxon",
                     "name": v["name"], "scientificName": v["sci"],
                     "alternateName": [v["sci"], v["en"] if en else v["zh"]],
                     "url": page_url(path), "image": v["og_image"],
                     "description": v["tagline"],
                     "isPartOf": {"@id": SITE + "/#website"}},
                    {"@type": "BreadcrumbList", "itemListElement": [
                        {"@type": "ListItem", "position": 1,
                         "name": T["nav"]["species"], "item": sp_canon},
                        {"@type": "ListItem", "position": 2,
                         "name": v["name"], "item": page_url(path)}]},
                ],
            })
            html = env.get_template("detail.html").render(
                **common, sp=v, prev=prev, next=nxt, sims=sims, nav="species",
                root=root_d, pr="../",
                group=next(g for g in groups if g["id"] == v["group"]),
                page_title=title, page_desc=desc,
                canon=page_url(path),
                zh_url=page_url(zh_path),
                en_url=page_url(en_path),
                alt_url=("../../zh/bird/%s.html" % v["slug"]) if en
                        else ("../../bird/%s.html" % v["slug"]),
                jsonld=d_jld)
            open(os.path.join(base, "bird", v["slug"] + ".html"), "w").write(html)

        # ---- 指南页 ----
        gpath = "/guide.html" if en else "/zh/guide.html"
        html = env.get_template("guide_en.html" if en else "guide.html").render(
            **common, root=root_i, pr=pr_i, nav="guide",
            page_title=T["guide"]["title"], page_desc=T["guide"]["desc"],
            canon=page_url(gpath), zh_url=page_url("/zh/guide.html"),
            en_url=page_url("/guide.html"),
            alt_url=("../zh/guide.html" if en else "../guide.html"),
            og=DEFAULT_OG, ogw=OG_W, ogh=OG_H)
        open(os.path.join(base, "guide.html"), "w").write(html)

        # ---- 留言板 ----
        bpath = "/board/" if en else "/zh/board/"
        html = env.get_template("board.html").render(
            **common, root=root_d, pr="../", nav="board",
            page_title="%s · %s" % (T["board"]["h1"], T["brand"]),
            page_desc=T["board"]["lede"],
            canon=SITE + bpath,
            zh_url=SITE + "/zh/board/", en_url=SITE + "/board/",
            alt_url=("../zh/board/index.html" if en else "../../board/index.html"),
            og=DEFAULT_OG, ogw=OG_W, ogh=OG_H)
        open(os.path.join(base, "board", "index.html"), "w").write(html)

        # ---- 404 ----
        html = env.get_template("404.html").render(
            **common, root=root_i, nav="", page_title=T["e"]["title"], page_desc=T["e"]["desc"],
            pr=pr_i, canon="", zh_url="", en_url="",
            picks=views[:6],
            alt_url=("../zh/index.html" if en else "../index.html"))
        open(os.path.join(base, "404.html"), "w").write(html)
        totals[lang] = len(views)

    # ---- 访客看板（站长专用：noindex、不进导航与 sitemap、robots 屏蔽）----
    Tzh = ui["zh"]
    birds_map = {s["slug"]: s["zh"] for s in species}
    html = env.get_template("visits.html").render(
        T=Tzh, hl="zh-CN", lang="zh", nav="", total=totals["zh"], SB=sb_on,
        root="../", pr="../zh/", alt_url="/zh/",
        GROUPS=GROUPS, SPOTS=SPOTS, ETHICS=ETHICS, rank_counts=rank_counts,
        BIRDS_JSON=json.dumps(birds_map, ensure_ascii=False).replace("</", "<\\/"))
    open(os.path.join(DIST, "visits", "index.html"), "w").write(html)

    # ---- robots / sitemap ----
    open(os.path.join(DIST, "robots.txt"), "w").write(
        # 不在 robots 里写 /visits/：那等于把路径告诉所有人；靠口令 + noindex 就够
        "User-agent: *\nDisallow: /admin/\nDisallow: /api/\nAllow: /\n"
        "Sitemap: %s/sitemap.xml\n" % SITE)
    open(os.path.join(DIST, INDEXNOW_KEY + ".txt"), "w").write(INDEXNOW_KEY + "\n")

    # ---- 缓存策略 ----
    # 静态资源都带 ?v=<内容哈希>，文件名没变时内容一定没变，可以放心永久缓存。
    # 图片和音频同理（文件名即内容），给 7 天足够回访时不重复下载。
    # HTML 不写规则：默认 max-age=0 是对的，页面要跟着日期变。
    open(os.path.join(DIST, "_headers"), "w").write(
        "/*\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n"
        "\n"
        "/static/*\n"
        "  Cache-Control: public, max-age=31536000, immutable\n"
        "\n"
        "/assets/img/*\n"
        "  Cache-Control: public, max-age=604800\n"
        "\n"
        "/assets/audio/*\n"
        "  Cache-Control: public, max-age=604800\n")
    pairs = [("/zh/", "/"), ("/zh/species.html", "/species.html"),
             ("/zh/guide.html", "/guide.html")]
    if sb_on:
        pairs.append(("/zh/board/", "/board/"))
    pairs += [("/zh/bird/%s.html" % s["slug"], "/bird/%s.html" % s["slug"]) for s in species]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
          '        xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for zh_p, en_p in pairs:
        for p, other in ((zh_p, en_p), (en_p, zh_p)):
            sm.append("  <url>")
            sm.append("    <loc>%s</loc>" % page_url(p))
            sm.append('    <xhtml:link rel="alternate" hreflang="zh-CN" href="%s"/>' % page_url(zh_p))
            sm.append('    <xhtml:link rel="alternate" hreflang="en" href="%s"/>' % page_url(en_p))
            sm.append('    <xhtml:link rel="alternate" hreflang="x-default" href="%s"/>' % page_url(en_p))
            sm.append("    <changefreq>monthly</changefreq>")
            sm.append("  </url>")
    sm.append("</urlset>")
    open(os.path.join(DIST, "sitemap.xml"), "w").write("\n".join(sm))

    # 旧地址（英文曾在 /en/ 下）永久跳转到新位置
    open(os.path.join(DIST, "_redirects"), "w").write(
        "/en/*  /:splat  301\n"
        "/en    /        301\n"
        "/admin/*  /visits/  301\n"
        "/admin    /visits/  301\n"
        "/zh/visits/*  /visits/  301\n"
        "/zh/visits    /visits/  301\n")

    n_img = sum(1 for s in species if s["img"])
    n_aud = sum(1 for s in species if s["audio"])
    print("生成完成：%d 个物种 × %d 种语言，%d 图片，%d 音频" % (len(species), len(LANGS), n_img, n_aud))
    print("留言板：%s" % ("已接通 Supabase，导航已显示入口" if sb_on
                        else "未配置 —— 填 static/supabase-config.js 后入口才出现"))
    missing = [s["zh"] for s in species if s["slug"] not in sen]
    if missing:
        print("待翻译（%d）：%s" % (len(missing), "、".join(missing)))
    if n_img < len(species):
        print("缺图：", [s["zh"] for s in species if not s["img"]])
    if n_aud < len(species):
        print("缺音频：", [s["zh"] for s in species if not s["audio"]])


if __name__ == "__main__":
    main()
