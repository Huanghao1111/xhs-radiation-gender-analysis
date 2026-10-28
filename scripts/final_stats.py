"""语料终版统计：输出 paper 用全部关键数字 → corpus/final-stats.json
用法: python scripts/final_stats.py
口径：
- 帖子层 L1a：C1 心内介入 / C2 导管室护技 / C3 其他介入 / C4 放疗放射 / C5 其他医护 / C6 医学生 / P 患者家属 / W 伴侣 / M 营销 / X 无法判断
- 主队列 = C1 + C2 + C6且note标cardio
- valence：V1 代价 / V2 中性 / V3 赋能；从业者帖 = L1a in C1..C6
- 作者性别：authors.json 资料页 gender 优先；无则用该作者帖的 l1b 文本自述多数票；再无记 U
- 射线主题集 RAD = {T1,T2,T3,T4,T5,T8,T9}（T6 职业选择/T7 文化/T0 不计入）
"""
import json
from collections import Counter, defaultdict

CORP = "corpus"

def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]

posts = {d["note_id"]: d for d in load_jsonl(f"{CORP}/posts.jsonl")}
coded = {}
for f in ("l1-posts-full-coded.jsonl", "l1-exp-coded.jsonl"):
    for d in load_jsonl(f"{CORP}/{f}"):
        coded[d["note_id"]] = d

# valence 合并（第一轮独立文件优先）
valence = {}
for d in load_jsonl(f"{CORP}/l1-posts-valence.jsonl"):
    valence[d["note_id"]] = d["valence"]
for nid, d in coded.items():
    if nid not in valence and d.get("valence"):
        valence[nid] = d["valence"]

# 全文人工裁定层（最高权威，覆盖角色/主题/valence）
import os
ADJ_N = 0
if os.path.exists(f"{CORP}/exp-fulltext-adjudicated.jsonl"):
    for d in load_jsonl(f"{CORP}/exp-fulltext-adjudicated.jsonl"):
        nid = d["note_id"]
        if nid not in coded:
            continue
        ADJ_N += 1
        if d.get("role_fix"):
            coded[nid]["l1a"] = d["role_fix"]
        if d.get("themes"):
            coded[nid]["themes"] = d["themes"]
        if d.get("valence"):
            valence[nid] = d["valence"]

# 作者性别
authors = {a["sha"]: a for a in json.load(open(f"{CORP}/authors.json", encoding="utf-8"))}
nid2sha = {nid: p["author_uid_sha"] for nid, p in posts.items()}
# 文本自述兜底：按作者聚合 l1b
l1b_votes = defaultdict(Counter)
for nid, d in coded.items():
    sha = nid2sha.get(nid)
    if sha and d.get("l1b") in ("F", "M"):
        l1b_votes[sha][d["l1b"]] += 1

def author_gender(sha):
    a = authors.get(sha)
    if a and a.get("gender") in ("F", "M"):
        return a["gender"], "profile"
    v = l1b_votes.get(sha)
    if v:
        g = v.most_common(1)[0][0]
        return g, "text"
    if a and a.get("gender") == "U":
        return "U", "profile_none"
    return "U", "no_data"

PRAC = {"C1", "C2", "C3", "C4", "C5", "C6"}
RAD = {"T1", "T2", "T3", "T4", "T5", "T8", "T9"}

out = {}
out["n_posts"] = len(posts)
out["l1a"] = dict(Counter(d["l1a"] for d in coded.values()))

# 主队列
CARDIO_KW = ["心内", "电生理", "造影", "冠脉", "起搏", "射频", "消融", "PCI", "pci",
             "房颤", "导管室", "DSA", "心律失常"]

def is_main(nid, d):
    if d["l1a"] in ("C1", "C2"):
        return True
    if d["l1a"] == "C6":
        txt = (d.get("title") or "") + (d.get("note") or "")
        return any(k in txt for k in CARDIO_KW)
    return False

main_ids = [nid for nid, d in coded.items() if is_main(nid, d)]
out["main_cohort"] = len(main_ids)
out["main_rad"] = sum(1 for nid in main_ids if set(coded[nid].get("themes", [])) & RAD)

# 从业者 valence × 性别
prac = [nid for nid, d in coded.items() if d["l1a"] in PRAC]
cross = defaultdict(Counter)   # gender -> valence
via_counter = Counter()
for nid in prac:
    g, via = author_gender(nid2sha[nid])
    via_counter[via] += 1
    v = valence.get(nid, "V?")
    cross[g][v] += 1

def pct(c, k):
    n = sum(c.values())
    return round(c.get(k, 0) / n * 100, 1) if n else 0

out["practitioner_total"] = len(prac)
out["gender_via"] = dict(via_counter)
out["valence_by_gender"] = {
    g: {"n": sum(c.values()), "V1": pct(c, "V1"), "V2": pct(c, "V2"), "V3": pct(c, "V3"),
        "raw": dict(c)} for g, c in cross.items()
}

# 卡方：V1 vs 非V1，F×M
def chi2_2x2(a, b, c, d):
    n = a + b + c + d
    num = n * (a * d - b * c) ** 2
    den = (a + b) * (c + d) * (a + c) * (b + d)
    return num / den if den else 0

fV1 = cross["F"].get("V1", 0); fN = sum(cross["F"].values()) - fV1
mV1 = cross["M"].get("V1", 0); mN = sum(cross["M"].values()) - mV1
out["chi2_V1_F_vs_M"] = round(chi2_2x2(fV1, fN, mV1, mN), 2)
fV3 = cross["F"].get("V3", 0); fN3 = sum(cross["F"].values()) - fV3
mV3 = cross["M"].get("V3", 0); mN3 = sum(cross["M"].values()) - mV3
out["chi2_V3_F_vs_M"] = round(chi2_2x2(fV3, fN3, mV3, mN3), 2)

# 射线主题子集
rad_prac = [nid for nid in prac if set(coded[nid].get("themes", [])) & RAD]
rad_cross = defaultdict(Counter)
for nid in rad_prac:
    g, _ = author_gender(nid2sha[nid])
    rad_cross[g][valence.get(nid, "V?")] += 1
out["rad_subset"] = {g: {"n": sum(c.values()), "V1": pct(c, "V1"), "V2": pct(c, "V2"),
                         "V3": pct(c, "V3"), "raw": dict(c)} for g, c in rad_cross.items()}

# 主题分布（从业者帖内）
th = Counter()
for nid in prac:
    for t in coded[nid].get("themes", []):
        th[t] += 1
out["prac_themes"] = dict(th)

# 分层作者性别覆盖
layers = defaultdict(set)
for nid, d in coded.items():
    sha = nid2sha.get(nid)
    if sha:
        layers[d["l1a"]].add(sha)
lay = {}
for L, shas in layers.items():
    c = Counter()
    for s in shas:
        g, via = author_gender(s)
        c[g] += 1
    lay[L] = {"authors": len(shas), **dict(c)}
out["layer_author_gender"] = lay

# 评论
com = load_jsonl(f"{CORP}/comments.jsonl")
out["comments_total"] = len(com)
out["comments_by_level"] = dict(Counter(c.get("level") for c in com))
det = load_jsonl(f"{CORP}/details.jsonl")
out["details_collected"] = len(det)
out["details_video"] = sum(1 for d in det if d.get("is_video"))

# 患者层 T1 子队列
p_t1 = []
for nid, d in coded.items():
    if d["l1a"] == "P" and "T1" in d.get("themes", []):
        sha = nid2sha.get(nid)
        g, _ = author_gender(sha) if sha else ("U", "")
        p_t1.append({"note_id": nid, "title": d.get("title"), "themes": d["themes"],
                     "note": d.get("note"), "gender": g})
out["P_T1_n"] = len(p_t1)
with open(f"{CORP}/p-t1-subcohort.jsonl", "w", encoding="utf-8") as f:
    for r in p_t1:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# 解决方案话语
solut = [(nid, coded[nid]) for nid in prac if "解决方案" in (coded[nid].get("note") or "")]
out["solution_notes_n"] = len(solut)

# KOL
kol = [nid for nid, p in posts.items()
       if any(str(k).startswith("KOL:") for k in (p.get("keywords") or []))]
out["kol_posts"] = len(kol)
out["adjudicated_overlay_n"] = ADJ_N

with open(f"{CORP}/final-stats.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

print(json.dumps(out, ensure_ascii=False, indent=1))
