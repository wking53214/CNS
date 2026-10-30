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
import threading
from pathlib import Path
from typing import Dict, Optional, Protocol, Tuple

from .envelope import Refused, now_ms

__all__ = ["Ledger", "MemoryLedger", "FileLedger"]


class Ledger(Protocol):
    def spend(self, sender: str, message_id: str, expires_at: Optional[int]) -> None: ...


class MemoryLedger:
    def __init__(self) -> None:
        self._seen: Dict[Tuple[str, str], Optional[int]] = {}
        self._lock = threading.Lock()

    def spend(self, sender: str, message_id: str, expires_at: Optional[int]) -> None:
        with self._lock:
            if (sender, message_id) in self._seen:
                raise Refused("replayed", "this message was already accepted once")
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

    def spend(self, sender: str, message_id: str, expires_at: Optional[int]) -> None:
        import fcntl

        with open(self._path, "r+", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                lines = [ln for ln in fh.read().splitlines() if ln.strip()]
                entries = [json.loads(ln) for ln in lines]
                if any(e["sender"] == sender and e["id"] == message_id for e in entries):
                    raise Refused("replayed", "this message was already accepted once")
                cutoff = now_ms() - self._keep_ms
                live = [e for e in entries if e["expires_at"] is None or e["expires_at"] > cutoff]
                live.append({"sender": sender, "id": message_id, "expires_at": expires_at})
                fh.seek(0)
                fh.truncate()
                fh.write("".join(json.dumps(e, sort_keys=True) + "\n" for e in live))
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
