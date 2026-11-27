"""Validate every samples/<name>.jsonl (or a dataset dir) against schemas/<name>.schema.json,
then run cross-file integrity checks.  Usage:  python validate.py [data_dir]   (default: samples)"""
import json, pathlib, sys
from jsonschema import Draft202012Validator

ROOT = pathlib.Path(__file__).parent
DATA = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples"
errors, warns = 0, 0
rows = {}

for sf in sorted((ROOT / "schemas").glob("*.schema.json")):
    name = sf.name.replace(".schema.json", "")
    f = DATA / f"{name}.jsonl"
    if not f.exists():
        print(f"- {name}: (no data file)"); continue
    v = Draft202012Validator(json.loads(sf.read_text(encoding="utf-8")))
    rows[name] = []
    for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        rec = json.loads(line); rows[name].append(rec)
        for e in v.iter_errors(rec):
            errors += 1
            print(f"ERROR {name}:{i} /{'/'.join(map(str, e.absolute_path))}: {e.message[:160]}")
    print(f"- {name}: {len(rows[name])} record(s) checked")

def ids(name, key):
    return {r[key] for r in rows.get(name, [])}

def check(cond, msg, hard=True):
    global errors, warns
    if not cond:
        if hard: errors += 1; print("ERROR", msg)
        else: warns += 1; print("WARN ", msg)

prec, prov, qry, pas = ids("precedents", "precedent_id"), ids("provisions", "prov_id"), ids("queries", "query_id"), ids("passages", "passage_id")

for p in rows.get("precedents", []):
    pid = p["precedent_id"]
    flagged = sorted(x["no"] for x in p["text_sections"]["nhan_dinh"] if x["in_an_le_content"])
    check(flagged == sorted(p["vi_tri_noi_dung"]["doan"]), f"{pid}: vi_tri_noi_dung.doan != paragraphs flagged in_an_le_content {flagged}")
    check(pid.split("-")[1] == p["so_hieu"].replace("/AL", ""), f"{pid}: precedent_id không khớp so_hieu")
    for h in p["holdings"]:
        for pr in h["provisions"]:
            check(pr in prov, f"{pid}/{h['id']}: provision {pr} chưa có trong provisions.jsonl", hard=False)
    for x in p["text_sections"]["nhan_dinh"]:
        if x["stance"] == "rejected_quoted":
            check(not any(h["id"] and x["no"] in h.get("applies_to_paragraphs", []) for h in p["holdings"]),
                  f"{pid}: đoạn {x['no']} bị bác bỏ nhưng được gán làm căn cứ holding")

for name in ("qrels", "annotations", "pairs", "reasoning_items"):
    for r in rows.get(name, []):
        check(r["query_id"] in qry, f"{name}: query {r['query_id']} không tồn tại")
        if "precedent_id" in r:
            check(r["precedent_id"] in prec, f"{name}: precedent {r['precedent_id']} chưa có trong precedents.jsonl", hard=False)
for r in rows.get("qrels", []):
    for pid in r.get("evidence_passage_ids", []):
        check(pid in pas, f"qrels: passage {pid} chưa có trong passages.jsonl", hard=False)
for r in rows.get("annotations", []):
    for h in r["highlights"]:
        check(h["passage_id"] in pas, f"annotations: passage {h['passage_id']} chưa có", hard=False)
for r in rows.get("passages", []):
    check(r["doc_id"] in prec or r["doc_type"] == "judgment", f"passages: doc {r['doc_id']} không tồn tại")

print(f"\n{errors} error(s), {warns} warning(s)")
sys.exit(1 if errors else 0)
