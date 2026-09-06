"""Exercise the checkpoint ceiling against real commits in disposable repos."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("file_count", "added", "deleted", "accepted"),
    [
        (1, 150, 0, True),
        (1, 151, 0, False),
        (1, 1, 0, True),
        (6, 1, 0, False),
        (1, 75, 75, True),
        (1, 75, 76, False),
    ],
)
def test_commit_hook_ceiling(tmp_path, file_count, added, deleted, accepted):
    git = shutil.which("git")
    assert git, "Git is required to validate commit enforcement"
    hooks = Path(__file__).resolve().parents[1] / ".githooks"
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    command = [
        git,
        "-C",
        str(tmp_path),
        "-c",
        f"core.hooksPath={hooks.as_posix()}",
        "-c",
        "user.name=Checkpoint test",
        "-c",
        "user.email=test@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.autocrlf=false",
    ]
    subprocess.run(
        [*command, "init", "--quiet"], env=env, check=True, capture_output=True
    )
    first = tmp_path / "checkpoint 0.txt"
    if deleted:
        first.write_text(
            "".join(f"old {i}\n" for i in range(deleted)), encoding="utf-8"
        )
        subprocess.run([*command, "add", "--", first.name], env=env, check=True)
        subprocess.run(
            [*command, "commit", "--quiet", "-m", "Seed deletion fixture"],
            env=env,
            check=True,
            capture_output=True,
        )
    paths = []
    for index in range(file_count):
        path = tmp_path / f"checkpoint {index}.txt"
        path.write_text("".join(f"new {i}\n" for i in range(added)), encoding="utf-8")
        paths.append(path.name)
    subprocess.run([*command, "add", "--", *paths], env=env, check=True)
    result = subprocess.run(
        [*command, "commit", "--quiet", "-m", "Test checkpoint"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) is accepted, result.stderr
    if not accepted:
        assert "Commit rejected" in result.stderr
        assert "150 added-plus-deleted lines" in result.stderr
