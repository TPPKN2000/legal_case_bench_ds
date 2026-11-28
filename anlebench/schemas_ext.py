"""Bổ sung schema cho pipeline xử lý án lệ / bản án (chạy SAU build_schemas.py):

    python build_schemas.py && python -m anlebench.schemas_ext

- precedents_raw.schema.json : bản ghi nguyên văn crawl từ trang án lệ (staging, trước khi chuẩn hoá thành precedents)
- judgment_texts.schema.json : text_clean của bản án — các `span` trong judgments tham chiếu vào chuỗi này
- judgments.schema.json      : thêm thuộc tính tuỳ chọn `source` (truy vết về congbobanan: case_id, url, ngày đăng, trường listing)
Idempotent: chạy nhiều lần cho cùng kết quả.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

DRAFT = "https://json-schema.org/draft/2020-12/schema"
ROOT = Path(__file__).resolve().parent.parent
S_DATE = {"type": ["string", "null"], "pattern": r"^\d{4}-\d{2}-\d{2}$"}

RAW = {
    "$schema": DRAFT, "$id": "urn:an-le-bench:precedents_raw", "title": "precedents_raw", "type": "object",
    "description": "Án lệ nguyên văn crawl từ anle.toaan.gov.vn (hoặc bản sao); nguồn để thay các trường diễn đạt lại bằng nguyên văn",
    "required": ["precedent_id", "so_hieu", "num", "year", "ten", "nhan_dinh", "quyet_dinh", "source", "parse_warnings"],
    "additionalProperties": False,
    "properties": {
        "precedent_id": {"type": "string", "pattern": r"^AL-\d{2,3}/\d{4}$"},
        "so_hieu": {"type": "string", "pattern": r"^\d{2,3}/\d{4}/AL$"},
        "num": {"type": "integer", "minimum": 1}, "year": {"type": "integer"},
        "ten": {"type": "string"}, "ngay_thong_qua": S_DATE, "ngay_hieu_luc": S_DATE,
        "quyet_dinh_cong_bo": {"oneOf": [{"type": "null"}, {"type": "object", "required": ["so_hieu", "ngay"], "additionalProperties": False,
                                                          "properties": {"so_hieu": {"type": "string"}, "ngay": {"type": "string"}}}]},
        "source_judgment": {"oneOf": [{"type": "null"}, {"type": "object", "required": ["so_hieu", "loai", "co_quan", "ve_viec"], "additionalProperties": False,
                                                       "properties": {"so_hieu": {"type": "string"}, "ngay": S_DATE,
                                                                      "loai": {"type": "string", "enum": ["giam_doc_tham", "tai_tham", "phuc_tham", "so_tham", "khac"]},
                                                                      "co_quan": {"type": "string"}, "ve_viec": {"type": "string"}}}]},
        "vi_tri_noi_dung": {"oneOf": [{"type": "null"}, {"type": "object", "required": ["phan", "doan"], "additionalProperties": False,
                                                       "properties": {"phan": {"type": "string", "enum": ["nhan_dinh_cua_toa_an", "noi_dung_vu_an", "khac"]},
                                                                      "doan": {"type": "array", "items": {"type": "integer", "minimum": 1}, "minItems": 1}}}]},
        "holdings_raw": {"type": "array", "items": {"type": "object", "required": ["idx"], "additionalProperties": False,
                                                    "properties": {"idx": {"type": "integer", "minimum": 1}, "tinh_huong": {"type": "string"},
                                                                   "giai_phap_phap_ly": {"type": "string"}}}},
        "quy_dinh_lien_quan": {"type": "array", "items": {"type": "string"}},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "noi_dung_an_le": {"type": ["string", "null"]},
        "noi_dung_vu_an": {"type": "string"},
        "nhan_dinh": {"type": "array", "items": {"type": "object", "required": ["no", "text"], "additionalProperties": False,
                                                 "properties": {"no": {"type": "integer", "minimum": 1}, "text": {"type": "string"}}}},
        "quyet_dinh": {"type": "string"},
        "source": {"type": "object", "required": ["url"], "additionalProperties": True,
                   "properties": {"site": {"type": "string"}, "url": {"type": ["string", "null"]}, "ddocname": {"type": ["string", "null"]},
                                  "fetched_at": {"type": "string"}, "html_sha1": {"type": "string"}}},
        "parse_warnings": {"type": "array", "items": {"type": "string"}},
    },
}

TEXTS = {
    "$schema": DRAFT, "$id": "urn:an-le-bench:judgment_texts", "title": "judgment_texts", "type": "object",
    "description": "text_clean của bản án; judgments[*].span là [start,end) ký tự trong text_clean này",
    "required": ["judgment_id", "text_clean", "text_sha256", "n_chars", "normalization", "source"], "additionalProperties": False,
    "properties": {"judgment_id": {"type": "string", "minLength": 3}, "text_clean": {"type": "string", "minLength": 1},
                   "text_sha256": {"type": "string"}, "n_chars": {"type": "integer", "minimum": 1},
                   "normalization": {"type": "object", "additionalProperties": True},
                   "source": {"type": "object", "additionalProperties": True}},
}

SOURCE_PROP = {
    "type": "object", "required": ["site", "case_id"], "additionalProperties": False,
    "description": "truy vết bản án về trang công bố gốc",
    "properties": {"site": {"type": "string"}, "case_id": {"type": "string"}, "url": {"type": ["string", "null"]},
                   "published": {"type": ["string", "null"]}, "listing_fields": {"type": "object", "additionalProperties": {"type": "string"}}},
}


def apply(schemas_dir=None) -> list[str]:
    d = Path(schemas_dir) if schemas_dir else ROOT / "schemas"
    d.mkdir(parents=True, exist_ok=True); done = []
    for name, sch in (("precedents_raw", RAW), ("judgment_texts", TEXTS)):
        (d / f"{name}.schema.json").write_text(json.dumps(sch, ensure_ascii=False, indent=2), encoding="utf-8"); done.append(name)
    jp = d / "judgments.schema.json"
    if jp.exists():
        j = json.loads(jp.read_text(encoding="utf-8"))
        j.setdefault("properties", {})["source"] = SOURCE_PROP
        jp.write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8"); done.append("judgments(+source)")
    else:
        print("[WARN] chưa có judgments.schema.json — chạy build_schemas.py trước", file=sys.stderr)
    return done


if __name__ == "__main__":
    print("schemas_ext:", apply())
