from typing import Dict, Any, Optional, List
from .manifest import ToolManifest, OutputSpec
import json
import os
from pathlib import Path


class ValidationResult:
    def __init__(self):
        self.valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.outputs: Dict[str, Any] = {}

    def add_error(self, message: str):
        self.valid = False
        self.errors.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    def set_outputs(self, outputs: Dict[str, Any]):
        self.outputs = outputs

    def __bool__(self):
        return self.valid


class ToolValidator:
    def __init__(self):
        self.validators = {
            "json": self._validate_json,
            "file": self._validate_file,
            "string": self._validate_string,
            "number": self._validate_number,
            "boolean": self._validate_boolean
        }

    def validate(self, manifest: ToolManifest, outputs: Dict[str, Any]) -> ValidationResult:
        """
        校验工具输出
        
        Checks:
        - 文件存在？
        - 数值范围合理？
        - 单位正确？
        """
        result = ValidationResult()
        
        for out_spec in manifest.outputs:
            if out_spec.name not in outputs:
                result.add_error(f"Missing required output: {out_spec.name}")
                continue
            
            value = outputs[out_spec.name]
            
            # 根据类型进行校验
            validator = self.validators.get(out_spec.type)
            if validator:
                validator(out_spec, value, result)
            
            # 数值范围校验
            if out_spec.type == "number":
                self._validate_number_range(out_spec, value, result)
            
            # 单位校验
            if out_spec.unit:
                self._validate_unit(out_spec, value, result)
        
        result.set_outputs(outputs)
        return result

    def _validate_json(self, spec: OutputSpec, value: Any, result: ValidationResult):
        """校验JSON输出"""
        if isinstance(value, str):
            try:
                json.loads(value)
            except json.JSONDecodeError:
                result.add_error(f"Output {spec.name} is not valid JSON")
        elif not isinstance(value, (dict, list)):
            result.add_error(f"Output {spec.name} should be JSON/dict/list")

    def _validate_file(self, spec: OutputSpec, value: Any, result: ValidationResult):
        """校验文件输出"""
        if isinstance(value, str):
            file_path = value if os.path.isabs(value) else os.path.join(os.getcwd(), value)
            if not os.path.exists(file_path):
                result.add_error(f"Output file {spec.name} not found: {file_path}")
            else:
                self._validate_file_size(file_path, spec, result)
        else:
            result.add_error(f"Output {spec.name} should be a file path string")

    def _validate_file_size(self, file_path: str, spec: OutputSpec, result: ValidationResult):
        """校验文件大小"""
        max_size_mb = 100  # 默认最大100MB
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        if file_size_mb > max_size_mb:
            result.add_warning(f"Output file {spec.name} is large ({file_size_mb:.2f} MB)")

    def _validate_string(self, spec: OutputSpec, value: Any, result: ValidationResult):
        """校验字符串输出"""
        if not isinstance(value, str):
            result.add_error(f"Output {spec.name} should be a string")
        elif len(value) == 0:
            result.add_warning(f"Output {spec.name} is empty string")

    def _validate_number(self, spec: OutputSpec, value: Any, result: ValidationResult):
        """校验数值输出"""
        if not isinstance(value, (int, float)):
            result.add_error(f"Output {spec.name} should be a number")

    def _validate_boolean(self, spec: OutputSpec, value: Any, result: ValidationResult):
        """校验布尔输出"""
        if not isinstance(value, bool):
            result.add_error(f"Output {spec.name} should be a boolean")

    def _validate_number_range(self, spec: OutputSpec, value: Any, result: ValidationResult):
        """校验数值范围"""
        if not isinstance(value, (int, float)):
            return
        
        if spec.min_value is not None and value < spec.min_value:
            result.add_error(f"Output {spec.name} ({value}) is below minimum ({spec.min_value})")
        
        if spec.max_value is not None and value > spec.max_value:
            result.add_error(f"Output {spec.name} ({value}) exceeds maximum ({spec.max_value})")

    def _validate_unit(self, spec: OutputSpec, value: Any, result: ValidationResult):
        """校验单位"""
        if spec.unit:
            result.add_warning(f"Output {spec.name} has unit: {spec.unit} (manual verification recommended)")

    def validate_inputs(self, manifest: ToolManifest, inputs: Dict[str, Any]) -> ValidationResult:
        """校验输入参数"""
        result = ValidationResult()
        
        for inp_spec in manifest.inputs:
            if inp_spec.required and inp_spec.name not in inputs:
                result.add_error(f"Missing required input: {inp_spec.name}")
            elif inp_spec.name in inputs:
                value = inputs[inp_spec.name]
                if inp_spec.type == "number":
                    if not isinstance(value, (int, float)):
                        result.add_error(f"Input {inp_spec.name} should be a number")
                elif inp_spec.type == "boolean":
                    if not isinstance(value, bool):
                        result.add_error(f"Input {inp_spec.name} should be a boolean")
                elif inp_spec.type == "file":
                    if isinstance(value, str):
                        file_path = value if os.path.isabs(value) else os.path.join(os.getcwd(), value)
                        if not os.path.exists(file_path):
                            result.add_error(f"Input file {inp_spec.name} not found: {file_path}")
        
        return result

    def validate_schema(self, spec: OutputSpec, value: Any) -> bool:
        """校验JSON Schema"""
        if not spec.schema:
            return True
        
        try:
            import jsonschema
            jsonschema.validate(value, spec.schema)
            return True
        except ImportError:
            return True  # Schema校验需要jsonschema库
        except jsonschema.ValidationError:
            return False

    def sanitize_outputs(self, manifest: ToolManifest, outputs: Dict[str, Any]) -> Dict[str, Any]:
        """清理输出，移除敏感信息"""
        sanitized = {}
        
        for out_spec in manifest.outputs:
            if out_spec.name in outputs:
                value = outputs[out_spec.name]
                
                if isinstance(value, str):
                    value = self._sanitize_string(value)
                elif isinstance(value, dict):
                    value = self._sanitize_dict(value)
                
                sanitized[out_spec.name] = value
        
        return sanitized

    def _sanitize_string(self, value: str) -> str:
        """清理字符串中的敏感信息"""
        sensitive_patterns = [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            r'1[3-9]\d{9}',
            r'key\s*[=:]\s*[\w]+',
            r'secret\s*[=:]\s*[\w]+',
            r'token\s*[=:]\s*[\w]+'
        ]
        
        import re
        for pattern in sensitive_patterns:
            value = re.sub(pattern, '[REDACTED]', value)
        
        return value

    def _sanitize_dict(self, value: dict) -> dict:
        """清理字典中的敏感信息"""
        sanitized = {}
        for k, v in value.items():
            if isinstance(v, str):
                sanitized[k] = self._sanitize_string(v)
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_dict(v)
            else:
                sanitized[k] = v
        return sanitized


validator = ToolValidator()
