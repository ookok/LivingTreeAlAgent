# 环评专业地图引擎设计方案

> 创建时间：2026-04-28
> 状态：设计阶段
> 优先级：P1

---

## 一、方案概述

### 1.1 目标
为环评智能体项目提供**专业离线地图生成能力**，包括场地位置图、敏感目标分布图、监测点位图、环境影响范围图等6类环评专用地图。

### 1.2 核心价值
- **真实地理坐标**：基于CGCS2000坐标系，支持多源坐标转换
- **专业底图**：在线/离线底图，自动应用环评样式
- **自动化制图**：一键生成6类环评专用地图
- **多格式输出**：支持图片(PNG)、矢量图(SVG/PDF)、地理参考(GeoTIFF)、Web交互地图(HTML)

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    EIA Workbench (主入口)                      │
└─────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐    ┌───────────────────┐    ┌─────────────────┐
│ 现有 map_overlay │    │ 现有 spatial_intelligence│    │ 现有 drawing_engine │
│  (Web地图API)   │    │   (POI识别/边界)    │    │   (工艺/厂房图)    │
└───────┬───────┘    └─────────┬─────────┘    └────────┬────────┘
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               ▼
              ┌────────────────────────────────────┐
              │     ProfessionalMapEngine (新增)    │
              │  ┌──────────────────────────────┐  │
              │  │ CoordinateIntelligentHandler │  │  ← 整合coord_transform
              │  │ ProfessionalBaseMapProvider  │  │  ← 核心新增
              │  │ EIAProfessionalMapGenerator   │  │  ← 整合drawing_engine
              │  │ AutoLegendAnnotation          │  │  ← 核心新增
              │  │ MapOutputGenerator            │  │  ← 整合export_manager
              │  └──────────────────────────────┘  │
              └────────────────────────────────────┘
                               │
                               ▼
              ┌────────────────────────────────────┐
              │   MapIntegratedReportGenerator      │
              │        (整合report_generator)        │
              └────────────────────────────────────┘
```

---

## 三、核心组件设计

### 3.1 CoordinateIntelligentHandler（坐标智能处理器）

**职责**：统一管理坐标系转换，提供CGCS2000标准坐标

**功能**：
| 功能 | 说明 |
|------|------|
| 坐标提取 | 支持GIS数据、CAD图纸、直接坐标、地址地理编码 |
| 坐标转换 | 统一到CGCS2000坐标系(EPSG:4490) |
| 投影选择 | 根据位置自动选择高斯-克吕格投影带 |

**坐标系支持**：
| 坐标系 | EPSG | 说明 |
|--------|------|------|
| CGCS2000 | 4490 | 国家2000坐标系 |
| WGS84 | 4326 | GPS通用坐标 |
| GCJ02 | - | 火星坐标系(高德/腾讯) |
| BD09 | - | 百度坐标系 |

### 3.2 ProfessionalBaseMapProvider（专业底图提供器）

**职责**：提供环评专用底图数据

**底图类型**：

| 类型 | 来源 | 用途 |
|------|------|------|
| 卫星影像 | Esri/天地图 | 项目选址、场地布局 |
| 行政区划 | 天地图/OSM | 场地位置图 |
| 水系分布 | 天地图 | 水环境影响分析 |
| 道路网络 | OSM | 交通影响分析 |
| DEM高程 | SRTM/CGIAR | 地形分析、大气扩散 |

**环评专用样式**：
- `eia_standard`：标准环评报告风格
- `eia_simplified`：简化版（章节插图）
- `eia_presentation`：汇报演示风格

### 3.3 EIAProfessionalMapGenerator（环评专业地图生成器）

**职责**：自动生成6类环评专用地图

| 地图类型 | 内容 | 对应报告章节 |
|---------|------|-------------|
| 场地位置图 | 项目位置、交通、所属行政区 | 项目概述 |
| 敏感目标分布图 | 居民区、学校、医院等敏感点 | 环境影响评价 |
| 监测点位图 | 大气/水质/噪声监测点 | 环境监测 |
| 环境影响范围图 | 预测浓度等值线、达标分析 | 环境影响预测 |
| 土地利用现状图 | 土地利用类型、规划用地 | 环境现状 |
| 风险源分布图 | 风险源位置、防护距离 | 环境风险评价 |

### 3.4 AutoLegendAnnotation（自动图例标注系统）

**职责**：自动添加专业地图元素

**专业元素**：
| 元素 | 说明 |
|------|------|
| 指北针 | 标准地图方向指示 |
| 比例尺 | 线性/数字化比例尺 |
| 图例 | 符号说明、颜色图例 |
| 坐标网格 | 经纬度/平面直角坐标网格 |
| 责任栏 | 编制单位、日期、图号 |
| 图框 | 标准图幅边框 |

### 3.5 MapOutputGenerator（多格式输出）

**输出格式**：

| 格式 | 用途 | 分辨率 |
|------|------|--------|
| PNG | 报告插图 | 300dpi |
| PDF | 正式报告(矢量) | - |
| SVG | 矢量编辑 | - |
| GeoTIFF | GIS系统 | 地理参考 |
| HTML | Web交互 | - |

### 3.6 MapIntegratedReportGenerator（报告集成）

**职责**：将地图自动嵌入Word文档

**功能**：
- 自动生成图编号（如"图3.1-1"）
- 自动生成图标题和说明
- 自动更新目录
- 保持版式一致

---

## 四、技术栈

| 类别 | 库/工具 | 用途 |
|------|--------|------|
| 坐标处理 | pyproj | 坐标系转换、投影变换 |
| 几何计算 | shapely, geopandas | 缓冲区分析、空间运算 |
| 地图绘制 | matplotlib, cartopy | 专业制图 |
| 在线地图 | contextily | OSM/卫星底图 |
| 离线地图 | rasterio | GeoTIFF处理 |
| Web地图 | folium | 交互地图生成 |

---

## 五、与现有系统匹配分析

### 5.1 现有能力盘点

| 现有模块 | 已具备能力 | 缺失能力 |
|---------|-----------|---------|
| `map_overlay.py` | 多地图API(Web)、坐标系转换 | 离线底图、专业制图、矢量输出 |
| `spatial_intelligence/` | POI敏感点识别、边界绘制 | 距离计算、投影变换、缓冲区分析 |
| `coord_transform.py` | CAD→GeoJSON坐标转换 | CGCS2000、pyproj投影引擎 |
| `report_generator.py` | 章节组装、DOCX导出 | 专业地图自动嵌入 |
| `drawing_engine.py` | 工艺流程图、厂房图 | GIS专题图 |

### 5.2 集成策略

| 组件 | 整合现有模块 | 开发方式 |
|------|-------------|---------|
| CoordinateIntelligentHandler | coord_transform.py | 扩展 |
| ProfessionalBaseMapProvider | 无 | 新建 |
| EIAProfessionalMapGenerator | drawing_engine.py | 整合 |
| AutoLegendAnnotation | 无 | 新建 |
| MapOutputGenerator | export_manager.py | 扩展 |
| MapIntegratedReportGenerator | report_generator.py | 扩展 |

---

## 六、技术风险与缓解

| 风险项 | 等级 | 缓解建议 |
|-------|------|---------|
| 离线底图数据准备 | 高 | 优先使用OSM在线底图 |
| pyproj/geopandas学习曲线 | 中 | 封装SimpleCoordinateHandler |
| 投影坐标系选择错误 | 高 | 内置中国区域投影配置表 |
| 地图与报告格式不兼容 | 中 | 先PNG嵌入，后续支持矢量 |

---

## 七、开发计划

### 7.1 优先级排序

| 优先级 | 组件 | 理由 | 预计工时 |
|-------|------|------|---------|
| P0 | CoordinateIntelligentHandler | 基础能力，其他模块依赖 | 1天 |
| P0 | EIAProfessionalMapGenerator | 核心业务价值 | 2天 |
| P1 | AutoLegendAnnotation | 专业性关键差异点 | 1天 |
| P2 | ProfessionalBaseMapProvider | 离线底图准备成本高 | 2天 |
| P3 | MapOutputGenerator | 现有export_manager已部分支持 | 1天 |
| P3 | MapIntegratedReportGenerator | 可复用report_generator | 1天 |

### 7.2 第一阶段实施

**目标**：实现核心地图生成能力

**交付物**：
1. CoordinateIntelligentHandler - 坐标智能处理
2. EIAProfessionalMapGenerator - 6类环评地图生成
3. 场地位置图DEMO

**底图策略**：
- 优先使用OSM在线底图（contextily）
- 离线底图作为可选增强

---

## 八、验收标准

### 8.1 功能验收
- [ ] 坐标转换误差 < 1米
- [ ] 成功生成6类环评专用地图
- [ ] 支持PNG/PDF双格式输出
- [ ] 地图自动嵌入Word报告

### 8.2 性能验收
- [ ] 单张地图生成 < 30秒
- [ ] 支持批量生成（10张/批次）

### 8.3 质量验收
- [ ] 图例、指北针、比例尺自动添加
- [ ] 地图样式符合环评规范
- [ ] 坐标系正确（CGCS2000）

---

## 九、文件结构

```
client/src/business/living_tree_ai/eia_system/
├── professional_map/                    # 新增目录
│   ├── __init__.py
│   ├── professional_map_engine.py       # 主引擎入口
│   ├── coordinate_handler.py            # 坐标智能处理
│   ├── base_map_provider.py              # 底图提供器
│   ├── eia_map_generator.py              # 环评地图生成器
│   ├── legend_annotation.py              # 图例标注系统
│   ├── output_generator.py               # 多格式输出
│   └── report_integrator.py              # 报告集成
└── ...
```

---

## 十、附录

### 10.1 相关标准
- HJ 2.1-2016 环境影响评价技术导则 总纲
- HJ 169-2018 建设项目环境风险评价技术导则
- GB/T 13923-2006 基础地理信息要素分类与代码

### 10.2 参考资料
- 项目现有 map_overlay.py
- 项目现有 spatial_intelligence/
- 项目现有 drawing_engine.py
- 项目现有 report_generator.py
