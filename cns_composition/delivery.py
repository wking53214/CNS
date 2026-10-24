"""delivery: a report that was not delivered is not a success, and a file is written whole or not at all.

WHY THIS EXISTS

Every command in this package prints a report and returns an exit code, and the exit code is what a workflow
reads. Measured on the base commit of 2.0.0: with file descriptor 1 closed, all seven commands exited 0 and
printed nothing, because Python sets `sys.stdout` to None and `print` becomes a no-op; with the reader of the
pipe gone before the summary was written, they ended in a `BrokenPipeError` at interpreter shutdown, exit 120,
with a traceback. The same class was found in four sibling repositories. A report nobody received that reads as
success is worse than a failure, because nobody looks.

Two of the commands also write a file (`repin` the manifest, `digest_vectors --write` the vectors) with
`write_text` in place: that truncates first, so an interrupted write leaves half a file; it follows a symbolic
link; and it blocks forever on a named pipe. Warden 0.13.8 closed the same gap for its receipt.

WHAT IT DOES

`run(main, argv, program)` is what a command returns: it runs `main(argv)` with stdout guarded and then calls
`deliver`. `deliver(code, program)` is the last thing a command does. It flushes stdout; if stdout is closed or the flush
fails (a broken pipe, a full device, any OSError), it says so on stderr and returns 2 in place of 0. A non-zero
code is kept, since the failure it reports went to stderr and was delivered. After a failed flush the stream's
descriptor is parked on a pipe of our own and stdout is detached from the interpreter, so the shutdown flush
cannot fail a second time; no device node is opened or written to achieve that.

`write_file(path, text)` writes to a temporary name in the same folder and renames it into place. The
destination must be absent or a regular file, checked before the write and again just before the rename; a
symbolic link, a named pipe, a device or a folder is refused by name. An existing regular file keeps its
permission bits. On any failure the temporary file is removed and the old file is untouched.

`read_text(path)` reads a file a person named on the command line (a manifest, a table, a ledger) and refuses
one that is not a regular file after links are followed: `read_text` on a named pipe with no writer blocks
forever, and a workflow step that blocks forever reads as "still running", never as a failure.
A file that is not UTF-8 text is refused the same way, as a DeliveryError (an OSError), so a command ends exit 2
with one line and not a traceback with exit 1, the code a stale pin gets.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import Callable, List, Optional

__all__ = ["CONTRACTS", "DeliveryError", "UNDELIVERED", "deliver", "read_text", "run", "write_file"]

#: The exit code for a report that could not be delivered. 2 is what every command here already means by
#: "the question could not be answered"; it is never 0.
UNDELIVERED = 2


class DeliveryError(OSError):
    """A file could not be written whole or read safely, and why. An OSError, so a caller that already turns
    OSError into its own error keeps doing so; the message is the reason."""


def deliver(code: int, program: str) -> int:
    """Flush the report. `code` when stdout took it; otherwise a note on stderr and 2 in place of 0."""
    stream = sys.stdout
    if stream is None or getattr(stream, "closed", False):
        _say(program, "stdout is closed, so the report was not delivered")
        return code or UNDELIVERED
    try:
        stream.flush()
    except OSError as err:
        return _lost(stream, err, code, program)
    return code


def run(main: Callable[[Optional[List[str]]], int], argv: Optional[List[str]], program: str) -> int:
    """Run a command's `main(argv)` with its report protected, then `deliver` it. This is what a command returns.

    `deliver` alone is not enough: in `deliver(main(argv), name)` the call to `main` runs, and prints, before
    `deliver` exists. With buffered stdout a print only fills a buffer and the failure waits for the flush that
    `deliver` makes; with unbuffered stdout (PYTHONUNBUFFERED=1, `python -u`) every print is a write, and a write to
    a pipe whose reader has gone, or to a full device, raised out of `main` as a traceback and exit 1.

    While `main` runs, stdout is a guard that takes the first write error as a fact and goes quiet: `main` carries
    on, so work that comes after a print (a file written, a second file rendered) is still done, and its own exit
    code is kept. A report that did not arrive is then handled exactly as `deliver` handles a failed flush."""
    real = sys.stdout
    if real is None:  # a closed descriptor 1: print is already a no-op, and `deliver` names it
        return deliver(main(argv), program)
    guard = _Guard(real)
    sys.stdout = guard
    try:
        code = main(argv)
    finally:
        sys.stdout = real
    if guard.error is None:
        return deliver(code, program)
    return _lost(real, guard.error, code, program)


class _Guard:
    """stdout while a command runs: the real stream, except that the first OSError (a broken pipe, ENOSPC, EIO) or
    ValueError (a stream closed under us) from a write or flush is kept in `error` and every write after it is
    taken and dropped. Everything else about the stream (fileno, encoding, isatty) is the real stream's."""

    def __init__(self, stream: object) -> None:
        self._stream = stream
        self.error: Optional[BaseException] = None

    def write(self, text: str) -> int:
        if self.error is None:
            try:
                return int(self._stream.write(text))  # type: ignore[attr-defined]
            except (OSError, ValueError) as err:
                self.error = err
        return len(text)

    def flush(self) -> None:
        if self.error is None:
            try:
                self._stream.flush()  # type: ignore[attr-defined]
            except (OSError, ValueError) as err:
                self.error = err

    def __getattr__(self, name: str) -> object:
        return getattr(self._stream, name)


def _lost(stream: object, err: BaseException, code: int, program: str) -> int:
    """The report did not arrive. Say so on stderr and return `code`, or 2 in place of 0."""
    if isinstance(err, ValueError) or getattr(stream, "closed", False):
        _say(program, "stdout is closed, so the report was not delivered")
        return code or UNDELIVERED
    # BrokenPipeError (the reader is gone), ENOSPC (a full device), EIO: the report did not arrive. Park the
    # descriptor and detach stdout, so the interpreter's own flush at exit cannot fail a second time.
    _park(stream)
    sys.stdout = sys.__stdout__ = None  # type: ignore[assignment]
    _say(program, f"the report could not be delivered ({type(err).__name__})")
    return code or UNDELIVERED


_parked: list = []


def _park(stream: object) -> None:
    """Point the stream's file descriptor at a pipe of our own whose reader stays open for the life of the
    process. The bytes the failed flush left behind then go somewhere a write succeeds, so the flush the
    interpreter runs at exit succeeds too: without this, Python 3.12 and older exit 120 with a traceback, and
    3.13 reports the failed finalization even when sys.stdout is None. No device node is opened or written."""
    try:
        fd = stream.fileno()  # type: ignore[attr-defined]
    except (OSError, ValueError, AttributeError):
        return
    try:
        reader, writer = os.pipe()
        os.dup2(writer, fd)
        os.close(writer)
    except OSError:
        return
    _parked.append(reader)


def _say(program: str, what: str) -> None:
    stream = sys.stderr
    if stream is None or getattr(stream, "closed", False):
        return
    try:
        stream.write(f"{program}: {what}\n")
        stream.flush()
    except OSError:
        pass


def _kind(path: Path) -> str:
    """What is at `path` without following a link: "absent", "file", "symlink", "fifo", "device", "folder" or
    "other"."""
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return "absent"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
        return "device"
    if stat.S_ISDIR(mode):
        return "folder"
    return "other"


def _refuse(path: Path, kind: str) -> DeliveryError:
    named = {"symlink": "a symbolic link", "fifo": "a named pipe", "device": "a device", "folder": "a folder",
             "other": "not a regular file"}[kind]
    return DeliveryError(f"{str(path)!r} is {named}; a file is only ever written over a regular file or into an "
                         "empty place, so nothing was written")


#: Where the contract files live: beside the package in a checkout, and nowhere in an installed wheel. A pin is
#: state and the package holds none (the README's rule), so the maintenance tools run from a checkout.
CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
_TOOLS = ("repin", "seat_pins", "cns_versions", "install_stack", "circuit_canary", "circuit_refusals",
          "link_ledger", "consumers", "digest_vectors")


def read_text(path: Path) -> str:
    """The text of a regular file. A named pipe, a device or a folder is refused by name instead of read. A
    contract file that is missing because `contracts/` is not beside the package is named as what it is: an
    installed wheel, where the maintenance tools do not run."""
    path = Path(path)
    if path.parent == CONTRACTS and not CONTRACTS.is_dir():
        raise DeliveryError(f"{str(path)!r} is not there because contracts/ is not beside this package: this is an "
                            f"installed wheel, not a checkout, and the maintenance tools ({', '.join(_TOOLS)}) run "
                            "from a CNS checkout")
    mode = os.stat(path).st_mode  # a missing file raises FileNotFoundError, as read_text itself would
    if not stat.S_ISREG(mode):
        kind = "fifo" if stat.S_ISFIFO(mode) else "device" if stat.S_ISCHR(mode) or stat.S_ISBLK(mode) \
            else "folder" if stat.S_ISDIR(mode) else "other"
        named = {"fifo": "a named pipe", "device": "a device", "folder": "a folder", "other": "not a regular file"}
        raise DeliveryError(f"{str(path)!r} is {named[kind]}, not a regular file, so it was not read")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as err:
        # A binary or non-UTF-8 file named on the command line. A DeliveryError is an OSError, so every command
        # that already turns an unreadable file into exit 2 and one line does the same here, instead of a traceback.
        raise DeliveryError(f"{str(path)!r} cannot be read: UnicodeDecodeError (it is not UTF-8 text)") from err


def write_file(path: Path, text: str) -> None:
    """Write `text` to `path` whole: a temporary file beside it, renamed into place. Raises DeliveryError."""
    path = Path(path)
    kind = _kind(path)
    if kind not in ("absent", "file"):
        raise _refuse(path, kind)
    mode = os.lstat(path).st_mode & 0o7777 if kind == "file" else None
    tmp = path.with_name(f".{path.name}.{os.getpid()}.part")
    try:
        with open(tmp, "x", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        kind = _kind(path)
        if kind not in ("absent", "file"):
            raise _refuse(path, kind)
        os.replace(tmp, path)
    except DeliveryError:
        raise
    except OSError as err:
        raise DeliveryError(f"{str(path)!r} could not be written: {type(err).__name__}") from err
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
