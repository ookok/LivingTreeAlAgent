"""
Map Agent主控制器 - 协调所有地图操作

核心功能：
1. 管理三种交互模式（Auto-Pilot、Co-Pilot、Sketch-to-Data）
2. 协调五个原子工具
3. 处理地图与文档的双向链接
4. 支持空间技能进化

交互模式：
- Auto-Pilot: 全自动批处理
- Co-Pilot: AI建议 + 人工修正
- Sketch-to-Data: 手绘驱动生成
"""
import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Callable

from .tools.perception_tool import PerceptionTool, SpatialIdentity
from .tools.geometry_tool import GeometryTool, GeometryOperation
from .tools.overlay_analysis_tool import OverlayAnalysisTool, OverlayResult
from .tools.mobility_tool import MobilityTool, RouteAnalysisResult
from .tools.export_tool import ExportTool, ExportFormat, DPILevel


class MapInteractionMode(Enum):
    """地图交互模式"""
    AUTO_PILOT = "auto_pilot"    # 全自动批处理
    CO_PILOT = "co_pilot"        # AI建议 + 人工修正
    SKETCH_TO_DATA = "sketch_to_data"  # 手绘驱动生成


@dataclass
class MapPoint:
    """地图点"""
    id: str
    longitude: float
    latitude: float
    name: str = ""
    type: str = "point"
    color: str = "#FF0000"
    score: float = 0.0  # AI推荐评分


@dataclass
class AIRecommendation:
    """AI建议"""
    points: List[MapPoint] = field(default_factory=list)
    message: str = ""
    confidence: float = 0.0


class MapAgentController:
    """
    Map Agent主控制器
    
    核心能力：
    1. 空间感知
    2. 几何操作
    3. 叠加分析
    4. 路径与可达性分析
    5. 截图与导出
    6. 三种交互模式支持
    """
    
    def __init__(self):
        # 初始化工具
        self.perception_tool = PerceptionTool()
        self.geometry_tool = GeometryTool()
        self.overlay_tool = OverlayAnalysisTool()
        self.mobility_tool = MobilityTool()
        self.export_tool = ExportTool()
        
        # 当前交互模式
        self.current_mode = MapInteractionMode.AUTO_PILOT
        
        # 回调函数
        self.on_recommendation: Optional[Callable[[AIRecommendation], None]] = None
        self.on_analysis_complete: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_map_update: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # 状态
        self.current_project_location = None
        self.recommended_points = []
        self.user_modified_points = {}
    
    # ==================== 模式切换 ====================
    
    def set_mode(self, mode: MapInteractionMode):
        """设置交互模式"""
        self.current_mode = mode
        print(f"切换到模式: {mode.value}")
    
    def get_mode(self) -> MapInteractionMode:
        """获取当前模式"""
        return self.current_mode
    
    # ==================== 空间感知 ====================
    
    def get_spatial_identity(self, longitude: float, latitude: float) -> SpatialIdentity:
        """获取空间身份证"""
        return self.perception_tool.get_spatial_identity(longitude, latitude)
    
    def batch_analyze_locations(self, coordinates: List[Tuple[float, float]]) -> List[SpatialIdentity]:
        """批量分析多个坐标"""
        return self.perception_tool.batch_analyze(coordinates)
    
    # ==================== 几何操作 ====================
    
    def draw_polygon(self, points: List[Tuple[float, float]], name: str = "") -> Dict[str, Any]:
        """画多边形"""
        result = self.geometry_tool.draw_polygon(points, name)
        return {
            "success": result.success,
            "message": result.message,
            "data": result.data
        }
    
    def draw_buffer(self, center: Tuple[float, float], radius: float, name: str = "") -> Dict[str, Any]:
        """画缓冲区"""
        result = self.geometry_tool.draw_buffer(center, radius, name)
        return {
            "success": result.success,
            "message": result.message,
            "data": result.data
        }
    
    def measure_distance(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> Dict[str, Any]:
        """测量距离"""
        result = self.geometry_tool.measure_distance(point1, point2)
        return {
            "success": result.success,
            "message": result.message,
            "data": result.data
        }
    
    def calculate_area(self, polygon_id: str) -> Dict[str, Any]:
        """计算面积"""
        result = self.geometry_tool.calculate_area(polygon_id)
        return {
            "success": result.success,
            "message": result.message,
            "data": result.data
        }
    
    # ==================== 叠加分析 ====================
    
    def analyze_overlap(self, polygon_a: List[Tuple[float, float]], 
                        polygon_b: List[Tuple[float, float]]) -> OverlayResult:
        """分析两个多边形的重叠情况"""
        return self.overlay_tool.overlaps(polygon_a, polygon_b)
    
    def analyze_protection_overlap(self, project_boundary: List[Tuple[float, float]],
                                   protection_area: List[Tuple[float, float]],
                                   protection_name: str = "保护区域") -> OverlayResult:
        """分析项目边界与保护区域的重叠"""
        return self.overlay_tool.analyze_protection_area_overlap(
            project_boundary, protection_area, protection_name
        )
    
    # ==================== 路径与可达性分析 ====================
    
    def calculate_route(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> RouteAnalysisResult:
        """计算路线"""
        return self.mobility_tool.calculate_route(origin, destination)
    
    def analyze_accessibility(self, project_location: Tuple[float, float],
                              sensitive_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """分析可达性"""
        results = self.mobility_tool.analyze_accessibility(project_location, sensitive_points)
        return [
            {
                "name": r.location_name,
                "distance": r.distance,
                "duration": r.duration,
                "accessibility_score": r.accessibility_score
            }
            for r in results
        ]
    
    def analyze_traffic_impact(self, project_location: Tuple[float, float]) -> Dict[str, Any]:
        """交通影响分析"""
        return self.mobility_tool.analyze_traffic_impact(project_location)
    
    # ==================== 导出工具 ====================
    
    def export_map(self, center: Tuple[float, float], zoom: int = 15,
                   width: int = 800, height: int = 600,
                   format: str = "png", dpi: str = "print") -> Dict[str, Any]:
        """导出地图"""
        from .tools.export_tool import MapView, ExportOptions
        
        view = MapView(
            center=center,
            zoom=zoom,
            width=width,
            height=height
        )
        
        format_enum = ExportFormat[format.upper()]
        dpi_enum = DPILevel[dpi.upper()]
        
        options = ExportOptions(
            format=format_enum,
            dpi=dpi_enum,
            include_legend=True,
            include_scale_bar=True,
            include_compass=True
        )
        
        result = self.export_tool.export_map(view, options)
        return {
            "success": result.success,
            "message": result.message,
            "file_path": result.file_path,
            "format": result.format.value,
            "dpi": result.dpi.value
        }
    
    def generate_report_images(self, project_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成报告所需的所有地图图片"""
        results = self.export_tool.generate_report_images(project_data)
        return [
            {
                "success": r.success,
                "message": r.message,
                "file_path": r.file_path,
                "format": r.format.value
            }
            for r in results
        ]
    
    # ==================== 交互模式实现 ====================
    
    def auto_pilot_analyze(self, coordinates: List[Tuple[float, float]]) -> Dict[str, Any]:
        """
        Auto-Pilot模式：全自动批处理
        
        Args:
            coordinates: 坐标列表
        
        Returns:
            分析结果
        """
        print("启动Auto-Pilot模式...")
        
        # 1. 批量分析所有坐标
        identities = self.batch_analyze_locations(coordinates)
        
        # 2. 自动在地图上标点
        for i, identity in enumerate(identities):
            point = MapPoint(
                id=f"point_{i}",
                longitude=identity.longitude,
                latitude=identity.latitude,
                name=f"点位{i+1}",
                type="analysis_point",
                color="#FF0000" if not identity.is_compliant else "#00FF00"
            )
            self.recommended_points.append(point)
        
        # 3. 生成分析报告
        report = self._generate_batch_report(identities)
        
        # 4. 批量导出图片
        images = []
        for coord in coordinates:
            export_result = self.export_map(coord)
            if export_result["success"]:
                images.append(export_result["file_path"])
        
        return {
            "mode": "auto_pilot",
            "analyzed_points": len(identities),
            "compliant_points": sum(1 for i in identities if i.is_compliant),
            "report": report,
            "exported_images": images
        }
    
    def co_pilot_recommend(self, project_requirements: Dict[str, Any]) -> AIRecommendation:
        """
        Co-Pilot模式：AI建议点位
        
        Args:
            project_requirements: 项目需求（如：靠近原料地、远离居民区等）
        
        Returns:
            AIRecommendation
        """
        print("启动Co-Pilot模式...")
        
        # 根据需求生成推荐点位（模拟）
        center_lon, center_lat = project_requirements.get("center", (116.4074, 39.9042))
        
        recommendations = []
        for i in range(3):
            # 在中心点附近生成推荐点位
            import random
            offset_lon = random.uniform(-0.1, 0.1)
            offset_lat = random.uniform(-0.1, 0.1)
            
            # 计算推荐评分（基于距离、合规性等）
            score = random.uniform(0.7, 0.95)
            
            point = MapPoint(
                id=f"recommend_{i+1}",
                longitude=center_lon + offset_lon,
                latitude=center_lat + offset_lat,
                name=f"推荐点位{i+1}",
                type="recommendation",
                color="#FFA500",
                score=score
            )
            recommendations.append(point)
        
        self.recommended_points = recommendations
        
        recommendation = AIRecommendation(
            points=recommendations,
            message=f"根据您的需求，我推荐了3个候选点位。点位A评分最高({round(recommendations[0].score*100, 1)}分)，因为它距离原料地较近且周边无敏感点。",
            confidence=0.85
        )
        
        # 触发回调
        if self.on_recommendation:
            self.on_recommendation(recommendation)
        
        return recommendation
    
    def handle_user_modification(self, point_id: str, new_coordinates: Tuple[float, float]):
        """
        处理用户修改点位
        
        Args:
            point_id: 点位ID
            new_coordinates: 新坐标
        """
        print(f"用户修改点位 {point_id} 到 {new_coordinates}")
        
        # 更新用户修改记录
        self.user_modified_points[point_id] = new_coordinates
        
        # 重新分析新位置
        identity = self.get_spatial_identity(*new_coordinates)
        
        # 触发地图更新回调
        if self.on_map_update:
            self.on_map_update({
                "action": "point_updated",
                "point_id": point_id,
                "new_coordinates": new_coordinates,
                "spatial_identity": {
                    "compliant": identity.is_compliant,
                    "issues": identity.compliance_issues,
                    "nearest_water": identity.nearest_water_distance,
                    "nearest_residential": identity.nearest_residential_distance
                }
            })
        
        # 更新报告草稿
        self._update_report_draft(point_id, new_coordinates, identity)
    
    def sketch_to_data(self, polygon_points: List[Tuple[float, float]]) -> Dict[str, Any]:
        """
        Sketch-to-Data模式：手绘驱动生成
        
        Args:
            polygon_points: 用户手绘的多边形坐标
        
        Returns:
            分析结果
        """
        print("启动Sketch-to-Data模式...")
        
        # 分析手绘区域内的信息（模拟）
        analysis = self._analyze_sketch_area(polygon_points)
        
        # 生成专业文字描述
        description = self._generate_description(analysis)
        
        return {
            "mode": "sketch_to_data",
            "area_analysis": analysis,
            "description": description,
            "polygon_points": polygon_points
        }
    
    def _analyze_sketch_area(self, polygon_points: List[Tuple[float, float]]) -> Dict[str, Any]:
        """分析手绘区域"""
        import random
        
        # 模拟分析结果
        return {
            "villages_count": random.randint(1, 5),
            "rivers_count": random.randint(0, 3),
            "population_affected": random.randint(1000, 10000),
            "area_m2": self.geometry_tool.calculate_polygon_area(
                [self.geometry_tool.Point(lon, lat) for lon, lat in polygon_points]
            ),
            "sensitive_points": [
                {"name": f"村庄{i+1}", "distance": random.uniform(100, 1000)}
                for i in range(random.randint(1, 3))
            ]
        }
    
    def _generate_description(self, analysis: Dict[str, Any]) -> str:
        """生成专业描述"""
        villages = analysis.get("villages_count", 0)
        rivers = analysis.get("rivers_count", 0)
        population = analysis.get("population_affected", 0)
        
        description = f"该区域范围内包含 {villages} 个村庄、{rivers} 条河流，"
        description += f"受影响人口约 {population} 人。"
        
        if villages > 0:
            description += "建议进一步评估对周边居民的环境影响。"
        
        if rivers > 0:
            description += "需重点关注对水体的保护措施。"
        
        return description
    
    def _generate_batch_report(self, identities: List[SpatialIdentity]) -> Dict[str, Any]:
        """生成批量分析报告"""
        compliant_count = sum(1 for i in identities if i.is_compliant)
        total_count = len(identities)
        
        return {
            "summary": f"共分析 {total_count} 个点位，其中 {compliant_count} 个点位符合要求",
            "compliance_rate": (compliant_count / total_count) * 100,
            "details": [
                {
                    "longitude": i.longitude,
                    "latitude": i.latitude,
                    "compliant": i.is_compliant,
                    "issues": i.compliance_issues,
                    "nearest_water": i.nearest_water_distance,
                    "nearest_residential": i.nearest_residential_distance
                }
                for i in identities
            ]
        }
    
    def _update_report_draft(self, point_id: str, coordinates: Tuple[float, float], identity: SpatialIdentity):
        """更新报告草稿"""
        print(f"更新报告草稿：点位 {point_id}")
        # 这里应该触发报告更新逻辑
        
        if self.on_analysis_complete:
            self.on_analysis_complete({
                "point_id": point_id,
                "coordinates": coordinates,
                "identity": {
                    "address": identity.address,
                    "compliant": identity.is_compliant,
                    "issues": identity.compliance_issues
                }
            })
    
    # ==================== 空间技能进化 ====================
    
    def learn_new_skill(self, skill_name: str, skill_function):
        """学习新的空间技能"""
        print(f"学习新技能: {skill_name}")
        # 这里可以注册新技能到工具库
    
    def list_skills(self) -> List[str]:
        """列出所有可用技能"""
        return [
            "get_spatial_identity",
            "draw_polygon",
            "draw_buffer",
            "measure_distance",
            "analyze_overlap",
            "calculate_route",
            "analyze_accessibility",
            "export_map"
        ]


# 单例模式
_map_agent_controller = None


def get_map_agent_controller() -> MapAgentController:
    """获取Map Agent控制器单例"""
    global _map_agent_controller
    if _map_agent_controller is None:
        _map_agent_controller = MapAgentController()
    return _map_agent_controller