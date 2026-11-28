# an-le-bench: schema & mẫu dữ liệu (bản nháp)

```
schemas/   10 JSON Schema (draft 2020-12), mỗi file tự chứa $defs
samples/   1 bản ghi mẫu mỗi file .jsonl + precedent_AL-53-2022.pretty.json (án lệ đầy đủ)
validate.py  kiểm schema + tính nhất quán chéo:  pip install jsonschema; python validate.py [thư_mục_dữ_liệu]
```
Lưu ý
- Bản ghi án lệ 53/2022/AL chỉ có **cấu trúc thật** (số hiệu, nguồn, vị trí đoạn, điều luật viện dẫn, từ khoá) lấy từ bản đăng lsvn.vn; các trường văn bản là **diễn đạt lại** (`text_mode: paraphrase`). Thay bằng nguyên văn từ anle.toaan.gov.vn trước khi dùng.
- `key_facts[].necessary`, `stance`, mọi nhãn trong qrels/annotations/pairs là MINH HOẠ, `curation.status = draft_unreviewed`.
- `ngay_hieu_luc` để null: chưa kiểm chứng.
- Checklist ở pairs.jsonl là đề xuất, cần đối chiếu Điều 8 NQ 03/2015.

## Pipeline xử lý án lệ & trích dẫn bản án (mới)
Package `anlebench/`, notebook Colab `notebooks/legal_case_bench_pipeline.ipynb` và hướng dẫn trong [`docs/PIPELINE.md`](docs/PIPELINE.md).
Sau `python build_schemas.py` chạy thêm `python -m anlebench.schemas_ext` (thêm schema `precedents_raw`, `judgment_texts`, trường `source` của `judgments`).
