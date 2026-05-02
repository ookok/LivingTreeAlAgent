from typing import Dict, Any, Optional, List
import re
from pathlib import Path


class DocumentSlot:
    def __init__(self, slot_id: str, tool_id: str, output_name: str, 
                 display_name: str = None, format: str = "text"):
        self.slot_id = slot_id
        self.tool_id = tool_id
        self.output_name = output_name
        self.display_name = display_name or output_name
        self.format = format
        self.value: Any = None
        self.filled = False
        self.error: Optional[str] = None

    def fill(self, value: Any):
        """填充插槽值"""
        self.value = value
        self.filled = True
        self.error = None

    def set_error(self, error: str):
        """设置错误"""
        self.error = error
        self.filled = False

    def render(self) -> str:
        """渲染插槽内容"""
        if self.error:
            return f"（注：{self.error}）"
        
        if not self.filled or self.value is None:
            return f"<!-- SLOT: {self.slot_id} -->"
        
        if self.format == "number":
            return str(self.value)
        elif self.format == "file":
            return f"![{self.display_name}]({self.value})"
        elif self.format == "figure":
            return f"![{self.display_name}]({self.value})"
        else:
            return str(self.value)


class ToolSlotter:
    def __init__(self):
        self.slots: Dict[str, DocumentSlot] = {}
        self.slot_pattern = re.compile(r'<!--\s*TOOL:\s*(\w+)\s*-->')
        self.output_pattern = re.compile(r'<!--\s*OUTPUT:\s*(\w+)\s*-->')
        self.figure_pattern = re.compile(r'<!--\s*FIGURE:\s*(\w+)\s*-->')

    def parse_document(self, content: str) -> List[DocumentSlot]:
        """解析文档中的插槽"""
        slots = []
        
        matches = self.slot_pattern.findall(content)
        for tool_id in matches:
            slot = DocumentSlot(
                slot_id=f"slot_{tool_id}",
                tool_id=tool_id,
                output_name="result",
                display_name=tool_id.replace("_", " ").title()
            )
            slots.append(slot)
            self.slots[slot.slot_id] = slot
        
        return slots

    def fill_slots(self, tool_id: str, outputs: Dict[str, Any]):
        """填充工具输出到插槽"""
        for slot in self.slots.values():
            if slot.tool_id == tool_id:
                if slot.output_name in outputs:
                    slot.fill(outputs[slot.output_name])
                else:
                    slot.set_error(f"工具 {tool_id} 未返回 {slot.output_name}")

    def render_document(self, content: str) -> str:
        """渲染文档，填充所有插槽"""
        rendered = content
        
        for slot in self.slots.values():
            placeholder = f"<!-- SLOT: {slot.slot_id} -->"
            rendered = rendered.replace(placeholder, slot.render())
        
        return rendered

    def get_unfilled_slots(self) -> List[DocumentSlot]:
        """获取未填充的插槽"""
        return [slot for slot in self.slots.values() if not slot.filled]

    def get_slot_by_id(self, slot_id: str) -> Optional[DocumentSlot]:
        """根据ID获取插槽"""
        return self.slots.get(slot_id)

    def register_slot(self, slot: DocumentSlot):
        """注册插槽"""
        self.slots[slot.slot_id] = slot

    def clear_slots(self):
        """清空所有插槽"""
        self.slots.clear()

    def generate_slot_markdown(self, tool_id: str, output_name: str, display_name: str = None) -> str:
        """生成插槽标记"""
        slot_id = f"slot_{tool_id}_{output_name}"
        return f"<!-- SLOT: {slot_id} -->"

    def handle_tool_failure(self, tool_id: str, error: str):
        """处理工具失败"""
        for slot in self.slots.values():
            if slot.tool_id == tool_id:
                slot.set_error(f"{tool_id} 执行失败: {error}")

    def bind_to_output(self, tool_id: str, output_name: str, value: Any, 
                       display_name: str = None, format: str = "text"):
        """绑定输出值到插槽"""
        slot_id = f"slot_{tool_id}_{output_name}"
        
        if slot_id not in self.slots:
            self.slots[slot_id] = DocumentSlot(
                slot_id=slot_id,
                tool_id=tool_id,
                output_name=output_name,
                display_name=display_name or output_name,
                format=format
            )
        
        self.slots[slot_id].fill(value)

    def get_slot_values(self) -> Dict[str, Any]:
        """获取所有已填充的插槽值"""
        return {slot.slot_id: slot.value for slot in self.slots.values() if slot.filled}


slotter = ToolSlotter()
