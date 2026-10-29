"""Check fixture hashes after real Git checkouts with both newline settings."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("git") is None, reason="Git is required for checkout regression checks")
@pytest.mark.parametrize("autocrlf", ["false", "true"])
def test_attack_hashes_survive_git_checkout(tmp_path, autocrlf):
    seed = tmp_path / "seed"
    seed.mkdir()
    shutil.copyfile(ROOT / ".gitattributes", seed / ".gitattributes")
    for folder in ("attacks/member5", "configs/member5"):
        destination = seed / folder
        destination.mkdir(parents=True)
        for source in (ROOT / folder).glob("*.json"):
            shutil.copyfile(source, destination / source.name)

    def git(*args, cwd=seed):
        return subprocess.run(["git", *args], cwd=cwd, check=True,
                              capture_output=True, text=True)

    git("init", "--quiet")
    git("-c", "core.autocrlf=false", "add", ".")
    git("-c", "user.name=Checkout regression test",
        "-c", "user.email=checkout-regression@example.test",
        "commit", "--quiet", "-m", "Record fixture bytes")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    # checkout-index uses Git's checkout conversion without a shell or network.
    git("-c", f"core.autocrlf={autocrlf}", "checkout-index", "--all",
        f"--prefix={checkout.as_posix()}/")

    manifest_path = Path("configs/member5/attack-manifest.json")
    assert (checkout / manifest_path).read_bytes() == (ROOT / manifest_path).read_bytes()
    for folder in ("attacks/member5", "configs/member5"):
        for path in (checkout / folder).glob("*.json"):
            assert b"\r" not in path.read_bytes(), path
    cases = json.loads((checkout / manifest_path).read_text(encoding="utf-8"))["cases"]
    assert len(cases) == 20
    for case in cases:
        data = (checkout / case["attack_file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == case["attack_file_sha256"]
