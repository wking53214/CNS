"""Step 13: a file that cannot be read, or a root that is not there, is exit 2 with one plain line, never a traceback.

Exit 1 means "the check ran and found a problem" (a stale pin, a disagreement). A manifest that is not UTF-8 text
crashed `repin --manifest` and `install_stack --install` with a traceback and exit 1, the same code as a stale pin,
so a workflow could not tell a broken input from a finding. `release --root <absent>` also exited 1. Each case below
calls the command in this process: an exception that escaped would fail the test.
"""

import json

from cns_composition import install_stack, release, repin

BINARY = b"\xff\xfe\x00not text\x80"


def one_line(capsys):
    err = capsys.readouterr().err
    assert "Traceback" not in err
    lines = [line for line in err.splitlines() if line.strip()]
    assert len(lines) == 1, lines
    return lines[0]


def test_repin_with_a_manifest_that_is_not_text_is_exit_two_and_one_line(tmp_path, capsys):
    bad = tmp_path / "m.json"
    bad.write_bytes(BINARY)
    assert repin.main(["--stack", str(tmp_path), "--manifest", str(bad)]) == 2
    line = one_line(capsys)
    assert line.startswith("repin: ") and "cannot be read" in line and "UnicodeDecodeError" in line
    assert bad.read_bytes() == BINARY  # nothing was written


def test_install_stack_with_an_install_file_that_is_not_text_is_exit_two_and_one_line(tmp_path, capsys):
    bad = tmp_path / "install.txt"
    bad.write_bytes(BINARY)
    assert install_stack.main(["--install", str(bad)]) == 2
    line = one_line(capsys)
    assert line.startswith("install_stack: ") and "cannot be read" in line
    assert bad.read_bytes() == BINARY


def test_install_stack_with_a_manifest_that_is_not_text_is_still_exit_two(tmp_path, capsys):
    bad = tmp_path / "m.json"
    bad.write_bytes(BINARY)
    assert install_stack.main(["--manifest", str(bad)]) == 2
    assert "cannot be read" in one_line(capsys)


def test_repin_that_moved_a_pin_but_cannot_read_the_install_file_beside_it_says_so(tmp_path, capsys):
    manifest = tmp_path / "warden-stack.json"
    manifest.write_text(json.dumps({"schema": "warden-stack/1", "contract": "1", "repos": {"a": "a" * 40}}),
                        encoding="utf-8")
    (tmp_path / "install-stack.txt").write_bytes(BINARY)
    assert repin.render_install(manifest, tmp_path) == 2
    err = capsys.readouterr().err
    assert "Traceback" not in err and "could not be rendered" in err


def test_release_with_a_root_that_is_not_there_is_exit_two_and_one_line(tmp_path, capsys):
    absent = tmp_path / "no-such-checkout"
    assert not absent.exists()
    assert release.main(["--root", str(absent)]) == 2
    line = one_line(capsys)
    assert line.startswith("release: ") and str(absent) in line
    assert release.main(["--root", str(absent), "--check"]) == 2
    capsys.readouterr()


def test_release_with_a_root_that_is_a_file_is_exit_two(tmp_path, capsys):
    not_a_folder = tmp_path / "file.txt"
    not_a_folder.write_text("x", encoding="utf-8")
    assert release.main(["--root", str(not_a_folder)]) == 2
    assert "release: " in one_line(capsys)


def test_release_with_a_pyproject_that_is_not_text_does_not_crash(tmp_path, capsys):
    root = tmp_path / "cns"
    root.mkdir()
    (root / "pyproject.toml").write_bytes(BINARY)
    code = release.main(["--root", str(root)])
    assert code != 0
    assert "Traceback" not in capsys.readouterr().err
