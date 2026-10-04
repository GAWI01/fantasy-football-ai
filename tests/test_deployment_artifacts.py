import fnmatch
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_backend_container_runs_as_non_root_with_healthcheck():
    content = (ROOT / "Dockerfile.backend").read_text(encoding="utf-8")

    assert "USER app" in content
    assert "HEALTHCHECK" in content
    assert "uvicorn" in content
    assert "backend.main:app" in content


def test_frontend_container_builds_and_runs_the_next_application():
    content = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")

    assert "pnpm build" in content
    assert 'CMD ["node", "server.js"]' in content
    assert "USER nextjs" in content
    assert "NEXT_PUBLIC_API_URL" in content
    assert "/app/.next/standalone" in content
    dockerignore = (ROOT / "frontend" / ".dockerignore").read_text(encoding="utf-8")
    assert "node_modules" in dockerignore
    assert ".next" in dockerignore
    assert ".env.*" in dockerignore


def test_frontend_production_sources_do_not_fall_back_to_localhost():
    sources = [
        ROOT / "frontend" / "lib" / "api.ts",
        ROOT / "frontend" / "app" / "[module]" / "page.tsx",
        ROOT / "frontend" / "app" / "providers" / "TeamProvider.tsx",
    ]

    for source in sources:
        content = source.read_text(encoding="utf-8")
        assert "http://127.0.0.1:8000" not in content
        assert "http://localhost:8000" not in content


def test_local_production_stack_and_render_blueprint_are_declared():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    deployment = (ROOT / "docs" / "DEPLOYMENT.md").read_text(encoding="utf-8")

    assert "backend:" in compose and "frontend:" in compose
    assert "Dockerfile.backend" in compose
    assert "healthcheck:" in compose
    assert "fpl-ai-api" in blueprint and "fpl-ai-web" in blueprint
    assert "Hosted smoke test" in deployment


def test_backend_allowlist_can_serve_without_developer_files(tmp_path):
    """Exercise only explicitly allowed serving files; not a Docker build substitute."""
    rules = (ROOT / ".dockerignore").read_text().splitlines()
    assert "**" in rules
    assert "**/.env" in rules and "**/.env.*" in rules
    for rule in rules:
        if not rule.startswith("!") or rule.endswith("/"):
            continue
        for source in ROOT.glob(rule[1:]):
            if source.is_file():
                destination = tmp_path / source.relative_to(ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
    assert not (tmp_path / "models").exists()
    assert not (tmp_path / "fpl.db").exists()
    assert not (tmp_path / "frontend").exists()
    result = subprocess.run(
        [sys.executable, "-c", (
            "from backend.runtime_artifacts import validate_runtime_artifacts; "
            "assert validate_runtime_artifacts()['loaded']; "
            "from backend.main import health; assert health() == {'status': 'ok'}"
        )],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_backend_allowlist_does_not_reinclude_whole_directories():
    """A directory exception admits descendants under Docker parent matching."""
    rules = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    exceptions = [rule[1:].rstrip("/") for rule in rules if rule.startswith("!")]
    for exception in exceptions:
        assert not (ROOT / exception).is_dir(), (
            f"Directory exception !{exception} also includes unwanted descendants"
        )


def test_backend_allowlist_includes_only_the_serving_data_bundle():
    from backend.runtime_artifacts import validate_runtime_artifacts
    rules = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    prefix = "!historical_data/"
    data_exceptions = {rule[len(prefix):] for rule in rules if rule.startswith(prefix)}
    served = {f"current_data/{name}" for name in validate_runtime_artifacts()["files"]}
    # Every served file is allowed, and every data exception serves a runtime file:
    # fixed current-data files, or the versioned forecast/sidecar patterns.
    assert all(any(fnmatch.fnmatchcase(name, rule) for rule in data_exceptions) for name in served)
    patterns = {rule for rule in data_exceptions if "*" in rule}
    assert patterns == {"current_data/gw*_predictions_v*.csv", "current_data/gw*_predictions_v*.csv.manifest.json"}
    assert data_exceptions - patterns <= served


def test_staging_documentation_is_valid_utf8():
    for name in ("PROJECT_HANDOFF.md", "docs/PRD_IMPLEMENTATION_STATUS.md"):
        (ROOT / name).read_text(encoding="utf-8")


def test_runtime_bundle_is_not_git_ignored():
    from backend.runtime_artifacts import validate_runtime_artifacts
    for name in validate_runtime_artifacts()["files"]:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", f"historical_data/current_data/{name}"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 1, result.stdout + result.stderr
