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

    def write(self, target, content, *, overwrite=False):
        if not overwrite:
            return self.create(target, content)
        path = self.path(target)
        if len(content.encode()) > 64000:
            raise ValueError("file exceeds bounded write size")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        return "artifact updated"

    def list_files(self, target=""):
        base = self.root if not target else self.path(target)
        if not base.is_dir():
            raise ValueError("target is not a directory")
        files = []
        for path in base.rglob("*"):
            if path.is_file() and not path.is_symlink():
                rel = path.relative_to(self.root)
                if not any(
                    part in {".snapshots", ".git", ".env", ".ssh"} or part.startswith(".env.")
                    for part in rel.parts
                ):
                    files.append(str(rel))
        return sorted(files)

    def delete(self, target):
        path = self.path(target)
        if not path.exists():
            raise FileNotFoundError("artifact does not exist")
        if path.is_dir():
            raise ValueError("cannot delete directory with file delete")
        path.unlink()
        return "artifact deleted"

    def snapshot(self, snapshot_name: str) -> Path:
        import shutil
        import time

        snapshot_dir = self.root / ".snapshots" / snapshot_name
        snapshot_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        target_dir = snapshot_dir / f"state_{int(time.time())}"
        target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        for item in self.root.iterdir():
            if item.name == ".snapshots":
                continue
            dest = target_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            elif item.is_file() and not item.is_symlink():
                shutil.copy2(item, dest)
        return target_dir

    def restore(self, snapshot_name: str) -> None:
        import shutil

        snapshot_dir = self.root / ".snapshots" / snapshot_name
        if not snapshot_dir.exists():
            raise FileNotFoundError(f"snapshot {snapshot_name} not found")
        # Find latest state dir in snapshot
        candidates = sorted(snapshot_dir.glob("state_*"))
        if not candidates:
            raise FileNotFoundError(f"no state snapshots in {snapshot_name}")
        latest = candidates[-1]
        # Clear current workspace files (except .snapshots)
        for item in self.root.iterdir():
            if item.name == ".snapshots":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        # Restore files from latest state
        for item in latest.iterdir():
            dest = self.root / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
