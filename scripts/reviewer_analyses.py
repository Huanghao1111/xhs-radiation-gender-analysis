"""审稿补充分析（Tom T1/T2/T3/T6/T8）
T1 作者层敏感性：从业者帖聚类到作者，比较「发过≥1条代价帖」的作者比例 F vs M
T2 射线子集卡方+P
T3 盲重编码一致性复核（valence 一致率/κ、角色一致率）
T6 生育主题从业者帖唯一作者数
T8 评论层裁定条数
"""
import json, math
from collections import Counter, defaultdict
import importlib.util

spec = importlib.util.spec_from_file_location("fs", "scripts/final_stats.py")
fs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fs)  # 复用其 coded/valence/posts/author_gender/nid2sha/PRAC/RAD

coded, valence, posts = fs.coded, fs.valence, fs.posts
nid2sha, author_gender, PRAC, RAD = fs.nid2sha, fs.author_gender, fs.PRAC, fs.RAD

def chi2_p(a, b, c, d):
    n = a + b + c + d
    num = n * (a * d - b * c) ** 2
    den = (a + b) * (c + d) * (a + c) * (b + d)
    x = num / den if den else 0
    p = math.erfc(math.sqrt(x / 2))  # df=1
    return x, p

out = {}

# ---- T1 作者层 ----
prac = [nid for nid, d in coded.items() if d["l1a"] in PRAC]
au = defaultdict(lambda: {"g": None, "v": Counter()})
for nid in prac:
    sha = nid2sha.get(nid)
    if not sha:
        continue
    g, _ = author_gender(sha)
    au[sha]["g"] = g
    au[sha]["v"][valence.get(nid, "V?")] += 1

auth_g = Counter(a["g"] for a in au.values())
out["T1_unique_authors"] = dict(auth_g)
out["T1_posts_per_author"] = round(len(prac) / len(au), 2)

# 「≥1 条代价帖」作者比例
def any_v1(g):
    ids = [s for s, a in au.items() if a["g"] == g]
    k = sum(1 for s in ids if au[s]["v"].get("V1", 0) > 0)
    return k, len(ids)
f1, fn = any_v1("F")
m1, mn = any_v1("M")
x, p = chi2_p(f1, fn - f1, m1, mn - m1)
out["T1_author_level_V1"] = {
    "F": {"k": f1, "n": fn, "pct": round(f1 / fn * 100, 1)},
    "M": {"k": m1, "n": mn, "pct": round(m1 / mn * 100, 1)},
    "chi2": round(x, 2), "P": p,
}

# 作者主导 valence（多数票，平票取最高优先级 V1>V3>V2）作稳健性
def dom_v(c):
    mx = max(c.values())
    for v in ("V1", "V3", "V2"):
        if c.get(v, 0) == mx:
            return v
dom = defaultdict(Counter)
for s, a in au.items():
    dom[a["g"]][dom_v(a["v"])] += 1
fd = dom["F"].get("V1", 0); md = dom["M"].get("V1", 0)
fn2 = sum(dom["F"].values()); mn2 = sum(dom["M"].values())
x2, p2 = chi2_p(fd, fn2 - fd, md, mn2 - md)
out["T1_author_dominant"] = {
    "F": {"V1": fd, "n": fn2, "pct": round(fd / fn2 * 100, 1)},
    "M": {"V1": md, "n": mn2, "pct": round(md / mn2 * 100, 1)},
    "chi2": round(x2, 2), "P": p2,
}

# ---- T2 射线子集 ----
rad = [nid for nid in prac if set(coded[nid].get("themes", [])) & RAD]
rc = defaultdict(Counter)
for nid in rad:
    g, _ = author_gender(nid2sha[nid])
    rc[g][valence.get(nid, "V?")] += 1
fr, mr = rc["F"], rc["M"]
fa, fnr = fr.get("V1", 0), sum(fr.values())
ma, mnr = mr.get("V1", 0), sum(mr.values())
x3, p3 = chi2_p(fa, fnr - fa, ma, mnr - ma)
out["T2_rad_subset"] = {
    "F": {"V1": fa, "n": fnr, "pct": round(fa / fnr * 100, 1)},
    "M": {"V1": ma, "n": mnr, "pct": round(ma / mnr * 100, 1)},
    "chi2": round(x3, 2), "P": round(p3, 4),
}

# ---- T3 盲重编码一致性 ----
# blind-recode.jsonl 键为 note_id/l1a/themes/valence（盲编值）；
# 原编码值从 final_stats 的 coded/valence（含裁定层覆盖）按 note_id 查回
blind = [json.loads(l) for l in open("corpus/blind-recode.jsonl", encoding="utf-8") if l.strip()]
blind = [d for d in blind if d["note_id"] in coded]
n = len(blind)
keys_b = list(blind[0].keys())
agree_v = sum(1 for d in blind if d.get("valence") == valence.get(d["note_id"]))
# Cohen's kappa on valence V1/V2/V3
cats = ["V1", "V2", "V3"]
po = agree_v / n
pe = 0
for c in cats:
    po_c = sum(1 for d in blind if valence.get(d["note_id"]) == c) / n
    pb_c = sum(1 for d in blind if d.get("valence") == c) / n
    pe += po_c * pb_c
kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
# 角色二分类（从业者 vs 非从业者）
def is_prac(r):
    return r in PRAC
agree_r = sum(1 for d in blind if is_prac(d.get("l1a")) == is_prac(coded[d["note_id"]].get("l1a")))
out["T3_blind_recode"] = {
    "n": n, "keys": keys_b,
    "valence_agree": f"{agree_v}/{n} ({agree_v/n*100:.1f}%)",
    "kappa": round(kappa, 2),
    "role_binary_agree": f"{agree_r}/{n} ({agree_r/n*100:.1f}%)",
}

# ---- T6 生育主题从业者帖唯一作者 ----
fert = [nid for nid in prac if "T1" in coded[nid].get("themes", [])]
fert_known = []
for nid in fert:
    g, _ = author_gender(nid2sha[nid])
    if g in ("F", "M"):
        fert_known.append((nid, g))
fert_sha = {nid2sha[nid] for nid, g in fert_known}
fert_f_sha = {nid2sha[nid] for nid, g in fert_known if g == "F"}
out["T6_fertility"] = {
    "posts_known_gender": len(fert_known),
    "gender_of_posts": dict(Counter(g for _, g in fert_known)),
    "unique_authors": len(fert_sha),
    "unique_authors_F": len(fert_f_sha),
}

# ---- T8 评论裁定条数 ----
import os
t8 = {}
for f in ("comment-themes-adjudicated.jsonl", "comment-partner-adjudicated.jsonl"):
    p = f"corpus/{f}"
    if os.path.exists(p):
        t8[f] = sum(1 for l in open(p, encoding="utf-8") if l.strip())
p = "corpus/comment-adjudicated-with-postgender.json"
if os.path.exists(p):
    t8["comment-adjudicated-with-postgender.json"] = len(json.load(open(p, encoding="utf-8")))
out["T8_comment_adjudicated"] = t8

print(json.dumps(out, ensure_ascii=False, indent=1))
json.dump(out, open("corpus/reviewer-analyses.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
