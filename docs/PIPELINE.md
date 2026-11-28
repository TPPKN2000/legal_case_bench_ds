# Pipeline xử lý án lệ + trích dẫn bản án (`anlebench/`)

```
build_schemas.py            (có sẵn)  → schemas/*.schema.json
anlebench/schemas_ext.py    (mới)     → +precedents_raw, +judgment_texts, judgments.source
anlebench/anle_crawl.py     (mới)     crawl án lệ (nguyên văn) → precedents_raw.jsonl
anlebench/anle_merge.py     (mới)     precedents_raw → precedents.jsonl (thay diễn đạt lại bằng nguyên văn, giữ nhãn đã duyệt)
anlebench/judgment_ingest.py(mới)     zip congbobanan → judgments / judgment_texts / citations_flat.csv
anlebench/citations.py      (mới)     trích dẫn án lệ + điều luật (offset ký tự trong text_clean)
anlebench/pipeline.py       (mới)     các giai đoạn + đường dẫn Drive;  anlebench/progress.py ghi file PROGRESS
notebooks/legal_case_bench_pipeline.ipynb   notebook Colab dùng repo này
```
Dựng schema: `python build_schemas.py && python -m anlebench.schemas_ext` — kiểm thử: `python -m unittest tests.test_pipeline -v`.

## Cấu trúc thư mục Drive (`MyDrive/legal_case_bench_ds_data/`)
```
PROGRESS                       JSON tiến trình (trạng thái từng giai đoạn, bộ đếm, các phiên chạy)
inputs/anle_judgments.zip      kết quả congbobanan_anle_crawler.ipynb (bạn đặt vào)
inputs/anle_urls.txt           (tuỳ chọn) URL/mã TAND… của 91 án lệ
inputs/anle_raw.jsonl          (tuỳ chọn) án lệ crawl sẵn ở máy khác
repo/…zip                      (tuỳ chọn) repo hoặc bản vá nếu không git clone
work/anle_html_cache/          HTML thô các trang án lệ
work/judgments_extracted/      listing.csv + judgments.jsonl giải nén từ zip (chỉ 2 file, bỏ PDF)
outputs/precedents/            precedents_raw.jsonl|.json  precedents.jsonl|.json  *_incomplete.jsonl  *_verbatim_report.json
outputs/judgments/             shards/part-*.jsonl  judgments.jsonl  judgment_texts.jsonl  citations_flat.csv  extraction_report.json
outputs/validation_report.json
```

## Quy ước dữ liệu bản án
- `judgments.jsonl` tuân `schemas/judgments.schema.json`; mọi `span` là `[start,end)` ký tự trong `text_clean` của `judgment_texts.jsonl` (cùng `judgment_id = CB-<case_id>`).
- `citations_precedent[*].usage`: **chỉ xét câu của Hội đồng xét xử** (phần nhận định / quyết định). Đương sự viện dẫn ở phần khác nằm ở
  `quality.citation_extraction.party_or_other_mentions` và cột `voice` của `citations_flat.csv`.
- `applied` / `considered_not_applied`: heuristic theo dấu hiệu phủ định ("không áp dụng", "không thuộc trường hợp áp dụng"…); cần kiểm tra mẫu.
- "án lệ số 12" (thiếu năm) chỉ được suy ra năm nếu có trong `precedents` (bảng số→năm); nếu không → `unresolved_precedent_mentions`.
- Điều luật → `prov_id` bằng bảng văn bản (`vnlegal.py`), chọn phiên bản luật theo năm ghi trong câu hoặc ngày xét xử. Điều không có tên luật đi kèm không được gán (đếm ở `unresolved_law_refs`).
- Zip bản án: `judgments.jsonl` của crawler có trường `anle_list` là **lượt xem/tải** (ul.list_count_pub), không phải số án lệ.

## Thay trường diễn đạt lại bằng nguyên văn
`anle_merge.build_precedents` luôn dựng lại từ `precedents_seed.jsonl` (bản đã soạn trong `samples/`) + `precedents_raw.jsonl`:
văn bản (`noi_dung_vu_an`, `nhan_dinh[].text`, `quyet_dinh`, `tinh_huong`, `giai_phap_phap_ly`, từ khoá…) = nguyên văn, `text_mode='verbatim'`;
nhãn đã duyệt (`key_facts`, `necessary`, `tags`, `legal_issue`, `stance`, `cites_provisions`) được giữ theo id/số đoạn. `precedents_verbatim_report.json`
ghi độ giống giữa bản cũ và nguyên văn của từng trường để bạn soát.

## Chạy cục bộ crawl án lệ (khi Colab bị chặn IP)
`python -m anlebench.anle_crawl --discover --out anle_raw.jsonl --cache anle_html_cache` (hoặc `--urls anle_urls.txt`), rồi upload `anle_raw.jsonl` vào `inputs/`.
Chưa kiểm chứng: khám phá danh sách tự động (trang Oracle WebCenter) — nếu không đủ 91, tự lập `anle_urls.txt`.
