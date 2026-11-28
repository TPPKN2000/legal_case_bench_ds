"""Crawl án lệ từ anle.toaan.gov.vn (hoặc bản sao ở trang khác có cùng khuôn mẫu công bố) → precedents_raw.jsonl.

Parser dựa trên NHÃN VĂN BẢN của mẫu công bố án lệ ("Vị trí nội dung án lệ", "Khái quát nội dung của án lệ",
"NỘI DUNG VỤ ÁN", "NHẬN ĐỊNH CỦA TÒA ÁN", "QUYẾT ĐỊNH"...) chứ không dựa vào CSS selector, nên dùng được cho cả
anle.toaan.gov.vn lẫn các bản sao (lsvn.vn, thuvienphapluat.vn...). Mỗi bản ghi giữ nguyên văn (verbatim) — việc thay
trường diễn đạt lại bằng nguyên văn do anle_merge.py làm.

CLI (chạy trên máy có IP Việt Nam nếu Colab bị chặn):
    python -m anlebench.anle_crawl --urls anle_urls.txt --out anle_raw.jsonl --cache cache_html [--discover]
"""
from __future__ import annotations
import argparse, re, sys, time, random
from pathlib import Path
from typing import Iterable

from .common import (read_jsonl, append_jsonl, repair_jsonl, ensure_dir, now_iso, sha1, atomic_write_text)
from .vnlegal import (fold, fold_same_len, nfc, fix_vn_text, parse_date_vn, precedent_id, precedent_so_hieu)

PORTAL = "https://anle.toaan.gov.vn"
DETAIL_URL = PORTAL + "/webcenter/portal/anle/chitietanle?dDocName={ddoc}"
LIST_URLS = [PORTAL + "/webcenter/portal/anle/anle", PORTAL + "/webcenter/portal/anle/home"]  # best-effort, chưa kiểm chứng
DDOC_RE = re.compile(r"chitietanle\?dDocName=(TAND\d+)", re.I)
EXPECTED_COUNT = 91


class FetchError(RuntimeError):
    pass


# ------------------------------------------------------------------ HTTP
def make_session():
    import requests
    from requests.adapters import HTTPAdapter
    s = requests.Session()
    try:   # site gov.vn thường thiếu chứng chỉ trung gian → dùng kho chứng chỉ hệ điều hành nếu có truststore
        import ssl, truststore

        class _TS(HTTPAdapter):
            def init_poolmanager(self, *a, **k):
                k["ssl_context"] = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                return super().init_poolmanager(*a, **k)
        s.mount("https://", _TS())
    except Exception:
        pass
    s.headers.update({"User-Agent": "Mozilla/5.0 (research; an-le-bench) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                      "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.5"})
    return s


def fetch(session, url: str, cache_dir, delay=(2.0, 4.0), timeout=(15, 90), retries=3, use_cache=True) -> str:
    cache_dir = ensure_dir(cache_dir)
    cf = Path(cache_dir) / (sha1(url) + ".html")
    if use_cache and cf.exists():
        return cf.read_text(encoding="utf-8")
    import requests
    last = None
    for i in range(retries):
        try:
            time.sleep(random.uniform(*delay))
            r = session.get(url, timeout=timeout)
            if r.status_code == 200:
                r.encoding = r.encoding or "utf-8"
                atomic_write_text(cf, r.text)
                return r.text
            last = f"HTTP {r.status_code}"
            if r.status_code in (403, 429, 500, 502, 503):
                time.sleep(20 * (i + 1))
        except requests.RequestException as e:
            last = repr(e)[:200]
            time.sleep(20 * (i + 1))
    raise FetchError(f"GET {url} thất bại: {last}")


# ------------------------------------------------------------------ HTML → dòng văn bản
def html_to_lines(html: str) -> list[str]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text("\n")
    return text_to_lines(text)


def text_to_lines(text: str) -> list[str]:
    out = []
    for raw in (text or "").replace("\r", "\n").split("\n"):
        s, _ = fix_vn_text(raw.replace("\xa0", " "))
        s = re.sub(r"[ \t]+", " ", s).strip()
        if s:
            out.append(s)
    return out


# ------------------------------------------------------------------ parser
_H = re.compile(r"^\s*an le so\s*(\d{1,3})\s*/\s*(\d{4})\s*/\s*al\b\s*[:\-–]?\s*")
_SRC = re.compile(r"(?P<loai>quyet dinh giam doc tham|quyet dinh tai tham|ban an phuc tham|ban an so tham|ban an|quyet dinh)\b.{0,80}?"
                  r"\bso\s*(?P<so>[^\s,;]+)\s*,?\s*(?:ngay\s*)?(?P<date>\d{1,2}\s*[/\-.]\s*\d{1,2}\s*[/\-.]\s*\d{4}|\d{1,2}\s*thang\s*\d{1,2}\s*nam\s*\d{4})\s*,?\s*"
                  r"(?:cua|do)\s+(?P<co>.+?)\s+(?:ve|trong)\s+(?P<ve>.+)$", re.S)
_FOOTER = ("noi nhan", "tm. hoi dong", "tm hoi dong", "tm. hdtp", "chu toa phien toa", "tai ve", "tin lien quan",
           "an le khac", "ban quyen", "copyright", "luot truy cap", "bai viet lien quan")
_LOAI = {"quyet dinh giam doc tham": "giam_doc_tham", "quyet dinh tai tham": "tai_tham",
         "ban an phuc tham": "phuc_tham", "ban an so tham": "so_tham"}


def _after_colon(line: str) -> str:
    if ":" in line[:80]:
        return line.split(":", 1)[1].strip()
    return ""


def _is_head(fl: str, names) -> bool:
    return fl.strip(" :.-–*#") in names


def _clean_quotes(s: str) -> str:
    return re.sub(r'^[\s“”"\'‘’.]+|[\s“”"\'‘’.]+$', "", s or "").strip()


def parse_anle_lines(lines: list[str], url: str | None = None) -> tuple[dict | None, list[str]]:
    warns: list[str] = []
    F = [fold_same_len(l) for l in lines]          # cùng độ dài với dòng gốc
    FF = [fold(l) for l in lines]                  # đã gộp khoảng trắng (so sánh nhãn)

    # --- vị trí tiêu đề
    anchor = next((i for i, f in enumerate(FF) if f.startswith("vi tri noi dung an le")), None)
    if anchor is None:
        anchor = next((i for i, f in enumerate(FF) if f.startswith("khai quat noi dung")), None)
    h = None
    rng = range(anchor, -1, -1) if anchor is not None else range(len(lines))
    for i in rng:
        if _H.match(F[i]):
            h = i; break
    if h is None:
        return None, ["không tìm thấy dòng tiêu đề 'Án lệ số NN/YYYY/AL'"]
    m = _H.match(F[h]); num, year = int(m.group(1)), int(m.group(2))
    title = lines[h][m.end():].strip(" -–:") or ""
    if not title and h + 1 < len(lines) and FF[h + 1].startswith("ve "):
        title = lines[h + 1].strip()
    elif title and fold(title).startswith("ve ") is False and h + 1 < len(lines) and FF[h + 1].startswith("ve "):
        title = lines[h + 1].strip()

    # --- định vị các nhãn
    key_of = {}   # idx -> key
    def mark(i, key):
        key_of.setdefault(i, key)
    seen_keys = set()
    nd_start = None
    for i in range(h + 1, len(lines)):
        f = FF[i]
        key = None
        if f.startswith("nguon an le") and "nguon" not in seen_keys: key = "nguon"
        elif f.startswith("vi tri noi dung an le") and "vitri" not in seen_keys: key = "vitri"
        elif (f.startswith("khai quat noi dung an le") or f.startswith("khai quat noi dung cua an le")) and "khaiquat" not in seen_keys: key = "khaiquat"
        elif f.startswith("noi dung an le") and "ndal" not in seen_keys: key = "ndal"
        elif f.startswith("quy dinh cua phap luat lien quan") and "quydinh" not in seen_keys: key = "quydinh"
        elif f.startswith("tu khoa") and "tukhoa" not in seen_keys: key = "tukhoa"
        elif _is_head(f, {"noi dung vu an", "noi dung vu viec"}) and "ndva" not in seen_keys: key = "ndva"; nd_start = i
        elif _is_head(f, {"nhan dinh cua toa an", "nhan dinh cua toa"}) and "nhandinh" not in seen_keys: key = "nhandinh"
        elif _is_head(f, {"quyet dinh"}) and "nhandinh" in seen_keys: key = "quyetdinh"
        if key:
            mark(i, key); seen_keys.add(key if key != "quyetdinh" else "qd_seen")
    order = sorted(key_of)
    def block(key):
        """(dòng nội dung gồm cả phần sau dấu ':' của dòng nhãn) của nhãn đầu tiên khớp."""
        for n, i in enumerate(order):
            if key_of[i] == key:
                j = order[n + 1] if n + 1 < len(order) else len(lines)
                inline = _after_colon(lines[i]) if key not in ("ndva", "nhandinh", "quyetdinh") else ""
                return ([inline] if inline else []) + lines[i + 1:j], i, j
        return None, None, None

    rec = {"precedent_id": precedent_id(num, year), "so_hieu": precedent_so_hieu(num, year), "num": num, "year": year,
           "ten": title}

    # --- khối giới thiệu (giữa tiêu đề và nhãn đầu tiên) + nguồn
    first_label = order[0] if order else len(lines)
    intro = lines[h + 1:first_label]
    nguon_lines = (block("nguon")[0] or [])
    ctx_lines = intro + nguon_lines
    ctx = " ".join(ctx_lines); ctx_f = fold_same_len(ctx)
    mt = re.search(r"thong qua\s+(?:vao\s+)?ngay\s+", ctx_f)
    rec["ngay_thong_qua"] = parse_date_vn(ctx[mt.end():mt.end() + 40]) if mt else None
    if not rec["ngay_thong_qua"]: warns.append("thiếu ngay_thong_qua")
    mc = re.search(r"cong bo\b", ctx_f)
    rec["quyet_dinh_cong_bo"] = None
    if mc:
        mq = re.search(r"quyet dinh\s+so\s*([^\s,;]+)", ctx_f[mc.end():])
        if mq:
            so = ctx[mc.end() + mq.start(1): mc.end() + mq.end(1)].strip(" ,;.")
            ngay = parse_date_vn(ctx[mc.end() + mq.end(): mc.end() + mq.end() + 60])
            if so and ngay: rec["quyet_dinh_cong_bo"] = {"so_hieu": so, "ngay": ngay}
    if not rec["quyet_dinh_cong_bo"]: warns.append("thiếu quyet_dinh_cong_bo")
    mh = re.search(r"(?:co hieu luc|ap dung)[^.;]{0,80}?tu ngay\s+", ctx_f)
    rec["ngay_hieu_luc"] = parse_date_vn(ctx[mh.end():mh.end() + 40]) if mh else None

    # --- nguồn án lệ (bản án/quyết định gốc)
    src_text = " ".join(nguon_lines) if nguon_lines else " ".join(intro)
    rec["source_judgment"] = None
    for cand in (src_text, " ".join(intro), ctx):
        cf = fold_same_len(cand)
        ms = _SRC.search(cf)
        if ms:
            loai = _LOAI.get(ms.group("loai"), "khac")
            ve = cand[ms.start("ve"):ms.end("ve")].strip()
            ve = re.sub(r"^(?:vụ án|việc)\s*", "", ve, flags=re.I)
            qm = re.search(r"[“\"]([^”\"]+)[”\"]", ve)
            ve = qm.group(1) if qm else ve
            rec["source_judgment"] = {"so_hieu": cand[ms.start("so"):ms.end("so")].strip(" ,;."),
                                      "ngay": parse_date_vn(ms.group("date")), "loai": loai,
                                      "co_quan": cand[ms.start("co"):ms.end("co")].strip(" ,;."),
                                      "ve_viec": _clean_quotes(ve)}
            break
    if not rec["source_judgment"] or not rec["source_judgment"].get("ngay"):
        warns.append("không parse được source_judgment")

    # --- vị trí nội dung án lệ
    vt, _, _ = block("vitri"); rec["vi_tri_noi_dung"] = None
    if vt:
        t = " ".join(vt); tf = fold_same_len(t)
        mp = re.search(r"\bphan\b", tf)
        nums_part = t[:mp.start()] if mp else t
        tail = tf[mp.end():] if mp else ""
        doan = []
        nf = fold_same_len(nums_part)
        for rm in re.finditer(r"(\d+)\s*(?:den|-|–)\s*(?:doan\s*)?(\d+)", nf):
            doan.extend(range(int(rm.group(1)), int(rm.group(2)) + 1))
        nf2 = re.sub(r"(\d+)\s*(?:den|-|–)\s*(?:doan\s*)?(\d+)", " ", nf)
        doan.extend(int(x) for x in re.findall(r"\d+", nf2))
        phan = ("nhan_dinh_cua_toa_an" if "nhan dinh" in tail else "noi_dung_vu_an" if "noi dung vu an" in tail else "khac")
        doan = sorted(set(doan))
        if doan: rec["vi_tri_noi_dung"] = {"phan": phan, "doan": doan}
    if not rec["vi_tri_noi_dung"]: warns.append("thiếu vi_tri_noi_dung")

    # --- khái quát nội dung (tình huống / giải pháp)
    kq, _, _ = block("khaiquat"); holdings = {}
    if kq:
        items = []; cur = None; thc = gpc = 0
        mk = re.compile(r"^[-–•*\s]*(tinh huong an le|tinh huong|giai phap phap ly|giai phap)\s*(\d+)?\s*[:.]?\s*")
        for ln in kq:
            fl = fold_same_len(ln); mm = mk.match(fl)
            if mm:
                kind = "tinh_huong" if mm.group(1).startswith("tinh") else "giai_phap_phap_ly"
                if mm.group(2): idx = int(mm.group(2))
                elif kind == "tinh_huong": thc += 1; idx = thc
                else: gpc += 1; idx = gpc
                cur = {"kind": kind, "idx": idx, "lines": [ln[mm.end():].strip()] if ln[mm.end():].strip() else []}
                items.append(cur)
            elif cur is not None:
                cur["lines"].append(ln)
        for it in items:
            holdings.setdefault(it["idx"], {"idx": it["idx"]})[it["kind"]] = "\n".join(it["lines"]).strip()
    rec["holdings_raw"] = [holdings[k] for k in sorted(holdings)]
    if not rec["holdings_raw"]: warns.append("thiếu khái quát nội dung (tình huống/giải pháp)")

    # --- quy định pháp luật liên quan
    qd, _, _ = block("quydinh"); refs = []
    for ln in qd or []:
        s = re.sub(r"^[-–•*\s]+", "", ln).strip()
        if not s: continue
        if refs and not re.search(r"[.;:]$", refs[-1]) and s[:1].islower():
            refs[-1] += " " + s
        else:
            refs.append(s)
    rec["quy_dinh_lien_quan"] = refs

    # --- từ khóa
    tk, _, _ = block("tukhoa")
    kws = []
    if tk:
        t = " ".join(tk)
        kws = [x.strip() for x in re.findall(r"[“\"]([^”\"]+)[”\"]", t)] or [x.strip(" .") for x in t.split(";") if x.strip(" .")]
    rec["keywords"] = kws
    if not kws: warns.append("thiếu từ khóa")

    # --- nội dung án lệ (mẫu cũ), nội dung vụ án, nhận định, quyết định
    nd, _, _ = block("ndal"); rec["noi_dung_an_le"] = "\n".join(nd).strip() if nd else None
    nv, _, _ = block("ndva"); rec["noi_dung_vu_an"] = "\n".join(nv or []).strip()
    if not rec["noi_dung_vu_an"]: warns.append("thiếu NỘI DUNG VỤ ÁN")
    nh, _, _ = block("nhandinh"); paras = []
    for ln in nh or []:
        mm = re.match(r"^\[(\d+)\]\s*(.*)$", ln)
        if mm:
            paras.append({"no": int(mm.group(1)), "text": mm.group(2).strip()})
        elif paras:
            paras[-1]["text"] += "\n" + ln
        else:
            warns.append("dòng nhận định không có số đoạn trước đoạn [1]: " + ln[:40])
    rec["nhan_dinh"] = paras
    if not paras: warns.append("thiếu NHẬN ĐỊNH CỦA TÒA ÁN")
    qdl, _, _ = block("quyetdinh"); qd_lines = []
    for ln in qdl or []:
        if any(fold(ln).startswith(fm) for fm in _FOOTER): break
        qd_lines.append(ln)
    rec["quyet_dinh"] = "\n".join(qd_lines).strip()
    if not rec["quyet_dinh"]: warns.append("thiếu QUYẾT ĐỊNH")
    # đối chiếu: các đoạn 'vị trí nội dung' phải có mặt trong nhận định
    if rec["vi_tri_noi_dung"] and paras and rec["vi_tri_noi_dung"]["phan"] == "nhan_dinh_cua_toa_an":
        nos = {p["no"] for p in paras}
        miss = [d for d in rec["vi_tri_noi_dung"]["doan"] if d not in nos]
        if miss: warns.append(f"vi_tri_noi_dung nhắc các đoạn {miss} không có trong nhận định đã parse")
    return rec, warns


def parse_anle_html(html: str, url: str | None = None) -> tuple[dict | None, list[str]]:
    rec, warns = parse_anle_lines(html_to_lines(html), url)
    if rec is not None:
        mm = DDOC_RE.search(url or "")
        rec["source"] = {"site": re.sub(r"^https?://([^/]+).*$", r"\1", url or "") or "unknown", "url": url,
                         "ddocname": mm.group(1) if mm else None, "fetched_at": now_iso(), "html_sha1": sha1(html)}
        rec["parse_warnings"] = warns
    return rec, warns


# ------------------------------------------------------------------ khám phá URL + chạy crawl
def discover_urls(session, cache_dir, log=print, max_list_pages=40) -> list[str]:
    """Best-effort: gom link chitietanle?dDocName=TAND... từ trang danh sách án lệ. Trang là Oracle WebCenter (ADF)
    nên phân trang có thể không theo URL; nếu không đủ EXPECTED_COUNT → dùng --urls / anle_urls.txt."""
    found: dict[str, str] = {}
    queue = list(LIST_URLS); seen = set()
    while queue and len(seen) < max_list_pages:
        u = queue.pop(0)
        if u in seen: continue
        seen.add(u)
        try:
            html = fetch(session, u, cache_dir)
        except FetchError as e:
            log(f"  [discover] {e}"); continue
        for m in DDOC_RE.finditer(html):
            found.setdefault(m.group(1), DETAIL_URL.format(ddoc=m.group(1)))
        for m in re.finditer(r'href="([^"]*anle[^"]*(?:page|trang)[^"]*)"', html, re.I):
            nu = re.sub(r"&amp;", "&", m.group(1))
            nu = nu if nu.startswith("http") else PORTAL + nu
            if nu not in seen: queue.append(nu)
    log(f"  [discover] tìm thấy {len(found)} án lệ từ {len(seen)} trang danh sách")
    return list(found.values())


def load_url_file(path) -> list[str]:
    out = []
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s or s.startswith("#"): continue
        out.append(DETAIL_URL.format(ddoc=s) if re.fullmatch(r"TAND\d+", s) else s)
    return list(dict.fromkeys(out))


def coverage_report(records: Iterable[dict], expected: int | None = None) -> dict:
    expected = EXPECTED_COUNT if expected is None else expected
    nums = sorted({r["num"] for r in records})
    mx = max(nums) if nums else 0
    return {"n_records": len(nums), "expected": expected, "max_number": mx,
            "missing_numbers": [n for n in range(1, mx + 1) if n not in set(nums)],
            "ok": len(nums) >= expected}


def crawl(urls: list[str], out_jsonl, cache_dir, session=None, delay=(2.0, 4.0), progress=None,
          stage="anle_crawl", max_consec_err=3, time_budget_s: float | None = None, log=print) -> dict:
    """Crawl tuần tự, ghi NGAY từng bản ghi vào out_jsonl (append) → bị ngắt vẫn giữ được phần đã xong."""
    out_jsonl = Path(out_jsonl); repair_jsonl(out_jsonl)
    session = session or make_session()
    done_urls = {r.get("source", {}).get("url") for r in read_jsonl(out_jsonl)}
    done_ids = {r["precedent_id"] for r in read_jsonl(out_jsonl)}
    todo = [u for u in urls if u not in done_urls]
    t0 = time.monotonic(); errs = []; consec = 0; n_ok = 0
    if progress: progress.start(stage, total=len(urls), done=len(done_urls))
    for k, u in enumerate(todo, 1):
        if time_budget_s and time.monotonic() - t0 > time_budget_s:
            if progress: progress.pause(stage, "hết ngân sách thời gian của phiên", done=len(done_urls) + n_ok, total=len(urls))
            log(f"[crawl] hết ngân sách thời gian — dừng sau {n_ok} bản ghi mới"); break
        try:
            html = fetch(session, u, cache_dir, delay=delay)
            rec, warns = parse_anle_html(html, u)
            if rec is None:
                raise ValueError("; ".join(warns))
            if rec["precedent_id"] in done_ids:
                log(f"  bỏ qua trùng {rec['precedent_id']} ({u})"); continue
            append_jsonl(out_jsonl, [rec]); done_ids.add(rec["precedent_id"]); n_ok += 1; consec = 0
            log(f"  [{k}/{len(todo)}] {rec['precedent_id']} ok" + (f" | cảnh báo: {len(warns)}" if warns else ""))
            if progress: progress.update(stage, done=len(done_ids), total=len(urls))
        except Exception as e:
            consec += 1; errs.append({"url": u, "error": repr(e)[:300]})
            log(f"  [{k}/{len(todo)}] LỖI {u}: {e!r}"[:300])
            if consec >= max_consec_err:
                if progress: progress.pause(stage, f"{consec} lỗi liên tiếp (có thể bị chặn IP)", done=len(done_ids), total=len(urls), errors=len(errs))
                log("[crawl] dừng vì lỗi liên tiếp — kiểm tra mạng/IP rồi chạy lại (phần đã xong được giữ)"); break
    recs = list(read_jsonl(out_jsonl)); cov = coverage_report(recs)
    summary = {"n_ok_new": n_ok, "n_total": len(recs), "errors": errs, "coverage": cov}
    if progress and not errs and len(recs) >= len(urls):
        progress.done(stage, done=len(recs), total=len(urls), n_missing=len(cov["missing_numbers"]))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--urls", help="file chứa URL hoặc mã TANDxxxxxx (mỗi dòng một mục)")
    ap.add_argument("--discover", action="store_true", help="thử tự khám phá danh sách từ trang chủ án lệ")
    ap.add_argument("--out", default="anle_raw.jsonl"); ap.add_argument("--cache", default="anle_html_cache")
    a = ap.parse_args(argv)
    s = make_session(); urls = []
    if a.urls: urls += load_url_file(a.urls)
    if a.discover: urls += discover_urls(s, a.cache)
    urls = list(dict.fromkeys(urls))
    if not urls:
        print("Không có URL: dùng --urls hoặc --discover"); return 2
    res = crawl(urls, a.out, a.cache, session=s)
    print({k: v for k, v in res.items() if k != "errors"}, "| lỗi:", len(res["errors"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
