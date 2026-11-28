"""Tiện ích tiếng Việt pháp lý: chuẩn hoá Unicode, sửa lỗi font PDF, ngày tháng, số hiệu án lệ,
bảng văn bản pháp luật → prov_id."""
from __future__ import annotations
import re, unicodedata
from dataclasses import dataclass

# ---------------------------------------------------------------- văn bản
_ZW = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def _strip_marks_char(c: str) -> str:
    if c == "đ": return "d"
    if c == "Đ": return "D"
    d = unicodedata.normalize("NFD", c)
    b = "".join(x for x in d if unicodedata.category(x) != "Mn")
    return b if len(b) == 1 else c


def fold_same_len(s: str) -> str:
    """Bỏ dấu + hạ chữ thường, GIỮ NGUYÊN độ dài (cho NFC) để dùng chung offset với văn bản gốc."""
    return "".join(_strip_marks_char(c).lower() if len(_strip_marks_char(c).lower()) == 1 else c for c in nfc(s))


def fold(s: str) -> str:
    return re.sub(r"\s+", " ", fold_same_len(s)).strip()


def fix_vn_text(s: str):
    """Sửa lỗi font hay gặp khi trích PDF/VNI/TCVN → (text, mô tả các sửa). ñ→đ, ð→đ/Đ theo ngữ cảnh, NFC, bỏ ký tự vô hình."""
    changes = []
    out = s or ""
    if "\u200b" in out or "\u00ad" in out or "\ufeff" in out:
        out = out.translate(_ZW); changes.append("zero_width")
    if any(c in out for c in "ñÑðÐ"):
        def _eth(m):
            ch = m.group(0); i = m.start(); st = m.string
            prev = st[i - 1] if i else "\n"; nxt = st[m.end()] if m.end() < len(st) else ""
            if ch == "ñ": return "đ"
            if ch == "Ñ": return "Đ"
            if ch == "Ð": return "Đ"
            # ch == 'ð': đầu từ + sau là chữ thường + đứng đầu câu/dòng → Đ ; kề chữ HOA → Đ ; còn lại → đ
            word_start = not prev.isalpha()
            sentence_start = word_start and (i == 0 or re.search(r"(?:^|[\n.:;!?\]\)”\"])\s*$", st[max(0, i - 4):i]) is not None)
            if (word_start and nxt.isupper()) or (prev.isupper() and nxt.isupper()) or (sentence_start and nxt.islower()):
                return "Đ"
            return "đ"
        out = re.sub(r"[ñÑðÐ]", _eth, out); changes.append("ñ/ð→đ")
    n = nfc(out)
    if n != out: changes.append("NFC")
    return n, changes


# ---------------------------------------------------------------- ngày
_DATE_PATS = [
    re.compile(r"(?:ngày\s*)?(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})", re.I),
    re.compile(r"(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4})"),
]


def parse_date_vn(s: str):
    """'ngày 07 tháng 9 năm 2022' | '07/9/2022' | '07 - 9 - 2022' → '2022-09-07' hoặc None."""
    if not s: return None
    for p in _DATE_PATS:
        m = p.search(s)
        if m:
            d, mo, y = map(int, m.groups())
            if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2100:
                try:
                    import datetime as dt
                    return dt.date(y, mo, d).isoformat()
                except ValueError:
                    return None
    return None


def iter_dates_vn(s: str):
    for p in _DATE_PATS:
        for m in p.finditer(s):
            iso = parse_date_vn(m.group(0))
            if iso: yield iso, m.start(), m.end()


def date_variants(iso: str):
    y, m, d = map(int, iso.split("-"))
    return {f"{d:02d}/{m:02d}/{y}", f"{d}/{m}/{y}", f"{d:02d}-{m:02d}-{y}", f"{d}-{m}-{y}",
            f"ngày {d} tháng {m} năm {y}", f"ngày {d:02d} tháng {m:02d} năm {y}"}


# ---------------------------------------------------------------- án lệ
def precedent_id(num: int, year: int) -> str:
    return f"AL-{int(num):02d}/{int(year)}"


def precedent_so_hieu(num: int, year: int) -> str:
    return f"{int(num):02d}/{int(year)}/AL"


def split_precedent_id(pid: str):
    m = re.fullmatch(r"AL-(\d{2,3})/(\d{4})", pid or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


# ---------------------------------------------------------------- văn bản pháp luật → prov_id
@dataclass(frozen=True)
class LawVersion:
    so_hieu: str
    ten: str
    year: int
    effective_from: str | None = None   # ISO
    effective_to: str | None = None


# (alias đã bỏ dấu, các phiên bản mới → cũ)
LAW_FAMILIES = [
    (["bo luat dan su", "blds"], [LawVersion("91/2015/QH13", "Bộ luật Dân sự", 2015, "2017-01-01"),
                                  LawVersion("33/2005/QH11", "Bộ luật Dân sự", 2005, "2006-01-01", "2016-12-31")]),
    (["bo luat to tung dan su", "bltds"], [LawVersion("92/2015/QH13", "Bộ luật Tố tụng dân sự", 2015, "2016-07-01"),
                                           LawVersion("24/2004/QH11", "Bộ luật Tố tụng dân sự", 2004, "2005-01-01", "2016-06-30")]),
    (["luat hon nhan va gia dinh", "luat hon nhan gia dinh", "luat hn&gd", "luat hn va gd", "luat hngd"],
     [LawVersion("52/2014/QH13", "Luật Hôn nhân và gia đình", 2014, "2015-01-01"),
      LawVersion("22/2000/QH10", "Luật Hôn nhân và gia đình", 2000, "2001-01-01", "2014-12-31")]),
    (["luat dat dai"], [LawVersion("31/2024/QH15", "Luật Đất đai", 2024, "2024-08-01"),
                        LawVersion("45/2013/QH13", "Luật Đất đai", 2013, "2014-07-01", "2024-07-31"),
                        LawVersion("13/2003/QH11", "Luật Đất đai", 2003, "2004-07-01", "2014-06-30")]),
    (["bo luat hinh su", "blhs"], [LawVersion("100/2015/QH13", "Bộ luật Hình sự", 2015, "2018-01-01"),
                                   LawVersion("15/1999/QH10", "Bộ luật Hình sự", 1999, "2000-07-01", "2017-12-31")]),
    (["bo luat to tung hinh su", "bltths"], [LawVersion("101/2015/QH13", "Bộ luật Tố tụng hình sự", 2015, "2018-01-01"),
                                             LawVersion("19/2003/QH11", "Bộ luật Tố tụng hình sự", 2003, "2004-07-01", "2017-12-31")]),
    (["bo luat lao dong", "bllđ", "bld"], [LawVersion("45/2019/QH14", "Bộ luật Lao động", 2019, "2021-01-01"),
                                           LawVersion("10/2012/QH13", "Bộ luật Lao động", 2012, "2013-05-01", "2020-12-31")]),
    (["luat cac to chuc tin dung", "luat cac tctd"], [LawVersion("32/2024/QH15", "Luật Các tổ chức tín dụng", 2024, "2024-07-01"),
                                                      LawVersion("47/2010/QH12", "Luật Các tổ chức tín dụng", 2010, "2011-01-01", "2024-06-30")]),
    (["luat thuong mai"], [LawVersion("36/2005/QH11", "Luật Thương mại", 2005, "2006-01-01")]),
    (["luat doanh nghiep"], [LawVersion("59/2020/QH14", "Luật Doanh nghiệp", 2020, "2021-01-01"),
                             LawVersion("68/2014/QH13", "Luật Doanh nghiệp", 2014, "2015-07-01", "2020-12-31"),
                             LawVersion("60/2005/QH11", "Luật Doanh nghiệp", 2005, "2006-07-01", "2015-06-30")]),
    (["luat nha o"], [LawVersion("27/2023/QH15", "Luật Nhà ở", 2023, "2024-08-01"),
                      LawVersion("65/2014/QH13", "Luật Nhà ở", 2014, "2015-07-01", "2024-07-31")]),
    (["luat kinh doanh bat dong san"], [LawVersion("29/2023/QH15", "Luật Kinh doanh bất động sản", 2023, "2024-08-01"),
                                        LawVersion("66/2014/QH13", "Luật Kinh doanh bất động sản", 2014, "2015-07-01", "2024-07-31")]),
    (["luat thi hanh an dan su"], [LawVersion("26/2008/QH12", "Luật Thi hành án dân sự", 2008, "2009-07-01")]),
    (["luat cong chung"], [LawVersion("53/2014/QH13", "Luật Công chứng", 2014, "2015-01-01")]),
    (["luat bao hiem xa hoi"], [LawVersion("41/2024/QH15", "Luật Bảo hiểm xã hội", 2024, "2025-07-01"),
                                LawVersion("58/2014/QH13", "Luật Bảo hiểm xã hội", 2014, "2016-01-01", "2025-06-30")]),
    (["luat to tung hanh chinh"], [LawVersion("93/2015/QH13", "Luật Tố tụng hành chính", 2015, "2016-07-01")]),
    (["luat trach nhiem boi thuong cua nha nuoc"], [LawVersion("10/2017/QH14", "Luật Trách nhiệm bồi thường của Nhà nước", 2017, "2018-07-01")]),
    (["luat ban hanh van ban quy pham phap luat"], [LawVersion("80/2015/QH13", "Luật Ban hành văn bản quy phạm pháp luật", 2015, "2016-07-01")]),
    (["luat giao thong duong bo"], [LawVersion("23/2008/QH12", "Luật Giao thông đường bộ", 2008, "2009-01-01", "2025-12-31")]),
    (["luat so huu tri tue"], [LawVersion("50/2005/QH11", "Luật Sở hữu trí tuệ", 2005, "2006-07-01")]),
    (["luat bao ve quyen loi nguoi tieu dung"], [LawVersion("59/2010/QH12", "Luật Bảo vệ quyền lợi người tiêu dùng", 2010, "2011-07-01")]),
]

PROCEDURE_LAWS = {"92/2015/QH13", "24/2004/QH11", "101/2015/QH13", "19/2003/QH11", "93/2015/QH13", "26/2008/QH12"}
FEE_DOCS = {"326/2016/UBTVQH14"}

_ALIAS_INDEX = []   # (alias_folded, family_idx) sắp theo độ dài giảm dần
for _i, (_names, _vers) in enumerate(LAW_FAMILIES):
    for _n in _names:
        _ALIAS_INDEX.append((fold(_n), _i))
_ALIAS_INDEX.sort(key=lambda x: -len(x[0]))

SOHIEU_RE = re.compile(r"(\d{1,4}\s*/\s*\d{4}\s*/\s*[A-ZĐ0-9][A-ZĐ0-9\-–]*(?:[-–][A-ZĐ0-9]+)*)")


def clean_so_hieu(s: str) -> str:
    return re.sub(r"\s+", "", s).replace("–", "-")


def pick_version(family_idx: int, year: int | None = None, ref_date: str | None = None) -> LawVersion:
    vers = LAW_FAMILIES[family_idx][1]
    if year:
        for v in vers:
            if v.year == year: return v
    if ref_date:
        for v in vers:
            if (v.effective_from is None or ref_date >= v.effective_from) and (v.effective_to is None or ref_date <= v.effective_to):
                return v
    return vers[0]


def match_law_at_start(tail: str, ref_date: str | None = None):
    """tail: văn bản ngay sau 'Điều N' (đã NFC). Trả về (LawVersion|None, so_hieu|None, độ_dài_đã_tiêu_thụ) hoặc None nếu không phải tên văn bản.
    Ưu tiên số hiệu tường minh ('Luật số 91/2015/QH13'), sau đó tên luật trong bảng."""
    m = re.match(r"\s*(?:của\s+|tại\s+|theo\s+)?(?:(?:Bộ\s+luật|Luật|Pháp\s+lệnh|Nghị\s+quyết|Nghị\s+định|Thông\s+tư(?:\s+liên\s+tịch)?)\b[^\n;,]{0,120})", tail, re.I)
    if not m:
        # viết tắt: BLDS, BLTTDS ...
        m2 = re.match(r"\s*(?:của\s+)?(BLDS|BLTTDS|BLHS|BLTTHS|BLLĐ|BLLD)\b(?:\s*(?:năm\s*)?(\d{4}))?", tail)
        if m2:
            f = fold(m2.group(1))
            for alias, fi in _ALIAS_INDEX:
                if alias == f:
                    v = pick_version(fi, int(m2.group(2)) if m2.group(2) else None, ref_date)
                    return v, v.so_hieu, m2.end()
        return None
    seg = m.group(0)
    sh = SOHIEU_RE.search(seg[:70])
    if sh:   # có số hiệu tường minh
        return None, clean_so_hieu(sh.group(1)), m.start() + sh.end()
    fseg = fold_same_len(seg)
    lead = len(seg) - len(seg.lstrip())
    # bỏ tiền tố 'của/tại/theo'
    pre = re.match(r"\s*(?:cua|tai|theo)\s+", fseg)
    off = pre.end() if pre else lead
    for alias, fi in _ALIAS_INDEX:
        if fseg.startswith(alias, off):
            end = off + len(alias)
            ym = re.match(r"\s*(?:\(sửa đổi[^)]*\)\s*)?(?:năm\s*)?(\d{4})\b", seg[end:], re.I)
            year = int(ym.group(1)) if ym and 1900 < int(ym.group(1)) < 2100 else None
            if ym and year: end += ym.end()
            v = pick_version(fi, year, ref_date)
            return v, v.so_hieu, end
    return None


def build_prov_id(so_hieu: str, dieu=None, khoan=None, diem=None, muc=None) -> str:
    """<số hiệu>#m2.d5.k2.c — điểm viết thẳng chữ cái (đ→dd vì pattern prov_id chỉ cho [A-Za-z0-9.]);
    nếu không có thành phần nào: '#all' (cả văn bản)."""
    parts = []
    if muc: parts.append(f"m{int(muc)}")
    if dieu: parts.append(f"d{int(dieu)}")
    if khoan: parts.append(f"k{int(khoan)}")
    if diem: parts.append(str(diem).lower().replace("đ", "dd"))
    return f"{clean_so_hieu(so_hieu)}#" + (".".join(parts) if parts else "all")


def linh_vuc_from_code(code: str, extra: str = "") -> str:
    """ký hiệu bản án (HNGĐ, DS, HS, KDTM, LĐ, HC) hoặc loại vụ/việc → enum linh_vuc."""
    f = fold(f"{code} {extra}")
    table = [("hngd", "hon_nhan_gia_dinh"), ("hon nhan", "hon_nhan_gia_dinh"), ("kdtm", "kinh_doanh_thuong_mai"),
             ("kinh doanh", "kinh_doanh_thuong_mai"), ("thuong mai", "kinh_doanh_thuong_mai"), ("hinh su", "hinh_su"),
             ("lao dong", "lao_dong"), ("hanh chinh", "hanh_chinh"), ("dan su", "dan_su")]
    for k, v in table:
        if k in f: return v
    toks = re.split(r"[^a-z]+", f)
    for tk, v in (("hs", "hinh_su"), ("ld", "lao_dong"), ("hc", "hanh_chinh"), ("ds", "dan_su"), ("dsst", "dan_su")):
        if tk in toks: return v
    return "khac"
