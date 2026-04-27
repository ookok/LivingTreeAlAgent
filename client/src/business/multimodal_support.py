"""
多模态支持模块
实现UI截图识别和代码生成功能
"""

import os
import base64
import asyncio
import subprocess
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class ScreenshotSource(Enum):
    """截图来源"""
    SCREEN = "screen"
    WINDOW = "window"
    REGION = "region"


class UIElements(Enum):
    """UI元素类型"""
    BUTTON = "button"
    TEXT_INPUT = "text_input"
    LABEL = "label"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    DROPDOWN = "dropdown"
    CARD = "card"
    NAVIGATION = "navigation"
    FORM = "form"
    GRID = "grid"


@dataclass
class UIElement:
    """UI元素"""
    element_type: UIElements
    x: int
    y: int
    width: int
    height: int
    text: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class Screenshot:
    """截图"""
    image_data: bytes
    source: ScreenshotSource
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeGenerationResult:
    """代码生成结果"""
    code: str
    language: str
    framework: str
    elements: List[UIElement] = field(default_factory=list)
    confidence: float = 0.0
    explanation: str = ""


class ScreenshotManager:
    """截图管理器"""
    
    def __init__(self):
        pass
    
    def capture_screen(self) -> Optional[Screenshot]:
        """捕获整个屏幕"""
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            
            # 转换为字节
            import io
            buffer = io.BytesIO()
            screenshot.save(buffer, format='PNG')
            image_data = buffer.getvalue()
            
            return Screenshot(
                image_data=image_data,
                source=ScreenshotSource.SCREEN
            )
        except Exception as e:
            print(f"捕获屏幕失败: {e}")
            return None
    
    def capture_window(self, window_title: str) -> Optional[Screenshot]:
        """捕获指定窗口"""
        try:
            import pygetwindow as gw
            window = gw.getWindowsWithTitle(window_title)[0]
            if window:
                import pyautogui
                screenshot = pyautogui.screenshot(region=(window.left, window.top, window.width, window.height))
                
                import io
                buffer = io.BytesIO()
                screenshot.save(buffer, format='PNG')
                image_data = buffer.getvalue()
                
                return Screenshot(
                    image_data=image_data,
                    source=ScreenshotSource.WINDOW,
                    metadata={'window_title': window_title}
                )
        except Exception as e:
            print(f"捕获窗口失败: {e}")
        return None
    
    def capture_region(self, x: int, y: int, width: int, height: int) -> Optional[Screenshot]:
        """捕获指定区域"""
        try:
            import pyautogui
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            
            import io
            buffer = io.BytesIO()
            screenshot.save(buffer, format='PNG')
            image_data = buffer.getvalue()
            
            return Screenshot(
                image_data=image_data,
                source=ScreenshotSource.REGION,
                metadata={'region': (x, y, width, height)}
            )
        except Exception as e:
            print(f"捕获区域失败: {e}")
            return None
    
    def save_screenshot(self, screenshot: Screenshot, path: str) -> bool:
        """保存截图"""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(screenshot.image_data)
            return True
        except Exception as e:
            print(f"保存截图失败: {e}")
            return False


class UIAnalyzer:
    """UI分析器"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    async def analyze_screenshot(self, screenshot: Screenshot) -> List[UIElement]:
        """分析截图中的UI元素"""
        elements = []
        
        # 这里使用简化的分析方法
        # 实际项目中可以使用OCR和计算机视觉技术
        elements.append(UIElement(
            element_type=UIElements.BUTTON,
            x=100,
            y=100,
            width=100,
            height=40,
            text="Submit",
            confidence=0.9
        ))
        
        elements.append(UIElement(
            element_type=UIElements.TEXT_INPUT,
            x=100,
            y=50,
            width=200,
            height=30,
            text="Input field",
            confidence=0.85
        ))
        
        return elements
    
    async def recognize_text(self, screenshot: Screenshot) -> str:
        """识别截图中的文本"""
        try:
            import pytesseract
            from PIL import Image
            import io
            
            image = Image.open(io.BytesIO(screenshot.image_data))
            text = pytesseract.image_to_string(image)
            return text
        except Exception as e:
            print(f"文本识别失败: {e}")
            return ""


class CodeGenerator:
    """代码生成器"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.templates = {
            "react": {
                "button": "<button className=\"btn\">{text}</button>",
                "text_input": "<input type=\"text\" className=\"input\" placeholder=\"{text}\" />",
                "label": "<label>{text}</label>",
                "form": "<form className=\"form\">{content}</form>",
                "container": "<div className=\"container\">{content}</div>"
            },
            "vue": {
                "button": "<button class=\"btn\">{text}</button>",
                "text_input": "<input type=\"text\" class=\"input\" placeholder=\"{text}\" />",
                "label": "<label>{text}</label>",
                "form": "<form class=\"form\">{content}</form>",
                "container": "<div class=\"container\">{content}</div>"
            },
            "html": {
                "button": "<button>{text}</button>",
                "text_input": "<input type=\"text\" placeholder=\"{text}\" />",
                "label": "<label>{text}</label>",
                "form": "<form>{content}</form>",
                "container": "<div>{content}</div>"
            }
        }
    
    async def generate_code(self, elements: List[UIElement], framework: str = "react") -> CodeGenerationResult:
        """根据UI元素生成代码"""
        if framework not in self.templates:
            framework = "react"
        
        template = self.templates[framework]
        content = []
        
        for element in elements:
            if element.element_type == UIElements.BUTTON:
                content.append(template["button"].format(text=element.text))
            elif element.element_type == UIElements.TEXT_INPUT:
                content.append(template["text_input"].format(text=element.text))
            elif element.element_type == UIElements.LABEL:
                content.append(template["label"].format(text=element.text))
        
        code = template["container"].format(content="\n        ".join(content))
        
        # 添加完整的组件结构
        if framework == "react":
            code = f"import React from 'react';\n\nconst UIPage = () => {{\n    return (\n        {code}\n    );\n}};\n\nexport default UIPage;"
        elif framework == "vue":
            code = f"<template>\n    {code}\n</template>\n\n<script>\nexport default {{\n    name: 'UIPage'\n}}\n</script>"
        elif framework == "html":
            code = f"<!DOCTYPE html>\n<html>\n<head>\n    <title>UI Page</title>\n</head>\n<body>\n    {code}\n</body>\n</html>"
        
        return CodeGenerationResult(
            code=code,
            language="javascript" if framework in ["react", "vue"] else "html",
            framework=framework,
            elements=elements,
            confidence=0.8
        )
    
    async def generate_with_llm(self, screenshot: Screenshot, framework: str = "react") -> CodeGenerationResult:
        """使用LLM生成代码"""
        if not self.llm_client:
            # 使用模板生成
            analyzer = UIAnalyzer()
            elements = await analyzer.analyze_screenshot(screenshot)
            return await self.generate_code(elements, framework)
        
        # 使用LLM生成
        try:
            # 将截图转换为base64
            base64_image = base64.b64encode(screenshot.image_data).decode('utf-8')
            
            prompt = f"""根据以下UI截图生成{framework}代码：

请分析截图中的UI元素，并生成完整的{framework}组件代码。

要求：
1. 生成完整的组件结构
2. 包含所有可见的UI元素
3. 使用合理的类名和结构
4. 确保代码可以直接使用

请只返回代码，不要包含解释。"""
            
            code = await self.llm_client.generate(prompt, images=[base64_image])
            
            return CodeGenerationResult(
                code=code,
                language="javascript" if framework in ["react", "vue"] else "html",
                framework=framework,
                confidence=0.9
            )
        except Exception as e:
            print(f"LLM生成代码失败: {e}")
            # 回退到模板生成
            analyzer = UIAnalyzer()
            elements = await analyzer.analyze_screenshot(screenshot)
            return await self.generate_code(elements, framework)


class MultimodalManager:
    """多模态管理器"""
    
    def __init__(self, llm_client=None):
        self.screenshot_manager = ScreenshotManager()
        self.ui_analyzer = UIAnalyzer(llm_client)
        self.code_generator = CodeGenerator(llm_client)
    
    async def capture_and_generate(self, source: ScreenshotSource, framework: str = "react", **kwargs) -> Optional[CodeGenerationResult]:
        """捕获截图并生成代码"""
        if source == ScreenshotSource.SCREEN:
            screenshot = self.screenshot_manager.capture_screen()
        elif source == ScreenshotSource.WINDOW:
            window_title = kwargs.get('window_title', '')
            screenshot = self.screenshot_manager.capture_window(window_title)
        elif source == ScreenshotSource.REGION:
            x = kwargs.get('x', 0)
            y = kwargs.get('y', 0)
            width = kwargs.get('width', 800)
            height = kwargs.get('height', 600)
            screenshot = self.screenshot_manager.capture_region(x, y, width, height)
        else:
            return None
        
        if not screenshot:
            return None
        
        # 分析截图
        elements = await self.ui_analyzer.analyze_screenshot(screenshot)
        
        # 生成代码
        result = await self.code_generator.generate_code(elements, framework)
        
        return result
    
    async def process_image(self, image_path: str, framework: str = "react") -> Optional[CodeGenerationResult]:
        """处理已有图片"""
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            screenshot = Screenshot(
                image_data=image_data,
                source=ScreenshotSource.SCREEN
            )
            
            # 分析截图
            elements = await self.ui_analyzer.analyze_screenshot(screenshot)
            
            # 生成代码
            result = await self.code_generator.generate_code(elements, framework)
            
            return result
        except Exception as e:
            print(f"处理图片失败: {e}")
            return None
    
    async def generate_from_text(self, text_description: str, framework: str = "react") -> Optional[CodeGenerationResult]:
        """从文本描述生成代码"""
        try:
            if not self.code_generator.llm_client:
                return None
            
            prompt = f"""根据以下文本描述生成{framework}代码：

{text_description}

要求：
1. 生成完整的组件结构
2. 包含所有描述的UI元素
3. 使用合理的类名和结构
4. 确保代码可以直接使用

请只返回代码，不要包含解释。"""
            
            code = await self.code_generator.llm_client.generate(prompt)
            
            return CodeGenerationResult(
                code=code,
                language="javascript" if framework in ["react", "vue"] else "html",
                framework=framework,
                confidence=0.85
            )
        except Exception as e:
            print(f"从文本生成代码失败: {e}")
            return None


def create_multimodal_manager(llm_client=None) -> MultimodalManager:
    """
    创建多模态管理器
    
    Args:
        llm_client: LLM客户端
        
    Returns:
        MultimodalManager: 多模态管理器实例
    """
    return MultimodalManager(llm_client)