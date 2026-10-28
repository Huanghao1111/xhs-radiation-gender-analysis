"""评论者性别 × 主题类别 交叉分析
join 链：raw detail 评论记录(ah 字段含 uid) -> comment_id；commenters.json (uid->gender)；
comment-adjudicated-with-postgender.json (comment_id -> cat, post_g)
用法：python scripts/commenter_gender_analysis.py
"""
import json, glob, re, hashlib, sys
from collections import Counter, defaultdict

def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

# 1) comment_id -> uid（从 raw detail 抓取恢复）
cid2uid = {}
TEXTS = {}
for f in glob.glob("corpus/raw/detail-*.json"):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    for c in d.get("comments", []):
        ah = c.get("ah") or ""
        m = re.search(r"/user/profile/([0-9a-f]{24})", ah)
        if m and c.get("cid"):
            cid2uid[c["cid"]] = m.group(1)
        if c.get("cid"):
            TEXTS[c["cid"]] = (c.get("c") or "")[:80]

print("cid->uid mappings:", len(cid2uid), file=sys.stderr)

# 2) uid -> gender
commenters = json.load(open("corpus/commenters.json", encoding="utf-8"))
uid2g = {u: v.get("gender") for u, v in commenters.items() if isinstance(v, dict)}

# 3) 裁定评论
adj = json.load(open("corpus/comment-adjudicated-with-postgender.json", encoding="utf-8"))

# 4) 交叉
by_cat = defaultdict(Counter)          # cat -> gender counter
unknown_cids = []
for r in adj:
    cat = r["cat"]
    uid = cid2uid.get(r["comment_id"])
    g = uid2g.get(uid) if uid else None
    by_cat[cat][g or "U"] += 1
    if not uid:
        unknown_cids.append(r["comment_id"])

print(f"{'cat':<4} {'F':>4} {'M':>4} {'U':>4}  total  F% (of known)")
for cat in sorted(by_cat):
    c = by_cat[cat]
    tot = sum(c.values())
    known = c["F"] + c["M"]
    fp = 100 * c["F"] / known if known else 0
    print(f"{cat:<4} {c['F']:>4} {c['M']:>4} {c['U']:>4}  {tot:>5}  {fp:.0f}%")

# 5) G 类明细（含文本，供人工核读）
print("\n=== G 类逐条 ===")
for r in adj:
    if r["cat"] == "G":
        uid = cid2uid.get(r["comment_id"])
        g = uid2g.get(uid, "?") if uid else "?"
        print(f"{g:>2} | post:{r['post_g']} | {TEXTS.get(r['comment_id'],'[no text]')}")

json.dump({k: dict(v) for k, v in by_cat.items()},
          open("corpus/commenter-gender-by-cat.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
