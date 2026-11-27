import json, pathlib

OUT = pathlib.Path(__file__).parent / "samples"
AL = "AL-53/2022"
SRC = "https://lsvn.vn/an-le-so-532022al-ve-viec-huy-ket-hon-trai-phap-luat1666598470-a125521.html"
HNGD = "52/2014/QH13"

P = {  # prov_id shortcuts
    "d5": f"{HNGD}#d5.k2.c", "d10": f"{HNGD}#d10.k2.a", "d11": f"{HNGD}#d11.k1", "d122": f"{HNGD}#d122.k1",
    "btt": "92/2015/QH13#d29.k1", "nq35": "35/2000/NQ-QH10#k3.a",
    "tt01": "01/2001/TTLT-TANDTC-VKSNDTC-BTP#m2.d", "tt16": "01/2016/TTLT-TANDTC-VKSNDTC-BTP#d2.k4.b",
}
CUR = {"status": "draft_unreviewed", "by": "assistant_draft", "date": "2026-11-26",
       "note": "Chưa có chuyên gia pháp lý duyệt; key_facts/necessary/stance là phỏng đoán của người soạn."}

nhan_dinh = [
    (1, "Cơ quan địa phương cho biết không còn sổ đăng ký trước năm 1989 và sổ còn lưu không có đăng ký của hai người; người yêu cầu cũng không có giấy chứng nhận, nên chưa đủ căn cứ cho rằng họ đã đăng ký kết hôn năm 1980.", False, "evidence_finding", []),
    (2, "Biên bản xác minh và lời người làm chứng xác nhận hai người có tổ chức đám cưới và sống chung năm 1980, sau đó đi nước ngoài.", True, "evidence_finding", []),
    (3, "Bản sao giấy khai sinh của người con đầu ghi tên cha mẹ, cho thấy hai người từng sống chung ở Việt Nam và người vợ sang Hồng Kông khi đã có thai.", True, "evidence_finding", []),
    (4, "Sổ hộ khẩu và hợp đồng thuê quyền sử dụng đất cũng thể hiện người này là vợ của ông H.", True, "evidence_finding", []),
    (5, "Viện dẫn quy định của Quốc hội về quan hệ vợ chồng xác lập trước 03/01/1987 mà chưa đăng ký.", False, "quoted_law", [P["nq35"]]),
    (6, "Viện dẫn hướng dẫn liên tịch năm 2001 về các trường hợp được coi là sống chung như vợ chồng.", False, "quoted_law", [P["tt01"]]),
    (7, "Viện dẫn hướng dẫn liên tịch năm 2016 về người được coi là đang có vợ, có chồng.", False, "quoted_law", [P["tt16"]]),
    (8, "Kết luận quan hệ sống chung trước năm 1987 là hôn nhân thực tế và vẫn được pháp luật công nhận dù không đăng ký.", True, "adopted", []),
    (9, "Việc ông H. đăng ký kết hôn với người khác khi quan hệ trước còn tồn tại vi phạm chế độ một vợ một chồng; cơ quan đăng ký làm không đúng quy định.", True, "adopted", [P["d5"]]),
    (10, "Tòa sơ thẩm tuyên hủy việc kết hôn trái pháp luật và giải quyết hậu quả là có căn cứ.", True, "adopted", []),
    (11, "Tòa phúc thẩm cho rằng luật Việt Nam không điều chỉnh việc chung sống chủ yếu ở nước ngoài nên không công nhận quan hệ vợ chồng; nhận định này bị cho là sai.", True, "rejected_quoted", []),
]

precedent = {
    "precedent_id": AL, "so_hieu": "53/2022/AL", "ten": "về việc hủy kết hôn trái pháp luật",
    "linh_vuc": "hon_nhan_gia_dinh", "status": "valid",
    "ngay_thong_qua": "2022-09-07",
    "quyet_dinh_cong_bo": {"so_hieu": "323/QĐ-CA", "ngay": "2022-10-14"},
    "ngay_hieu_luc": None,
    "ngay_hieu_luc_note": "Chưa kiểm chứng; lấy từ quyết định công bố/Cổng thông tin án lệ trước khi dùng cho lọc theo thời gian.",
    "source_judgment": {"so_hieu": "04/2021/HNGĐ-GĐT", "ngay": "2021-07-07", "loai": "giam_doc_tham",
                        "co_quan": "Hội đồng Thẩm phán Tòa án nhân dân tối cao",
                        "ve_viec": "Yêu cầu hủy việc kết hôn trái pháp luật"},
    "vi_tri_noi_dung": {"phan": "nhan_dinh_cua_toa_an", "doan": [2, 3, 4, 8, 9, 10, 11]},
    "keywords": ["Hôn nhân thực tế", "Hủy việc kết hôn trái pháp luật"],
    "holdings": [{
        "id": "H1",
        "tinh_huong": "Hai người chung sống như vợ chồng từ trước ngày 03/01/1987 mà không đăng ký, nhưng có đám cưới và từng sống với nhau ở Việt Nam; sau đó ra nước ngoài và phát sinh mâu thuẫn. Chưa giải quyết ly hôn thì một bên đi đăng ký kết hôn với người khác tại cơ quan có thẩm quyền của Việt Nam.",
        "giai_phap_phap_ly": "Tòa phải coi quan hệ đầu tiên là hôn nhân thực tế. Vì quan hệ này chưa chấm dứt mà một bên đã đăng ký kết hôn với người khác ở Việt Nam, lần đăng ký sau là trái pháp luật và yêu cầu hủy được chấp nhận.",
        "legal_issue": "Quan hệ sống chung như vợ chồng trước 03/01/1987 chưa đăng ký có được coi là hôn nhân thực tế, và việc đăng ký kết hôn sau đó với người khác khi chưa chấm dứt quan hệ này có phải kết hôn trái pháp luật không?",
        "key_facts": [
            {"id": "K1", "text": "Sống chung như vợ chồng trước ngày 03/01/1987, không đăng ký kết hôn", "necessary": True, "tags": ["hon_nhan_thuc_te", "moc_thoi_gian_1987"]},
            {"id": "K2", "text": "Có tổ chức lễ cưới và có thời gian chung sống tại Việt Nam", "necessary": True, "tags": ["le_cuoi", "chung_song_tai_vn"]},
            {"id": "K3", "text": "Sau đó cả hai ra nước ngoài sinh sống và phát sinh mâu thuẫn", "necessary": False, "tags": ["yeu_to_nuoc_ngoai"]},
            {"id": "K4", "text": "Chưa giải quyết ly hôn thì một bên đăng ký kết hôn với người khác tại cơ quan có thẩm quyền của Việt Nam", "necessary": True, "tags": ["dang_ky_ket_hon_sau", "chua_cham_dut_quan_he"]},
        ],
        "provisions": [P[k] for k in ("d5", "d10", "d11", "d122", "btt", "nq35", "tt01", "tt16")],
        "applies_to_paragraphs": [8, 9, 10],
        "curation": CUR,
    }],
    "provisions_cited": [
        {"ref": "Điểm c khoản 2 Điều 5 Luật Hôn nhân và gia đình năm 2014", "prov_id": P["d5"], "role": "an_le_quy_dinh_lien_quan", "paragraph": 9},
        {"ref": "Điểm a khoản 2 Điều 10 Luật Hôn nhân và gia đình năm 2014", "prov_id": P["d10"], "role": "an_le_quy_dinh_lien_quan", "paragraph": None},
        {"ref": "Khoản 1 Điều 11 Luật Hôn nhân và gia đình năm 2014", "prov_id": P["d11"], "role": "an_le_quy_dinh_lien_quan", "paragraph": None},
        {"ref": "Khoản 1 Điều 122 Luật Hôn nhân và gia đình năm 2014", "prov_id": P["d122"], "role": "an_le_quy_dinh_lien_quan", "paragraph": None},
        {"ref": "Khoản 1 Điều 29 Bộ luật Tố tụng dân sự năm 2015", "prov_id": P["btt"], "role": "an_le_quy_dinh_lien_quan", "paragraph": None},
        {"ref": "Điểm a khoản 3 Nghị quyết số 35/2000/NQ-QH10 ngày 09/6/2000", "prov_id": P["nq35"], "role": "an_le_quy_dinh_lien_quan", "paragraph": 5},
        {"ref": "Điểm d Mục 2 Thông tư liên tịch số 01/2001/TTLT-TANDTC-VKSNDTC-BTP", "prov_id": P["tt01"], "role": "an_le_quy_dinh_lien_quan", "paragraph": 6},
        {"ref": "Điểm b khoản 4 Điều 2 Thông tư liên tịch số 01/2016/TTLT-TANDTC-VKSNDTC-BTP", "prov_id": P["tt16"], "role": "an_le_quy_dinh_lien_quan", "paragraph": 7},
    ],
    "text_sections": {
        "noi_dung_vu_an": "Người yêu cầu (bà S.) cho biết bà và ông H. cưới nhau năm 1980, sau đó ra nước ngoài, về Việt Nam năm 2008 và có ba người con. Từ 2011 ông H. ngoại tình và đưa người khác về nhà; năm 2017 ông đăng ký kết hôn với bà L. Bà S. yêu cầu hủy việc kết hôn đó. Tòa sơ thẩm Quảng Ninh chấp nhận; Tòa cấp cao tại Hà Nội (phúc thẩm) sửa, công nhận hôn nhân của ông H. và bà L.; Chánh án TANDTC kháng nghị giám đốc thẩm.",
        "nhan_dinh": [{"no": n, "text": t, "in_an_le_content": a, "stance": s, "cites_provisions": c} for n, t, a, s, c in nhan_dinh],
        "quyet_dinh": "Hội đồng Thẩm phán chấp nhận kháng nghị, hủy quyết định phúc thẩm số 12/2019/QĐPT-DS ngày 18/9/2019 của TAND cấp cao tại Hà Nội và giữ nguyên quyết định sơ thẩm số 01/2018/QĐDS-ST ngày 02/02/2018 của TAND tỉnh Quảng Ninh.",
    },
    "text_mode": "paraphrase",
    "source_url": SRC, "official_source_url": None,
    "entities": [
        {"type": "PRECEDENT_NO", "text": "Án lệ số 53/2022/AL", "norm": AL, "span": None},
        {"type": "JUDGMENT_NO", "text": "Quyết định giám đốc thẩm số 04/2021/HNGĐ-GĐT", "norm": "04/2021/HNGĐ-GĐT", "span": None},
        {"type": "COURT", "text": "Hội đồng Thẩm phán Tòa án nhân dân tối cao", "norm": "HDTP-TANDTC", "span": None},
        {"type": "LAW_REF", "text": "Điểm c khoản 2 Điều 5 Luật Hôn nhân và gia đình năm 2014", "norm": P["d5"], "span": None},
        {"type": "LEGAL_ACT", "text": "hủy việc kết hôn trái pháp luật", "norm": None, "span": None},
    ],
    "cited_by": [],
    "curation": CUR,
}

judgment = {
    "judgment_id": "TBINH-2017-HNGD-ST-11",
    "meta": {"so_hieu": "11/2017/HNGĐ-ST", "ky_hieu": "HNGĐ-ST", "nam": 2017, "ngay_xu": "2017-03-16",
             "toa_an": "TAND thành phố Thái Bình, tỉnh Thái Bình", "cap_toa": "district", "cap_xet_xu": "first_instance",
             "linh_vuc": "hon_nhan_gia_dinh", "trich_yeu": "tranh chấp hôn nhân và gia đình (ly hôn)"},
    "sections": [
        {"id": "S_HEADER", "type": "header", "span": None},
        {"id": "S_PLAINTIFF", "type": "plaintiff_statement", "span": None},
        {"id": "S_DEFENDANT", "type": "defendant_statement", "span": None},
        {"id": "S_EVIDENCE", "type": "verification_record", "span": None},
        {"id": "S_PROSECUTOR", "type": "prosecutor_opinion", "span": None},
        {"id": "S_REASONING", "type": "court_reasoning", "span": None,
         "paragraphs": [{"id": f"P[{i}]", "span": None} for i in range(1, 6)]},
        {"id": "S_DECISION", "type": "decision", "span": None},
    ],
    "issues": [{"id": "I1", "label": "ly_hon_tinh_trang_tram_trong", "paragraph": "P[1]",
                "question": "Hôn nhân có lâm vào tình trạng trầm trọng, mục đích hôn nhân không đạt được hay không?"}],
    "facts": [
        {"id": "F1", "sent": "Chồng uống rượu say, xúc phạm và đánh vợ", "role": "plaintiff_alleged", "status": "accepted_by_court", "tags": ["bao_luc_gia_dinh"], "source_section": "S_PLAINTIFF", "span": None},
        {"id": "F2", "sent": "Vợ chồng ly thân từ tháng 11/2016", "role": "undisputed", "status": "accepted_by_court", "tags": ["ly_than"], "source_section": "S_PLAINTIFF", "span": None},
        {"id": "F3", "sent": "Gia đình hai bên và tổ dân phố đã hòa giải nhiều lần nhưng không hiệu quả", "role": "undisputed", "status": "accepted_by_court", "tags": ["hoa_giai_that_bai"], "source_section": "S_EVIDENCE", "span": None},
        {"id": "F4", "sent": "Bị đơn không đồng ý ly hôn, nói vẫn còn tình cảm", "role": "defendant_alleged", "status": "rejected_by_court", "tags": ["khong_dong_y_ly_hon"], "source_section": "S_DEFENDANT", "span": None},
        {"id": "F5", "sent": "Hai bên không có con chung và không có tài sản chung", "role": "undisputed", "status": "accepted_by_court", "tags": ["khong_con_chung", "khong_tai_san_chung"], "source_section": "S_PLAINTIFF", "span": None},
    ],
    "citations_law": [
        {"ref": "Khoản 1 Điều 51 Luật Hôn nhân và gia đình số 52/2014/QH13", "prov_id": f"{HNGD}#d51.k1", "role": "decision_basis", "paragraph": "S_DECISION", "span": None},
        {"ref": "Khoản 1 Điều 56 Luật Hôn nhân và gia đình số 52/2014/QH13", "prov_id": f"{HNGD}#d56.k1", "role": "decision_basis", "paragraph": "S_DECISION", "span": None},
        {"ref": "Điểm a khoản 1 Điều 35 Bộ luật Tố tụng dân sự", "prov_id": "92/2015/QH13#d35.k1.a", "role": "procedure", "paragraph": "S_DECISION", "span": None},
        {"ref": "Nghị quyết 326/2016/UBTVQH14", "prov_id": "326/2016/UBTVQH14#", "role": "fee", "paragraph": "S_DECISION", "span": None},
    ],
    "citations_precedent": [],
    "precedent_usage": "none",
    "decision_text_span": None,
    "role_in_benchmark": "non_citing_reference",
    "pii_policy": "anonymized_as_published",
    "entities": [
        {"type": "JUDGMENT_NO", "text": "11/2017/HNGĐ-ST", "norm": "11/2017/HNGĐ-ST", "span": None},
        {"type": "COURT", "text": "Tòa án nhân dân thành phố Thái Bình", "norm": None, "span": None},
        {"type": "PARTY_ROLE", "text": "nguyên đơn", "norm": "plaintiff", "span": None},
        {"type": "RELIEF", "text": "ly hôn", "norm": "divorce", "span": None},
    ],
    "quality": {"ocr_fixed": True, "font_fix": "ñ→đ, ð→Đ/đ theo ngữ cảnh, NFC", "confidence": 0.9},
    "curation": {"status": "draft_unreviewed", "by": "assistant_draft", "date": "2026-11-26"},
}

# prov_id pattern requires non-empty id after '#': fix the fee ref
judgment["citations_law"][3]["prov_id"] = "326/2016/UBTVQH14#nq"

provision = {
    "prov_id": P["d5"],
    "van_ban": {"so_hieu": HNGD, "ten": "Luật Hôn nhân và gia đình", "loai": "luat", "co_quan_ban_hanh": "Quốc hội"},
    "muc": None, "dieu": 5, "khoan": 2, "diem": "c",
    "text": None, "text_mode": "stub",
    "hieu_luc_tu": None, "hieu_luc_den": None, "status": "unknown",
    "parent_prov_id": f"{HNGD}#d5.k2",
}

passages = [
    {"passage_id": f"{AL}#P[8]", "doc_type": "precedent", "doc_id": AL, "role": "nhan_dinh", "chunking": "structural",
     "paragraph_no": 8, "in_an_le_content": True, "stance": "adopted", "span": None,
     "text": P_TXT if (P_TXT := nhan_dinh[7][1]) else "", "text_mode": "paraphrase", "word_count": len(nhan_dinh[7][1].split())},
    {"passage_id": f"{AL}#P[11]", "doc_type": "precedent", "doc_id": AL, "role": "nhan_dinh", "chunking": "structural",
     "paragraph_no": 11, "in_an_le_content": True, "stance": "rejected_quoted", "span": None,
     "text": nhan_dinh[10][1], "text_mode": "paraphrase", "word_count": len(nhan_dinh[10][1].split())},
    {"passage_id": f"{AL}#H1.tinh_huong", "doc_type": "precedent", "doc_id": AL, "role": "tinh_huong", "chunking": "structural",
     "paragraph_no": None, "in_an_le_content": None, "stance": None, "span": None,
     "text": precedent["holdings"][0]["tinh_huong"], "text_mode": "paraphrase", "word_count": len(precedent["holdings"][0]["tinh_huong"].split())},
]

query = {
    "query_id": "Q001",
    "text": "Hai người chung sống công khai như vợ chồng từ trước năm 1987, có tổ chức đám cưới nhưng không đăng ký. Sau đó họ đi nước ngoài sinh sống và mâu thuẫn. Khi chưa ly hôn, người chồng về Việt Nam đăng ký kết hôn với người khác. Người vợ đầu có yêu cầu hủy việc đăng ký kết hôn đó được không?",
    "linh_vuc": "hon_nhan_gia_dinh", "type": "common",
    "provenance": {"judgment_id": None, "rewritten_by": "assistant_illustrative", "method": "illustrative"},
    "key_facts": ["sống chung như vợ chồng trước 1987", "có đám cưới, không đăng ký", "ra nước ngoài", "đăng ký kết hôn với người khác khi chưa ly hôn"],
    "legal_issue": "hủy việc kết hôn trái pháp luật khi còn hôn nhân thực tế",
    "query_reference_date": None, "anonymized": True, "fold": None,
    "note": "MINH HOẠ do người soạn viết để thử schema; không phải truy vấn chuyên gia thật.",
    "curation": {"status": "draft_unreviewed", "by": "assistant_draft", "date": "2026-11-26"},
}

qrels = [
    {"query_id": "Q001", "precedent_id": AL, "labels": {"tinh_tiet": 4, "van_de_phap_ly": 4, "giai_phap_phap_ly": 4, "overall": 4},
     "applicable": True, "near_miss": None, "evidence_passage_ids": [f"{AL}#P[8]", f"{AL}#P[9]"], "n_annotators": 2, "adjudicated": False,
     "note": "MINH HOẠ, chưa có nhãn chuyên gia"},
]

annotations = [
    {"annotation_id": "ANN-0001", "query_id": "Q001", "precedent_id": AL, "annotator": "A1", "round": "pilot",
     "labels": {"tinh_tiet": 4, "van_de_phap_ly": 4, "giai_phap_phap_ly": 4, "overall": 4},
     "highlights": [{"passage_id": f"{AL}#H1.tinh_huong", "span": None, "aspect": "tinh_tiet"},
                    {"passage_id": f"{AL}#P[8]", "span": None, "aspect": "giai_phap_phap_ly"}],
     "timestamp": "2026-11-26T00:00:00Z", "note": "MINH HOẠ"},
    {"annotation_id": "ANN-0002", "query_id": "Q001", "precedent_id": AL, "annotator": "A2", "round": "pilot",
     "labels": {"tinh_tiet": 3, "van_de_phap_ly": 4, "giai_phap_phap_ly": 4, "overall": 4},
     "highlights": [{"passage_id": f"{AL}#P[9]", "span": None, "aspect": "van_de_phap_ly"}],
     "timestamp": "2026-11-26T00:00:00Z", "note": "MINH HOẠ"},
]

pairs = [
    {"pair_id": "PR-0001", "query_id": "Q001", "precedent_id": AL, "applicable": True, "near_miss_type": None, "reason_aspect": None,
     "checklist": {"cung_quan_he_phap_luat": True, "tinh_tiet_tuong_tu": True, "cung_van_de_phap_ly": True, "dieu_luat_con_hieu_luc": None},
     "eligible_by_date": True, "expert_verified": False, "note": "MINH HOẠ"},
    {"pair_id": "PR-0002", "query_id": "Q001", "precedent_id": "AL-54/2022", "applicable": False, "near_miss_type": "same_domain", "reason_aspect": "van_de_phap_ly",
     "checklist": {"cung_quan_he_phap_luat": True, "tinh_tiet_tuong_tu": False, "cung_van_de_phap_ly": False, "dieu_luat_con_hieu_luc": None},
     "eligible_by_date": True, "expert_verified": False,
     "note": "MINH HOẠ: cùng lĩnh vực hôn nhân gia đình nhưng án lệ 54/2022 nói về quyền nuôi con dưới 36 tháng tuổi; cần chuyên gia xác nhận"},
]

reasoning = [{
    "item_id": "RI-0001", "query_id": "Q001", "condition": "statute_plus_case",
    "provided_sources": [AL, P["d5"], P["nq35"]],
    "gold_citations": [AL], "gold_provisions": [P["d5"]],
    "reference_answer": None,
    "rubric": {"scale_min": 1, "scale_max": 5, "criteria": [
        {"name": "reasonableness", "description": "Lập luận có đúng và chặt chẽ về pháp lý không"},
        {"name": "completeness", "description": "Có xét đủ các yếu tố của án lệ và điều luật liên quan không"},
        {"name": "clarity", "description": "Trình bày rõ ràng, dễ hiểu"},
        {"name": "logical_structure", "description": "Chuỗi lập luận mạch lạc từ tình tiết đến kết luận"},
        {"name": "citation_faithfulness", "description": "Chỉ trích dẫn nguồn được cung cấp và đúng nội dung"}]},
    "note": "MINH HOẠ",
}]

leak = [{
    "probe_id": "LP-0001", "target_type": "precedent", "target_id": AL, "variant": "anonymized_citation",
    "text": "Theo án lệ số 99/2099/AL, quan hệ sống chung như vợ chồng trước ngày mốc luật định mà chưa đăng ký vẫn được coi là hôn nhân thực tế; đăng ký kết hôn sau với người khác khi quan hệ này chưa chấm dứt là trái pháp luật.",
    "mapping": [{"original": "53/2022/AL", "replacement": "99/2099/AL", "type": "PRECEDENT_NO"},
                {"original": "03/01/1987", "replacement": "ngày mốc luật định", "type": "DATE"}],
    "generated_by": {"method": "manual", "model": None, "date": "2026-11-26"},
    "direct_quote_flag": False,
    "expected_invariants": ["cấu trúc lập luận hôn nhân thực tế -> kết hôn sau trái pháp luật", "điều luật liên quan không đổi"],
}]

files = {
    "precedents": [precedent], "provisions": [provision], "judgments": [judgment], "passages": passages,
    "queries": [query], "qrels": qrels, "annotations": annotations, "pairs": pairs,
    "reasoning_items": reasoning, "leak_probe": leak,
}
for name, rows in files.items():
    (OUT / f"{name}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
# pretty copy of the headline record
(OUT / "precedent_AL-53-2022.pretty.json").write_text(json.dumps(precedent, ensure_ascii=False, indent=2), encoding="utf-8")
print({k: len(v) for k, v in files.items()})
