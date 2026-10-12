"""Resolved-path containment. Symlinked outputs are refused.

A real path must sit inside the expected root. Output files are written to a
temp file created in that directory, then os.replace. Opens use O_NOFOLLOW.
"""

import os
import secrets
import stat
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


def _read_fd(fd):
    chunks = []
    while True:
        block = os.read(fd, 65536)
        if not block:
            break
        chunks.append(block)
    return b"".join(chunks)


def read_text_nofollow(path):
    reject_symlink(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ContainmentError(f"refusing symlinked file: {path}: {exc}") from exc
    try:
        return _read_fd(fd).decode("utf-8")
    finally:
        os.close(fd)


def read_bytes_inside(path, root):
    """Read path with O_NOFOLLOW and refuse a real path outside root."""
    path = Path(path)
    root = Path(root)
    reject_symlink(path)
    try:
        fd = os.open(os.fspath(path), os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ContainmentError(f"refusing symlinked file: {path}: {exc}") from exc
    try:
        require_inside(path, root)
        opened = os.fstat(fd)
        current = os.stat(os.fspath(path))
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise ContainmentError(f"escapes the knowledge root: {path}")
        return _read_fd(fd)
    finally:
        os.close(fd)


def read_text_inside(path, root):
    return read_bytes_inside(path, root).decode("utf-8")


def write_all(fd, data):
    """Write every byte. A short or empty write is not success."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("write_all requires bytes")
    offset = 0
    length = len(data)
    while offset < length:
        written = os.write(fd, data[offset:])
        if written <= 0:
            raise OSError("short write made no progress")
        offset += written


def _output_name(filename):
    if (
        not isinstance(filename, str)
        or filename in {"", ".", ".."}
        or "/" in filename
        or "\\" in filename
    ):
        raise ContainmentError(f"refusing output name: {filename}")
    return filename


def _reject_linked_name(dir_fd, filename):
    try:
        info = os.lstat(filename, dir_fd=dir_fd)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode):
        raise ContainmentError(f"refusing symlinked output: {filename}")


def _exclusive_temp(dir_fd, filename):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    for _ in range(16):
        name = f".{filename}.{secrets.token_hex(8)}"
        try:
            fd = os.open(name, flags, 0o644, dir_fd=dir_fd)
        except FileExistsError:
            continue
        return fd, name
    raise ContainmentError("could not create a temporary file in the output directory")


def _discard_temp(dir_fd, tmp_name):
    if tmp_name is None:
        return
    try:
        os.unlink(tmp_name, dir_fd=dir_fd)
    except OSError:
        pass


def atomic_write(directory, filename, data):
    """Publish directory/filename through one pinned directory descriptor.

    The directory is opened once with O_DIRECTORY|O_NOFOLLOW. The temp file is
    created, written, and fsynced on that descriptor, then os.replace uses the
    same descriptor for both names. A later swap of the directory path cannot
    retarget the replace.
    """
    directory = Path(directory)
    filename = _output_name(filename)
    reject_symlink(directory)
    if not directory.is_dir():
        raise ContainmentError(f"not a directory: {directory}")
    reject_symlink(directory / filename)
    flags = os.O_RDONLY | os.O_NOFOLLOW
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        dir_fd = os.open(os.fspath(directory), flags)
    except OSError as exc:
        raise ContainmentError(f"refusing output directory {directory}: {exc}") from exc
    tmp_name = None
    try:
        info = os.fstat(dir_fd)
        if not stat.S_ISDIR(info.st_mode):
            raise ContainmentError(f"not a directory: {directory}")
        _reject_linked_name(dir_fd, filename)
        file_fd, tmp_name = _exclusive_temp(dir_fd, filename)
        try:
            write_all(file_fd, data)
            os.fsync(file_fd)
        finally:
            os.close(file_fd)
        _reject_linked_name(dir_fd, filename)
        os.replace(tmp_name, filename, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        tmp_name = None
    except Exception:
        _discard_temp(dir_fd, tmp_name)
        raise
    finally:
        os.close(dir_fd)


def file_identity(path):
    """Canonical file identity. os.stat follows a symlink to the target inode."""
    st = os.stat(path)
    return (st.st_dev, st.st_ino)
