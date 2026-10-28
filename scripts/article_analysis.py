"""Article 补充分析：主题×性别计数与检验（口径与 scripts/final_stats.py 完全一致）"""
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

valence = {}
for d in load_jsonl(f"{CORP}/l1-posts-valence.jsonl"):
    valence[d["note_id"]] = d["valence"]
for nid, d in coded.items():
    if nid not in valence and d.get("valence"):
        valence[nid] = d["valence"]

import os
if os.path.exists(f"{CORP}/exp-fulltext-adjudicated.jsonl"):
    for d in load_jsonl(f"{CORP}/exp-fulltext-adjudicated.jsonl"):
        nid = d["note_id"]
        if nid not in coded:
            continue
        if d.get("role_fix"):
            coded[nid]["l1a"] = d["role_fix"]
        if d.get("themes"):
            coded[nid]["themes"] = d["themes"]
        if d.get("valence"):
            valence[nid] = d["valence"]

authors = {a["sha"]: a for a in json.load(open(f"{CORP}/authors.json", encoding="utf-8"))}
nid2sha = {nid: p["author_uid_sha"] for nid, p in posts.items()}
l1b_votes = defaultdict(Counter)
for nid, d in coded.items():
    sha = nid2sha.get(nid)
    if sha and d.get("l1b") in ("F", "M"):
        l1b_votes[sha][d["l1b"]] += 1

def author_gender(sha):
    a = authors.get(sha)
    if a and a.get("gender") in ("F", "M"):
        return a["gender"]
    v = l1b_votes.get(sha)
    if v:
        return v.most_common(1)[0][0]
    return "U"

PRAC = {"C1", "C2", "C3", "C4", "C5", "C6"}
prac = [nid for nid, d in coded.items() if d["l1a"] in PRAC]
g_of = {nid: author_gender(nid2sha[nid]) for nid in prac}
n_by_g = Counter(g_of.values())

def chi2_2x2(a, b, c, d):
    n = a + b + c + d
    den = (a + b) * (c + d) * (a + c) * (b + d)
    return n * (a * d - b * c) ** 2 / den if den else 0

def chi2_p(x):
    # df=1 survival function
    import math
    return math.erfc(math.sqrt(x / 2))

THEMES = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"]
out = {}
for t in THEMES:
    row = {}
    for g in ("F", "M", "U"):
        k = sum(1 for nid in prac if g_of[nid] == g and t in coded[nid].get("themes", []))
        row[g] = {"k": k, "n": n_by_g[g], "pct": round(k / n_by_g[g] * 100, 1)}
    a = row["F"]["k"]; b = row["F"]["n"] - a
    c = row["M"]["k"]; d = row["M"]["n"] - c
    x = chi2_2x2(a, b, c, d)
    row["chi2"] = round(x, 2)
    row["P"] = chi2_p(x)
    out[t] = row

# 从业者视频帖数（与 letter 口径核对）
det = {d["note_id"]: d for d in load_jsonl(f"{CORP}/details.jsonl")}
vid_prac = sum(1 for nid in prac if det.get(nid, {}).get("is_video"))

# 患者/家属层
p_posts = [nid for nid, d in coded.items() if d["l1a"] == "P"]
p_g = Counter(author_gender(nid2sha[nid]) for nid in p_posts)

res = {"n_by_g": dict(n_by_g), "themes": out, "video_prac": vid_prac,
       "P_gender": dict(p_g), "P_n": len(p_posts)}
with open(f"{CORP}/article-theme-gender.json", "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
