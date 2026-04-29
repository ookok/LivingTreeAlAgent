"""
文件预览模块
File Preview Module

支持常见文件格式的在线预览
from __future__ import annotations
"""


import os
import mimetypes
from typing import Dict, Optional, Any
from pathlib import Path


class FilePreviewer:
    """文件预览器"""

    def __init__(self):
        self.supported_formats = {
            "text": ["txt", "md", "json", "xml", "html", "css", "js", "py", "java", "c", "cpp", "h", "hpp"],
            "image": ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
            "pdf": ["pdf"],
            "office": ["doc", "docx", "xls", "xlsx", "ppt", "pptx"],
            "video": ["mp4", "avi", "mov", "wmv", "flv", "mkv"],
            "audio": ["mp3", "wav", "ogg", "flac", "aac"]
        }

    def can_preview(self, file_path: str) -> bool:
        """检查文件是否可预览"""
        ext = Path(file_path).suffix.lower().lstrip('.')
        for format_type, extensions in self.supported_formats.items():
            if ext in extensions:
                return True
        return False

    def get_preview_type(self, file_path: str) -> Optional[str]:
        """获取预览类型"""
        ext = Path(file_path).suffix.lower().lstrip('.')
        for format_type, extensions in self.supported_formats.items():
            if ext in extensions:
                return format_type
        return None

    def generate_preview(self, file_path: str, local_path: str) -> Dict[str, Any]:
        """生成文件预览"""
        preview_type = self.get_preview_type(file_path)
        if not preview_type:
            return {
                "success": False,
                "message": "File format not supported for preview"
            }

        try:
            if preview_type == "text":
                return self._preview_text(local_path)
            elif preview_type == "image":
                return self._preview_image(local_path)
            elif preview_type == "pdf":
                return self._preview_pdf(local_path)
            elif preview_type == "office":
                return self._preview_office(local_path)
            elif preview_type == "video":
                return self._preview_video(local_path)
            elif preview_type == "audio":
                return self._preview_audio(local_path)
            else:
                return {
                    "success": False,
                    "message": "Preview not implemented for this format"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error generating preview: {str(e)}"
            }

    def _preview_text(self, local_path: str) -> Dict[str, Any]:
        """预览文本文件"""
        try:
            with open(local_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return {
                "success": True,
                "type": "text",
                "content": content,
                "size": len(content)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error reading text file: {str(e)}"
            }

    def _preview_image(self, local_path: str) -> Dict[str, Any]:
        """预览图片文件"""
        try:
            import base64
            with open(local_path, 'rb') as f:
                image_data = f.read()
            base64_data = base64.b64encode(image_data).decode('utf-8')
            mime_type = mimetypes.guess_type(local_path)[0] or 'image/*'
            return {
                "success": True,
                "type": "image",
                "data": base64_data,
                "mime_type": mime_type
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error reading image file: {str(e)}"
            }

    def _preview_pdf(self, local_path: str) -> Dict[str, Any]:
        """预览PDF文件"""
        try:
            # 这里简化处理，实际应该使用PDF库提取内容或生成预览
            return {
                "success": True,
                "type": "pdf",
                "message": "PDF preview is available",
                "file_size": os.path.getsize(local_path)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing PDF file: {str(e)}"
            }

    def _preview_office(self, local_path: str) -> Dict[str, Any]:
        """预览Office文件"""
        try:
            # 这里简化处理，实际应该使用Office库提取内容
            ext = Path(local_path).suffix.lower().lstrip('.')
            return {
                "success": True,
                "type": "office",
                "format": ext,
                "message": "Office file preview is available",
                "file_size": os.path.getsize(local_path)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing Office file: {str(e)}"
            }

    def _preview_video(self, local_path: str) -> Dict[str, Any]:
        """预览视频文件"""
        try:
            return {
                "success": True,
                "type": "video",
                "message": "Video preview is available",
                "file_size": os.path.getsize(local_path),
                "mime_type": mimetypes.guess_type(local_path)[0] or 'video/*'
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing video file: {str(e)}"
            }

    def _preview_audio(self, local_path: str) -> Dict[str, Any]:
        """预览音频文件"""
        try:
            return {
                "success": True,
                "type": "audio",
                "message": "Audio preview is available",
                "file_size": os.path.getsize(local_path),
                "mime_type": mimetypes.guess_type(local_path)[0] or 'audio/*'
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing audio file: {str(e)}"
            }

    def get_supported_formats(self) -> Dict[str, List[str]]:
        """获取支持的文件格式"""
        return self.supported_formats


# 单例
file_previewer = FilePreviewer()


def get_file_previewer() -> FilePreviewer:
    """获取文件预览器"""
    return file_previewer
