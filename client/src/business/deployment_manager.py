#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
部署管理器 - 自动化部署
=====================

功能：
1. 读取部署配置（deploy.yaml）
2. 执行部署脚本
3. 部署历史记录
4. 回滚支持
5. 多环境部署（dev/test/prod）

Author: LivingTreeAI Agent
Date: 2026-04-26
"""

import os
import sys
import subprocess
import yaml
import json
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime


# ── 数据结构 ─────────────────────────────────────────────────────

@dataclass
class DeploymentConfig:
    """部署配置"""
    name: str
    environment: str  # dev, test, prod
    deploy_type: str  # docker, script, ssh, kubernetes
    target_path: str
    commands: List[str]
    pre_commands: List[str] = field(default_factory=list)
    post_commands: List[str] = field(default_factory=list)
    rollback_commands: List[str] = field(default_factory=list)
    timeout: int = 300  # 秒


@dataclass
class DeploymentResult:
    """部署结果"""
    success: bool
    environment: str
    start_time: datetime
    end_time: datetime
    output: str = ""
    error: str = ""
    rollback_available: bool = False


# ── 部署管理器 ─────────────────────────────────────────────────

class DeploymentManager:
    """
    部署管理器
    
    功能：
    1. 读取部署配置
    2. 执行部署
    3. 记录历史
    4. 回滚
    """
    
    def __init__(self, project_root: str):
        """
        初始化部署管理器
        
        Args:
            project_root: 项目根目录
        """
        self.project_root = project_root
        self.config_file = os.path.join(project_root, "deploy.yaml")
        self.history_file = os.path.join(project_root, ".deploy_history.json")
        self.configs: List[DeploymentConfig] = []
        self.history: List[Dict] = []
        
        self._load_config()
        self._load_history()
    
    def _load_config(self):
        """加载部署配置"""
        if not os.path.exists(self.config_file):
            # 创建默认配置
            self._create_default_config()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if config_data and 'deployments' in config_data:
                for dep in config_data['deployments']:
                    self.configs.append(DeploymentConfig(**dep))
        
        except Exception as e:
            print(f"加载部署配置失败: {e}")
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认部署配置"""
        default_config = {
            'deployments': [
                {
                    'name': 'Development',
                    'environment': 'dev',
                    'deploy_type': 'script',
                    'target_path': './',
                    'commands': [
                        'echo "开发环境部署"',
                        'python main.py client',
                    ],
                    'pre_commands': [
                        'echo "开始部署..."',
                    ],
                    'post_commands': [
                        'echo "部署完成!"',
                    ],
                    'rollback_commands': [
                        'echo "回滚..."',
                    ],
                },
                {
                    'name': 'Docker',
                    'environment': 'docker',
                    'deploy_type': 'docker',
                    'target_path': './',
                    'commands': [
                        'docker build -t livingtree:latest .',
                        'docker run -d -p 8899:8899 livingtree:latest',
                    ],
                    'pre_commands': [
                        'docker stop livingtree || true',
                        'docker rm livingtree || true',
                    ],
                    'post_commands': [
                        'echo "Docker 容器已启动"',
                    ],
                    'rollback_commands': [
                        'docker rollback livingtree:latest',
                    ],
                },
            ]
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
            
            # 重新加载
            self.configs = []
            for dep in default_config['deployments']:
                self.configs.append(DeploymentConfig(**dep))
        
        except Exception as e:
            print(f"创建默认配置失败: {e}")
    
    def _load_history(self):
        """加载部署历史"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []
    
    def _save_history(self):
        """保存部署历史"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存部署历史失败: {e}")
    
    def get_configs(self) -> List[DeploymentConfig]:
        """
        获取所有部署配置
        
        Returns:
            List[DeploymentConfig]: 部署配置列表
        """
        return self.configs
    
    def get_config(self, name: str) -> Optional[DeploymentConfig]:
        """
        获取指定名称的部署配置
        
        Args:
            name: 配置名称
            
        Returns:
            Optional[DeploymentConfig]: 部署配置，如果不存在则返回 None
        """
        for config in self.configs:
            if config.name == name:
                return config
        return None
    
    def deploy(
        self,
        config_name: str,
        dry_run: bool = False
    ) -> DeploymentResult:
        """
        执行部署
        
        Args:
            config_name: 配置名称
            dry_run: 是否仅模拟运行（不实际执行）
            
        Returns:
            DeploymentResult: 部署结果
        """
        config = self.get_config(config_name)
        
        if not config:
            return DeploymentResult(
                success=False,
                environment=config_name,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error=f"找不到部署配置: {config_name}",
            )
        
        start_time = datetime.now()
        output = ""
        error = ""
        success = True
        
        try:
            # 执行前置命令
            if config.pre_commands:
                output += "── 前置命令 ──\n"
                for cmd in config.pre_commands:
                    output += f"$ {cmd}\n"
                    if not dry_run:
                        result = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            cwd=self.project_root,
                            timeout=config.timeout,
                        )
                        output += result.stdout
                        if result.stderr:
                            output += result.stderr
                        if result.returncode != 0:
                            success = False
                            error = f"前置命令失败: {cmd}"
                            break
                    else:
                        output += "(dry run)\n"
            
            # 执行部署命令
            if success:
                output += "\n── 部署命令 ──\n"
                for cmd in config.commands:
                    output += f"$ {cmd}\n"
                    if not dry_run:
                        result = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            cwd=self.project_root,
                            timeout=config.timeout,
                        )
                        output += result.stdout
                        if result.stderr:
                            output += result.stderr
                        if result.returncode != 0:
                            success = False
                            error = f"部署命令失败: {cmd}"
                            break
                    else:
                        output += "(dry run)\n"
            
            # 执行后置命令
            if success and config.post_commands:
                output += "\n── 后置命令 ──\n"
                for cmd in config.post_commands:
                    output += f"$ {cmd}\n"
                    if not dry_run:
                        result = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            cwd=self.project_root,
                            timeout=config.timeout,
                        )
                        output += result.stdout
                        if result.stderr:
                            output += result.stderr
                    else:
                        output += "(dry run)\n"
        
        except subprocess.TimeoutExpired:
            success = False
            error = f"部署超时（>{config.timeout}秒）"
        except Exception as e:
            success = False
            error = str(e)
        
        end_time = datetime.now()
        
        # 记录历史
        history_entry = {
            'config_name': config_name,
            'environment': config.environment,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'success': success,
            'output': output,
            'error': error,
        }
        self.history.append(history_entry)
        self._save_history()
        
        return DeploymentResult(
            success=success,
            environment=config.environment,
            start_time=start_time,
            end_time=end_time,
            output=output,
            error=error,
            rollback_available=len(config.rollback_commands) > 0,
        )
    
    def rollback(self, config_name: str) -> DeploymentResult:
        """
        回滚部署
        
        Args:
            config_name: 配置名称
            
        Returns:
            DeploymentResult: 回滚结果
        """
        config = self.get_config(config_name)
        
        if not config:
            return DeploymentResult(
                success=False,
                environment=config_name,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error=f"找不到部署配置: {config_name}",
            )
        
        if not config.rollback_commands:
            return DeploymentResult(
                success=False,
                environment=config.environment,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error="该配置没有定义回滚命令",
            )
        
        start_time = datetime.now()
        output = "── 回滚命令 ──\n"
        error = ""
        success = True
        
        try:
            for cmd in config.rollback_commands:
                output += f"$ {cmd}\n"
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                    timeout=config.timeout,
                )
                output += result.stdout
                if result.stderr:
                    output += result.stderr
                if result.returncode != 0:
                    success = False
                    error = f"回滚命令失败: {cmd}"
                    break
        
        except Exception as e:
            success = False
            error = str(e)
        
        end_time = datetime.now()
        
        # 记录历史
        history_entry = {
            'config_name': config_name,
            'environment': config.environment,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'success': success,
            'output': output,
            'error': error,
            'is_rollback': True,
        }
        self.history.append(history_entry)
        self._save_history()
        
        return DeploymentResult(
            success=success,
            environment=config.environment,
            start_time=start_time,
            end_time=end_time,
            output=output,
            error=error,
            rollback_available=False,
        )
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """
        获取部署历史
        
        Args:
            limit: 返回的记录数
            
        Returns:
            List[Dict]: 部署历史列表
        """
        return self.history[-limit:][::-1]  # 返回最近的记录，按时间倒序


# ── 测试 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # 测试部署管理器
    project_root = str(Path(__file__).parent.parent)
    manager = DeploymentManager(project_root)
    
    print("=" * 60)
    print("部署配置列表")
    print("=" * 60)
    
    configs = manager.get_configs()
    for config in configs:
        print(f"\n配置: {config.name}")
        print(f"  环境: {config.environment}")
        print(f"  类型: {config.deploy_type}")
        print(f"  命令数: {len(config.commands)}")
    
    print("\n" + "=" * 60)
    print("测试部署（dry run）")
    print("=" * 60)
    
    if configs:
        result = manager.deploy(configs[0].name, dry_run=True)
        print(f"\n成功: {result.success}")
        print(f"输出:\n{result.output}")
        if result.error:
            print(f"错误:\n{result.error}")
    
    print("\n" + "=" * 60)
    print("部署历史")
    print("=" * 60)
    
    history = manager.get_history(limit=5)
    for entry in history:
        status = "✅" if entry['success'] else "❌"
        print(f"{status} {entry['config_name']} - {entry['start_time']}")
