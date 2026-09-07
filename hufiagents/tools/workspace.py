import os
from pathlib import Path


class Workspace:
    """Private directory; no symlinks, hardlinks, traversal or reserved metadata paths."""

    def __init__(self, root: Path):
        if root.is_symlink():
            raise PermissionError("workspace root cannot be a symlink")
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, target):
        relative = Path(target)
        if (
            relative.is_absolute()
            or not relative.parts
            or any(
                part in {"..", ".git", ".env", ".ssh"} or part.startswith(".env.")
                for part in relative.parts
            )
        ):
            raise PermissionError("path outside allowed workspace scope")
        current = self.root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise PermissionError("symlinks are not allowed")
            if current.exists() and current.is_file() and current.stat().st_nlink > 1:
                raise PermissionError("hardlinks are not allowed")
        if not current.resolve().is_relative_to(self.root):
            raise PermissionError("workspace escape")
        return current

    def read(self, target):
        path = self.path(target)
        with path.open("r", encoding="utf-8") as stream:
            value = stream.read(64001)
        if len(value) > 64000:
            raise ValueError("file exceeds bounded read size")
        return value

    def create(self, target, content):
        path = self.path(target)
        if len(content.encode()) > 64000:
            raise ValueError("file exceeds bounded write size")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Exclusive creation: existing content is never overwritten.
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            if self.read(target) == content:
                return "existing identical artifact reconciled"
            raise FileExistsError(
                "artifact exists with different content; refusing overwrite"
            ) from None
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        return "artifact created"
