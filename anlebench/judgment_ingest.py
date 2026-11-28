"""Dữ liệu bản án từ congbobanan_anle_crawler.ipynb → bản ghi theo schemas/judgments.schema.json (+ văn bản sạch + trích dẫn).

Cấu trúc zip được SUY LUẬN từ notebook crawler (cell 7 "ĐÓNG GÓI"):
    anle_judgments.zip
    ├── listing.csv                      # case_id, kind, judgment_number, judgment_date, court, published, anle_applied, anle,
    │                                    #   case_type, legal_relation, level, has_full_text, url
    ├── judgments.jsonl                  # mỗi dòng: bản ghi listing (case_id,url,kind,title,judgment_number,judgment_date,court,
    │                                    #   published,fields{...},anle_list,anle_applied) + "full_text"
    └── details/<case_id>/{detail.html, full_text.txt, [judgment_0.pdf]}
`judgments.jsonl` đã chứa full_text nên chỉ cần giải nén 2 file (listing.csv + judgments.jsonl) ra Drive; nếu thiếu
judgments.jsonl thì dự phòng đọc details/<id>/full_text.txt.  Lưu ý: trường `anle_list` của crawler thực ra là số lượt
xem/tải (ul.list_count_pub), KHÔNG phải số án lệ → số án lệ được viện dẫn phải trích từ văn bản bản án.
"""
from __future__ import annotations
import csv, io, json, re, shutil, time, zipfile
from pathlib import Path
from typing import Iterator

from .common import (ensure_dir, read_jsonl, write_jsonl, write_json, atomic_write_text, atomic_write_bytes,
                     now_iso, today_iso, sha1)
from .vnlegal import fix_vn_text, fold, fold_same_len, parse_date_vn, linh_vuc_from_code, precedent_id
from .citations import (extract_precedent_mentions, extract_law_refs, sentence_span, classify_usage, law_role)

# ------------------------------------------------------------------ zip
def _find(names, suffix):
    c = [n for n in names if n.replace("\\", "/").lower().endswith(suffix)]
    return sorted(c, key=len)[0] if c else None


def inspect_zip(zip_path) -> dict:
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        info = {"n_members": len(names), "jsonl": _find(names, "judgments.jsonl"), "listing_csv": _find(names, "listing.csv"),
                "n_full_text": sum(1 for n in names if n.replace("\\", "/").endswith("/full_text.txt")),
                "n_pdf": sum(1 for n in names if n.lower().endswith(".pdf")), "total_uncompressed_mb": round(sum(i.file_size for i in z.infolist()) / 1e6, 1)}
    return info


def extract_zip_inputs(zip_path, dest_dir, log=print) -> dict:
    """Chỉ giải nén listing.csv + judgments.jsonl (đủ dữ liệu, bỏ PDF/HTML nặng). Idempotent: bỏ qua nếu đã có đúng kích thước."""
    dest_dir = ensure_dir(dest_dir); out = {}
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist(); info = z.infolist()
        sizes = {i.filename: i.file_size for i in info}
        for key, suffix in (("listing_csv", "listing.csv"), ("jsonl", "judgments.jsonl")):
            member = _find(names, suffix)
            if not member:
                out[key] = None; continue
            dst = Path(dest_dir) / suffix
            if dst.exists() and dst.stat().st_size == sizes[member]:
                log(f"  [unzip] bỏ qua {suffix} (đã có, đúng kích thước)")
            else:
                tmp = dst.with_name(dst.name + ".tmp")
                with z.open(member) as src, open(tmp, "wb") as f:
                    shutil.copyfileobj(src, f, 1 << 20)
                tmp.replace(dst); log(f"  [unzip] {member} → {dst} ({sizes[member] / 1e6:.1f} MB)")
            out[key] = str(dst)
        if not out.get("jsonl"):   # dự phòng: gom từ details/*/full_text.txt + listing.csv
            log("  [unzip] không có judgments.jsonl → dựng từ details/*/full_text.txt")
            rows = {}
            if out.get("listing_csv"):
                with open(out["listing_csv"], encoding="utf-8-sig", newline="") as f:
                    rows = {r["case_id"]: r for r in csv.DictReader(f)}
            recs = []
            for n in names:
                nn = n.replace("\\", "/")
                m = re.search(r"details/([^/]+)/full_text\.txt$", nn)
                if m:
                    cid = m.group(1); r = rows.get(cid, {})
                    recs.append({"case_id": cid, "url": r.get("url"), "kind": r.get("kind", ""), "judgment_number": r.get("judgment_number", ""),
                                 "judgment_date": r.get("judgment_date", ""), "court": r.get("court", ""), "published": r.get("published", ""),
                                 "fields": {"Loại vụ/việc": r.get("case_type", ""), "Quan hệ pháp luật": r.get("legal_relation", ""),
                                            "Cấp xét xử": r.get("level", "")}, "full_text": z.read(n).decode("utf-8")})
            dst = Path(dest_dir) / "judgments.jsonl"; write_jsonl(dst, recs); out["jsonl"] = str(dst)
    return out


def iter_listing_records(jsonl_path) -> Iterator[dict]:
    yield from read_jsonl(jsonl_path)


# ------------------------------------------------------------------ làm sạch + chia đoạn
_TAIL_STOP = ("ban quyen", "copyright", "so luot truy cap", "tong so luot", "luot truy cap")


def clean_judgment_text(raw: str) -> tuple[str, dict]:
    """full_text (cả trang) → text_clean: NFC/sửa font, bỏ phần đầu trang trước 'CỘNG HÒA XÃ HỘI...' và chân trang web."""
    text, fixes = fix_vn_text(raw or "")
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.replace("\r", "\n").split("\n")]
    lines = [l for l in lines if l]
    F = [fold(l) for l in lines]
    head = next((i for i, f in enumerate(F) if f.startswith("cong hoa xa hoi chu nghia viet nam")), None)
    if head is None:
        head = next((i for i, f in enumerate(F) if re.match(r"^(ban an|quyet dinh)\b", f)), 0)
    tail = len(lines)
    for i in range(head, len(lines)):
        if any(F[i].startswith(m) for m in _TAIL_STOP):
            tail = i; break
    body = lines[head:tail]
    return "\n".join(body), {"fixes": fixes, "trimmed_head_lines": head, "trimmed_tail_lines": len(lines) - tail,
                              "n_lines_raw": len(lines), "n_chars_raw": len(raw or "")}


_FACT_H = {"noi dung vu an", "noi dung vu viec", "nhan thay", "noi dung"}
_REASON_H = {"nhan dinh cua toa an", "xet thay", "nhan dinh cua toa"}


def segment(text: str) -> tuple[list[dict], dict]:
    """Chia văn bản thành header / facts / court_reasoning / decision (span [start,end) trên text). Trả về (sections, info)."""
    lines = text.split("\n"); starts = []; pos = 0
    for l in lines:
        starts.append(pos); pos += len(l) + 1
    F = [fold(l).strip(" :.-–") for l in lines]
    fi = next((i for i, f in enumerate(F) if f in _FACT_H), None)
    ri = next((i for i, f in enumerate(F) if f in _REASON_H and (fi is None or i > fi)), None)
    if ri is None:
        ri = next((i for i, f in enumerate(F) if f in _REASON_H), None)
    after = ri if ri is not None else (fi if fi is not None else 0)
    di = None
    for i in range(len(F) - 1, after - 1, -1):          # 'QUYẾT ĐỊNH' cuối cùng sau phần nhận định
        if F[i] == "quyet dinh":
            di = i; break
    marks = sorted(x for x in (fi, ri, di) if x is not None)
    n = len(text)
    def pos_of(i): return starts[i]
    secs = []
    first = marks[0] if marks else len(lines)
    secs.append({"id": "S_HEADER", "type": "header", "span": [0, pos_of(first) - 1 if first > 0 else 0]})
    def add(i, sid, typ, nxt):
        end = pos_of(nxt) - 1 if nxt is not None else n
        secs.append({"id": sid, "type": typ, "span": [pos_of(i), max(end, pos_of(i))]})
    order = [(fi, "S_FACTS", "other"), (ri, "S_REASONING", "court_reasoning"), (di, "S_DECISION", "decision")]
    present = [(i, sid, t) for i, sid, t in order if i is not None]
    for k, (i, sid, t) in enumerate(present):
        add(i, sid, t, present[k + 1][0] if k + 1 < len(present) else None)
    # đoạn (mỗi dòng không rỗng) của phần nhận định
    for s in secs:
        if s["id"] == "S_REASONING":
            a, b = s["span"]; paras = []; k = 0
            for li, st in enumerate(starts):
                if a < st <= b - 0 and st < b and lines[li]:
                    k += 1; paras.append({"id": f"P[{k}]", "span": [st, st + len(lines[li])]})
            s["paragraphs"] = paras
    info = {"has_facts": fi is not None, "has_reasoning": ri is not None, "has_decision": di is not None}
    return secs, info


def locate(pos: int, sections: list[dict]) -> tuple[str, str, str]:
    """vị trí → (section_id, section_type, paragraph_id hoặc section_id)."""
    for s in sections:
        a, b = s["span"]
        if a <= pos < b or (s is sections[-1] and pos >= a):
            for p in s.get("paragraphs", []):
                if p["span"][0] <= pos <= p["span"][1]:
                    return s["id"], s["type"], p["id"]
            return s["id"], s["type"], s["id"]
    return "S_HEADER", "header", "S_HEADER"


# ------------------------------------------------------------------ meta
_LINH_VUC_FIELD = {"dan su": "dan_su", "hinh su": "hinh_su", "hon nhan va gia dinh": "hon_nhan_gia_dinh", "hon nhan gia dinh": "hon_nhan_gia_dinh",
                   "kinh doanh thuong mai": "kinh_doanh_thuong_mai", "lao dong": "lao_dong", "hanh chinh": "hanh_chinh"}
_CAP_XX = {"so tham": "first_instance", "phuc tham": "appeal", "giam doc tham": "cassation", "tai tham": "reopening"}
_SUFFIX_XX = {"ST": "first_instance", "PT": "appeal", "GDT": "cassation", "TT": "reopening"}


def cap_toa(court: str) -> str:
    f = fold(court)
    if "toi cao" in f: return "supreme"
    if "cap cao" in f: return "high"
    if re.search(r"khu vuc|huyen|quan |thi xa|thanh pho thuoc|, ", f): return "district"
    return "provincial"


def build_meta(rec: dict, text: str) -> tuple[dict | None, list[str]]:
    issues = []
    fields = rec.get("fields") or {}
    head = text[:2500]
    m = re.search(r"(?i:số)\s*:?\s*(\d{1,5}\s*/\s*\d{4}\s*/\s*[A-ZĐ0-9][A-ZĐ0-9\-–]*)", head)
    so_hieu = re.sub(r"\s+", "", m.group(1)).replace("–", "-") if m else None
    dt = parse_date_vn(rec.get("judgment_date") or "")
    if not dt:
        mm = re.search(r"ngày\s*\d{1,2}\s*tháng\s*\d{1,2}\s*năm\s*\d{4}", head, re.I)
        dt = parse_date_vn(mm.group(0)) if mm else None
    if not dt: issues.append("thiếu ngày xét xử")
    year = int(dt[:4]) if dt else (int(so_hieu.split("/")[1]) if so_hieu else None)
    if not so_hieu:
        so_hieu = f"{rec.get('judgment_number', '').strip() or 'NA'}/{year or 'NA'}/NA"; issues.append("không đọc được số hiệu từ văn bản (dùng số trong listing)")
    parts = so_hieu.split("/")
    ky_hieu = parts[2] if len(parts) > 2 else "NA"
    court = (rec.get("court") or "").strip()
    if not court:
        mc = re.search(r"(TÒA ÁN NHÂN DÂN[^\n]{3,120})", head)
        court = mc.group(1).strip() if mc else ""
    if not court: issues.append("thiếu tên tòa án")
    capxx_f = fold(fields.get("Cấp xét xử", ""))
    cap_xx = next((v for k, v in _CAP_XX.items() if k in capxx_f), None)
    if not cap_xx:
        suf = re.sub(r"[^A-Z]", "", fold(ky_hieu.split("-")[-1]).upper())
        cap_xx = _SUFFIX_XX.get(suf, "first_instance")
        issues.append("cấp xét xử suy từ ký hiệu/mặc định")
    lv_f = fold(fields.get("Loại vụ/việc", ""))
    linh_vuc = next((v for k, v in _LINH_VUC_FIELD.items() if k == lv_f), None) or linh_vuc_from_code(ky_hieu.split("-")[0], lv_f)
    if not dt or not court:
        return None, issues
    meta = {"so_hieu": so_hieu, "ky_hieu": ky_hieu, "nam": year, "ngay_xu": dt, "toa_an": court, "cap_toa": cap_toa(court),
            "cap_xet_xu": cap_xx, "linh_vuc": linh_vuc}
    if fields.get("Thông tin về vụ/việc"): meta["trich_yeu"] = fields["Thông tin về vụ/việc"]
    return meta, issues


# ------------------------------------------------------------------ 1 bản ghi → judgment
COURT_VOICE = ("court_reasoning", "decision")


def process_record(rec: dict, num2year: dict[int, int] | None = None) -> dict:
    cid = str(rec.get("case_id", ""))
    text, norm = clean_judgment_text(rec.get("full_text", ""))
    if len(text) < 200:
        return {"case_id": cid, "error": f"văn bản quá ngắn ({len(text)} ký tự)"}
    meta, issues = build_meta(rec, text)
    if meta is None:
        return {"case_id": cid, "error": "; ".join(issues)}
    secs, sinfo = segment(text)
    ref_date = meta["ngay_xu"]

    # --- án lệ
    mentions = extract_precedent_mentions(text, num2year)
    cit_prec, party, unresolved_al, seen = [], [], [], set()
    flat = []
    for mt in mentions:
        sid, stype, para = locate(mt["span"][0], secs)
        a, b = sentence_span(text, *mt["span"]); sent = text[a:b]
        usage, reason = classify_usage(sent)
        court_voice = stype in COURT_VOICE
        if not mt["resolved"]:
            unresolved_al.append(mt["raw"]); continue
        flat.append({"judgment_id": f"CB-{cid}", "case_id": cid, "url": rec.get("url"), "precedent_id": mt["precedent_id"],
                     "voice": "court" if court_voice else "other", "usage": usage, "section": sid, "paragraph": para,
                     "span_start": mt["span"][0], "span_end": mt["span"][1], "sentence": re.sub(r"\s+", " ", sent)[:400]})
        if not court_voice:
            party.append({"precedent_id": mt["precedent_id"], "section": sid, "span": mt["span"]}); continue
        key = (mt["precedent_id"], para, usage)
        if key in seen: continue
        seen.add(key)
        item = {"precedent_id": mt["precedent_id"], "usage": usage, "paragraph": para, "citing_sentence_span": [a, b],
                "similar_facts": [], "matched_holding": None}
        if usage == "considered_not_applied": item["reason_if_not_applied"] = re.sub(r"\s+", " ", reason or sent)[:400]
        cit_prec.append(item)
    usages = {c["usage"] for c in cit_prec}
    precedent_usage = "applied" if "applied" in usages else ("considered_not_applied" if usages else "none")

    # --- điều luật
    refs, n_unres = extract_law_refs(text, ref_date)
    cit_law, seen_l, prov_first = [], set(), {}
    for r in refs:
        sid, stype, para = locate(r["span"][0], secs)
        role = law_role(r["so_hieu"], stype)
        key = (r["prov_id"], role, para)
        prov_first.setdefault(r["prov_id"], r["span"])
        if key in seen_l: continue
        seen_l.add(key)
        cit_law.append({"ref": r["ref"], "prov_id": r["prov_id"], "role": role, "paragraph": para, "span": r["span"]})

    jid = f"CB-{cid}"
    ents = [{"type": "JUDGMENT_NO", "text": meta["so_hieu"], "norm": meta["so_hieu"], "span": None},
            {"type": "COURT", "text": meta["toa_an"], "norm": None, "span": None}]
    for c in cit_prec:
        ents.append({"type": "PRECEDENT_NO", "text": c["precedent_id"], "norm": c["precedent_id"], "span": c["citing_sentence_span"]})
    conf = 0.4 + 0.2 * (sinfo["has_reasoning"] and sinfo["has_decision"]) + 0.2 * (not any("số hiệu" in i for i in issues)) + 0.2 * bool(cit_prec)
    judgment = {
        "judgment_id": jid, "meta": meta, "sections": secs, "issues": [], "facts": [], "citations_law": cit_law,
        "citations_precedent": cit_prec, "precedent_usage": precedent_usage,
        "decision_text_span": next((s["span"] for s in secs if s["id"] == "S_DECISION"), None),
        "role_in_benchmark": "provenance_only" if cit_prec else "non_citing_reference", "pii_policy": "anonymized_as_published",
        "entities": ents,
        "quality": {"ocr_fixed": False, "font_fix": ", ".join(norm["fixes"]) or "none", "confidence": round(min(conf, 1.0), 2),
                    "segmentation": sinfo, "meta_issues": issues,
                    "citation_extraction": {"n_mentions": len(mentions), "n_court_voice": len(cit_prec), "party_or_other_mentions": party,
                                            "unresolved_precedent_mentions": unresolved_al, "unresolved_law_refs": n_unres,
                                            "zero_precedent_mentions": len(mentions) == 0,
                                            "zero_court_voice_citation": len(cit_prec) == 0}},
        "source": {"site": "congbobanan.toaan.gov.vn", "case_id": cid, "url": rec.get("url"), "published": rec.get("published"),
                   "listing_fields": {k: v for k, v in (rec.get("fields") or {}).items() if isinstance(v, str)}},
        "curation": {"status": "draft_unreviewed", "by": "rule_based_pipeline", "date": today_iso(),
                     "note": "Trích dẫn án lệ/điều luật do bộ trích xuất theo luật; cần kiểm tra mẫu. 'applied' chỉ xét câu của Hội đồng xét xử (nhận định/quyết định); lời viện dẫn của đương sự nằm ở quality.citation_extraction."},
    }
    text_rec = {"judgment_id": jid, "text_clean": text, "text_sha256": sha1(text), "n_chars": len(text),
                "normalization": norm, "source": {"case_id": cid, "url": rec.get("url")}}
    return {"case_id": cid, "judgment": judgment, "text": text_rec, "flat": flat}


# ------------------------------------------------------------------ chạy hàng loạt theo shard (chạy tiếp được)
def load_num2year(*paths) -> dict[int, int]:
    out = {}
    for p in paths:
        if p and Path(p).exists():
            for r in read_jsonl(p):
                m = re.fullmatch(r"AL-(\d{2,3})/(\d{4})", r.get("precedent_id", ""))
                if m: out[int(m.group(1))] = int(m.group(2))
    return out


def process_all(records: Iterator[dict], out_dir, num2year=None, progress=None, stage="judgments_process", batch=200,
                time_budget_s: float | None = None, limit: int | None = None, log=print) -> dict:
    out_dir = ensure_dir(out_dir); sh = ensure_dir(Path(out_dir) / "shards")
    done = set()
    for f in sorted(sh.glob("part-*.jsonl")):
        for r in read_jsonl(f): done.add(str(r.get("case_id")))
    nshard = len(list(sh.glob("part-*.jsonl")))
    t0 = time.monotonic(); buf = []; n_new = 0; n_err = 0; seen_total = 0
    if progress: progress.start(stage, shards_written=nshard, done=len(done))

    def flush():
        nonlocal buf, nshard
        if not buf: return
        write_jsonl(sh / f"part-{nshard:05d}.jsonl", buf); nshard += 1
        if progress: progress.update(stage, force=True, done=len(done), shards_written=nshard, errors=n_err)
        buf = []

    stopped = False
    for rec in records:
        seen_total += 1
        cid = str(rec.get("case_id"))
        if cid in done: continue
        if limit and n_new >= limit: break
        if time_budget_s and time.monotonic() - t0 > time_budget_s:
            stopped = True; break
        try:
            res = process_record(rec, num2year)
        except Exception as e:   # một bản ghi lỗi không làm hỏng cả lô
            res = {"case_id": cid, "error": f"exception: {e!r}"[:300]}
        if "error" in res: n_err += 1
        buf.append(res); done.add(cid); n_new += 1
        if len(buf) >= batch:
            flush(); log(f"  [judgments] {len(done)} bản ghi đã xử lý (shard {nshard})")
    flush()
    complete = not stopped and not limit
    if progress:
        if complete: progress.done(stage, done=len(done), shards_written=nshard, errors=n_err, total=seen_total)
        else: progress.pause(stage, "hết ngân sách thời gian" if stopped else "đã đạt giới hạn thử", done=len(done), shards_written=nshard)
    return {"n_new": n_new, "n_done": len(done), "n_errors_new": n_err, "complete": complete}


def finalize(out_dir, report_path=None) -> dict:
    """Gộp shard → judgments.jsonl, judgment_texts.jsonl, citations_flat.csv, judgments_errors.jsonl + báo cáo thống kê."""
    out_dir = Path(out_dir); sh = out_dir / "shards"
    J, T, E = [], [], []; flat = []
    for f in sorted(sh.glob("part-*.jsonl")):
        for r in read_jsonl(f):
            if "error" in r: E.append({"case_id": r["case_id"], "error": r["error"]}); continue
            J.append(r["judgment"]); T.append(r["text"]); flat.extend(r["flat"])
    write_jsonl(out_dir / "judgments.jsonl", J); write_jsonl(out_dir / "judgment_texts.jsonl", T); write_jsonl(out_dir / "judgments_errors.jsonl", E)
    cols = ["judgment_id", "case_id", "url", "precedent_id", "voice", "usage", "section", "paragraph", "span_start", "span_end", "sentence"]
    buf = io.StringIO(newline=""); w = csv.DictWriter(buf, fieldnames=cols); w.writeheader(); w.writerows(flat)
    atomic_write_bytes(out_dir / "citations_flat.csv", ("\ufeff" + buf.getvalue()).encode("utf-8"))
    from collections import Counter
    by_prec = Counter(c["precedent_id"] for j in J for c in j["citations_precedent"])
    rep = {"generated_at": now_iso(), "n_judgments": len(J), "n_errors": len(E),
           "precedent_usage": dict(Counter(j["precedent_usage"] for j in J)),
           "with_court_voice_precedent_citation": sum(1 for j in J if j["citations_precedent"]),
           "zero_mentions_case_ids": [j["source"]["case_id"] for j in J if j["quality"]["citation_extraction"]["zero_precedent_mentions"]][:500],
           "n_zero_mentions": sum(1 for j in J if j["quality"]["citation_extraction"]["zero_precedent_mentions"]),
           "no_court_voice_citation_case_ids": [j["source"]["case_id"] for j in J if j["quality"]["citation_extraction"]["zero_court_voice_citation"]][:500],
           "n_no_court_voice_citation": sum(1 for j in J if j["quality"]["citation_extraction"]["zero_court_voice_citation"]),
           "unresolved_precedent_mentions": sum(len(j["quality"]["citation_extraction"]["unresolved_precedent_mentions"]) for j in J),
           "unresolved_law_refs": sum(j["quality"]["citation_extraction"]["unresolved_law_refs"] for j in J),
           "mentions_outside_court_voice": sum(len(j["quality"]["citation_extraction"]["party_or_other_mentions"]) for j in J),
           "segmentation": {k: sum(1 for j in J if j["quality"]["segmentation"][k]) for k in ("has_facts", "has_reasoning", "has_decision")},
           "top_precedents": by_prec.most_common(25), "n_distinct_precedents_cited": len(by_prec),
           "law_citations_total": sum(len(j["citations_law"]) for j in J),
           "errors_sample": E[:20]}
    if report_path: write_json(report_path, rep)
    return rep
