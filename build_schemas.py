import json, pathlib

OUT = pathlib.Path(__file__).parent / "schemas"
DRAFT = "https://json-schema.org/draft/2020-12/schema"

LINH_VUC = ["hon_nhan_gia_dinh", "dan_su", "hinh_su", "kinh_doanh_thuong_mai",
            "lao_dong", "hanh_chinh", "to_tung", "khac"]
ASPECT = ["tinh_tiet", "van_de_phap_ly", "giai_phap_phap_ly"]

DEFS = {
    "span": {"type": "array", "items": {"type": "integer", "minimum": 0},
             "minItems": 2, "maxItems": 2, "description": "[start,end) ký tự trong text_clean của tài liệu"},
    "date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
    "date_or_null": {"type": ["string", "null"], "pattern": r"^\d{4}-\d{2}-\d{2}$"},
    "precedent_id": {"type": "string", "pattern": r"^AL-\d{2,3}/\d{4}$",
                     "description": "vd AL-53/2022 (số hiệu án lệ bỏ hậu tố /AL)"},
    "prov_id": {"type": "string", "pattern": r"^[^#\s]+#[A-Za-z0-9.]+$",
                "description": "<số hiệu văn bản>#<d=điều|k=khoản|c=điểm|m=mục>, vd 52/2014/QH13#d5.k2.c"},
    "query_id": {"type": "string", "pattern": r"^Q\d{3,}$"},
    "passage_id": {"type": "string", "pattern": r"^[A-Za-z0-9\-/_]+#[A-Za-z0-9._\[\]\-]+$"},
    "linh_vuc": {"type": "string", "enum": LINH_VUC},
    "text_mode": {"type": "string", "enum": ["verbatim", "paraphrase", "stub"],
                  "description": "verbatim = nguyên văn từ nguồn chính thức; paraphrase = diễn đạt lại; stub = chưa điền"},
    "curation": {"type": "object", "additionalProperties": False,
                 "required": ["status", "by"],
                 "properties": {"status": {"type": "string", "enum": ["draft_unreviewed", "expert_reviewed", "adjudicated"]},
                                "by": {"type": "string"},
                                "date": {"$ref": "#/$defs/date_or_null"},
                                "note": {"type": "string"}}},
    "entity": {"type": "object", "additionalProperties": False, "required": ["type", "text"],
               "properties": {"type": {"type": "string", "enum": ["PRECEDENT_NO", "JUDGMENT_NO", "LAW_REF", "COURT", "DATE",
                                                                  "MONEY", "PARTY_ROLE", "LEGAL_ACT", "RELIEF"]},
                              "text": {"type": "string"},
                              "norm": {"type": ["string", "null"], "description": "dạng chuẩn hoá, vd prov_id hoặc precedent_id"},
                              "span": {"oneOf": [{"$ref": "#/$defs/span"}, {"type": "null"}]}}},
    "aspect_labels": {"type": "object", "additionalProperties": False,
                      "required": ASPECT + ["overall"],
                      "description": "0 = khía cạnh không liên quan đến vụ việc; 1-4 tăng dần (theo LeCaRDv2 §3.5); overall 1-4, KHÔNG suy ra từ nhãn con",
                      "properties": {**{a: {"type": "integer", "minimum": 0, "maximum": 4} for a in ASPECT},
                                     "overall": {"type": "integer", "minimum": 1, "maximum": 4}}},
}


def used(schema):
    """keep only $defs actually referenced"""
    txt = json.dumps(schema)
    keep = {k: v for k, v in DEFS.items() if f"#/$defs/{k}" in txt}
    # transitive (entity->span, curation->date_or_null)
    changed = True
    while changed:
        changed = False
        t = json.dumps(keep)
        for k, v in DEFS.items():
            if k not in keep and f"#/$defs/{k}" in t:
                keep[k] = v; changed = True
    return keep


def R(name):
    return {"$ref": f"#/$defs/{name}"}


def obj(props, required, desc=None, extra=False):
    d = {"type": "object", "properties": props, "required": required, "additionalProperties": extra}
    if desc:
        d["description"] = desc
    return d


def arr(items, **kw):
    return {"type": "array", "items": items, **kw}


S = {}

# ---------------------------------------------------------------- precedents
S["precedents"] = obj({
    "precedent_id": R("precedent_id"),
    "so_hieu": {"type": "string", "pattern": r"^\d{2,3}/\d{4}/AL$"},
    "ten": {"type": "string", "description": "tiêu đề án lệ, vd 'về việc hủy kết hôn trái pháp luật'"},
    "linh_vuc": R("linh_vuc"),
    "status": {"type": "string", "enum": ["valid", "replaced", "revoked", "unknown"]},
    "ngay_thong_qua": R("date"),
    "quyet_dinh_cong_bo": obj({"so_hieu": {"type": "string"}, "ngay": R("date")}, ["so_hieu", "ngay"]),
    "ngay_hieu_luc": R("date_or_null"),
    "ngay_hieu_luc_note": {"type": "string"},
    "source_judgment": obj({
        "so_hieu": {"type": "string"}, "ngay": R("date"),
        "loai": {"type": "string", "enum": ["giam_doc_tham", "tai_tham", "phuc_tham", "so_tham", "khac"]},
        "co_quan": {"type": "string"}, "ve_viec": {"type": "string"}},
        ["so_hieu", "ngay", "loai", "co_quan", "ve_viec"]),
    "vi_tri_noi_dung": obj({
        "phan": {"type": "string", "enum": ["nhan_dinh_cua_toa_an", "noi_dung_vu_an", "khac"]},
        "doan": arr({"type": "integer", "minimum": 1}, minItems=1, uniqueItems=True)},
        ["phan", "doan"], "Đoạn của phần Nhận định cấu thành án lệ (như công bố chính thức)"),
    "keywords": arr({"type": "string"}, minItems=1),
    "holdings": arr(obj({
        "id": {"type": "string", "pattern": r"^H\d+$"},
        "tinh_huong": {"type": "string", "description": "Tình huống án lệ (cặp với giải_phap cùng id)"},
        "giai_phap_phap_ly": {"type": "string"},
        "legal_issue": {"type": "string"},
        "key_facts": arr(obj({
            "id": {"type": "string", "pattern": r"^K\d+$"},
            "text": {"type": "string"},
            "necessary": {"type": "boolean", "description": "tình tiết cốt lõi: thiếu thì không áp dụng được"},
            "tags": arr({"type": "string"})}, ["id", "text", "necessary"])),
        "provisions": arr(R("prov_id")),
        "applies_to_paragraphs": arr({"type": "integer", "minimum": 1}),
        "curation": R("curation")},
        ["id", "tinh_huong", "giai_phap_phap_ly", "key_facts", "curation"]), minItems=1),
    "provisions_cited": arr(obj({
        "ref": {"type": "string", "description": "như in trong văn bản"},
        "prov_id": {"oneOf": [R("prov_id"), {"type": "null"}]},
        "role": {"type": "string", "enum": ["an_le_quy_dinh_lien_quan", "trich_trong_nhan_dinh"]},
        "paragraph": {"type": ["integer", "null"]}}, ["ref", "prov_id", "role"])),
    "text_sections": obj({
        "noi_dung_vu_an": {"type": "string"},
        "nhan_dinh": arr(obj({
            "no": {"type": "integer", "minimum": 1},
            "text": {"type": "string"},
            "in_an_le_content": {"type": "boolean"},
            "stance": {"type": "string", "enum": ["adopted", "evidence_finding", "quoted_law", "rejected_quoted", "procedural"],
                       "description": "rejected_quoted = đoạn trích lập luận của cấp dưới mà án lệ bác bỏ -> không phải giải pháp"},
            "cites_provisions": arr(R("prov_id"))},
            ["no", "text", "in_an_le_content", "stance"]), minItems=1),
        "quyet_dinh": {"type": "string"}},
        ["noi_dung_vu_an", "nhan_dinh", "quyet_dinh"]),
    "text_mode": R("text_mode"),
    "source_url": {"type": "string"},
    "official_source_url": {"type": ["string", "null"]},
    "entities": arr(R("entity")),
    "cited_by": arr({"type": "string"}),
    "curation": R("curation"),
}, ["precedent_id", "so_hieu", "ten", "linh_vuc", "status", "ngay_thong_qua", "quyet_dinh_cong_bo", "ngay_hieu_luc",
    "source_judgment", "vi_tri_noi_dung", "keywords", "holdings", "provisions_cited", "text_sections", "text_mode",
    "source_url", "curation"], "Một án lệ (corpus truy xuất chính)")

# ---------------------------------------------------------------- provisions
S["provisions"] = obj({
    "prov_id": R("prov_id"),
    "van_ban": obj({"so_hieu": {"type": "string"}, "ten": {"type": "string"},
                    "loai": {"type": "string", "enum": ["luat", "bo_luat", "nghi_quyet", "phap_lenh", "thong_tu_lien_tich", "nghi_dinh", "khac"]},
                    "co_quan_ban_hanh": {"type": "string"}}, ["so_hieu", "ten", "loai"]),
    "muc": {"type": ["integer", "null"]}, "dieu": {"type": ["integer", "null"]},
    "khoan": {"type": ["integer", "null"]}, "diem": {"type": ["string", "null"]},
    "text": {"type": ["string", "null"]},
    "text_mode": R("text_mode"),
    "hieu_luc_tu": R("date_or_null"), "hieu_luc_den": R("date_or_null"),
    "status": {"type": "string", "enum": ["con_hieu_luc", "het_hieu_luc", "unknown"]},
    "parent_prov_id": {"oneOf": [R("prov_id"), {"type": "null"}]},
}, ["prov_id", "van_ban", "text", "text_mode", "status"], "Điều/khoản/điểm quy phạm; phiên bản theo hiệu lực")

# ---------------------------------------------------------------- judgments
S["judgments"] = obj({
    "judgment_id": {"type": "string", "minLength": 3},
    "meta": obj({
        "so_hieu": {"type": "string"}, "ky_hieu": {"type": "string"}, "nam": {"type": "integer"},
        "ngay_xu": R("date"), "toa_an": {"type": "string"},
        "cap_toa": {"type": "string", "enum": ["district", "provincial", "high", "supreme"]},
        "cap_xet_xu": {"type": "string", "enum": ["first_instance", "appeal", "cassation", "reopening"]},
        "linh_vuc": R("linh_vuc"), "trich_yeu": {"type": "string"}},
        ["so_hieu", "ky_hieu", "nam", "ngay_xu", "toa_an", "cap_xet_xu", "linh_vuc"]),
    "sections": arr(obj({
        "id": {"type": "string"},
        "type": {"type": "string", "enum": ["header", "plaintiff_statement", "defendant_statement", "verification_record",
                                            "prosecutor_opinion", "court_reasoning", "decision", "other"]},
        "span": {"oneOf": [R("span"), {"type": "null"}]},
        "paragraphs": arr(obj({"id": {"type": "string"}, "span": {"oneOf": [R("span"), {"type": "null"}]}}, ["id"]))},
        ["id", "type"]), minItems=1),
    "issues": arr(obj({"id": {"type": "string"}, "label": {"type": "string"}, "paragraph": {"type": "string"},
                       "question": {"type": "string"}}, ["id", "label", "question"])),
    "facts": arr(obj({
        "id": {"type": "string", "pattern": r"^F\d+$"}, "sent": {"type": "string"},
        "role": {"type": "string", "enum": ["plaintiff_alleged", "defendant_alleged", "undisputed", "court_found"]},
        "status": {"type": "string", "enum": ["accepted_by_court", "rejected_by_court", "not_addressed"]},
        "tags": arr({"type": "string"}), "source_section": {"type": "string"},
        "span": {"oneOf": [R("span"), {"type": "null"}]}}, ["id", "sent", "role"])),
    "citations_law": arr(obj({
        "ref": {"type": "string"}, "prov_id": {"oneOf": [R("prov_id"), {"type": "null"}]},
        "role": {"type": "string", "enum": ["decision_basis", "procedure", "fee", "other"]},
        "paragraph": {"type": ["string", "null"]}, "span": {"oneOf": [R("span"), {"type": "null"}]}},
        ["ref", "prov_id", "role"])),
    "citations_precedent": arr(obj({
        "precedent_id": R("precedent_id"),
        "usage": {"type": "string", "enum": ["applied", "considered_not_applied"]},
        "paragraph": {"type": "string"}, "citing_sentence_span": {"oneOf": [R("span"), {"type": "null"}]},
        "similar_facts": arr({"type": "string"}), "matched_holding": {"type": ["string", "null"]},
        "reason_if_not_applied": {"type": ["string", "null"]}},
        ["precedent_id", "usage", "paragraph"])),
    "precedent_usage": {"type": "string", "enum": ["none", "applied", "considered_not_applied"]},
    "decision_text_span": {"oneOf": [R("span"), {"type": "null"}],
                           "description": "chỉ giữ vị trí phần Quyết định làm nguồn; KHÔNG có nhãn kết quả (ngoài phạm vi: không dự đoán phán quyết)"},
    "role_in_benchmark": {"type": "string",
                          "enum": ["provenance_only", "external_validation", "hard_negative_source", "non_citing_reference"]},
    "pii_policy": {"type": "string"},
    "entities": arr(R("entity")),
    "quality": obj({"ocr_fixed": {"type": "boolean"}, "font_fix": {"type": "string"}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}},
                   ["ocr_fixed"], extra=True),
    "curation": R("curation"),
}, ["judgment_id", "meta", "sections", "issues", "facts", "citations_law", "citations_precedent", "precedent_usage",
    "role_in_benchmark", "pii_policy", "quality", "curation"],
    "Bản án: nguồn gốc truy vấn / kiểm chứng ngoại; không phải đối tượng dự đoán")

# ---------------------------------------------------------------- passages
S["passages"] = obj({
    "passage_id": R("passage_id"),
    "doc_type": {"type": "string", "enum": ["precedent", "judgment"]},
    "doc_id": {"type": "string"},
    "role": {"type": "string", "enum": ["tinh_huong", "giai_phap", "noi_dung_vu_an", "nhan_dinh", "quyet_dinh", "khac"]},
    "chunking": {"type": "string", "enum": ["structural", "sliding_350_175", "sentence"]},
    "paragraph_no": {"type": ["integer", "null"]},
    "in_an_le_content": {"type": ["boolean", "null"]},
    "stance": {"type": ["string", "null"], "enum": ["adopted", "evidence_finding", "quoted_law", "rejected_quoted", "procedural", None]},
    "span": {"oneOf": [R("span"), {"type": "null"}]},
    "text": {"type": "string"},
    "text_mode": R("text_mode"),
    "word_count": {"type": "integer", "minimum": 0},
}, ["passage_id", "doc_type", "doc_id", "role", "chunking", "text", "text_mode"],
    "Đơn vị truy xuất mức đoạn (tầng 3)")

# ---------------------------------------------------------------- queries
S["queries"] = obj({
    "query_id": R("query_id"),
    "text": {"type": "string", "minLength": 10},
    "linh_vuc": R("linh_vuc"),
    "type": {"type": "string", "enum": ["common", "controversial"]},
    "provenance": obj({
        "judgment_id": {"type": ["string", "null"]},
        "rewritten_by": {"type": "string"},
        "method": {"type": "string", "enum": ["expert_rewrite", "llm_assisted_expert_checked", "illustrative"]}},
        ["judgment_id", "rewritten_by", "method"]),
    "key_facts": arr({"type": "string"}),
    "legal_issue": {"type": "string"},
    "query_reference_date": R("date_or_null"),
    "anonymized": {"type": "boolean"},
    "fold": {"type": ["integer", "null"], "minimum": 0},
    "note": {"type": "string"},
    "curation": R("curation"),
}, ["query_id", "text", "linh_vuc", "type", "provenance", "anonymized", "curation"],
    "Truy vấn do chuyên gia viết lại, ẩn danh, ngắn (LEAD §3.1; ECtHR-PCR §3.3)")

# ---------------------------------------------------------------- qrels
S["qrels"] = obj({
    "query_id": R("query_id"), "precedent_id": R("precedent_id"),
    "labels": R("aspect_labels"),
    "applicable": {"type": "boolean"},
    "near_miss": {"type": ["string", "null"], "enum": ["same_domain", "same_provision", "different_solution", None]},
    "evidence_passage_ids": arr(R("passage_id")),
    "n_annotators": {"type": "integer", "minimum": 1},
    "adjudicated": {"type": "boolean"},
    "note": {"type": "string"},
}, ["query_id", "precedent_id", "labels", "applicable", "n_annotators", "adjudicated"],
    "Nhãn tổng hợp cuối cùng (tầng 1–2)")

# ---------------------------------------------------------------- annotations
S["annotations"] = obj({
    "annotation_id": {"type": "string"},
    "query_id": R("query_id"), "precedent_id": R("precedent_id"),
    "annotator": {"type": "string"},
    "round": {"type": "string", "enum": ["pilot", "main", "adjudication"]},
    "labels": R("aspect_labels"),
    "highlights": arr(obj({"passage_id": R("passage_id"), "span": {"oneOf": [R("span"), {"type": "null"}]},
                           "aspect": {"type": "string", "enum": ASPECT}}, ["passage_id", "aspect"])),
    "timestamp": {"type": "string"},
    "note": {"type": "string"},
}, ["annotation_id", "query_id", "precedent_id", "annotator", "round", "labels", "highlights"],
    "Nhãn từng người chấm + đoạn căn cứ (để tính Cohen's kappa; LeCaRDv2 §3.6)")

# ---------------------------------------------------------------- pairs (tầng 2)
S["pairs"] = obj({
    "pair_id": {"type": "string"},
    "query_id": R("query_id"), "precedent_id": R("precedent_id"),
    "applicable": {"type": "boolean"},
    "near_miss_type": {"type": ["string", "null"], "enum": ["same_domain", "same_provision", "different_solution", None]},
    "reason_aspect": {"type": ["string", "null"], "enum": ASPECT + [None]},
    "checklist": obj({k: {"type": ["boolean", "null"]} for k in
                      ["cung_quan_he_phap_luat", "tinh_tiet_tuong_tu", "cung_van_de_phap_ly", "dieu_luat_con_hieu_luc"]},
                     ["cung_quan_he_phap_luat", "tinh_tiet_tuong_tu", "cung_van_de_phap_ly", "dieu_luat_con_hieu_luc"],
                     "ĐỀ XUẤT, cần đối chiếu Điều 8 NQ 03/2015 trước khi dùng làm tiêu chí chấm"),
    "eligible_by_date": {"type": "boolean"},
    "mc_options": arr(obj({"id": {"type": "string"}, "text": {"type": "string"}, "is_gold": {"type": "boolean"}}, ["id", "text", "is_gold"]),
                      description="tuỳ chọn: dạng trắc nghiệm chọn đúng giải pháp pháp lý (kiểu CaseHOLD)"),
    "expert_verified": {"type": "boolean"},
    "note": {"type": "string"},
}, ["pair_id", "query_id", "precedent_id", "applicable", "checklist", "eligible_by_date", "expert_verified"],
    "Cặp truy vấn–án lệ cho nhận diện áp dụng được / gần giống nhưng không áp dụng (tầng 2)")

# ---------------------------------------------------------------- reasoning_items
S["reasoning_items"] = obj({
    "item_id": {"type": "string"}, "query_id": R("query_id"),
    "condition": {"type": "string", "enum": ["none", "statute", "statute_plus_case"]},
    "provided_sources": arr({"type": "string"}, description="id điều luật/án lệ được đưa vào prompt; ngoài danh sách này = ảo giác (CFP)"),
    "gold_citations": arr(R("precedent_id")),
    "gold_provisions": arr(R("prov_id")),
    "reference_answer": {"type": ["string", "null"]},
    "rubric": obj({"scale_min": {"type": "integer", "const": 1}, "scale_max": {"type": "integer", "const": 5},
                   "criteria": arr(obj({"name": {"type": "string"}, "description": {"type": "string"}}, ["name", "description"]), minItems=1)},
                  ["scale_min", "scale_max", "criteria"]),
    "note": {"type": "string"},
}, ["item_id", "query_id", "condition", "provided_sources", "gold_citations", "gold_provisions", "rubric"],
    "Tác vụ vận dụng + trung thực (tầng 3–4); CR/CP/CFP tính theo CLERC §4.2.1")

# ---------------------------------------------------------------- leak_probe
S["leak_probe"] = obj({
    "probe_id": {"type": "string"},
    "target_type": {"type": "string", "enum": ["precedent", "query", "passage"]},
    "target_id": {"type": "string"},
    "variant": {"type": "string", "enum": ["original", "anonymized_citation", "anonymized_entities", "no_citation_context", "citing_sentence_removed"]},
    "text": {"type": "string"},
    "mapping": arr(obj({"original": {"type": "string"}, "replacement": {"type": "string"},
                        "type": {"type": "string", "enum": ["PRECEDENT_NO", "JUDGMENT_NO", "COURT", "PERSON", "PLACE", "DATE", "LAW_REF"]}},
                       ["original", "replacement", "type"])),
    "generated_by": obj({"method": {"type": "string", "enum": ["rule", "llm", "manual"]}, "model": {"type": ["string", "null"]},
                         "date": R("date_or_null")}, ["method"]),
    "direct_quote_flag": {"type": "boolean"},
    "expected_invariants": arr({"type": "string"}, description="phải giữ nguyên sau ẩn danh: cấu trúc lập luận, điều luật"),
}, ["probe_id", "target_type", "target_id", "variant", "text", "mapping", "generated_by"],
    "Biến thể ẩn danh để kiểm tra ghi nhớ/rò rỉ (Arvin §3; LePaRD App. C)")

for name, sch in S.items():
    sch = {"$schema": DRAFT, "$id": f"urn:an-le-bench:{name}", "title": name, **sch}
    sch["$defs"] = used(sch)
    (OUT / f"{name}.schema.json").write_text(json.dumps(sch, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", len(S), "schemas")
