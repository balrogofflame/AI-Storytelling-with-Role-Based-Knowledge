"""Validated, append-only scenario updates with a backup and atomic replacement."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock

from ai_client import AppError

LOCAL_LOCK = RLock()


def validate_facts(facts):
    if not isinstance(facts, list) or not facts:
        raise ValueError("Expected facts")
    ids = set()
    for fact in facts:
        if not isinstance(fact, dict) or set(fact) != {"id", "text", "allowed_roles"}:
            raise ValueError("Invalid fact fields")
        identifier, text, roles = fact["id"], fact["text"], fact["allowed_roles"]
        if not isinstance(identifier, str) or not re.fullmatch(r"F\d+", identifier) or identifier in ids:
            raise ValueError("Invalid or duplicate ID")
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            raise ValueError("Invalid fact text")
        if not isinstance(roles, list) or not roles or any(role not in ("gm", "innkeeper") for role in roles):
            raise ValueError("Invalid roles")
        if len(set(roles)) != len(roles):
            raise ValueError("Duplicate roles")
        ids.add(identifier)
    return facts


def read_snapshot(path):
    try:
        raw = Path(path).read_bytes()
        facts = validate_facts(json.loads(raw.decode("utf-8-sig")))
        return raw, facts
    except (OSError, ValueError, TypeError, UnicodeError):
        raise AppError("scenario_invalid", "無法讀取場景設定，請檢查 scenario.json 的內容與格式。", 500) from None


@contextmanager
def file_lock(path):
    # The lock covers only the short compare-and-write step, never an API wait.
    with LOCAL_LOCK:
        try:
            lock_file = Path(str(path) + ".lock").open("a+b")
        except OSError:
            raise AppError("save_failed", "無法鎖定場景檔案，本次新增設定未保存。", 500) from None
        with lock_file:
            lock_file.seek(0, 2)
            if lock_file.tell() == 0:
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise AppError("scenario_busy", "其他程序正在保存設定，請稍後重新詢問。", 409) from None
            try:
                yield
            finally:
                lock_file.seek(0)
                if os.name == "nt":
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def atomic_write(path, data):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".scenario-", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def prepare_additions(facts, proposals, role):
    """IDs and permissions are assigned by the application, not by user text."""
    known = {fact["text"].strip() for fact in facts}
    next_id = max(int(fact["id"][1:]) for fact in facts) + 1
    additions = []
    for proposal in proposals:
        text = proposal["text"].strip()
        if text in known or (role == "innkeeper" and proposal["visibility"] == "gm"):
            continue
        roles = ["gm", "innkeeper"] if proposal["visibility"] == "shared" else ["gm"]
        additions.append({"id": f"F{next_id:02d}", "text": text, "allowed_roles": roles})
        next_id += 1
        known.add(text)
    return additions


def commit_additions(path, original, facts, additions):
    if not additions:
        return
    path = Path(path)
    try:
        updated = validate_facts(facts + additions)
        with file_lock(path):
            if path.read_bytes() != original:
                raise AppError("scenario_changed", "回答期間設定已被修改，本次新增未保存，請重新詢問。", 409)
            atomic_write(Path(str(path) + ".bak"), original)
            encoded = (json.dumps(updated, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            atomic_write(path, encoded)
    except AppError:
        raise
    except (OSError, ValueError, TypeError):
        raise AppError("save_failed", "新增設定無法保存，本次答案未顯示，請檢查檔案權限與磁碟空間。", 500) from None
