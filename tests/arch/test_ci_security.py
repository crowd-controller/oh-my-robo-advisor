"""M0 CI must remain credential-free and least-privileged."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def test_ci_has_read_only_repository_permission_and_no_secrets() -> None:
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in workflow
    assert "secrets." not in workflow
    assert "pull_request_target" not in workflow
    assert ".env" not in workflow


def test_ci_actions_are_pinned_to_full_commit_shas() -> None:
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    action_lines = [line.strip() for line in workflow.splitlines() if "uses:" in line]

    assert action_lines
    for line in action_lines:
        reference = line.split("@", maxsplit=1)[1].split(maxsplit=1)[0]
        assert len(reference) == 40
        assert all(character in "0123456789abcdef" for character in reference)


def test_ci_runs_bounded_credential_free_container_smoke() -> None:
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "container-smoke:" in workflow
    assert "name: M0 container smoke" in workflow
    assert "timeout-minutes: 15" in workflow
    assert "run: scripts/container_smoke.sh" in workflow
