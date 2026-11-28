"""IO an toàn (ghi nguyên tử, JSONL append) dùng chung cho mọi module. Thiết kế cho Google Drive (FUSE):
ghi file tạm rồi os.replace; thử lại khi file bị khóa."""
from __future__ import annotations
import json, os, time, hashlib, datetime as _dt
from pathlib import Path
from typing import Iterable, Iterator, Any


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_iso() -> str:
    return _dt.date.today().isoformat()


def ensure_dir(p) -> Path:
    p = Path(p); p.mkdir(parents=True, exist_ok=True); return p


def _replace(tmp: Path, dst: Path, retries: int = 5):
    for i in range(retries):
        try:
            os.replace(tmp, dst); return
        except PermissionError:
            time.sleep(1 + i)
    os.replace(tmp, dst)


def atomic_write_text(path, text: str, encoding: str = "utf-8"):
    path = Path(path); ensure_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding=encoding, newline="\n") as f:
        f.write(text); f.flush()
        try: os.fsync(f.fileno())
        except OSError: pass
    _replace(tmp, path)


def atomic_write_bytes(path, data: bytes):
    path = Path(path); ensure_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data); f.flush()
        try: os.fsync(f.fileno())
        except OSError: pass
    _replace(tmp, path)


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        bak = path.with_name(path.name + ".bak")   # file hỏng giữa chừng → thử bản sao lưu
        if bak.exists():
            return json.loads(bak.read_text(encoding="utf-8"))
        raise


def write_json(path, obj, indent: int | None = 1, backup: bool = False):
    path = Path(path)
    if backup and path.exists():
        try: atomic_write_bytes(path.with_name(path.name + ".bak"), path.read_bytes())
        except OSError: pass
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=indent))


def read_jsonl(path) -> Iterator[dict]:
    path = Path(path)
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue   # dòng cuối có thể dở dang nếu phiên bị ngắt giữa chừng


def append_jsonl(path, records: Iterable[dict]):
    path = Path(path); ensure_dir(path.parent)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        try: os.fsync(f.fileno())
        except OSError: pass


def write_jsonl(path, records: Iterable[dict]):
    atomic_write_text(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))


def repair_jsonl(path) -> int:
    """Cắt bỏ dòng cuối bị dở dang (nếu có) để append tiếp an toàn. Trả về số dòng hợp lệ."""
    path = Path(path)
    if not path.exists(): return 0
    good, bad_tail = [], False
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s: continue
            try:
                json.loads(s); good.append(s)
            except json.JSONDecodeError:
                bad_tail = True
    if bad_tail:
        atomic_write_text(path, "".join(g + "\n" for g in good))
    return len(good)


def sha1(data: bytes | str) -> str:
    if isinstance(data, str): data = data.encode("utf-8")
    return hashlib.sha1(data).hexdigest()
