from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class InputSpec(BaseModel):
    name: str
    type: Literal["json", "file", "string", "number", "boolean"]
    description: str
    required: bool = True
    schema: Optional[Dict[str, Any]] = None
    example: Optional[Any] = None


class OutputSpec(BaseModel):
    name: str
    type: Literal["json", "file", "string", "number", "boolean"]
    description: str
    schema: Optional[Dict[str, Any]] = None
    unit: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class ToolManifest(BaseModel):
    tool_id: str = Field(description="唯一工具标识")
    name: str = Field(description="工具名称")
    type: Literal["cli", "python", "api", "docker"] = Field(description="工具类型")
    description: str = Field(description="工具功能描述")
    inputs: List[InputSpec] = Field(description="输入参数规范")
    outputs: List[OutputSpec] = Field(description="输出参数规范")
    deps: List[str] = Field(default_factory=list, description="依赖列表")
    install: List[str] = Field(default_factory=list, description="安装命令")
    check_cmd: str = Field(description="检查命令")
    fallback_tools: List[str] = Field(default_factory=list, description="降级工具列表")
    version: str = Field(default="1.0.0", description="工具版本")
    tags: List[str] = Field(default_factory=list, description="标签")

    @validator('tool_id')
    def tool_id_must_be_lowercase(cls, v):
        if not v.islower():
            raise ValueError('tool_id must be lowercase')
        return v

    def get_input_names(self) -> List[str]:
        return [inp.name for inp in self.inputs]

    def get_required_inputs(self) -> List[str]:
        return [inp.name for inp in self.inputs if inp.required]

    def get_output_names(self) -> List[str]:
        return [out.name for out in self.outputs]

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        required = self.get_required_inputs()
        for req in required:
            if req not in inputs:
                return False
        return True


class ToolStatus(BaseModel):
    tool_id: str
    available: bool
    version: Optional[str] = None
    error: Optional[str] = None
    last_checked: Optional[str] = None


class ToolExecutionResult(BaseModel):
    success: bool
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    execution_time: Optional[float] = None
    tool_id: Optional[str] = None
    used_fallback: bool = False
    fallback_reason: Optional[str] = None
