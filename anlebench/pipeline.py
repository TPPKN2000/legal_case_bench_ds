"""Các GIAI ĐOẠN của pipeline (gọi từ notebook Colab hoặc CLI). Mọi dữ liệu nằm dưới DRIVE_ROOT; PROGRESS ghi tiến độ.

    DRIVE_ROOT/
      PROGRESS                         # JSON tiến trình (đọc/ghi bởi anlebench.progress.Progress)
      inputs/                          # bạn đặt vào: anle_judgments.zip [, anle_urls.txt, anle_raw.jsonl (crawl sẵn ở máy khác)]
      work/anle_html_cache/            # HTML thô các trang án lệ (cache)
      work/judgments_extracted/        # listing.csv + judgments.jsonl giải nén từ zip
      outputs/precedents/              # precedents_raw.jsonl|.json, precedents.jsonl|.json, *_incomplete, *_report
      outputs/judgments/               # shards/, judgments.jsonl, judgment_texts.jsonl, citations_flat.csv, extraction_report.json
      outputs/validation_report.json
"""
from __future__ import annotations
import shutil
from dataclasses import dataclass
from pathlib import Path

from .common import ensure_dir, read_jsonl, write_json, write_jsonl, repair_jsonl
from .progress import Progress
from . import anle_crawl, anle_merge, judgment_ingest, validate_outputs, schemas_ext

STAGES = ["setup", "schemas", "anle_crawl", "anle_dataset", "judgments_unzip", "judgments_process", "validate"]


@dataclass
class Paths:
    root: Path
    @property
    def progress(self): return self.root / "PROGRESS"
    @property
    def inputs(self): return ensure_dir(self.root / "inputs")
    @property
    def html_cache(self): return ensure_dir(self.root / "work" / "anle_html_cache")
    @property
    def extracted(self): return ensure_dir(self.root / "work" / "judgments_extracted")
    @property
    def prec_dir(self): return ensure_dir(self.root / "outputs" / "precedents")
    @property
    def judg_dir(self): return ensure_dir(self.root / "outputs" / "judgments")
    @property
    def raw(self): return self.prec_dir / "precedents_raw.jsonl"
    @property
    def precedents(self): return self.prec_dir / "precedents.jsonl"
    @property
    def seed(self): return self.prec_dir / "precedents_seed.jsonl"


def make_paths(drive_root) -> Paths:
    p = Paths(Path(drive_root)); [getattr(p, a) for a in ("inputs", "html_cache", "extracted", "prec_dir", "judg_dir")]
    return p


# ---------------------------------------------------------------- schemas
def stage_schemas(repo_dir, P: Paths, prog: Progress, log=print):
    import subprocess, sys
    repo_dir = Path(repo_dir)
    prog.start("schemas")
    subprocess.run([sys.executable, "build_schemas.py"], cwd=repo_dir, check=True, capture_output=True)
    done = schemas_ext.apply(repo_dir / "schemas")
    prog.done("schemas", built=done); log("schemas OK:", done)


# ---------------------------------------------------------------- crawl án lệ
def check_anle_reachable(session, timeout=20):
    import requests
    try:
        r = session.get(anle_crawl.PORTAL, timeout=timeout)
        return (r.status_code < 500), f"HTTP {r.status_code}"
    except requests.RequestException as e:
        return False, repr(e)[:200]


def stage_anle_crawl(P: Paths, prog: Progress, discover=True, time_budget_s=None, require=True, log=print) -> dict:
    stage = "anle_crawl"
    # 1) bản crawl sẵn từ máy khác (vd chạy cục bộ ở Việt Nam) → nhập vào
    imported = P.inputs / "anle_raw.jsonl"
    if imported.exists() and not P.raw.exists():
        shutil.copy(imported, P.raw); log(f"[anle] nhập {imported.name} → {P.raw}")
    cov = anle_crawl.coverage_report(read_jsonl(P.raw))
    if cov["ok"]:
        prog.done(stage, done=cov["n_records"], total=anle_crawl.EXPECTED_COUNT, n_missing=len(cov["missing_numbers"]))
        log(f"[anle] đã đủ {cov['n_records']}/{cov['expected']} án lệ — bỏ qua crawl"); return {"skipped": True, "coverage": cov}
    # 2) danh sách URL
    session = anle_crawl.make_session(); urls = []
    uf = P.inputs / "anle_urls.txt"
    if uf.exists(): urls += anle_crawl.load_url_file(uf)
    ok, msg = check_anle_reachable(session)
    if not ok:
        prog.pause(stage, f"không truy cập được anle.toaan.gov.vn từ môi trường này ({msg})")
        text = ("Không truy cập được anle.toaan.gov.vn (có thể site chặn IP ngoài Việt Nam, như congbobanan). Cách xử lý: chạy cục bộ ở máy có IP Việt Nam\n"
                "    python -m anlebench.anle_crawl --discover --out anle_raw.jsonl   (hoặc --urls anle_urls.txt)\n"
                f"rồi upload anle_raw.jsonl vào {P.inputs} và chạy lại bước này. Chi tiết: {msg}")
        if require: raise RuntimeError(text)
        log("[anle] CẢNH BÁO:", text); return {"blocked": True}
    if discover and len(urls) < anle_crawl.EXPECTED_COUNT:
        urls += anle_crawl.discover_urls(session, P.html_cache, log=log)
    urls = list(dict.fromkeys(urls))
    if not urls:
        prog.pause(stage, "không có URL án lệ (khám phá tự động không ra kết quả)")
        raise RuntimeError(f"Không có URL án lệ nào. Tạo file {uf} (mỗi dòng 1 URL chitietanle?dDocName=TAND... hoặc mã TANDxxxxxx) rồi chạy lại.")
    res = anle_crawl.crawl(urls, P.raw, P.html_cache, session=session, progress=prog, stage=stage, time_budget_s=time_budget_s, log=log)
    cov = res["coverage"]
    if len(urls) < anle_crawl.EXPECTED_COUNT:
        prog.update(stage, force=True, note=f"chỉ có {len(urls)} URL < {anle_crawl.EXPECTED_COUNT}; bổ sung anle_urls.txt")
    log(f"[anle] {cov['n_records']}/{cov['expected']} án lệ; thiếu số: {cov['missing_numbers']}")
    return res


def stage_anle_dataset(P: Paths, prog: Progress, repo_dir=None, log=print) -> dict:
    stage = "anle_dataset"; prog.start(stage)
    raws = list(read_jsonl(P.raw))
    if not raws:
        prog.pause(stage, "chưa có precedents_raw.jsonl"); raise RuntimeError("Chưa có dữ liệu án lệ thô — chạy stage anle_crawl trước.")
    if repo_dir and not P.seed.exists():       # bản mẫu đã soạn tay (diễn đạt lại) dùng làm nền để giữ nhãn đã duyệt
        sp = Path(repo_dir) / "samples" / "precedents.jsonl"
        if sp.exists(): shutil.copy(sp, P.seed)
    write_json(P.prec_dir / "precedents_raw.json", raws, indent=1)
    rep = anle_merge.build_precedents(P.raw, P.precedents, P.seed if P.seed.exists() else None,
                                      P.prec_dir / "precedents_incomplete.jsonl", P.prec_dir / "precedents_verbatim_report.json")
    write_json(P.prec_dir / "precedents.json", list(read_jsonl(P.precedents)), indent=1)
    prog.done(stage, n_ok=rep["n_precedents"], errors=rep["n_incomplete"], n_missing=0)
    log(f"[dataset] {rep['n_precedents']} án lệ chuẩn hoá ({rep['n_merged_with_existing']} gộp với bản đã soạn), {rep['n_incomplete']} thiếu trường bắt buộc")
    return rep


# ---------------------------------------------------------------- bản án
def find_judgment_zip(P: Paths, explicit=None) -> Path:
    cands = [Path(explicit)] if explicit else sorted(P.inputs.glob("*.zip"))
    for c in cands:
        if c.exists():
            try:
                if judgment_ingest.inspect_zip(c)["jsonl"] or judgment_ingest.inspect_zip(c)["n_full_text"]:
                    return c
            except Exception:
                continue
    raise FileNotFoundError(f"Không thấy zip bản án (có judgments.jsonl hoặc details/*/full_text.txt) trong {P.inputs}. "
                            f"Đặt anle_judgments.zip vào thư mục đó hoặc truyền đường dẫn.")


def stage_judgments_unzip(P: Paths, prog: Progress, zip_path=None, log=print) -> dict:
    stage = "judgments_unzip"; prog.start(stage)
    z = find_judgment_zip(P, zip_path)
    info = judgment_ingest.inspect_zip(z); log("[zip]", z.name, info)
    out = judgment_ingest.extract_zip_inputs(z, P.extracted, log=log)
    n = sum(1 for _ in read_jsonl(out["jsonl"]))
    prog.done(stage, n_ok=n, zip=z.name, zip_info=info, extracted=out); log(f"[zip] {n} bản án trong judgments.jsonl")
    return out


def stage_judgments_process(P: Paths, prog: Progress, batch=200, time_budget_s=None, limit=None, log=print) -> dict:
    stage = "judgments_process"
    src = P.extracted / "judgments.jsonl"
    if not src.exists(): raise FileNotFoundError(f"{src} chưa có — chạy judgments_unzip trước")
    n2y = judgment_ingest.load_num2year(P.precedents, P.raw)
    log(f"[judgments] bảng số→năm án lệ: {len(n2y)} mục")
    res = judgment_ingest.process_all(read_jsonl(src), P.judg_dir, num2year=n2y, progress=prog, stage=stage, batch=batch,
                                      time_budget_s=time_budget_s, limit=limit, log=log)
    rep = judgment_ingest.finalize(P.judg_dir, P.judg_dir / "extraction_report.json")   # luôn gộp phần đã xong để có output dùng được
    prog.update(stage, force=True, n_ok=rep["n_judgments"], errors=rep["n_errors"])
    log(f"[judgments] gộp: {rep['n_judgments']} bản án, {rep['with_court_voice_precedent_citation']} có trích dẫn án lệ (lời HĐXX), {rep['n_zero_mentions']} không thấy 'án lệ' trong văn bản")
    return {**res, "report": rep}


def stage_validate(P: Paths, prog: Progress, repo_dir, log=print) -> dict:
    stage = "validate"; prog.start(stage)
    rep = validate_outputs.validate_outputs({"precedents_raw": P.raw, "precedents": P.precedents, "judgments": P.judg_dir / "judgments.jsonl",
                                             "judgment_texts": P.judg_dir / "judgment_texts.jsonl"}, Path(repo_dir) / "schemas")
    write_json(P.root / "outputs" / "validation_report.json", rep)
    bad = {k: v.get("n_errors", 0) for k, v in rep["files"].items() if v.get("n_errors")}
    (prog.done if rep["ok"] else prog.fail)(stage, **({"n_ok": sum(v.get("n", 0) for v in rep["files"].values())} if rep["ok"] else {"error": f"schema errors: {bad}; cross: {rep['cross']['errors'][:3]}"}))
    log("[validate] OK" if rep["ok"] else f"[validate] LỖI {bad} {rep['cross']['errors'][:3]}")
    return rep
