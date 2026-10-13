"""One lock per root for every action: `_actions/.root.lock`.

The lock file is removed on release (and `_actions/` when this lock created it), so a rejected action
leaves the root byte-identical. A waiter that wakes on an unlinked file reopens the new one.
"""

import fcntl
import os
from contextlib import contextmanager

from knowledge_builder.containment import ContainmentError, ensure_real_dir, open_lock_nofollow

LOCK_NAME = ".root.lock"


@contextmanager
def root_lock(root):
    fd, directory, created = _acquire(root)
    try:
        yield
    finally:
        (directory / LOCK_NAME).unlink(missing_ok=True)
        if created:
            try:
                directory.rmdir()
            except OSError:
                pass
        os.close(fd)


def _acquire(root):
    while True:
        existed = (root / "_actions").exists()
        try:
            directory = ensure_real_dir(root / "_actions")
            fd = open_lock_nofollow(directory / LOCK_NAME)
        except (ContainmentError, OSError) as exc:
            from knowledge_builder.ontology.action_plan import ActionError

            raise ActionError(f"cannot take the root lock: {exc}") from exc
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            same = os.stat(directory / LOCK_NAME).st_ino == os.fstat(fd).st_ino
        except FileNotFoundError:
            same = False
        if same:
            return fd, directory, not existed
        os.close(fd)
