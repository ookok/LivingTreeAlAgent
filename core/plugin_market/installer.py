# -*- coding: utf-8 -*-
"""
插件安装器 - Plugin Installer
"""

from __future__ import annotations
import hashlib
import logging
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


class PluginInstaller:
    """
    插件安装器
    
    处理插件的下载、解压、验证和安装
    """
    
    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self.temp_dir = Path(tempfile.gettempdir()) / "livingtree_plugins"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 回调
        self._on_progress: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
    
    def set_progress_callback(self, callback: Callable[[str, float], None]):
        """设置进度回调"""
        self._on_progress = callback
    
    def set_error_callback(self, callback: Callable[[str, Exception], None]):
        """设置错误回调"""
        self._on_error = callback
    
    def _report_progress(self, message: str, progress: float):
        """报告进度"""
        if self._on_progress:
            self._on_progress(message, progress)
    
    def _report_error(self, message: str, error: Exception):
        """报告错误"""
        if self._on_error:
            self._on_error(message, error)
        else:
            logger.error(f"{message}: {error}")
    
    # ── 安装流程 ──────────────────────────────────────────────────────────────
    
    def install(
        self,
        plugin_id: str,
        download_url: str,
        version: str,
        permissions: List[str],
        expected_checksum: Optional[str] = None
    ) -> bool:
        """
        安装插件
        
        Args:
            plugin_id: 插件ID
            download_url: 下载地址
            version: 版本号
            permissions: 所需权限
            expected_checksum: 预期校验和
            
        Returns:
            是否安装成功
        """
        plugin_dir = self.plugins_dir / plugin_id
        temp_file = self.temp_dir / f"{plugin_id}_{version}.zip"
        
        try:
            # 1. 下载
            self._report_progress("正在下载插件...", 0.1)
            if not self._download(download_url, temp_file):
                raise Exception("Download failed")
            
            # 2. 验证
            self._report_progress("正在验证插件...", 0.3)
            if expected_checksum:
                if not self._verify_checksum(temp_file, expected_checksum):
                    raise Exception("Checksum verification failed")
            
            # 3. 解压
            self._report_progress("正在安装插件...", 0.5)
            if not self._extract(temp_file, plugin_dir):
                raise Exception("Extraction failed")
            
            # 4. 验证权限
            self._report_progress("正在检查权限...", 0.8)
            if not self._check_permissions(plugin_dir, permissions):
                raise Exception("Permission check failed")
            
            # 5. 完成
            self._report_progress("安装完成", 1.0)
            
            # 清理临时文件
            if temp_file.exists():
                temp_file.unlink()
            
            logger.info(f"Plugin installed: {plugin_id}")
            return True
            
        except Exception as e:
            self._report_error(f"Installation failed for {plugin_id}", e)
            
            # 清理
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
            if temp_file.exists():
                temp_file.unlink()
            
            return False
    
    def uninstall(self, plugin_id: str) -> bool:
        """
        卸载插件
        """
        plugin_dir = self.plugins_dir / plugin_id
        
        if not plugin_dir.exists():
            return True
        
        try:
            # 删除插件目录
            shutil.rmtree(plugin_dir)
            logger.info(f"Plugin uninstalled: {plugin_id}")
            return True
            
        except Exception as e:
            self._report_error(f"Uninstallation failed for {plugin_id}", e)
            return False
    
    def update(
        self,
        plugin_id: str,
        download_url: str,
        version: str,
        expected_checksum: Optional[str] = None
    ) -> bool:
        """
        更新插件
        """
        plugin_dir = self.plugins_dir / plugin_id
        backup_dir = self.temp_dir / f"{plugin_id}_backup"
        
        try:
            # 备份
            if plugin_dir.exists():
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                shutil.move(str(plugin_dir), str(backup_dir))
            
            # 安装新版本
            success = self.install(
                plugin_id=plugin_id,
                download_url=download_url,
                version=version,
                permissions=[],
                expected_checksum=expected_checksum
            )
            
            if not success:
                # 恢复备份
                if backup_dir.exists():
                    if plugin_dir.exists():
                        shutil.rmtree(plugin_dir)
                    shutil.move(str(backup_dir), str(plugin_dir))
                return False
            
            # 删除备份
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            
            return True
            
        except Exception as e:
            self._report_error(f"Update failed for {plugin_id}", e)
            
            # 恢复备份
            if backup_dir.exists() and not plugin_dir.exists():
                shutil.move(str(backup_dir), str(plugin_dir))
            
            return False
    
    # ── 内部方法 ─────────────────────────────────────────────────────────────
    
    def _download(self, url: str, dest: Path) -> bool:
        """下载文件"""
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                
                with open(dest, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size:
                            progress = 0.3 * downloaded / total_size + 0.1
                            self._report_progress(
                                f"下载中... ({downloaded / 1024 / 1024:.1f} MB)",
                                progress
                            )
            
            return True
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
    
    def _verify_checksum(self, file_path: Path, expected: str) -> bool:
        """验证校验和"""
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        
        actual = sha256.hexdigest()
        
        if actual != expected:
            logger.error(f"Checksum mismatch: expected {expected}, got {actual}")
            return False
        
        return True
    
    def _extract(self, zip_path: Path, dest_dir: Path) -> bool:
        """解压文件"""
        try:
            # 清理目标目录
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(dest_dir)
            
            return True
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return False
    
    def _check_permissions(self, plugin_dir: Path, required: List[str]) -> bool:
        """
        检查权限
        
        检查插件是否请求了危险权限
        """
        dangerous_permissions = {
            'file:write:any',      # 写入任意文件
            'exec',                 # 执行命令
            'network:all',         # 访问任意网络
            'system',              # 系统权限
        }
        
        # 简单检查：如果需要危险权限，记录警告
        for perm in required:
            if perm in dangerous_permissions:
                logger.warning(f"Plugin requests dangerous permission: {perm}")
        
        return True
    
    # ── 工具方法 ─────────────────────────────────────────────────────────────
    
    def get_installed_version(self, plugin_id: str) -> Optional[str]:
        """获取已安装版本"""
        manifest_file = self.plugins_dir / plugin_id / "manifest.json"
        
        if not manifest_file.exists():
            return None
        
        try:
            import json
            with open(manifest_file, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            return manifest.get('version')
        except:
            return None
    
    def validate_plugin(self, plugin_dir: Path) -> Dict:
        """验证插件"""
        manifest_file = plugin_dir / "manifest.json"
        
        if not manifest_file.exists():
            return {"valid": False, "error": "Missing manifest.json"}
        
        try:
            import json
            with open(manifest_file, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            # 必需字段
            required = ['name', 'version', 'main']
            for field in required:
                if field not in manifest:
                    return {"valid": False, "error": f"Missing required field: {field}"}
            
            return {
                "valid": True,
                "name": manifest.get('name'),
                "version": manifest.get('version'),
                "permissions": manifest.get('permissions', [])
            }
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
