"""Kiểm thử end-to-end với dữ liệu giả (không cần mạng/Drive):  python -m unittest tests.test_pipeline -v"""
import csv, io, json, shutil, tempfile, unittest, zipfile
from pathlib import Path

from anlebench import anle_crawl, anle_merge, judgment_ingest, citations, pipeline, validate_outputs
from anlebench.common import read_jsonl, write_jsonl, append_jsonl, repair_jsonl
from anlebench.progress import Progress
from anlebench.vnlegal import fix_vn_text, parse_date_vn, build_prov_id

REPO = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures"

BODY = """CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
TÒA ÁN NHÂN DÂN HUYỆN A
Bản án số: {num}/2017/HNGĐ-ST
Ngày: 22/09/2017
V/v tranh chấp hôn nhân và gia đình
NHÂN DANH NƯỚC CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
NỘI DUNG VỤ ÁN:
Nguyên đơn trình bày: vợ chồng sống chung từ năm 1980, có đám cưới nhưng không đăng ký kết hôn. Nguyên đơn đề nghị áp dụng án lệ số 08/2016/AL.
Bị đơn không đồng ý với yêu cầu của nguyên đơn và cho rằng cần xem xét lại toàn bộ quan hệ tài sản chung.
NHẬN ĐỊNH CỦA TÒA ÁN:
[1] {reason}
[2] Căn cứ khoản 1 Điều 51 Luật Hôn nhân và gia đình năm 2014 thì yêu cầu của nguyên đơn là có căn cứ.
QUYẾT ĐỊNH:
Căn cứ khoản 1 Điều 51, Điều 56 Luật Hôn nhân và gia đình năm 2014; điểm a khoản 1 Điều 35 Bộ luật Tố tụng dân sự; Nghị quyết số 326/2016/UBTVQH14.
Chấp nhận yêu cầu khởi kiện của nguyên đơn. Án phí dân sự sơ thẩm theo quy định của pháp luật.
Nơi nhận:
Bản quyền thuộc Tòa án nhân dân tối cao"""
CHROME = "TRANG CHỦ\nGIỚI THIỆU\nBẢN ÁN - QUYẾT ĐỊNH\nTải bản án\n"


def make_rec(cid, num, reason, chrome=True, date="22/09/2017"):
    return {"case_id": str(cid), "url": f"https://congbobanan.toaan.gov.vn/2ta{cid}t1cvn/chi-tiet-ban-an", "kind": "Bản án",
            "title": f"số {num} ngày {date} của Tòa án nhân dân huyện A", "judgment_number": str(num), "judgment_date": date,
            "court": "Tòa án nhân dân huyện A, tỉnh B", "published": "02.11.2026",
            "fields": {"Quan hệ pháp luật": "Ly hôn", "Cấp xét xử": "Sơ thẩm", "Áp dụng án lệ": "Có áp dụng",
                       "Loại vụ/việc": "Hôn nhân và gia đình", "Thông tin về vụ/việc": "Tranh chấp ly hôn"},
            "anle_list": ["12", "8"], "anle_applied": True,
            "full_text": (CHROME if chrome else "") + BODY.format(num=num, reason=reason)}


def build_zip(path):
    recs = [make_rec(1001, 13, "Hội đồng xét xử áp dụng án lệ số 08/2016/AL để giải quyết vụ án vì tình tiết tương tự."),
            make_rec(1002, 14, "Tòa án nhận thấy án lệ số 53/2022/AL không thuộc trường hợp áp dụng trong vụ án này vì tình tiết khác."),
            make_rec(1003, 15, "Hội đồng xét xử nhận định yêu cầu là có căn cứ, không cần viện dẫn nguồn khác."),
            make_rec(1004, 16, "Áp dụng các án lệ số 04/2016/AL và 08/2016/AL và án lệ số 12 để giải quyết."),
            {"case_id": "1005", "url": "u", "fields": {}, "judgment_date": "", "court": "", "full_text": "quá ngắn"}]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("anle_judgments/judgments.jsonl", "\n".join(json.dumps(r, ensure_ascii=False) for r in recs))
        z.writestr("anle_judgments/listing.csv", "case_id,url\n1001,u\n")
        z.writestr("anle_judgments/details/1001/full_text.txt", recs[0]["full_text"])
        z.writestr("anle_judgments/details/1001/judgment_0.pdf", b"%PDF-1.4 fake")


class T(unittest.TestCase):
    def test_parser_and_merge_keep_curated(self):
        rec, w = anle_crawl.parse_anle_lines(anle_crawl.text_to_lines((FIX / "anle_53_2022.txt").read_text(encoding="utf-8")))
        self.assertEqual(rec["precedent_id"], "AL-53/2022"); self.assertEqual(rec["vi_tri_noi_dung"]["doan"], [2, 3, 4, 8, 9, 10, 11])
        self.assertEqual(w, []); self.assertEqual(rec["source_judgment"]["so_hieu"], "04/2021/HNGĐ-GĐT")
        rec["source"] = {"url": "https://anle.toaan.gov.vn/webcenter/portal/anle/chitietanle?dDocName=TAND014298"}
        new, _ = anle_merge.raw_to_precedent(rec)
        old = next(read_jsonl(REPO / "samples" / "precedents.jsonl"))
        merged, rep = anle_merge.merge_with_existing(new, old)
        self.assertEqual(merged["text_mode"], "verbatim")
        self.assertEqual(merged["holdings"][0]["key_facts"], old["holdings"][0]["key_facts"])          # nhãn đã duyệt được giữ
        self.assertEqual(merged["text_sections"]["nhan_dinh"][10]["stance"], "rejected_quoted")
        self.assertIn("Chấp nhận kháng nghị", merged["text_sections"]["quyet_dinh"])                   # đã là nguyên văn

    def test_law_refs_match_sample_prov_ids(self):
        cases = {"Điểm c khoản 2 Điều 5 Luật Hôn nhân và gia đình năm 2014": "52/2014/QH13#d5.k2.c",
                 "Điểm a khoản 3 Nghị quyết số 35/2000/NQ-QH10 ngày 09/6/2000": "35/2000/NQ-QH10#k3.a",
                 "Điểm d Mục 2 Thông tư liên tịch số 01/2001/TTLT-TANDTC-VKSNDTC-BTP": "01/2001/TTLT-TANDTC-VKSNDTC-BTP#m2.d",
                 "Điểm b khoản 4 Điều 2 Thông tư liên tịch số 01/2016/TTLT-TANDTC-VKSNDTC-BTP": "01/2016/TTLT-TANDTC-VKSNDTC-BTP#d2.k4.b"}
        for t, pid in cases.items():
            self.assertEqual([r["prov_id"] for r in citations.extract_law_refs(t, "2022-01-01")[0]], [pid])

    def test_precedent_mentions(self):
        t = "áp dụng án lệ số 08/2016/AL và Án lệ số 04/2016/AL; án lệ 2016; án lệ số 12"
        ms = citations.extract_precedent_mentions(t, {12: 2017})
        self.assertEqual([m["precedent_id"] for m in ms], ["AL-08/2016", "AL-04/2016", "AL-12/2017"])

    def test_progress_and_jsonl_repair(self):
        d = Path(tempfile.mkdtemp())
        p = Progress(d / "PROGRESS"); p.start("x", total=3); p.update("x", force=True, done=1); p.pause("x", "test")
        p2 = Progress(d / "PROGRESS"); self.assertEqual(p2.status("x"), "paused"); self.assertEqual(p2.stage("x")["done"], 1)
        f = d / "a.jsonl"; append_jsonl(f, [{"a": 1}])
        with open(f, "a") as h: h.write('{"a": 2')
        self.assertEqual(repair_jsonl(f), 1)

    def test_end_to_end_with_resume(self):
        root = Path(tempfile.mkdtemp()); P = pipeline.make_paths(root); prog = Progress(P.progress)
        build_zip(P.inputs / "anle_judgments.zip")
        # dữ liệu án lệ giả: nhập từ inputs/anle_raw.jsonl (mô phỏng crawl cục bộ)
        rec, _ = anle_crawl.parse_anle_lines(anle_crawl.text_to_lines((FIX / "anle_53_2022.txt").read_text(encoding="utf-8")))
        rec["source"] = {"url": "https://anle.toaan.gov.vn/x?dDocName=TAND1"}; rec["parse_warnings"] = []
        write_jsonl(P.inputs / "anle_raw.jsonl", [rec])
        old = anle_crawl.EXPECTED_COUNT; anle_crawl.EXPECTED_COUNT = 1
        try:
            pipeline.stage_anle_crawl(P, prog, log=lambda *a: None)
        finally:
            anle_crawl.EXPECTED_COUNT = old
        pipeline.stage_schemas(REPO, P, prog, log=lambda *a: None)
        rep = pipeline.stage_anle_dataset(P, prog, repo_dir=REPO, log=lambda *a: None); self.assertEqual(rep["n_precedents"], 1)
        pipeline.stage_judgments_unzip(P, prog, log=lambda *a: None)
        self.assertFalse((P.extracted / "judgments.jsonl").stat().st_size == 0)
        self.assertFalse(list(P.extracted.glob("*.pdf")))                                              # không giải nén PDF
        # lượt 1: chỉ xử lý 2 bản ghi (mô phỏng phiên bị ngắt)
        r1 = pipeline.stage_judgments_process(P, prog, batch=1, limit=2, log=lambda *a: None)
        self.assertEqual(prog.status("judgments_process"), "paused"); n1 = r1["report"]["n_judgments"]
        # lượt 2: chạy tiếp → không xử lý lại
        r2 = pipeline.stage_judgments_process(P, prog, batch=2, log=lambda *a: None)
        self.assertEqual(prog.status("judgments_process"), "done")
        self.assertEqual(r2["n_new"], 3); rep = r2["report"]
        self.assertEqual(rep["n_judgments"], 4); self.assertEqual(rep["n_errors"], 1)
        J = {j["source"]["case_id"]: j for j in read_jsonl(P.judg_dir / "judgments.jsonl")}
        self.assertEqual(J["1001"]["precedent_usage"], "applied")
        self.assertEqual([c["precedent_id"] for c in J["1001"]["citations_precedent"]], ["AL-08/2016"])
        self.assertEqual(J["1001"]["quality"]["citation_extraction"]["party_or_other_mentions"][0]["precedent_id"], "AL-08/2016")  # lời đương sự tách riêng
        self.assertEqual(J["1002"]["precedent_usage"], "considered_not_applied")
        self.assertEqual(J["1003"]["precedent_usage"], "none"); self.assertTrue(J["1003"]["quality"]["citation_extraction"]["zero_court_voice_citation"])   # chỉ đương sự nhắc
        self.assertEqual(rep["n_no_court_voice_citation"], 1)
        self.assertEqual(sorted(c["precedent_id"] for c in J["1004"]["citations_precedent"]), ["AL-04/2016", "AL-08/2016"])   # 'án lệ số 12' chưa có năm → không đoán
        self.assertEqual(J["1004"]["quality"]["citation_extraction"]["unresolved_precedent_mentions"], ["12"])
        roles = {c["prov_id"]: c["role"] for c in J["1001"]["citations_law"]}
        self.assertEqual(roles["326/2016/UBTVQH14#all"], "fee")
        self.assertEqual(J["1001"]["meta"]["cap_toa"], "district"); self.assertEqual(J["1001"]["meta"]["so_hieu"], "13/2017/HNGĐ-ST")
        self.assertTrue(any(k.startswith("92/2015/QH13#d35") and v == "procedure" for k, v in roles.items()))
        v = pipeline.stage_validate(P, prog, REPO, log=lambda *a: None)
        self.assertTrue(v["ok"], v)


if __name__ == "__main__":
    unittest.main()
