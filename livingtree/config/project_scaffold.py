from __future__ import annotations

"""
Project scaffolding for per-repo LivingTree configurations.

This module provides a lightweight, self-contained per-project scaffold
inspired by mattpocock/skills patterns. It generates a minimal yet useful set
of capabilities, prompt templates, and domain glossary terms tailored to a
project's characteristics.
"""

from logging import getLogger
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import time

from loguru import logger
from pydantic import BaseModel, Field


logger = logger  # type: ignore


ROOT_DIR = Path.cwd()  # base workspace, typically repository root
PROJECTS_ROOT = ROOT_DIR / ".livingtree" / "projects"


class ProjectProfile(BaseModel):
    name: str
    language: str
    framework: str = ""
    type: str
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    repo_url: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0


class ProjectSkills(BaseModel):
    project_name: str
    enabled_capabilities: List[str] = Field(default_factory=list)
    disabled_capabilities: List[str] = Field(default_factory=list)
    prompt_templates: List[str] = Field(default_factory=list)
    domain_terms: List[str] = Field(default_factory=list)
    buckets: List[str] = Field(default_factory=list)
    config_overrides: Dict[str, Any] = Field(default_factory=dict)
    custom_rules: List[str] = Field(default_factory=list)


class ProjectScaffold:
    def __init__(self, base_root: Optional[Path] = None) -> None:
        self.base_root = base_root or PROJECTS_ROOT
        self.base_root.mkdir(parents=True, exist_ok=True)
        logger.debug("Project scaffold root initialized at %s", self.base_root)

    # --- helpers ---------------------------------------------------------
    def _now(self) -> float:
        return time.time()

    def _project_path(self, name: str) -> Path:
        return self.base_root / name

    def _ensure_project_dir(self, name: str) -> Path:
        p = self._project_path(name)
        p.mkdir(parents=True, exist_ok=True)
        (p / "profile.json").parent.mkdir(parents=True, exist_ok=True)
        return p

    # --- core lifecycle --------------------------------------------------
    def init_project(self, profile: ProjectProfile) -> ProjectSkills:
        # Base set of always-enabled capabilities
        capabilities = {
            "skill_discovery",
            "tool_market",
            "memory_pipeline",
            "knowledge_quality",
        }

        # Language-based augmentations
        lang = profile.language.lower()
        if lang in {"python"}:
            capabilities.update({"ast_parser", "code_engine"})
        elif lang in {"typescript", "ts", "javascript"}:
            capabilities.update({"ast_parser", "code_engine"})
        elif lang in {"rust"}:
            capabilities.update({"code_engine"})

        # Type-based augmentations
        ptype = profile.type.lower()
        if ptype == "web-app":
            capabilities.update({"doc_engine", "template_engine"})
        elif ptype == "cli-tool":
            capabilities.update({"tool_synthesis", "tool_executor"})
        elif ptype == "ai-agent":
            capabilities.update({"self_discovery", "agent_marketplace", "progressive_trust"})
        elif ptype == "api-server":
            capabilities.update({"unified_file_tool"})
        elif ptype == "data-pipeline":
            capabilities.update({"extraction_engine", "data_lineage"})
        elif ptype == "library":
            capabilities.update({"semantic_diff", "patch_manager"})

        # Framework-based augmentations
        framework = (profile.framework or "").lower()
        if framework == "fastapi":
            capabilities.add("network_brain")
        elif framework == "nextjs":
            capabilities.add("doc_engine")
        elif framework == "actix":
            capabilities.add("code_engine")

        # Convert to lists, ensuring no duplicates
        enabled = sorted(list(set(capabilities)))

        # Generate templates populated by the type
        templates = self._generate_templates(profile)

        # Domain glossary terms
        glossary = self._generate_domain_terms(profile)

        # Buckets prioritization
        buckets = self._generate_buckets(profile)

        # Overrides
        overrides = self._generate_overrides(profile)

        skills = ProjectSkills(
            project_name=profile.name,
            enabled_capabilities=enabled,
            disabled_capabilities=[],
            prompt_templates=templates,
            domain_terms=glossary,
            buckets=buckets,
            config_overrides=overrides,
            custom_rules=self._generate_custom_rules(profile),
        )
        return skills

    def save_project(self, profile: ProjectProfile, skills: ProjectSkills) -> None:
        p = self._ensure_project_dir(profile.name)
        profile_path = p / "profile.json"
        skills_path = p / "skills.json"
        with profile_path.open("w", encoding="utf-8") as f:
            f.write(__import__("json").dumps(profile.dict(), indent=4, default=str))
        with skills_path.open("w", encoding="utf-8") as f:
            f.write(__import__("json").dumps(skills.dict(), indent=4, default=str))
        logger.info("Saved project scaffold for %s", profile.name)

    def load_project(self, name: str) -> Optional[Tuple[ProjectProfile, ProjectSkills]]:
        path = self._project_path(name)
        profile_path = path / "profile.json"
        skills_path = path / "skills.json"
        if not profile_path.exists() or not skills_path.exists():
            return None
        with profile_path.open("r", encoding="utf-8") as f:
            profile = ProjectProfile.parse_raw(f.read())
        with skills_path.open("r", encoding="utf-8") as f:
            skills = ProjectSkills.parse_raw(f.read())
        return profile, skills

    def list_projects(self) -> List[str]:
        if not PROJECTS_ROOT.exists():
            return []
        return [p.name for p in PROJECTS_ROOT.iterdir() if p.is_dir()]

    def delete_project(self, name: str) -> bool:
        path = self._project_path(name)
        if not path.exists():
            return False
        for child in path.iterdir():
            if child.is_dir():
                for sub in child.iterdir():
                    sub.unlink(missing_ok=True)
                child.rmdir()
            else:
                child.unlink(missing_ok=True)
        path.rmdir()
        return True

    def export_project_config(self, name: str) -> Dict[str, Any]:
        loaded = self.load_project(name)
        if not loaded:
            return {}
        profile, skills = loaded
        return {
            "profile": profile.dict(),
            "skills": skills.dict(),
        }

    def get_active_capabilities(self, name: str) -> List[str]:
        loaded = self.load_project(name)
        if not loaded:
            return []
        _, skills = loaded
        return list(skills.enabled_capabilities)

    def get_prompt_templates(self, name: str) -> List[str]:
        loaded = self.load_project(name)
        if not loaded:
            return []
        _, skills = loaded
        return list(skills.prompt_templates)

    def get_domain_glossary(self, name: str) -> str:
        loaded = self.load_project(name)
        if not loaded:
            return ""
        _, skills = loaded
        return ", ".join(skills.domain_terms)

    def get_scaffold_rules(self, name: str) -> str:
        # Simple textual rules suitable for injecting into an agent prompt
        glossary = self.get_domain_glossary(name)
        caps = ", ".join(self.get_active_capabilities(name))
        return f"Domain: {glossary}\nCapabilities: {caps}"

    def update_skills(self, name: str, skills: ProjectSkills) -> bool:
        if not self._project_path(name).exists():
            return False
        self.save_project(ProjectProfile(name=name, language="", type=""), skills)
        return True

    def quick_init(self, name: str, language: str, project_type: str, **kwargs) -> ProjectSkills:
        profile = ProjectProfile(
            name=name,
            language=language,
            framework=kwargs.get("framework", ""),
            type=project_type,
            description=kwargs.get("description", ""),
            tags=kwargs.get("tags", []),
            repo_url=kwargs.get("repo_url", ""),
            created_at=kwargs.get("created_at", self._now()),
            updated_at=kwargs.get("updated_at", self._now()),
        )
        skills = self.init_project(profile)
        self.save_project(profile, skills)
        return skills

    # --- private helpers for content generation ---------------------------
    def _generate_templates(self, profile: ProjectProfile) -> List[str]:
        t = []
        t.append("default_template")
        tname = profile.type.lower()
        if tname == "web-app":
            t.extend(["web_app_init", "user_flow_setup"])
        elif tname == "cli-tool":
            t.extend(["cli_init", "command_docs"])
        elif tname == "api-server":
            t.extend(["api_endpoint_doc", "api_usage_template"])
        elif tname == "data-pipeline":
            t.append("data_pipeline_template")
        elif tname == "library":
            t.append("library_diff_template")
        elif tname == "ai-agent":
            t.append("agent_discovery_template")
        return t

    def _generate_domain_terms(self, profile: ProjectProfile) -> List[str]:
        terms = []
        lang = (profile.language or "").lower()
        fw = (profile.framework or "").lower()
        if lang:
            terms.append(lang)
        if fw:
            terms.append(fw)
        if profile.type:
            terms.append(profile.type)
        return terms

    def _generate_buckets(self, profile: ProjectProfile) -> List[str]:
        t = profile.type.lower()
        if t == "api-server":
            return ["api", "security", "integration"]
        if t == "web-app":
            return ["ui", "backend", "db"]
        if t == "cli-tool":
            return ["cli", "scripting"]
        if t == "data-pipeline":
            return ["extract", "transform", "load"]
        if t == "library":
            return ["diffs", "patches"]
        return ["default"]

    def _generate_overrides(self, profile: ProjectProfile) -> Dict[str, Any]:
        overrides: Dict[str, Any] = {}
        t = profile.type.lower()
        if t == "api-server":
            overrides["api"] = {"port": 8080, "timeout": 60}
        if t == "cli-tool":
            overrides["sandbox"] = True
        return overrides

    def _generate_custom_rules(self, profile: ProjectProfile) -> List[str]:
        rules: List[str] = []
        if profile.type.lower() == "ai-agent":
            rules.append("maintain_progressive_trust_score")
        return rules


# Singleton instance exposed for quick_init usage in tests/examples
PROJECT_SCAFFOLD = ProjectScaffold()
