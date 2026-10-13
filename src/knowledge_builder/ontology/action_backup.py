"""On-disk originals for rollback. Restore is os.replace, so it needs no free space."""

import os
import secrets
import shutil
from pathlib import Path

from knowledge_builder.containment import ensure_real_dir

BACKUP_PARENT = "_actions"


class Backup:
    def __init__(self, root):
        self.root = root
        self.parent_existed = (root / BACKUP_PARENT).exists()
        self.directory = ensure_real_dir(root / BACKUP_PARENT) / f".rollback-{secrets.token_hex(6)}"
        self.directory.mkdir()
        self.saved, self.new_dirs = {}, []

    def save(self, rel):
        """Keep the current bytes of rel. A hard link shares the inode, because writes replace the name."""
        source = self.root / rel
        if not source.is_file():
            self.saved[rel] = None
            if not source.parent.exists() and source.parent not in self.new_dirs:
                self.new_dirs.append(source.parent)
            return
        target = self.directory / f"{len(self.saved)}"
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
        self.saved[rel] = target

    def restore(self):
        for rel, kept in self.saved.items():
            if kept is None:
                (self.root / rel).unlink(missing_ok=True)
            else:
                os.replace(kept, self.root / rel)
        for directory in self.new_dirs:
            try:
                directory.rmdir()
            except OSError:
                pass
        self.discard()

    def discard(self):
        shutil.rmtree(self.directory, ignore_errors=True)
        if not self.parent_existed:
            try:
                (self.root / BACKUP_PARENT).rmdir()
            except OSError:
                pass
