"""Kiểm tra output pipeline: JSON Schema từng file + tính nhất quán chéo (span nằm trong text_clean, id khớp, án lệ được viện dẫn có trong corpus)."""
from __future__ import annotations
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from .common import read_jsonl

ROOT = Path(__file__).resolve().parent.parent


def _validator(schemas_dir, name):
    return Draft202012Validator(json.loads((Path(schemas_dir) / f"{name}.schema.json").read_text(encoding="utf-8")))


def validate_outputs(files: dict[str, str], schemas_dir=None, max_errors: int = 15) -> dict:
    """files: {tên_schema: đường_dẫn_jsonl}, vd {'judgments': '.../judgments.jsonl', 'judgment_texts': ..., 'precedents': ...}"""
    schemas_dir = schemas_dir or ROOT / "schemas"
    rep = {"files": {}, "cross": {"errors": [], "warnings": []}, "ok": True}
    data = {}
    for name, path in files.items():
        if not path or not Path(path).exists():
            rep["files"][name] = {"n": 0, "missing_file": True}; continue
        v = _validator(schemas_dir, name); errs = []; rows = []
        for i, r in enumerate(read_jsonl(path), 1):
            rows.append(r)
            for e in v.iter_errors(r):
                errs.append(f"{name}:{i} /{'/'.join(map(str, e.absolute_path))}: {e.message[:140]}")
        data[name] = rows
        rep["files"][name] = {"n": len(rows), "n_errors": len(errs), "errors": errs[:max_errors]}
        if errs: rep["ok"] = False
    c = rep["cross"]
    J, T = data.get("judgments", []), {t["judgment_id"]: t for t in data.get("judgment_texts", [])}
    prec = {p["precedent_id"] for p in data.get("precedents", [])}
    for j in J:
        jid = j["judgment_id"]; t = T.get(jid)
        if t is None:
            c["errors"].append(f"{jid}: thiếu bản ghi trong judgment_texts"); continue
        n = len(t["text_clean"])
        spans = [("section", s["span"]) for s in j["sections"] if s.get("span")]
        spans += [("para", p["span"]) for s in j["sections"] for p in s.get("paragraphs", []) if p.get("span")]
        spans += [("law", x["span"]) for x in j["citations_law"] if x.get("span")]
        spans += [("prec", x["citing_sentence_span"]) for x in j["citations_precedent"] if x.get("citing_sentence_span")]
        for kind, (a, b) in spans:
            if not (0 <= a <= b <= n):
                c["errors"].append(f"{jid}: span {kind} {[a, b]} ngoài text_clean (len={n})"); break
        for x in j["citations_precedent"]:
            a, b = x["citing_sentence_span"]
            if "án lệ" not in t["text_clean"][a:b].lower():
                c["errors"].append(f"{jid}: câu trích dẫn {x['precedent_id']} không chứa 'án lệ'")
            if prec and x["precedent_id"] not in prec:
                c["warnings"].append(f"{jid}: {x['precedent_id']} không có trong precedents (corpus 91 án lệ?)")
    if len(J) != len(T): c["warnings"].append(f"số judgments ({len(J)}) ≠ số judgment_texts ({len(T)})")
    c["errors"] = c["errors"][:50]; c["warnings"] = sorted(set(c["warnings"]))[:50]
    if c["errors"]: rep["ok"] = False
    return rep
