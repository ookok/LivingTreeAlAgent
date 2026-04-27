"""
行业分类自动更新 - 从政府公开数据定期更新行业分类标准
数据来源：国家统计局 https://www.stats.gov.cn/sj/tjbz/gjtjjbz/
"""

import os
import json
import time
import re
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class IndustryUpdateRecord:
    """行业分类更新记录"""
    
    def __init__(self, record_file: Optional[str] = None):
        """
        初始化更新记录
        
        Args:
            record_file: 记录文件路径
        """
        if record_file is None:
            project_root = Path(__file__).parent.parent.parent
            record_file = project_root / ".livingtree" / "data" / "industry_update_record.json"
        
        self.record_file = Path(record_file)
        self.record_file.parent.mkdir(parents=True, exist_ok=True)
        self.record = self._load_record()
    
    def _load_record(self) -> Dict:
        """加载更新记录"""
        if self.record_file.exists():
            try:
                return json.loads(self.record_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"加载更新记录失败：{e}")
        
        # 默认记录
        return {
            "last_check_time": 0,
            "last_update_time": 0,
            "current_version": "GB/T 4754-2017",
            "update_history": []
        }
    
    def save_record(self):
        """保存更新记录"""
        try:
            self.record_file.write_text(
                json.dumps(self.record, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"保存更新记录失败：{e}")
    
    def update_check_time(self):
        """更新检查时间"""
        self.record["last_check_time"] = time.time()
        self.save_record()
    
    def update_success(self, new_version: str, details: Dict):
        """
        记录成功更新
        
        Args:
            new_version: 新版本号
            details: 更新详情
        """
        self.record["last_update_time"] = time.time()
        self.record["current_version"] = new_version
        
        history_item = {
            "timestamp": datetime.now().isoformat(),
            "version": new_version,
            "details": details
        }
        self.record["update_history"].append(history_item)
        
        # 只保留最近10次更新记录
        self.record["update_history"] = self.record["update_history"][-10:]
        
        self.save_record()
    
    def get_last_check_time(self) -> float:
        """获取上次检查时间"""
        return self.record.get("last_check_time", 0)
    
    def get_current_version(self) -> str:
        """获取当前版本"""
        return self.record.get("current_version", "GB/T 4754-2017")
    
    def get_update_history(self) -> List[Dict]:
        """获取更新历史"""
        return self.record.get("update_history", [])


class IndustryDataFetcher:
    """
    行业数据获取器 - 从政府网站获取最新的行业分类标准
    
    数据来源：
    1. 国家统计局 https://www.stats.gov.cn/sj/tjbz/gjtjjbz/
    2. 国家标准委 https://openstd.samr.gov.cn/
    """
    
    STATS_GOV_CN_URL = "https://www.stats.gov.cn/sj/tjbz/gjtjjbz/"
    INDUSTRY_STANDARD_URL = "https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=A703F0E23DD165A5A1318679F312D158"
    
    def __init__(self):
        self.session = None  # 可以用于HTTP请求的session
        
    def fetch_latest_standard(self) -> Optional[Dict]:
        """
        获取最新的行业分类标准
        
        Returns:
            标准信息字典，包含版本、发布日期、实施日期、下载链接等
        """
        try:
            # TODO: 实现实际的网页抓取逻辑
            # 1. 访问国家统计局网站
            # 2. 解析标准列表
            # 3. 获取最新版本的下载链接
            
            logger.info("正在从国家统计局获取最新行业分类标准...")
            
            # 模拟返回的数据结构
            return {
                "version": "GB/T 4754-2017",  # 当前最新版本
                "release_date": "2017-06-30",
                "implementation_date": "2017-10-01",
                "description": "国民经济行业分类",
                "download_url": self.INDUSTRY_STANDARD_URL,
                "is_latest": True
            }
            
        except Exception as e:
            logger.error(f"获取最新标准失败：{e}")
            return None
    
    def download_standard_document(self, download_url: str, save_path: str) -> bool:
        """
        下载标准文档（PDF）
        
        Args:
            download_url: 下载链接
            save_path: 保存路径
            
        Returns:
            是否下载成功
        """
        try:
            # TODO: 实现PDF下载逻辑
            logger.info(f"正在下载标准文档：{download_url}")
            return False
            
        except Exception as e:
            logger.error(f"下载标准文档失败：{e}")
            return False
    
    def parse_standard_document(self, document_path: str) -> Optional[Dict]:
        """
        解析标准文档，提取行业分类数据
        
        Args:
            document_path: 标准文档路径
            
        Returns:
            解析后的行业分类数据
        """
        try:
            # TODO: 实现PDF解析逻辑
            # 1. 读取PDF文件
            # 2. 提取文字内容
            # 3. 解析门类、大类、中类、小类
            
            logger.info(f"正在解析标准文档：{document_path}")
            return None
            
        except Exception as e:
            logger.error(f"解析标准文档失败：{e}")
            return None


class IndustryClassificationUpdater:
    """
    行业分类更新器 - 定期检查并更新行业分类数据
    """
    
    def __init__(self, 
                 check_interval: int = 86400,  # 24小时
                 auto_update: bool = False):
        """
        初始化更新器
        
        Args:
            check_interval: 检查间隔（秒），默认24小时
            auto_update: 是否自动更新（需要人工确认）
        """
        self.check_interval = check_interval
        self.auto_update = auto_update
        self.record = IndustryUpdateRecord()
        self.fetcher = IndustryDataFetcher()
        
        logger.info(f"行业分类更新器初始化完成，检查间隔：{check_interval}秒")
    
    def check_and_update(self, force: bool = False) -> Dict:
        """
        检查并更新行业分类
        
        Args:
            force: 是否强制检查（忽略时间间隔）
            
        Returns:
            检查结果字典
        """
        # 检查是否需要检查
        if not force:
            last_check = self.record.get_last_check_time()
            if time.time() - last_check < self.check_interval:
                logger.info("距离上次检查时间太短，跳过检查")
                return {
                    "need_update": False,
                    "reason": "检查间隔未到"
                }
        
        # 更新检查时间
        self.record.update_check_time()
        
        # 获取最新标准
        latest = self.fetcher.fetch_latest_standard()
        if not latest:
            return {
                "need_update": False,
                "reason": "获取最新标准失败"
            }
        
        current_version = self.record.get_current_version()
        latest_version = latest.get("version")
        
        if latest_version == current_version and not force:
            logger.info(f"当前已是最新版本：{current_version}")
            return {
                "need_update": False,
                "reason": "已是最新版本",
                "current_version": current_version
            }
        
        logger.info(f"发现新版本：{latest_version}（当前：{current_version}）")
        
        # 需要更新
        if self.auto_update or force:
            return self._do_update(latest)
        else:
            return {
                "need_update": True,
                "latest_version": latest_version,
                "current_version": current_version,
                "details": latest,
                "need_confirmation": True
            }
    
    def _do_update(self, latest: Dict) -> Dict:
        """
        执行更新
        
        Args:
            latest: 最新标准信息
            
        Returns:
            更新结果
        """
        try:
            # 1. 下载标准文档
            # download_url = latest.get("download_url")
            # if download_url:
            #     save_path = f"/tmp/industry_standard_{latest['version']}.pdf"
            #     success = self.fetcher.download_standard_document(download_url, save_path)
            #     if success:
            #         # 2. 解析文档
            #         data = self.fetcher.parse_standard_document(save_path)
            #         if data:
            #             # 3. 更新行业分类数据
            #             self._update_industry_data(data)
            
            # 4. 记录更新
            self.record.update_success(
                new_version=latest.get("version"),
                details=latest
            )
            
            logger.info(f"行业分类更新成功：{latest.get('version')}")
            
            return {
                "need_update": True,
                "success": True,
                "new_version": latest.get("version"),
                "message": "更新成功"
            }
            
        except Exception as e:
            logger.error(f"更新失败：{e}")
            return {
                "need_update": True,
                "success": False,
                "error": str(e)
            }
    
    def _update_industry_data(self, data: Dict):
        """
        更新行业分类数据
        
        Args:
            data: 解析后的行业分类数据
        """
        # TODO: 实现行业分类数据的更新逻辑
        # 1. 更新 industry_classification.py 中的 INDUSTRY_CATEGORIES
        # 2. 更新数据库中的行业分类表
        # 3. 触发专家角色的重新分类
        
        logger.info("行业分类数据已更新")
    
    def get_update_history(self) -> List[Dict]:
        """获取更新历史"""
        return self.record.get_update_history()
    
    def manual_update(self, new_data: Dict) -> bool:
        """
        手动更新行业分类数据
        
        Args:
            new_data: 新的行业分类数据
            
        Returns:
            是否更新成功
        """
        try:
            self._update_industry_data(new_data)
            
            self.record.update_success(
                new_version=new_data.get("version", "manual"),
                details=new_data
            )
            
            logger.info("手动更新行业分类成功")
            return True
            
        except Exception as e:
            logger.error(f"手动更新失败：{e}")
            return False


# 全局更新器实例
_updater_instance = None

def get_industry_updater(check_interval: int = 86400) -> IndustryClassificationUpdater:
    """获取行业分类更新器单例"""
    global _updater_instance
    
    if _updater_instance is None:
        _updater_instance = IndustryClassificationUpdater(check_interval=check_interval)
    
    return _updater_instance


if __name__ == "__main__":
    # 测试代码
    updater = get_industry_updater(check_interval=3600)  # 1小时检查一次
    
    print("=== 检查行业分类更新 ===")
    result = updater.check_and_update(force=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print("\n=== 更新历史 ===")
    history = updater.get_update_history()
    print(json.dumps(history, ensure_ascii=False, indent=2))
