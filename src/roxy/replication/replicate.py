"""Replicate — export portable Roxy runtime bundles.

v0.9: generates self-contained bundles for deployment/replication.
Never includes API keys, tokens, or raw secrets.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roxy import __version__
from roxy.config.paths import roxy_home


def _git_commit() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip()[:8] if r.returncode == 0 else ""
    except Exception:
        return ""


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Replicator:
    """Exports a portable, verifiable Roxy runtime bundle."""

    def __init__(self, repo_root: Path | None = None):
        self._repo = repo_root or Path.cwd()

    def export_bundle(self, output_path: Path, include_kb: bool = True) -> dict:
        """Create a replicable bundle at output_path. Returns manifest dict."""
        now = datetime.now(timezone.utc).isoformat()

        manifest = {
            "roxy_version": __version__,
            "git_commit": _git_commit(),
            "exported_at": now,
            "contents": {},
        }

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Source code (git archive)
            src_data = self._archive_source()
            zf.writestr("roxy-src.zip", src_data)
            manifest["contents"]["source"] = {
                "file": "roxy-src.zip",
                "sha256": _sha256_hex(src_data),
            }

            # 2. OKF knowledge base
            if include_kb:
                kb_data = self._export_kb()
                if kb_data:
                    zf.writestr("kb.jsonl", kb_data)
                    manifest["contents"]["knowledge"] = {
                        "file": "kb.jsonl",
                        "sha256": _sha256_hex(kb_data),
                    }

            # 3. Eval seeds
            seeds_data = self._export_seeds()
            if seeds_data:
                zf.writestr("eval_seeds.jsonl", seeds_data)
                manifest["contents"]["eval_seeds"] = {
                    "file": "eval_seeds.jsonl",
                    "sha256": _sha256_hex(seeds_data),
                }

            # 4. Config template (sanitized)
            config_data = self._export_config_template()
            zf.writestr("config.template.yaml", config_data)
            manifest["contents"]["config_template"] = {
                "file": "config.template.yaml",
                "sha256": _sha256_hex(config_data),
            }

            # 5. Skills
            skills_data = self._export_skills()
            if skills_data:
                zf.writestr("skills.zip", skills_data)
                manifest["contents"]["skills"] = {
                    "file": "skills.zip",
                    "sha256": _sha256_hex(skills_data),
                }

            # 6. Manifest itself
            manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
            zf.writestr("manifest.json", manifest_bytes)

        return manifest

    def validate_bundle(self, bundle_path: Path) -> dict:
        """Validate a replication bundle. Returns {valid, errors, manifest}."""
        errors: list[str] = []
        manifest = {}

        if not bundle_path.exists():
            return {"valid": False, "errors": ["Bundle file not found"], "manifest": {}}

        try:
            with zipfile.ZipFile(bundle_path, "r") as zf:
                names = zf.namelist()

                # Check manifest
                if "manifest.json" not in names:
                    errors.append("Missing manifest.json")
                    return {"valid": False, "errors": errors, "manifest": {}}

                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))

                # Validate each content entry
                for key, info in manifest.get("contents", {}).items():
                    filename = info.get("file", "")
                    expected_hash = info.get("sha256", "")
                    if filename not in names:
                        errors.append(f"Missing file: {filename}")
                        continue
                    actual = _sha256_hex(zf.read(filename))
                    if actual != expected_hash:
                        errors.append(f"Hash mismatch for {filename}: expected {expected_hash[:8]}, got {actual[:8]}")

                # Validate OKF if present
                if "kb.jsonl" in names:
                    okf_errors = self._validate_okf_inline(zf.read("kb.jsonl").decode("utf-8"))
                    if okf_errors:
                        errors.extend(okf_errors[:5])

        except zipfile.BadZipFile:
            errors.append("Not a valid zip file")
        except Exception as exc:
            errors.append(str(exc))

        return {"valid": len(errors) == 0, "errors": errors, "manifest": manifest}

    def generate_deploy_plan(self, bundle_path: Path, target_dir: str) -> str:
        """Generate a human-readable deployment plan (dry-run only)."""
        validation = self.validate_bundle(bundle_path)
        manifest = validation.get("manifest", {})

        lines = [
            "# Roxy Deployment Plan",
            "",
            f"**Bundle**: {bundle_path}",
            f"**Version**: {manifest.get('roxy_version', 'unknown')}",
            f"**Commit**: {manifest.get('git_commit', 'unknown')}",
            f"**Exported**: {manifest.get('exported_at', 'unknown')[:19]}",
            f"**Valid**: {'[green]✓[/green]' if validation['valid'] else '[red]✗[/red]'}",
            "",
            "## Deployment Steps",
            "",
            "### 1. Extract bundle",
            f"```bash",
            f"mkdir -p {target_dir}",
            f"unzip {bundle_path} -d {target_dir}",
            f"```",
            "",
            "### 2. Install Roxy",
            "```bash",
            f"cd {target_dir}",
            f"unzip roxy-src.zip -d roxy",
            f"cd roxy && pip install -e '.[tui]'",
            "```",
            "",
            "### 3. Configure",
            "```bash",
            "# Copy and edit the config template",
            f"cp config.template.yaml ~/.roxy/config.yaml",
            "# Set your API keys:",
            "#   roxy config set models.providers.<name>.api_key \"<key>\"",
            "# Or use env vars: OPENAI_API_KEY, DEEPSEEK_API_KEY, etc.",
            "```",
            "",
            "### 4. Import knowledge",
            "```bash",
            "roxy knowledge import kb.jsonl",
            "```",
            "",
            "### 5. Restore eval seeds",
            "```bash",
            "cp eval_seeds.jsonl .",
            "roxy eval validate eval_seeds.jsonl",
            "```",
            "",
            "### 6. Verify",
            "```bash",
            "roxy doctor",
            "roxy dev check",
            "```",
            "",
            "## Environment Requirements",
            "- Python 3.11+",
            "- git",
            "- pip",
            "",
            "## Security Notes",
            "- **No API keys are included in this bundle**",
            "- Config template has empty key placeholders",
            "- Set keys via environment variables or `roxy config set`",
            "- Do not commit config.yaml with real keys to version control",
            "",
            f"*Generated by Roxy Replicator — {datetime.now(timezone.utc).isoformat()[:19]}*",
        ]

        return "\n".join(lines)

    # ── internal exporters ─────────────────────────────────────

    def _archive_source(self) -> bytes:
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp.close()
        try:
            subprocess.run(
                ["git", "archive", "--format=zip", "--output", tmp.name, "HEAD"],
                cwd=str(self._repo), capture_output=True, check=True,
            )
            return Path(tmp.name).read_bytes()
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

    def _export_kb(self) -> bytes | None:
        try:
            from roxy.knowledge.store import KnowledgeStore
            ks = KnowledgeStore(); ks.init_db()
            if ks.get_stats().get("entry_count", 0) == 0:
                return None
            tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
            tmp.close()
            try:
                ks.export_jsonl(Path(tmp.name))
                return Path(tmp.name).read_bytes()
            finally:
                try: os.unlink(tmp.name)
                except Exception: pass
        except Exception:
            return None

    def _export_seeds(self) -> bytes | None:
        seeds_path = Path("eval_seeds.jsonl")
        if not seeds_path.exists():
            return None
        return seeds_path.read_bytes()

    def _export_config_template(self) -> bytes:
        """Generate a sanitized config template — no real keys."""
        template = {
            "models": {
                "default": "deepseek/deepseek-chat",
                "providers": {
                    "deepseek": {"api_key": "", "base_url": "https://api.deepseek.com"},
                    "openai": {"api_key": "", "base_url": ""},
                    "anthropic": {"api_key": "", "base_url": ""},
                },
            },
            "user": {"name": "", "identity": "", "research_domain": "", "topics": []},
            "workspace": {"path": ""},
            "research": {"feeds": [], "topics_data": [], "wechat": {"db_path": ""}},
        }
        import yaml
        return yaml.safe_dump(template, allow_unicode=True, default_flow_style=False).encode("utf-8")

    def _export_skills(self) -> bytes | None:
        skills_dir = self._repo / "skills"
        if not skills_dir.exists() or not list(skills_dir.glob("**/*")):
            return None
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp.close()
        try:
            with zipfile.ZipFile(tmp.name, "w") as zf:
                for sk in skills_dir.glob("**/*"):
                    if sk.is_file():
                        zf.write(sk, sk.relative_to(skills_dir))
            return Path(tmp.name).read_bytes()
        finally:
            try: os.unlink(tmp.name)
            except Exception: pass

    def _validate_okf_inline(self, text: str) -> list[str]:
        errors: list[str] = []
        for i, line in enumerate(text.split("\n"), 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if "okf_version" not in entry:
                    errors.append(f"Line {i}: missing okf_version")
                if "id" not in entry:
                    errors.append(f"Line {i}: missing id")
            except json.JSONDecodeError:
                errors.append(f"Line {i}: invalid JSON")
        return errors
