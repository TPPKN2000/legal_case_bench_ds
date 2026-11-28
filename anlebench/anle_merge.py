"""precedents_raw.jsonl (nguyên văn, từ anle_crawl) → precedents.jsonl theo schemas/precedents.schema.json.

- Án lệ CHƯA có trong precedents.jsonl: tạo bản ghi mới, text_mode='verbatim', curation.status='draft_unreviewed'
  (key_facts để rỗng; stance/in_an_le_content được SUY RA theo luật heuristic — cần chuyên gia duyệt).
- Án lệ ĐÃ có (vd AL-53/2022 do người soạn diễn đạt lại): thay các trường văn bản bằng nguyên văn, GIỮ các nhãn đã
  duyệt (key_facts, necessary, tags, legal_issue, stance, cites_provisions, applies_to_paragraphs) khi khớp theo id/số đoạn.
- Bản ghi thiếu trường bắt buộc → precedents_incomplete.jsonl (không chèn giá trị giả).
"""
from __future__ import annotations
import re, difflib
from pathlib import Path
from urllib.parse import urlparse
from .common import read_jsonl, write_jsonl, write_json, today_iso
from .vnlegal import fold_same_len, linh_vuc_from_code
from .citations import extract_law_refs

CUR_NOTE = "Văn bản là nguyên văn từ {src}; stance/in_an_le_content/key_facts do quy tắc/người soạn đề xuất, chưa có chuyên gia pháp lý duyệt."


def guess_stance(text: str, in_content: bool) -> str:
    f = fold_same_len(text)
    if re.search(r"(cap phuc tham|toa an cap duoi|toa an nhan dan cap cao|ban an so tham|ban an phuc tham|quyet dinh phuc tham|toa an cap so tham)"
                 r"[^.]{0,250}(cho rang|nhan dinh|cho la|cho thay|ket luan)", f) and \
       re.search(r"(khong dung|khong co can cu|chua dung|\bsai\b|khong chinh xac|khong phu hop)", f):
        return "rejected_quoted"
    if re.match(r"^\s*(can cu|theo quy dinh|tai (?:diem|khoan|dieu)|(?:diem|khoan|dieu) \d)", f) and not in_content:
        return "quoted_law"
    return "adopted" if in_content else "evidence_finding"


def _code_from_so_hieu(so: str) -> str:
    m = re.search(r"/([A-ZĐ]+)(?:-|$)", so or "")
    return m.group(1) if m else ""


def raw_to_precedent(raw: dict) -> tuple[dict | None, list[str]]:
    issues: list[str] = []
    src = raw.get("source") or {}
    url = src.get("url") or ""
    host = urlparse(url).netloc
    official = host.endswith("toaan.gov.vn")
    sj = raw.get("source_judgment"); qb = raw.get("quyet_dinh_cong_bo"); vt = raw.get("vi_tri_noi_dung")
    must = {"ngay_thong_qua": raw.get("ngay_thong_qua"), "quyet_dinh_cong_bo": qb, "source_judgment": sj and sj.get("ngay") and sj,
            "vi_tri_noi_dung": vt, "keywords": raw.get("keywords"), "holdings": raw.get("holdings_raw"), "nhan_dinh": raw.get("nhan_dinh")}
    missing = [k for k, v in must.items() if not v]
    if missing:
        return None, [f"thiếu trường bắt buộc: {missing}"] + list(raw.get("parse_warnings", []))
    in_set = set(vt["doan"]) if vt["phan"] == "nhan_dinh_cua_toa_an" else set()

    # điều luật liên quan (từ mục "Quy định của pháp luật liên quan đến án lệ")
    prov_cited, all_prov = [], []
    ref_date = raw.get("ngay_thong_qua")
    for line in raw.get("quy_dinh_lien_quan", []):
        refs, _ = extract_law_refs(line, ref_date)
        if not refs:
            prov_cited.append({"ref": line.strip(" ;."), "prov_id": None, "role": "an_le_quy_dinh_lien_quan", "paragraph": None})
            issues.append(f"không map được prov_id cho: {line[:80]}")
        for r in refs:
            prov_cited.append({"ref": line.strip(" ;."), "prov_id": r["prov_id"], "role": "an_le_quy_dinh_lien_quan", "paragraph": None})
            all_prov.append(r["prov_id"])
    all_prov = list(dict.fromkeys(all_prov))

    nhan_dinh = []
    for p in raw["nhan_dinh"]:
        inc = p["no"] in in_set
        refs, _ = extract_law_refs(p["text"], ref_date)
        nhan_dinh.append({"no": p["no"], "text": p["text"], "in_an_le_content": inc, "stance": guess_stance(p["text"], inc),
                          "cites_provisions": list(dict.fromkeys(r["prov_id"] for r in refs))})
    holdings = []
    for h in raw["holdings_raw"]:
        if not h.get("tinh_huong") or not h.get("giai_phap_phap_ly"):
            issues.append(f"holding {h.get('idx')} thiếu tình huống hoặc giải pháp")
        holdings.append({"id": f"H{h['idx']}", "tinh_huong": h.get("tinh_huong", ""), "giai_phap_phap_ly": h.get("giai_phap_phap_ly", ""),
                         "key_facts": [], "provisions": all_prov, "applies_to_paragraphs": sorted(in_set),
                         "curation": {"status": "draft_unreviewed", "by": "rule_based_pipeline", "date": today_iso(),
                                      "note": "key_facts chưa gán; applies_to_paragraphs mặc định = vị trí nội dung án lệ."}})
    code = _code_from_so_hieu(sj["so_hieu"])
    linh_vuc = linh_vuc_from_code(code, "" if code else raw.get("ten", "") + " " + " ".join(raw["keywords"]))
    rec = {
        "precedent_id": raw["precedent_id"], "so_hieu": raw["so_hieu"], "ten": raw.get("ten", ""), "linh_vuc": linh_vuc,
        "status": "unknown", "ngay_thong_qua": raw["ngay_thong_qua"], "quyet_dinh_cong_bo": qb,
        "ngay_hieu_luc": raw.get("ngay_hieu_luc"),
        "source_judgment": {k: sj[k] for k in ("so_hieu", "ngay", "loai", "co_quan", "ve_viec")},
        "vi_tri_noi_dung": vt, "keywords": raw["keywords"], "holdings": holdings, "provisions_cited": prov_cited,
        "text_sections": {"noi_dung_vu_an": raw.get("noi_dung_vu_an", ""), "nhan_dinh": nhan_dinh, "quyet_dinh": raw.get("quyet_dinh", "")},
        "text_mode": "verbatim", "source_url": url, "official_source_url": url if official else None,
        "entities": [
            {"type": "PRECEDENT_NO", "text": f"Án lệ số {raw['so_hieu']}", "norm": raw["precedent_id"], "span": None},
            {"type": "JUDGMENT_NO", "text": sj["so_hieu"], "norm": sj["so_hieu"], "span": None},
            {"type": "COURT", "text": sj["co_quan"], "norm": None, "span": None}],
        "cited_by": [],
        "curation": {"status": "draft_unreviewed", "by": "rule_based_pipeline", "date": today_iso(),
                     "note": CUR_NOTE.format(src=host or "nguồn không rõ")},
    }
    if raw.get("ngay_hieu_luc") is None:
        rec["ngay_hieu_luc_note"] = "Chưa xác định được từ trang công bố; lấy từ quyết định công bố trước khi dùng cho lọc theo thời gian."
    return rec, issues + list(raw.get("parse_warnings", []))


def _sim(a: str, b: str) -> float:
    return round(difflib.SequenceMatcher(None, a or "", b or "", autojunk=False).ratio(), 3) if (a or b) else 1.0


def merge_with_existing(new: dict, old: dict) -> tuple[dict, dict]:
    """Thay văn bản diễn đạt lại bằng nguyên văn; giữ nhãn đã duyệt. Trả về (bản ghi hợp nhất, báo cáo thay đổi)."""
    rep = {"precedent_id": new["precedent_id"], "replaced": {}, "kept_from_old": [], "dropped_paragraphs": [], "notes": []}
    out = dict(old)
    for f in ("ten", "keywords", "quyet_dinh_cong_bo", "source_judgment", "ngay_thong_qua"):
        if old.get(f) != new.get(f):
            rep["replaced"][f] = {"similarity": _sim(str(old.get(f)), str(new.get(f)))}
        out[f] = new[f]
    out["vi_tri_noi_dung"] = new["vi_tri_noi_dung"]
    if old["vi_tri_noi_dung"]["doan"] != new["vi_tri_noi_dung"]["doan"]:
        rep["notes"].append(f"vi_tri_noi_dung.doan đổi {old['vi_tri_noi_dung']['doan']} → {new['vi_tri_noi_dung']['doan']}")
    if old.get("ngay_hieu_luc") is None and new.get("ngay_hieu_luc"):
        out["ngay_hieu_luc"] = new["ngay_hieu_luc"]; out.pop("ngay_hieu_luc_note", None)
    # văn bản
    ts_old, ts_new = old["text_sections"], new["text_sections"]
    ts = {"noi_dung_vu_an": ts_new["noi_dung_vu_an"], "quyet_dinh": ts_new["quyet_dinh"], "nhan_dinh": []}
    rep["replaced"]["noi_dung_vu_an"] = {"similarity": _sim(ts_old["noi_dung_vu_an"], ts_new["noi_dung_vu_an"])}
    rep["replaced"]["quyet_dinh"] = {"similarity": _sim(ts_old["quyet_dinh"], ts_new["quyet_dinh"])}
    old_nd = {p["no"]: p for p in ts_old["nhan_dinh"]}
    for p in ts_new["nhan_dinh"]:
        q = dict(p); o = old_nd.get(p["no"])
        if o:
            q["stance"], q["cites_provisions"] = o["stance"], o.get("cites_provisions", p["cites_provisions"])
            rep["replaced"][f"nhan_dinh[{p['no']}]"] = {"similarity": _sim(o["text"], p["text"])}
            if o["in_an_le_content"] != p["in_an_le_content"]:
                rep["notes"].append(f"đoạn {p['no']}: in_an_le_content đổi {o['in_an_le_content']}→{p['in_an_le_content']} theo công bố chính thức")
        ts["nhan_dinh"].append(q)
    rep["dropped_paragraphs"] = sorted(set(old_nd) - {p["no"] for p in ts["nhan_dinh"]})
    out["text_sections"] = ts
    # holdings
    old_h = {h["id"]: h for h in old["holdings"]}; hs = []
    for h in new["holdings"]:
        o = old_h.get(h["id"])
        if o:
            m = dict(o); m["tinh_huong"], m["giai_phap_phap_ly"] = h["tinh_huong"], h["giai_phap_phap_ly"]
            rep["replaced"][f"{h['id']}.tinh_huong"] = {"similarity": _sim(o["tinh_huong"], h["tinh_huong"])}
            rep["replaced"][f"{h['id']}.giai_phap_phap_ly"] = {"similarity": _sim(o["giai_phap_phap_ly"], h["giai_phap_phap_ly"])}
            rep["kept_from_old"].append(f"{h['id']}: key_facts/legal_issue/provisions/applies_to_paragraphs")
            hs.append(m)
        else:
            hs.append(h); rep["notes"].append(f"holding mới {h['id']} (chưa có trong bản cũ)")
    out["holdings"] = hs
    out["provisions_cited"] = new["provisions_cited"]
    out["text_mode"] = "verbatim"
    out["official_source_url"] = new.get("official_source_url") or old.get("official_source_url")
    if not old.get("source_url"): out["source_url"] = new["source_url"]
    cur = dict(old.get("curation", {})); cur["date"] = today_iso()
    cur["note"] = (cur.get("note", "") + " | " if cur.get("note") else "") + "Văn bản thay bằng nguyên văn từ " + (urlparse(new["source_url"]).netloc or "nguồn") + " ngày " + today_iso() + "; nhãn đã duyệt được giữ."
    out["curation"] = cur
    return out, rep


def build_precedents(raw_path, out_path, existing_path=None, incomplete_path=None, report_path=None) -> dict:
    existing = {r["precedent_id"]: r for r in read_jsonl(existing_path)} if existing_path and Path(existing_path).exists() else {}
    out, incomplete, per, seen = [], [], [], set()
    for raw in read_jsonl(raw_path):
        pid = raw.get("precedent_id")
        if pid in seen: continue
        seen.add(pid)
        rec, issues = raw_to_precedent(raw)
        if rec is None:
            incomplete.append({"precedent_id": pid, "issues": issues, "source": raw.get("source")}); continue
        if pid in existing:
            rec, rep = merge_with_existing(rec, existing[pid]); rep["issues"] = issues; per.append(rep)
        else:
            per.append({"precedent_id": pid, "new": True, "issues": issues})
        out.append(rec)
    keep_old = [r for pid, r in existing.items() if pid not in seen]   # án lệ cũ không có trong lần crawl → giữ nguyên
    out.sort(key=lambda r: (int(r["so_hieu"].split("/")[1]), int(r["so_hieu"].split("/")[0])))
    write_jsonl(out_path, out + keep_old)
    if incomplete_path: write_jsonl(incomplete_path, incomplete)
    report = {"n_raw": len(seen), "n_precedents": len(out) + len(keep_old), "n_incomplete": len(incomplete),
              "n_merged_with_existing": sum(1 for p in per if not p.get("new")), "kept_old_not_in_crawl": [r["precedent_id"] for r in keep_old],
              "incomplete": incomplete, "per_precedent": per}
    if report_path: write_json(report_path, report)
    return report
