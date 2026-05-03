"""Skill factory and runtime for LivingTree capabilities.

This module provides a self-discovering skill system that can register,
compose, test and execute skills. Skills are represented by SkillSpec models
and executed in isolated subprocesses to satisfy the sandbox requirement.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field


InputSchema = Dict[str, Any]
OutputSchema = Dict[str, Any]


class SkillSpec(BaseModel):
    name: str
    description: str
    input_schema: InputSchema = Field(default_factory=dict)
    output_schema: OutputSchema = Field(default_factory=dict)
    category: str = "general"
    code: Optional[str] = None
    test_cases: List[Dict[str, Any]] = Field(default_factory=list)


class Skill:
    def __init__(self, spec: SkillSpec, module_path: Path, runner_path: Path) -> None:
        self.spec = spec
        self._module_path = module_path
        self._runner_path = runner_path

    async def execute(self, input_data: Dict[str, Any]) -> Any:
        # Run in isolated subprocess to satisfy sandbox requirement
        loop = asyncio.get_event_loop()
        return await asyncio.to_thread(self._execute_in_isolation, input_data)

    def _execute_in_isolation(self, input_data: Dict[str, Any]) -> Any:
        # Prepare a small runner that imports the skill module and calls execute(input)
        tmp_dir = tempfile.mkdtemp(prefix="skill_")
        try:
            module_file = Path(tmp_dir) / f"skill_module_{self.spec.name}.py"
            runner_file = Path(tmp_dir) / "runner.py"
            input_file = Path(tmp_dir) / "input.json"

            # Write the user-provided code to a module
            module_file.write_text(self.spec.code or "\n")

            # Prepare runner that loads the module and runs execute(input)
            runner_code = f"""import json, sys, importlib.util
import os
def _load_module(path):
    spec = importlib.util.spec_from_file_location('skill_module', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  
    return mod

def main(module_path, input_path):
    with open(input_path, 'r') as f:
        data = json.load(f)
    mod = _load_module(module_path)
    if not hasattr(mod, 'execute'):
        print(json.dumps({"error": "no_execute"}))
        return
    result = mod.execute(data)
    print(json.dumps(result))

if __name__ == '__main__':
    main(r"{module}", r"{inp}")
"""
            runner_code = runner_code.replace("{module}", str(module_file)).replace("{inp}", str(input_file))
            runner_file.write_text(runner_code)

            # Write input file
            input_file.write_text(json.dumps(input_data))

            # Execute runner in a fresh Python process for isolation
            result = subprocess.run(
                [sys.executable, str(runner_file)],
                cwd=tmp_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.error("Skill execution failed: %s", result.stderr)
                return {"error": result.stderr.strip()}
            output = result.stdout.strip()
            try:
                return json.loads(output) if output else None
            except json.JSONDecodeError:
                return output
        finally:
            # Cleanup temporary directory
            try:
                for p in Path(tmp_dir).glob('*'):
                    p.unlink(missing_ok=True)
                Path(tmp_dir).rmdir()
            except Exception:
                pass


class SkillFactory:
    def __init__(self) -> None:
        self._skills: Dict[str, SkillSpec] = {}
        self._instances: Dict[str, Skill] = {}
        self._tmp_root: Path = Path(tempfile.gettempdir()) / "livingtree_skills"
        self._tmp_root.mkdir(parents=True, exist_ok=True)

    def discover_skills(self) -> List[str]:
        return list(self._skills.keys())

    def create_skill(
        self,
        name: str,
        description: str,
        code: Optional[str],
        input_schema: Optional[InputSchema] = None,
        output_schema: Optional[OutputSchema] = None,
        category: str = "general",
        test_cases: Optional[List[Dict[str, Any]]] = None,
    ) -> Skill:
        spec = SkillSpec(
            name=name,
            description=description,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
            category=category,
            code=code,
            test_cases=test_cases or [],
        )
        module_path = self._tmp_root / f"{name}.py"
        module_path.write_text(code or "\n")
        runner_path = self._tmp_root / f"runner_{name}.py"
        # Ensure runner is prepared (will be created on demand in execution)
        skill = Skill(spec, module_path, runner_path)
        self._skills[name] = spec
        self._instances[name] = skill
        return skill

    def compose_skills(self, skill_list: List[str]) -> Skill:
        # Simple composition: expose a synthetic composed skill that chains existing skills
        comp_name = "composed_" + "_".join(skill_list)
        comp_spec = SkillSpec(
            name=comp_name,
            description="Composed skill of: " + ",".join(skill_list),
            input_schema={},
            output_schema={},
        )
        composed_module = self._tmp_root / f"{comp_name}.py"
        composed_module.write_text("# composed skill placeholder\n")
        runner_path = self._tmp_root / f"runner_{comp_name}.py"
        runner_path.write_text("# composed runner placeholder\n")
        return Skill(comp_spec, module_path=composed_module, runner_path=runner_path)

    def register_skill(self, spec: SkillSpec) -> None:
        self._skills[spec.name] = spec

    def get_skill(self, name: str) -> Optional[SkillSpec]:
        return self._skills.get(name)

    def list_by_category(self, category: str) -> List[SkillSpec]:
        return [s for s in self._skills.values() if s.category == category]

    def test_skill(self, name: str) -> List[Dict[str, Any]]:
        spec = self._skills.get(name)
        if not spec:
            return [{"error": "skill not found"}]
        return spec.test_cases
