"""Dựng notebooks/legal_case_bench_pipeline.ipynb (Colab) bằng nbformat:  python scripts/build_notebook.py"""
import ast, sys
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent
C = []   # (kind, source)
md = lambda s: C.append(("md", s.strip("\n")))
code = lambda s: C.append(("code", s.strip("\n")))

md("""
# legal_case_bench_ds — Crawl án lệ + xử lý trích dẫn án lệ trong bản án (Colab, chạy tiếp được)

**Luồng (mọi bước idempotent; bị ngắt thì chạy lại notebook từ đầu, các bước đã xong tự bỏ qua):**

| # | Giai đoạn | Output trên Drive |
|---|-----------|-------------------|
| 1 | cài đặt repo + dựng schema | — |
| 2 | **crawl 91 án lệ** từ anle.toaan.gov.vn (nguyên văn) | `outputs/precedents/precedents_raw.jsonl` (+ `.json`) |
| 3 | chuẩn hoá thành `precedents.jsonl` (thay trường diễn đạt lại bằng nguyên văn, giữ nhãn đã duyệt) | `outputs/precedents/precedents.jsonl` (+ `.json`, `*_report.json`) |
| 4 | giải nén zip bản án (từ `congbobanan_anle_crawler.ipynb`) | `work/judgments_extracted/` |
| 5 | xử lý bản án: làm sạch, chia đoạn, **trích dẫn án lệ / điều luật** | `outputs/judgments/` (shard + gộp) |
| 6 | kiểm tra schema + nhất quán chéo | `outputs/validation_report.json` |

Tiến trình ghi ở file **`PROGRESS`** (JSON) ngay trong thư mục gốc trên Drive. Các giai đoạn 2–3 chạy **trước** và ghi lên Drive ngay,
nên nếu bước 5 bị ngắt do giới hạn thời gian của Colab free thì dữ liệu án lệ vẫn an toàn.

**Chuẩn bị trên Drive** (`MyDrive/legal_case_bench_ds_data/inputs/`): đặt `anle_judgments.zip`. Tuỳ chọn: `anle_urls.txt` (URL/mã `TAND…` của các án lệ),
`anle_raw.jsonl` (nếu bạn crawl án lệ ở máy có IP Việt Nam — xem ô crawl), và `repo/legal_case_bench_ds.zip` hoặc `repo/legal_case_bench_ds_patch.zip`.
""")

code('''
# ===== CELL 1: CẤU HÌNH + DRIVE + REPO =====
import os, sys, json, subprocess, shutil, zipfile
from pathlib import Path

# --- cấu hình ---
DRIVE_SUBDIR   = "legal_case_bench_ds_data"       # thư mục gốc dữ liệu trên Drive
REPO_URL       = "https://github.com/TPPKN2000/legal_case_bench_ds.git"   # chỉnh nếu repo ở nơi khác; để "" nếu dùng zip trên Drive
EXPECTED_ANLE  = int(os.environ.get("ANLE_EXPECTED", 91))
TIME_BUDGET_MIN_JUDGMENTS = 50     # phút tối đa cho bước xử lý bản án trong 1 phiên (None = không giới hạn)
REQUIRE_ANLE   = True              # True: dừng nếu không có dữ liệu án lệ; False: vẫn xử lý bản án (năm án lệ sẽ không suy ra được)
BATCH          = 200               # số bản án mỗi shard

# --- Drive ---
try:
    from google.colab import drive
    drive.mount("/content/drive")
    DRIVE_ROOT = Path("/content/drive/MyDrive") / DRIVE_SUBDIR
    IN_COLAB = True
except ImportError:                                  # chạy cục bộ (không phải Colab)
    DRIVE_ROOT = Path(os.environ.get("LOCAL_DRIVE_ROOT", "./drive_local")) / DRIVE_SUBDIR
    IN_COLAB = False
DRIVE_ROOT.mkdir(parents=True, exist_ok=True)
(DRIVE_ROOT / "inputs").mkdir(exist_ok=True); (DRIVE_ROOT / "repo").mkdir(exist_ok=True)

# --- repo ---
REPO_DIR = Path(os.environ.get("REPO_DIR", "/content/legal_case_bench_ds" if IN_COLAB else "./legal_case_bench_ds"))
if not (REPO_DIR / "build_schemas.py").exists():
    zr = DRIVE_ROOT / "repo" / "legal_case_bench_ds.zip"
    if zr.exists():
        with zipfile.ZipFile(zr) as z: z.extractall(REPO_DIR.parent)
    elif REPO_URL:
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)
    if not (REPO_DIR / "build_schemas.py").exists() and REPO_DIR.parent.joinpath("legal_case_bench_ds-main", "build_schemas.py").exists():
        shutil.move(str(REPO_DIR.parent / "legal_case_bench_ds-main"), str(REPO_DIR))
if not (REPO_DIR / "anlebench" / "pipeline.py").exists():        # repo chưa có package xử lý → phủ bản vá từ Drive
    pz = DRIVE_ROOT / "repo" / "legal_case_bench_ds_patch.zip"
    if not pz.exists():
        raise FileNotFoundError(f"Repo thiếu anlebench/. Commit bản vá vào repo, hoặc đặt legal_case_bench_ds_patch.zip vào {pz.parent}")
    with zipfile.ZipFile(pz) as z: z.extractall(REPO_DIR)
import importlib.util
_need = {"jsonschema": "jsonschema", "beautifulsoup4": "bs4", "lxml": "lxml", "requests": "requests", "truststore": "truststore"}
_missing = [pkg for pkg, mod in _need.items() if importlib.util.find_spec(mod) is None]
if _missing:
    _cmd = [sys.executable, "-m", "pip", "install", "-q", *_missing]
    if subprocess.run(_cmd).returncode != 0:
        subprocess.run(_cmd + ["--break-system-packages"], check=True)
sys.path.insert(0, str(REPO_DIR))

from anlebench import pipeline, anle_crawl, judgment_ingest
from anlebench.progress import Progress
anle_crawl.EXPECTED_COUNT = EXPECTED_ANLE
P = pipeline.make_paths(DRIVE_ROOT)
prog = Progress(P.progress)                               # ← file PROGRESS trên Drive
print("Drive root :", DRIVE_ROOT); print("Repo       :", REPO_DIR); print(prog.summary())
''')

code('''
# ===== CELL 2: DỰNG SCHEMA (build_schemas.py + schemas_ext) =====
pipeline.stage_schemas(REPO_DIR, P, prog)
''')

md("""
## Giai đoạn 2 — Crawl 91 án lệ (chạy TRƯỚC khi xử lý bản án)
- Đọc `inputs/anle_urls.txt` (mỗi dòng: URL `…/chitietanle?dDocName=TANDxxxxxx` hoặc chỉ mã `TANDxxxxxx`) **và/hoặc** tự khám phá từ trang danh sách (best-effort).
- Mỗi án lệ được ghi ngay vào `outputs/precedents/precedents_raw.jsonl` trên Drive → bị ngắt vẫn giữ phần đã xong.
- ⚠️ `anle.toaan.gov.vn` có thể chặn IP của Colab (như `congbobanan`). Nếu vậy notebook sẽ dừng với hướng dẫn: chạy cục bộ ở máy có IP Việt Nam
  `python -m anlebench.anle_crawl --discover --out anle_raw.jsonl` (hoặc `--urls anle_urls.txt`), upload `anle_raw.jsonl` vào `inputs/`, rồi chạy lại ô này.
""")
code('''
# ===== CELL 3: CRAWL ÁN LỆ =====
res = pipeline.stage_anle_crawl(P, prog, discover=True, require=REQUIRE_ANLE)
print(prog.summary())
''')
code('''
# ===== CELL 4: CHUẨN HOÁ BỘ DỮ LIỆU ÁN LỆ → precedents.jsonl / .json (nguyên văn) =====
rep = pipeline.stage_anle_dataset(P, prog, repo_dir=REPO_DIR)
cov = anle_crawl.coverage_report(pipeline.read_jsonl(P.raw))
print("Bao phủ:", cov)
if rep["n_incomplete"]:
    print("Án lệ thiếu trường bắt buộc (xem precedents_incomplete.jsonl):", [x["precedent_id"] for x in rep["incomplete"]])
''')

md("## Giai đoạn 4–5 — Bản án: giải nén zip và trích dẫn án lệ\nZip được suy luận theo `congbobanan_anle_crawler.ipynb`: `listing.csv`, `judgments.jsonl` (đã chứa `full_text`), `details/<case_id>/…`. Chỉ 2 file đầu được giải nén ra Drive (bỏ PDF/HTML nặng).")
code('''
# ===== CELL 5: GIẢI NÉN ZIP BẢN ÁN LÊN DRIVE =====
ZIP_PATH = None     # None: tự tìm *.zip trong inputs/ ; hoặc "/content/drive/MyDrive/.../anle_judgments.zip"
out = pipeline.stage_judgments_unzip(P, prog, zip_path=ZIP_PATH)
''')
code('''
# ===== CELL 6: XỬ LÝ BẢN ÁN (shard + checkpoint; chạy lại ô này để tiếp tục) =====
budget = TIME_BUDGET_MIN_JUDGMENTS * 60 if TIME_BUDGET_MIN_JUDGMENTS else None
LIMIT = None        # đặt số nhỏ (vd 20) để chạy thử
r = pipeline.stage_judgments_process(P, prog, batch=BATCH, time_budget_s=budget, limit=LIMIT)
print({k: v for k, v in r.items() if k != "report"})
print("Hoàn tất toàn bộ." if r["complete"] else "CHƯA XONG → chạy lại ô này (hoặc cả notebook) để tiếp tục.")
''')
code('''
# ===== CELL 7: KIỂM TRA + BÁO CÁO =====
v = pipeline.stage_validate(P, prog, REPO_DIR)
rep = json.loads((P.judg_dir / "extraction_report.json").read_text(encoding="utf-8"))
for k in ("n_judgments", "n_errors", "precedent_usage", "with_court_voice_precedent_citation", "n_no_court_voice_citation",
          "n_zero_mentions", "unresolved_precedent_mentions", "unresolved_law_refs", "mentions_outside_court_voice", "segmentation",
          "n_distinct_precedents_cited"):
    print(f"{k:<40}", rep[k])
print("Top án lệ được viện dẫn:", rep["top_precedents"][:10])
print(); print(prog.summary())
''')
code('''
# ===== CELL 8: XEM NHANH 1 BẢN GHI + TIẾN TRÌNH =====
import itertools
j = next(itertools.islice(pipeline.read_jsonl(P.judg_dir / "judgments.jsonl"), 0, 1), None)
if j:
    print(json.dumps({k: j[k] for k in ("judgment_id", "meta", "precedent_usage", "citations_precedent")}, ensure_ascii=False, indent=1)[:2000])
print("\\nPROGRESS:", P.progress)
print(P.progress.read_text(encoding="utf-8")[:1500])
''')

nb = nbf.v4.new_notebook(); nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
nb.metadata["colab"] = {"provenance": [], "name": "legal_case_bench_pipeline"}
for k, s in C:
    if k == "code": ast.parse(s)
    nb.cells.append(nbf.v4.new_markdown_cell(s) if k == "md" else nbf.v4.new_code_cell(s))
out = ROOT / "notebooks" / "legal_case_bench_pipeline.ipynb"
nbf.write(nb, out); print("ok", out, len(nb.cells))
