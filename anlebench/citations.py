"""Trích xuất trích dẫn trong văn bản bản án (text_clean) — mọi offset là vị trí ký tự [start,end) trong chính chuỗi được đưa vào.

- extract_precedent_mentions: "án lệ số 08/2016/AL", "các án lệ số 04/2016/AL và 08/2016/AL", "án lệ số 08" (nếu có bảng số→năm)
- extract_law_refs: "điểm a khoản 1 Điều 51 Luật Hôn nhân và gia đình năm 2014" → prov_id (xem vnlegal.build_prov_id)
- sentence_span / classify_usage: câu chứa trích dẫn và nhãn applied / considered_not_applied (heuristic theo dấu hiệu phủ định)

Đây là bộ trích xuất theo luật (rule-based): ưu tiên độ chính xác, các trường hợp mơ hồ được trả về kèm cờ
(`resolved=False`, `law_unresolved`) để báo cáo thay vì đoán.
"""
from __future__ import annotations
import re
from .vnlegal import (fold_same_len, match_law_at_start, build_prov_id, precedent_id, PROCEDURE_LAWS, FEE_DOCS)

# ------------------------------------------------------------------ án lệ
_AL_START = re.compile(r"án\s+lệ(?:\s+số)?\s*(?=\d)", re.I)
_AL_ITEM = re.compile(r"(\d{1,3})(?!\d)(?:\s*/\s*(\d{4}))?(?:\s*/\s*AL\b)?", re.I)
_AL_SEP = re.compile(r"\s*(?:,|;|và|hoặc)\s*(?:(?:các\s+)?án\s+lệ\s+)?(?:số\s*)?", re.I)


def extract_precedent_mentions(text: str, num2year: dict[int, int] | None = None) -> list[dict]:
    out = []; last_end = -1
    for m in _AL_START.finditer(text):
        if m.start() < last_end:   # đã nằm trong danh sách 'A và B' vừa xử lý
            continue
        pos = m.end()
        while True:
            im = _AL_ITEM.match(text, pos)
            if not im: break
            num = int(im.group(1)); year = int(im.group(2)) if im.group(2) else None
            if year is not None and not (2015 <= year <= 2100):
                break
            resolved = year is not None
            if year is None and num2year and num in num2year:
                year, resolved = num2year[num], True
            rec = {"num": num, "year": year, "resolved": year is not None,
                   "explicit_year": im.group(2) is not None, "span": [m.start() if pos == m.end() else im.start(), im.end()],
                   "precedent_id": precedent_id(num, year) if year else None, "raw": text[im.start():im.end()]}
            out.append(rec); last_end = im.end()
            sm = _AL_SEP.match(text, im.end())
            if not sm or not re.match(r"\d", text[sm.end():sm.end() + 1] or ""): break
            pos = sm.end()
    return out


# ------------------------------------------------------------------ câu / phủ định
_SENT_B = re.compile(r"\n|(?<=[.;:!?])\s+(?=[A-ZĐÀ-Ỹ“\"(\[])")


def sentence_span(text: str, a: int, b: int, window: int = 700) -> tuple[int, int]:
    lo, hi = max(0, a - window), min(len(text), b + window)
    seg = text[lo:hi]
    start, end = lo, hi
    for m in _SENT_B.finditer(seg):
        p, q = lo + m.start(), lo + m.end()
        if q <= a: start = q
        elif p >= b: end = p; break
    return start, max(end, b)


_NEG = [re.compile(p) for p in (
    r"(khong|chua)\s+(?:the\s+|du\s+dieu\s+kien\s+|phu\s+hop\s+de\s+|thuoc\s+truong\s+hop\s+)*ap\s+dung(?:\s+duoc)?(?:\s+(?:cac\s+)?an\s+le|\s+tinh\s+huong)",
    r"khong\s+ap\s+dung\s+(?:cac\s+)?an\s+le",
    r"an\s+le[^.;\n]{0,80}\bkhong\s+(?:duoc\s+|the\s+)?ap\s+dung",
    r"khong\s+(?:co\s+)?(?:tinh\s+huong\s+|tinh\s+tiet\s+)?(?:tuong\s+tu|giong)\s+(?:voi\s+)?an\s+le",
    r"(?:khong|chua)\s+du\s+can\s+cu\s+ap\s+dung\s+an\s+le",
    r"an\s+le[^.;\n]{0,100}\bkhong\s+(?:thuoc\s+truong\s+hop|phu\s+hop|du\s+dieu\s+kien)[^.;\n]{0,40}ap\s+dung",
)]


def classify_usage(sentence: str) -> tuple[str, str | None]:
    f = fold_same_len(sentence)
    for p in _NEG:
        if p.search(f):
            return "considered_not_applied", sentence.strip()
    return "applied", None


# ------------------------------------------------------------------ điều luật
_SPLIT_LIST = re.compile(r"\s*(?:,|\bvà\b)\s*", re.I)
_DIEU = re.compile(
    r"(?:(?:các\s+)?điểm\s+(?P<diem>[a-zđ](?:\s*(?:,|và)\s*[a-zđ]\b)*)\s*(?:,\s*)?)?"
    r"(?:(?:các\s+)?khoản\s+(?P<khoan>\d+(?:\s*(?:,|và)\s*\d+)*)\s*(?:,\s*)?)?"
    r"(?:(?:các\s+)?điều\s+(?P<dieu>\d+[a-z]?(?:\s*(?:,|và)\s*\d+[a-z]?)*))\b(?!\s*/)", re.I)


_KM = re.compile(
    r"(?:(?:các\s+)?điểm\s+(?P<diem>[a-zđ](?:\s*(?:,|và)\s*[a-zđ]\b)*)\s*(?:,\s*)?)?"
    r"(?:(?:các\s+)?khoản\s+(?P<khoan>\d+(?:\s*(?:,|và)\s*\d+)*)\s*(?:,\s*)?)?"
    r"(?:(?:phần\s+)?mục\s+(?P<muc>\d+)\s*)?(?=\s*(?:của\s+|tại\s+)?(?:Bộ\s+luật|Luật|Pháp\s+lệnh|Nghị|Thông))", re.I)


_BARE_DOCS = re.compile(r"(?:Nghị\s+quyết\s+)?(?:số\s+)?(326\s*/\s*2016\s*/\s*UBTVQH14)", re.I)   # án phí, lệ phí tòa án


def _items(g: str | None) -> list[str]:
    return [x.strip() for x in _SPLIT_LIST.split(g) if x.strip()] if g else []


def extract_law_refs(text: str, ref_date: str | None = None) -> tuple[list[dict], int]:
    """→ (refs, n_unresolved). ref_date (ISO) dùng chọn phiên bản luật khi câu không ghi năm.
    Điều đứng trước tên luật ("khoản 1 Điều 51, khoản 1 Điều 56 Luật HNGĐ") kế thừa tên luật ở điều liền sau
    nếu chỉ cách nhau dấu , ; hoặc 'và'."""
    items = [(m, "dieu") for m in _DIEU.finditer(text)]
    taken = [m.span() for m, _ in items]
    for m in _KM.finditer(text):      # dạng 'điểm a khoản 3 Nghị quyết số ...' (không có chữ 'Điều')
        if (m.group("khoan") or m.group("muc")) and not any(a <= m.start() < b for a, b in taken):
            items.append((m, "km"))
    items.sort(key=lambda x: x[0].start())
    ms = [m for m, _ in items]; kinds = [k for _, k in items]; resolved = []
    for m in ms:
        tail = text[m.end(): m.end() + 200].lstrip(",; ")
        skip = len(text[m.end(): m.end() + 200]) - len(tail)
        res = match_law_at_start(tail, ref_date)
        resolved.append((res[0], res[1], m.end() + skip + res[2]) if res else None)
    for i in range(len(ms) - 2, -1, -1):          # kế thừa ngược từ điều sau
        if resolved[i] is None and resolved[i + 1] is not None and re.fullmatch(r"[\s,;]*(?:và\s*)?", text[ms[i].end():ms[i + 1].start()]):
            resolved[i] = (resolved[i + 1][0], resolved[i + 1][1], ms[i].end())
    refs, unresolved = [], 0
    for m, kind, r in zip(ms, kinds, resolved):
        if r is None:
            if kind == "dieu": unresolved += 1
            continue
        ver, so_hieu, end = r
        dieus = _items(m.group("dieu")) if kind == "dieu" else [None]
        muc = int(m.group("muc")) if kind == "km" and m.group("muc") else None
        for d in dieus:
            dnum = int(re.match(r"\d+", d).group()) if d else None
            for k in (_items(m.group("khoan")) or [None]):
                for dm in (_items(m.group("diem")) or [None]):
                    kk = int(k) if k else None; dd = dm.lower() if dm else None
                    refs.append({"ref": text[m.start():end].strip(" ,;."), "span": [m.start(), end], "so_hieu": so_hieu,
                                 "law_name": ver.ten if ver else None, "dieu": dnum, "khoan": kk, "diem": dd, "muc": muc,
                                 "prov_id": build_prov_id(so_hieu, dnum, kk, dd, muc)})
    for m in _BARE_DOCS.finditer(text):      # văn bản án phí thường chỉ nêu số hiệu, không kèm điều
        if not any(r["span"][0] <= m.start() < r["span"][1] for r in refs):
            so = re.sub(r"\s+", "", m.group(1)).upper()
            refs.append({"ref": m.group(0).strip(), "span": [m.start(), m.end()], "so_hieu": so, "law_name": None,
                         "dieu": None, "khoan": None, "diem": None, "muc": None, "prov_id": build_prov_id(so)})
    refs.sort(key=lambda r: r["span"][0])
    return refs, unresolved


def law_role(so_hieu: str | None, section_type: str) -> str:
    """decision_basis | procedure | fee | other (theo schema judgments.citations_law.role)."""
    if so_hieu in FEE_DOCS: return "fee"
    if so_hieu in PROCEDURE_LAWS: return "procedure"
    if section_type in ("court_reasoning", "decision"): return "decision_basis"
    return "other"
