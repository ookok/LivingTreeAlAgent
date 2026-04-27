# 专家蒸馏模块使用指南

## 快速开始

### 1. 短期方案：专家提示注入（无需训练）

```python
from core.expert_distillation import ExpertDistillationPipeline

# 创建流水线
pipeline = ExpertDistillationPipeline()

# 直接使用，自动注入专家提示
result = pipeline.chat("分析贵州茅台的估值", domain="金融")
print(result.response)
```

### 2. 中期方案：生成蒸馏数据

```python
from core.expert_distillation import ExpertDistillationPipeline

pipeline = ExpertDistillationPipeline()

# 生成金融领域蒸馏数据
qa_list = pipeline.generate_distillation_data(
    domain="金融",
    topics=["股票估值", "财报分析", "投资策略"],
    samples_per_topic=50
)

# 保存为 LLaMA-Factory 格式
pipeline.save_distillation_data(qa_list, format="llama_factory")
```

### 3. 训练专家模型

```bash
# 使用微调脚本
python core/expert_distillation/fine_tune_expert.py \
    --domain 金融 \
    --data data/distillation/金融_train.jsonl \
    --base-model qwen2.5:1.5b \
    --epochs 3 \
    --lora-rank 16
```

## 架构说明

```
┌─────────────────────────────────────────────────────────┐
│                    用户查询                              │
│              "分析这只股票走势"                          │
└─────────────────┬───────────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────────┐
│              ExpertRouter (路由层)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 领域检测    │  │ 复杂度评估  │  │ 路由决策    │     │
│  │ 金融(0.9)  │  │ MODERATE    │  │ HYBRID     │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────┬───────────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────────┐
│          L4EnhancedCaller (增强调用)                     │
│  ┌─────────────────────────────────────────────────┐    │
│  │ 注入 ExpertTemplateLibrary 中的专家提示           │    │
│  │                                                 │    │
│  │ 【金融分析师】                                   │    │
│  │ 1. 明确分析的公司/产品                          │    │
│  │ 2. 收集财务、市场、行业数据                      │    │
│  │ 3. 与行业和竞争对手对比                          │    │
│  │ ...                                             │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────┬───────────────────────────────────────┘
                  ▼
         ┌────────────────┐
         │    L4 模型     │
         │  (qwen3.5:9b) │
         └────────────────┘
```

## 注册专家模型

```python
pipeline = ExpertDistillationPipeline()

# 注册训练好的专家模型
pipeline.register_expert_model(
    domain="金融",
    model_id="fin_expert_1.5b",
    model_path="models/experts/fin_1.5b.gguf",
    priority=1
)

# 之后的查询会自动路由到专家模型
result = pipeline.chat_with_expert("什么是PE？", domain="金融")
```

## 领域支持

| 领域 | 专家角色 | 模板 |
|------|---------|------|
| 金融 | 分析师、风控师 | 股票分析、风险评估 |
| 技术 | 架构师、安全专家 | 问题诊断、架构设计 |
| 法律 | 律师 | 合同审查、风险分析 |
| 医疗 | 医生 | 临床诊断、病例分析 |

## 文件结构

```
core/expert_distillation/
├── __init__.py          # 模块入口
├── data_generator.py    # 蒸馏数据生成器
├── template_library.py  # 专家模板库
├── router.py            # 路由决策
├── l4_caller.py         # L4 增强调用
├── pipeline.py          # 完整流水线
├── fine_tune_expert.py  # 微调脚本
└── templates/           # 模板存储目录
```
