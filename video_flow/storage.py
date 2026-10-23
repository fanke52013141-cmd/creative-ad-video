"""Atomic local state transactions. This is acceptance enforcement, not an ACL."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import os
import uuid
from .contracts import FlowError, require


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_digest(root):
    root = Path(root)
    rows = []
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "skill symlinks are not permitted")
        if path.is_file():
            rows.append([path.relative_to(root).as_posix(), digest(path)])
    require(rows, f"empty skill: {root}")
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()


def inside(root, relative, exists=False):
    root = Path(root).resolve()
    relative = Path(relative)
    require(not relative.is_absolute() and '..' not in relative.parts, "path must be relative without traversal")
    result = (root / relative).resolve()
    require(result.is_relative_to(root) and result != root, "path escapes assigned root")
    if exists:
        require(result.is_file(), f"missing file: {relative}")
    return result


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


@contextmanager
def transaction(run):
    run = Path(run)
    lock = run / '.flow.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise FlowError("run is locked; inspect owner/process before removing stale lock") from exc
    try:
        os.write(fd, str(os.getpid()).encode())
        state = read(run / 'checkpoint.json')
        yield state
        state['sequence'] += 1
        write(run / 'checkpoint.json', state)
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)
