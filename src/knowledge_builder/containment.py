"""Resolved-path containment. Symlinked outputs are refused.

A real path must sit inside the expected root. Output files are written to a
temp file created in that directory, then os.replace. Opens use O_NOFOLLOW.
"""

import os
import tempfile
from pathlib import Path


class ContainmentError(ValueError):
    """A path is a symlink, unreadable, or outside the expected directory."""


def real_path(path):
    return Path(os.path.realpath(path))


def require_inside(path, root):
    """Return the real path of path when it sits inside the real root."""
    root_real = real_path(root)
    try:
        path_real = real_path(path)
    except OSError as exc:
        raise ContainmentError(f"unreadable: {path}: {exc}") from exc
    try:
        path_real.relative_to(root_real)
    except ValueError:
        raise ContainmentError(f"escapes the knowledge root: {path}")
    return path_real


def reject_symlink(path):
    if os.path.islink(path):
        raise ContainmentError(f"refusing symlinked output: {path}")


def ensure_real_dir(path):
    """Create path as a real directory. Refuse a symlink at path."""
    path = Path(path)
    reject_symlink(path)
    if path.exists():
        if not path.is_dir():
            raise ContainmentError(f"not a directory: {path}")
        return path
    parent = path.parent
    reject_symlink(parent)
    if not parent.is_dir():
        raise ContainmentError(f"refusing to create {path} under {parent}")
    try:
        os.mkdir(path)
    except FileExistsError:
        reject_symlink(path)
        if not path.is_dir():
            raise ContainmentError(f"not a directory: {path}")
    return path


def open_append_nofollow(path):
    reject_symlink(path)
    try:
        return os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o644)
    except OSError as exc:
        raise ContainmentError(f"refusing output {path}: {exc}") from exc


def open_lock_nofollow(path):
    reject_symlink(path)
    try:
        return os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o644)
    except OSError as exc:
        raise ContainmentError(f"refusing output {path}: {exc}") from exc


def create_empty_nofollow(path):
    reject_symlink(path)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
    except OSError as exc:
        raise ContainmentError(f"refusing output {path}: {exc}") from exc
    os.close(fd)


def read_text_nofollow(path):
    reject_symlink(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ContainmentError(f"refusing symlinked file: {path}: {exc}") from exc
    try:
        chunks = []
        while True:
            block = os.read(fd, 65536)
            if not block:
                break
            chunks.append(block)
    finally:
        os.close(fd)
    return b"".join(chunks).decode("utf-8")


def atomic_write(directory, filename, data):
    """Write directory/filename through a temp file in directory. Refuse symlinks."""
    directory = Path(directory)
    reject_symlink(directory)
    if not directory.is_dir():
        raise ContainmentError(f"not a directory: {directory}")
    dest = directory / filename
    reject_symlink(dest)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{filename}.", dir=directory)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        reject_symlink(dest)
        os.replace(tmp_name, dest)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def file_identity(path):
    """Canonical file identity. os.stat follows a symlink to the target inode."""
    st = os.stat(path)
    return (st.st_dev, st.st_ino)
