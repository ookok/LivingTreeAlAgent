from typing import Dict, Any, Optional, Callable
from .manifest import ToolManifest, ToolExecutionResult
from .registry import registry
from .tool_downloader import downloader, env_tool_registry
import subprocess
import tempfile
import os
import json
from datetime import datetime
import uuid


class ToolResolver:
    def __init__(self):
        self.registry = registry
        self.on_human_request: Optional[Callable[[str, Dict[str, Any]], bool]] = None
        self.downloader = downloader
        self.env_tool_registry = env_tool_registry

    def resolve(self, intent: str, inputs: Dict[str, Any] = None) -> Optional[ToolExecutionResult]:
        """
        五步安全流水线：
        Step 1: 意图 → 工具匹配
        Step 2: 依赖检查
        Step 3: 自动准备
        Step 4: 执行
        Step 5: 输出校验
        """
        inputs = inputs or {}
        
        # Step 1: 意图匹配
        manifests = self.registry.search_by_intent(intent)
        if not manifests:
            return ToolExecutionResult(
                success=False,
                error=f"No tool found for intent: {intent}",
                used_fallback=False
            )
        
        for manifest in manifests:
            result = self._try_resolve_manifest(manifest, inputs)
            if result.success:
                return result
        
        # 所有工具都失败，尝试降级策略
        return self._try_fallback_strategy(manifests[0], inputs)

    def _try_resolve_manifest(self, manifest: ToolManifest, inputs: Dict[str, Any]) -> ToolExecutionResult:
        """尝试解析并执行单个工具"""
        # Step 2: 依赖检查
        status = self.registry.get_tool_status(manifest.tool_id)
        if not status.available:
            # Step 3: 自动准备
            prepare_result = self._prepare_tool(manifest)
            if not prepare_result:
                return ToolExecutionResult(
                    success=False,
                    error=f"Failed to prepare tool {manifest.tool_id}: {status.error}",
                    tool_id=manifest.tool_id,
                    used_fallback=False
                )
        
        # Step 4: 执行
        execution_result = self._execute_tool(manifest, inputs)
        if not execution_result.success:
            return execution_result
        
        # Step 5: 输出校验
        validation_result = self._validate_output(manifest, execution_result.outputs)
        if validation_result:
            return execution_result
        else:
            return ToolExecutionResult(
                success=False,
                error="Output validation failed",
                tool_id=manifest.tool_id,
                used_fallback=False
            )

    def _prepare_tool(self, manifest: ToolManifest) -> bool:
        """自动准备工具（安装依赖 + 下载CLI工具）"""
        # 策略A：自动安装
        if manifest.install:
            print(f"[ToolResolver] Auto-installing {manifest.tool_id}...")
            for cmd in manifest.install:
                try:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    if result.returncode == 0:
                        print(f"[ToolResolver] Install command succeeded: {cmd}")
                    else:
                        print(f"[ToolResolver] Install command failed: {cmd}")
                        print(f"  Error: {result.stderr}")
                except Exception as e:
                    print(f"[ToolResolver] Install exception: {e}")
        
        # 尝试从环境工具注册表下载CLI工具
        env_tool = self.env_tool_registry.get_tool(manifest.tool_id)
        if env_tool:
            if not self.downloader.is_tool_installed(manifest.tool_id):
                print(f"[ToolResolver] Downloading CLI tool {manifest.tool_id}...")
                success = self.downloader.download_tool(env_tool)
                if success:
                    print(f"[ToolResolver] Successfully downloaded {manifest.tool_id}")
                else:
                    print(f"[ToolResolver] Failed to download {manifest.tool_id}")
        
        # 刷新状态
        self.registry.refresh_status(manifest.tool_id)
        new_status = self.registry.get_tool_status(manifest.tool_id)
        return new_status.available

    def _try_fallback_strategy(self, primary_manifest: ToolManifest, inputs: Dict[str, Any]) -> ToolExecutionResult:
        """尝试降级策略"""
        # 策略B：自动替代
        fallback_tools = self.registry.get_equivalent_tools(primary_manifest.tool_id)
        for fallback_manifest in fallback_tools:
            result = self._try_resolve_manifest(fallback_manifest, inputs)
            if result.success:
                result.used_fallback = True
                result.fallback_reason = f"Primary tool {primary_manifest.tool_id} unavailable"
                return result
        
        # 策略C：自动生成工具
        generated_result = self._generate_tool(primary_manifest, inputs)
        if generated_result.success:
            generated_result.used_fallback = True
            generated_result.fallback_reason = f"Generated fallback tool for {primary_manifest.tool_id}"
            return generated_result
        
        # 策略D：人机共驾
        human_result = self._request_human_assistance(primary_manifest, inputs)
        if human_result is not None:
            return human_result
        
        return ToolExecutionResult(
            success=False,
            error=f"No available tools for {primary_manifest.tool_id} and no fallback options",
            tool_id=primary_manifest.tool_id,
            used_fallback=False
        )

    def _generate_tool(self, manifest: ToolManifest, inputs: Dict[str, Any]) -> ToolExecutionResult:
        """策略C：自动生成工具"""
        print(f"[ToolResolver] Generating fallback tool for {manifest.tool_id}...")
        
        try:
            tool_code = self._generate_tool_code(manifest)
            if tool_code:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(tool_code)
                    temp_file = f.name
                
                result = subprocess.run(
                    ['python', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                os.unlink(temp_file)
                
                if result.returncode == 0:
                    try:
                        outputs = json.loads(result.stdout)
                        return ToolExecutionResult(
                            success=True,
                            outputs=outputs,
                            tool_id=manifest.tool_id,
                            used_fallback=True
                        )
                    except:
                        return ToolExecutionResult(
                            success=True,
                            outputs={"result": result.stdout.strip()},
                            tool_id=manifest.tool_id,
                            used_fallback=True
                        )
        
        except Exception as e:
            print(f"[ToolResolver] Tool generation failed: {e}")
        
        return ToolExecutionResult(
            success=False,
            error="Tool generation failed",
            tool_id=manifest.tool_id
        )

    def _generate_tool_code(self, manifest: ToolManifest) -> Optional[str]:
        """生成工具代码"""
        input_names = [inp.name for inp in manifest.inputs]
        output_names = [out.name for out in manifest.outputs]
        
        code = f"""
import json
import sys

def main():
    inputs = {{}}
    try:
        inputs = json.loads(sys.stdin.read())
    except:
        pass
    
    result = {{}}
    {chr(34)}{chr(34)}{chr(34)}Auto-generated fallback tool for {manifest.tool_id}{chr(34)}{chr(34)}{chr(34)}
    
    # Mock implementation based on manifest
    {chr(10).join([f"result['{out}'] = None" for out in output_names])}
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()
"""
        return code

    def _request_human_assistance(self, manifest: ToolManifest, inputs: Dict[str, Any]) -> Optional[ToolExecutionResult]:
        """策略D：请求人工协助"""
        if self.on_human_request:
            request_data = {
                "tool_id": manifest.tool_id,
                "tool_name": manifest.name,
                "description": manifest.description,
                "inputs": inputs,
                "deps": manifest.deps,
                "install": manifest.install,
                "timestamp": datetime.now().isoformat()
            }
            user_approved = self.on_human_request("tool_required", request_data)
            if user_approved:
                # 用户批准后重试
                return self._try_resolve_manifest(manifest, inputs)
        
        return None

    def _execute_tool(self, manifest: ToolManifest, inputs: Dict[str, Any]) -> ToolExecutionResult:
        """执行工具"""
        start_time = datetime.now()
        
        try:
            if manifest.type == "cli":
                return self._execute_cli(manifest, inputs)
            elif manifest.type == "python":
                return self._execute_python(manifest, inputs)
            elif manifest.type == "api":
                return self._execute_api(manifest, inputs)
            elif manifest.type == "docker":
                return self._execute_docker(manifest, inputs)
            else:
                return ToolExecutionResult(
                    success=False,
                    error=f"Unsupported tool type: {manifest.type}",
                    tool_id=manifest.tool_id
                )
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return ToolExecutionResult(
                success=False,
                error=str(e),
                tool_id=manifest.tool_id,
                execution_time=execution_time
            )

    def _execute_cli(self, manifest: ToolManifest, inputs: Dict[str, Any]) -> ToolExecutionResult:
        """执行CLI工具"""
        args = []
        for inp in manifest.inputs:
            if inp.name in inputs:
                args.append(f"--{inp.name}")
                args.append(str(inputs[inp.name]))
        
        cmd = " ".join([manifest.check_cmd.split()[0]] + args)
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        
        execution_time = (datetime.now() - datetime.now()).total_seconds()
        
        if result.returncode == 0:
            try:
                outputs = json.loads(result.stdout)
            except:
                outputs = {"stdout": result.stdout, "stderr": result.stderr}
            
            return ToolExecutionResult(
                success=True,
                outputs=outputs,
                tool_id=manifest.tool_id,
                execution_time=execution_time
            )
        else:
            return ToolExecutionResult(
                success=False,
                error=result.stderr or result.stdout,
                tool_id=manifest.tool_id,
                execution_time=execution_time
            )

    def _execute_python(self, manifest: ToolManifest, inputs: Dict[str, Any]) -> ToolExecutionResult:
        """执行Python工具"""
        import importlib
        module_name = manifest.tool_id.replace("-", "_")
        
        try:
            module = importlib.import_module(f"business.tools.{module_name}")
            func = getattr(module, "execute", None)
            if func:
                outputs = func(inputs)
                return ToolExecutionResult(
                    success=True,
                    outputs=outputs,
                    tool_id=manifest.tool_id
                )
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                error=str(e),
                tool_id=manifest.tool_id
            )
        
        return ToolExecutionResult(
            success=False,
            error="Python tool not found or has no execute function",
            tool_id=manifest.tool_id
        )

    def _execute_api(self, manifest: ToolManifest, inputs: Dict[str, Any]) -> ToolExecutionResult:
        """执行API工具"""
        import requests
        
        try:
            response = requests.post(
                manifest.check_cmd,
                json=inputs,
                timeout=30
            )
            response.raise_for_status()
            return ToolExecutionResult(
                success=True,
                outputs=response.json(),
                tool_id=manifest.tool_id
            )
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                error=str(e),
                tool_id=manifest.tool_id
            )

    def _execute_docker(self, manifest: ToolManifest, inputs: Dict[str, Any]) -> ToolExecutionResult:
        """执行Docker工具"""
        import docker
        
        try:
            client = docker.from_env()
            container = client.containers.run(
                manifest.check_cmd,
                command=json.dumps(inputs),
                detach=False,
                remove=True
            )
            return ToolExecutionResult(
                success=True,
                outputs={"output": container.decode("utf-8")},
                tool_id=manifest.tool_id
            )
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                error=str(e),
                tool_id=manifest.tool_id
            )

    def _validate_output(self, manifest: ToolManifest, outputs: Dict[str, Any]) -> bool:
        """校验输出"""
        for out_spec in manifest.outputs:
            if out_spec.name not in outputs:
                return False
            
            value = outputs[out_spec.name]
            
            if out_spec.min_value is not None and value < out_spec.min_value:
                return False
            if out_spec.max_value is not None and value > out_spec.max_value:
                return False
        
        return True

    def set_human_request_callback(self, callback: Callable[[str, Dict[str, Any]], bool]):
        """设置人机交互回调"""
        self.on_human_request = callback


resolver = ToolResolver()
