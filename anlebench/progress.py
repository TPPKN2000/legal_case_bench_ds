"""PROGRESS – một file JSON trên Drive ghi lại tiến trình mọi giai đoạn để chạy tiếp được sau khi bị ngắt.

Nguồn sự thật của dữ liệu là các file output append-only (JSONL); PROGRESS chỉ là sổ ghi + bộ đếm,
nên nếu phiên Colab chết giữa lúc ghi, lần sau vẫn khôi phục được từ chính output (xem pipeline.py)."""
from __future__ import annotations
import time
from pathlib import Path
from .common import read_json, write_json, now_iso

SCHEMA_VERSION = 1


class Progress:
    def __init__(self, path, min_save_interval: float = 5.0):
        self.path = Path(path)
        self.min_save_interval = min_save_interval
        self._last_save = 0.0
        d = read_json(self.path, default=None)
        if not d:
            d = {"schema_version": SCHEMA_VERSION, "created_at": now_iso(), "updated_at": now_iso(),
                 "sessions": [], "stages": {}, "events": []}
        self.data = d
        self.data["sessions"].append({"started_at": now_iso()})
        self.data["sessions"] = self.data["sessions"][-30:]
        self.save(force=True)

    # --- stage API -----------------------------------------------------
    def stage(self, name: str) -> dict:
        return self.data["stages"].setdefault(name, {"status": "pending"})

    def status(self, name: str) -> str:
        return self.stage(name).get("status", "pending")

    def is_done(self, name: str) -> bool:
        return self.status(name) == "done"

    def update(self, name: str, force: bool = False, **kv):
        st = self.stage(name); st.update(kv); st["updated_at"] = now_iso()
        self.save(force=force)

    def start(self, name: str, **kv):
        st = self.stage(name)
        st.setdefault("first_started_at", now_iso())
        self.update(name, force=True, status="running", last_started_at=now_iso(), **kv)

    def done(self, name: str, **kv):
        self.update(name, force=True, status="done", finished_at=now_iso(), **kv)

    def pause(self, name: str, reason: str, **kv):
        self.update(name, force=True, status="paused", pause_reason=reason, **kv)

    def fail(self, name: str, error: str, **kv):
        self.update(name, force=True, status="failed", error=error[:500], **kv)

    def reset(self, name: str):
        self.data["stages"].pop(name, None); self.event(f"reset {name}"); self.save(force=True)

    def event(self, msg: str):
        self.data["events"].append({"t": now_iso(), "msg": msg})
        self.data["events"] = self.data["events"][-200:]
        self.save()

    # --- persistence ---------------------------------------------------
    def save(self, force: bool = False):
        now = time.monotonic()
        if not force and now - self._last_save < self.min_save_interval:
            return
        self.data["updated_at"] = now_iso()
        write_json(self.path, self.data, backup=True)
        self._last_save = now

    def summary(self) -> str:
        rows = []
        for k, v in self.data["stages"].items():
            extra = {x: v[x] for x in v if x in ("done", "total", "errors", "pause_reason", "n_ok", "n_missing") and v[x] not in (None, "")}
            rows.append(f"  {k:<28} {v.get('status','?'):<8} {extra if extra else ''}")
        return "PROGRESS (" + str(self.path) + ")\n" + ("\n".join(rows) if rows else "  (trống)")
