"""signet_live: a real signet, running as its own process, for the spine runner's `signet:` scenarios.

WHAT IT IS

SIGNET (github.com/wking53214/SIGNET) is the keyholder: one program that holds the private keys, signs only bytes that
start with each purpose's label, and writes down every signature before it releases it. A caller gets a `sign(data)`
callable from `signet.client`; a checker gets a `verify(data, signature)` callable from `signet.verify` and the signed
registry. Those are exactly the shapes zeta, beta and delta already take, so none of them changes.

This module starts one such signet in a private temporary directory, through signet's own command line: the keys are
written by `signet keygen`, the registry by `signet registry`, and `signet serve` runs in a child process. This process
never loads signet's key store, server, log or config modules (the `signet:` scenarios hold that), so the runner holds
no private key for these runs.

WHAT IT IS NOT

A deployment. signet and the runner run as one account here, so signet prints its same-account WARNING: this proves
the wiring (the right bytes, the right keys, the registry, fail closed, the log) and not the separation between
accounts, which only a second account or container gives. See SIGNET's README, "On a one-user machine".
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

ZETA = "zeta-lock-result"
DELTA = "delta-receipt"
ZETA_LABEL = "zeta-lock-result-signature/1\n"
DELTA_LABEL = "delta-ledger-receipt-signature/1\n"

#: signet's modules that hold or touch a private key, or run the signer. A caller loads none of them.
KEY_SIDE_MODULES = ("signet.keys", "signet.server", "signet.log", "signet.config")


def cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "signet", *args], capture_output=True, text=True, timeout=60)


def _ok(done: subprocess.CompletedProcess, what: str) -> str:
    if done.returncode != 0:
        raise RuntimeError(f"signet {what} failed (exit {done.returncode}): {done.stderr.strip()}")
    return done.stdout


class LiveSignet:
    """One signet with a root key, a log key, and one key each for zeta's lock results and delta's receipts."""

    def __init__(self, ids: Optional[Dict[str, str]] = None) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="cns-signet-"))  # 0700, ours: signet accepts it as its socket directory
        self.keys_dir = self.root / "keys"
        self.keys_dir.mkdir(mode=0o700)
        self.socket = self.root / "signet.sock"
        self.log = self.root / "signatures.log"
        self.ids = {"root": "root-1", "log": "log-1", "zeta": "zeta-1", "delta": "delta-1", **(ids or {})}
        self.public = {name: _ok(cli("keygen", "--keys-dir", str(self.keys_dir), key_id), "keygen").strip()
                       for name, key_id in self.ids.items()}
        self.config = self.root / "config.json"
        self.write_config()
        self.proc: Optional[subprocess.Popen] = None
        self.stderr: List[str] = []

    def write_config(self) -> None:
        uid = os.getuid()
        self.config.write_text(json.dumps({
            "schema": "signet-config/1", "socket": str(self.socket), "keys_dir": str(self.keys_dir),
            "log": str(self.log), "registry_key_id": self.ids["root"], "log_key_id": self.ids["log"],
            "request_timeout_ms": 5000,
            "purposes": {ZETA: {"key_id": self.ids["zeta"], "label": ZETA_LABEL, "allowed_uids": [uid]},
                         DELTA: {"key_id": self.ids["delta"], "label": DELTA_LABEL, "allowed_uids": [uid]}}}))

    def start(self) -> "LiveSignet":
        """Start `signet serve` and wait for its "serving" line (a connection to check would itself be logged)."""
        self.proc = subprocess.Popen([sys.executable, "-m", "signet", "serve", "--config", str(self.config)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        line = self.proc.stderr.readline()
        if "signet: serving" not in line:
            self.proc.wait(timeout=10)
            raise RuntimeError(f"signet did not start: {line}{self.proc.stderr.read()}")
        self.stderr.append(line)
        # Keep reading, so signet's warnings and refusal lines never fill the pipe and stall it.
        threading.Thread(target=self._drain, args=(self.proc,), daemon=True).start()
        return self

    def _drain(self, proc: subprocess.Popen) -> None:
        for line in proc.stderr:
            self.stderr.append(line)

    def stop(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)

    def close(self) -> None:
        self.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> "LiveSignet":
        return self.start()

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def signer(self, purpose: str) -> Callable[[bytes], bytes]:
        """A caller's `sign`, which checks that the program on the socket runs as signet's account before sending."""
        from signet.client import signer
        return signer(self.socket, purpose, expected_uid=os.getuid())

    def registry(self, name: str = "registry-1.json", *extra: str) -> bytes:
        out = self.root / name
        _ok(cli("registry", "--config", str(self.config), "--out", str(out), *extra), "registry")
        return out.read_bytes()

    def verifier(self, purpose: str, registry: bytes, *, min_version: int = 1) -> Callable[[bytes, bytes], bool]:
        """A checker's `verify`, from the registry checked against the root key pinned here (never one in the file)."""
        from signet.registry import load_registry
        from signet.verify import verifier
        return verifier(load_registry(registry, self.public["root"], min_version=min_version), purpose)

    def log_lines(self) -> List[dict]:
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def log_verifies(self) -> bool:
        return cli("verify-log", "--log", str(self.log)).returncode == 0


def loaded_key_side_modules() -> List[str]:
    """signet's key-side modules this process has loaded. Empty for a caller that holds no key."""
    return [name for name in KEY_SIDE_MODULES if name in sys.modules]


def signet_pyproject() -> Path:
    """The pyproject of the signet this process imports (its checkout's root)."""
    import signet
    return Path(signet.__file__).resolve().parents[1] / "pyproject.toml"
