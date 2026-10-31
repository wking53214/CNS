"""ledger: a receiver's memory of which messages it has already acted on, so none is acted on twice.

A signature proves a message is genuine; it cannot prove the message is new. Anyone who saw a signed decision can
send it again. The receiver therefore keeps a ledger of (sender, message id) pairs it has accepted, and `spend`
refuses a pair it has seen. Because every message the session layer accepts must expire, an entry only has to be
kept until its message would be refused as expired anyway.

`MemoryLedger` is one process. `FileLedger` is an append-only file under an exclusive lock, so several processes on
one host (a receiver and the separate process that performs the action, say) share one memory and still spend a
message once. It is the receiver's ledger: single use is enforced per audience, which is why every decision is
addressed to exactly one identity (`to`). A decision addressed to A is refused by B's `audience` check, so B never
needs A's ledger.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Protocol, Tuple

from .envelope import Refused, now_ms

__all__ = ["Ledger", "MemoryLedger", "FileLedger"]


class Ledger(Protocol):
    def spend(self, sender: str, message_id: str, expires_at: Optional[int], *, now: Optional[int] = None) -> None: ...


class MemoryLedger:
    def __init__(self, *, keep_ms: int = 120_000) -> None:
        self._seen: Dict[Tuple[str, str], Optional[int]] = {}
        self._lock = threading.Lock()
        self._keep_ms = keep_ms

    def spend(self, sender: str, message_id: str, expires_at: Optional[int], *, now: Optional[int] = None) -> None:
        with self._lock:
            if (sender, message_id) in self._seen:
                raise Refused("replayed", "this message was already accepted once")
            cutoff = _cutoff(now, self._keep_ms)  # an entry is kept until its message would be refused as expired
            self._seen = {k: e for k, e in self._seen.items() if e is None or e > cutoff}
            self._seen[(sender, message_id)] = expires_at


class FileLedger:
    """Shared by every process on this host that opens the same path. POSIX file locks; not for network filesystems."""

    def __init__(self, path: os.PathLike | str, *, keep_ms: int = 120_000) -> None:
        try:
            import fcntl  # noqa: F401
        except ImportError:  # pragma: no cover - there is no POSIX lock to share
            raise RuntimeError("FileLedger needs POSIX file locks (fcntl); use one process with MemoryLedger") from None
        self._path = Path(path)
        self._keep_ms = keep_ms
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.touch(exist_ok=True)

    def spend(self, sender: str, message_id: str, expires_at: Optional[int], *, now: Optional[int] = None) -> None:
        with self._locked() as fh:
            fd = fh.fileno()
            entries = self._read(fd, fh.read())
            if any(e["sender"] == sender and e["id"] == message_id for e in entries):
                raise Refused("replayed", "this message was already accepted once")
            cutoff = _cutoff(now, self._keep_ms)
            live = [e for e in entries if e["expires_at"] is None or e["expires_at"] > cutoff]
            new = {"sender": sender, "id": message_id, "expires_at": expires_at}
            if len(live) == len(entries):
                self._append(fd, _line(new))
            else:
                self._compact([*live, new])

    @staticmethod
    def _read(fd: int, raw: bytes) -> List[Dict[str, Any]]:
        """The entries in the file, or Refused('unavailable') when the file cannot be trusted to be complete.

        A final line with no newline is a write a killed process never finished. `spend` returns only after the line
        and its newline are durable, so that fragment was never acknowledged to anyone and is cut off. Any other line
        that does not read as an entry means the file was damaged some other way, and a ledger that cannot be read
        cannot say a message is new: it refuses and spends nothing, rather than guess."""
        torn = bool(raw) and not raw.endswith(b"\n")
        lines = raw.split(b"\n")
        tail = lines.pop() if torn else None
        entries: List[Dict[str, Any]] = []
        for number, ln in enumerate(lines, 1):
            if not ln.strip():
                continue
            try:
                e = json.loads(ln.decode("utf-8"))
                if (not isinstance(e, dict) or set(e) != {"sender", "id", "expires_at"}
                        or not isinstance(e["sender"], str) or not isinstance(e["id"], str)
                        or not (e["expires_at"] is None or (isinstance(e["expires_at"], int)
                                                            and not isinstance(e["expires_at"], bool)))):
                    raise ValueError("not a ledger entry")
            except (ValueError, UnicodeDecodeError):
                raise Refused("unavailable", f"the ledger file is damaged at line {number}; no message can be "
                                             "judged new until it is repaired") from None
            entries.append(e)
        if tail is not None:
            os.ftruncate(fd, len(raw) - len(tail))
            os.fsync(fd)
        return entries

    @contextmanager
    def _locked(self) -> Iterator[BinaryIO]:
        """The ledger file, open and exclusively locked. Compaction replaces the file, so a lock taken on a file that
        was replaced while this process waited is on the wrong file: it is dropped and the current file locked."""
        import fcntl

        while True:
            fh = open(self._path, "r+b", buffering=0)
            try:
                fcntl.flock(fh, fcntl.LOCK_EX)
                try:
                    current = os.stat(self._path).st_ino == os.fstat(fh.fileno()).st_ino
                except FileNotFoundError:  # pragma: no cover - replaced between the open and the stat
                    current = False
                if current:
                    yield fh
                    return
            finally:
                fh.close()

    @staticmethod
    def _append(fd: int, data: bytes) -> None:
        """Add one line at the end and make it durable. The earlier entries are never rewritten, so a failure cannot
        lose them; a failure partway through is undone so no torn line is left for the next reader."""
        end = os.lseek(fd, 0, os.SEEK_END)
        try:
            _write_all(fd, data)
            os.fsync(fd)
        except BaseException:
            try:
                os.ftruncate(fd, end)
            except OSError:  # pragma: no cover - best effort; the original failure is the one that matters
                pass
            raise

    def _compact(self, entries: List[Dict[str, Any]]) -> None:
        """Replace the file with `entries`, all or nothing: write a temp file beside it, flush it to disk, rename it
        over the ledger, then flush the directory so the rename itself survives a crash."""
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=self._path.name + ".", suffix=".tmp")
        try:
            try:
                _write_all(fd, b"".join(_line(e) for e in entries))
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(tmp, self._path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        dir_fd = os.open(self._path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


def _cutoff(now: Optional[int], keep_ms: int) -> int:
    """Entries that expired before this are forgotten. It is taken from the EARLIER of the verifier's clock and this
    host's clock, so a verifier whose clock runs behind never finds a message it still accepts already forgotten."""
    wall = now_ms()
    return (wall if now is None else min(now, wall)) - keep_ms


def _line(entry: Dict[str, Any]) -> bytes:
    return (json.dumps(entry, sort_keys=True) + "\n").encode("utf-8")


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]
