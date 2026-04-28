"""
系统Agent初始化 + 环评报告编写专家训练（递归5层） + 知识库搜索"污染物"
==========================================================================
测试流程：
  1. 系统 Agent 初始化（SystemConfig + L0-L4 组件加载）
  2. 专家训练：使用 DRET 系统，主题=环评报告编写，递归深度=5
  3. 知识库搜索："污染物"关键词
  4. 汇总输出结果
"""

import sys
import os
import time
import json

# 确保项目根目录在 PYTHONPATH
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ═══════════════════════════════════════════════════════════
# STEP 0: 打印系统信息
# ═══════════════════════════════════════════════════════════
print("=" * 70)
print("  系统 Agent 初始化 + 环评报告专家训练（递归5层）+ 知识库搜索")
print("=" * 70)
print(f"[INFO] Python: {sys.version}")
print(f"[INFO] 项目根目录: {PROJECT_ROOT}")
print()

# ═══════════════════════════════════════════════════════════
# STEP 1: 系统 Agent 初始化
# ═══════════════════════════════════════════════════════════
print("─" * 70)
print("【STEP 1】系统 Agent 初始化")
print("─" * 70)

# --- 1.1 加载 SystemConfig ---
agent_config = {}
try:
    from core.smolllm2.models import SystemConfig
    config = SystemConfig()
    agent_config["system_config"] = "OK"
    print(f"  [OK] SystemConfig 加载成功")
    print(f"       L0 模型路径: {getattr(config, 'l0_model_path', 'N/A')}")
    print(f"       Ollama Base: {getattr(config, 'ollama_base_url', 'http://localhost:11434')}")
except Exception as e:
    agent_config["system_config"] = f"SKIP: {e}"
    print(f"  [--] SystemConfig: {e}")

# --- 1.2 加载 SkillEvolutionDatabase ---
skill_db = None
try:
    from core.skill_evolution.database import SkillEvolutionDatabase
    skill_db = SkillEvolutionDatabase(":memory:")
    agent_config["skill_db"] = "OK"
    print(f"  [OK] SkillEvolutionDatabase 初始化（内存模式）")
except Exception as e:
    agent_config["skill_db"] = f"SKIP: {e}"
    print(f"  [--] SkillEvolutionDatabase: {e}")

# --- 1.3 加载知识库 KnowledgeBaseLayer ---
kb = None
try:
    from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
    kb = KnowledgeBaseLayer()
    agent_config["knowledge_base"] = "OK"
    print(f"  [OK] KnowledgeBaseLayer 初始化成功")
except Exception as e:
    agent_config["knowledge_base"] = f"SKIP: {e}"
    print(f"  [--] KnowledgeBaseLayer: {e}")

# --- 1.4 加载 DRET 系统（专家训练核心）---
dret = None
try:
    from core.skill_evolution.dret_l04_integration import create_l04_dret_system
    dret = create_l04_dret_system(
        max_recursion_depth=5,  # 递归5层
        enable_l04=True,
        enable_expert=True
    )
    agent_config["dret_system"] = "OK"
    print(f"  [OK] DRET 系统创建成功（递归深度=5）")
except Exception as e:
    agent_config["dret_system"] = f"FAIL: {e}"
    print(f"  [FAIL] DRET: {e}")

# --- 1.5 加载 ExpertRoleFinder ---
expert_finder = None
try:
    from core.skill_evolution.dret_l04_integration import ExpertRoleFinder
    expert_finder = ExpertRoleFinder(enable_expert=True)
    agent_config["expert_finder"] = "OK"
    print(f"  [OK] ExpertRoleFinder 加载成功")
except Exception as e:
    agent_config["expert_finder"] = f"SKIP: {e}"
    print(f"  [--] ExpertRoleFinder: {e}")

print()
print(f"  ✅ Agent 初始化完成，组件状态:")
for k, v in agent_config.items():
    status = "✓" if v == "OK" else "~"
    print(f"     {status} {k}: {v}")

# ═══════════════════════════════════════════════════════════
# STEP 2: 向知识库注入环评专业文档
# ═══════════════════════════════════════════════════════════
print()
print("─" * 70)
print("【STEP 2】向知识库注入环评专业文档（预训练语料）")
print("─" * 70)

ENV_DOCS = [
    {
        "id": "env_001",
        "title": "环境影响评价报告编写规范",
        "content": """
        环境影响评价（EIA）报告编写规范要求：
        
        一、总则
        环境影响评价报告必须遵循《中华人民共和国环境影响评价法》及相关技术规范。
        编写单位必须具备环评资质，评价范围应全面覆盖项目建设期和运营期。
        
        二、污染物分析
        2.1 大气污染物
        主要包括：SO₂（二氧化硫）、NOₓ（氮氧化物）、PM₂.₅（细颗粒物）、PM₁₀（可吸入颗粒物）、
        VOCs（挥发性有机物）、CO（一氧化碳）、氟化物、氯化氢等。
        大气污染物排放必须满足《大气污染物综合排放标准》（GB16297）要求。
        
        2.2 水污染物
        主要包括：COD（化学需氧量）、BOD₅（五日生化需氧量）、SS（悬浮固体）、
        氨氮、总磷、总氮、重金属（铅、汞、镉、铬、砷）等。
        废水排放必须达到相应行业排放标准或《污水综合排放标准》（GB8978）。
        
        2.3 固体废物
        分为一般固体废弃物和危险废弃物。危险废物必须委托有资质单位处置，
        不得随意堆放或填埋，需建立台账记录，转移需填写危险废物转移联单。
        
        2.4 噪声
        施工期噪声执行《建筑施工场界环境噪声排放标准》（GB12523）；
        运营期噪声执行《工业企业厂界环境噪声排放标准》（GB12348）。
        
        三、环境质量现状评价
        报告必须包括：声环境、地表水、地下水、土壤、大气、生态等专项评价。
        监测数据必须具有代表性，监测方案需经审核。
        
        四、环境影响预测
        采用数学模型预测各污染物的扩散、迁移和转化规律，
        预测关心点处的环境质量变化，评估是否满足功能区标准。
        """
    },
    {
        "id": "env_002",
        "title": "污染物排放标准与控制措施",
        "content": """
        污染物排放控制技术规范：
        
        一、大气污染控制
        1.1 除尘技术
        - 布袋除尘器：效率≥99.5%，适用于含尘气体处理
        - 静电除尘器：效率≥99%，适用于大型燃煤锅炉
        - 湿式除尘：适用于高温、高湿烟气
        
        1.2 脱硫技术
        - 石灰石-石膏湿法脱硫：效率≥95%，为主流技术
        - 海水脱硫：适用于沿海地区
        - 活性炭脱硫：效率高，同时去除SO₂和NOₓ
        
        1.3 脱硝技术
        - SCR（选择性催化还原）：效率≥85%，使用NH₃为还原剂
        - SNCR（选择性非催化还原）：效率50-70%，成本低
        
        二、水污染控制
        2.1 预处理
        - 格栅、沉砂池：去除大颗粒悬浮物
        - 调节池：均化水量和水质
        
        2.2 生化处理
        - 活性污泥法（A/O、A²/O）：去除COD、BOD、氨氮、总磷
        - 氧化沟：适用于中小型污水处理
        - MBR（膜生物反应器）：出水水质好，占地小
        
        2.3 深度处理
        - 过滤、消毒
        - 活性炭吸附：去除难降解有机物
        - 反渗透（RO）：达到回用水标准
        
        三、固废处置
        危险废物需交由持有危险废物经营许可证的单位处置。
        一般固废可采用资源化利用（优先）、无害化填埋等方式。
        
        四、污染物总量控制
        建设项目须申请污染物排放总量指标，
        排放总量不得超过总量控制指标。
        COD、氨氮、SO₂、NOₓ为主要总量控制指标。
        """
    },
    {
        "id": "env_003",
        "title": "环评报告编写工作程序",
        "content": """
        环评工作程序：
        
        阶段一：前期准备
        - 收集项目基本资料（可研报告、工艺流程等）
        - 确定评价等级和评价范围
        - 编制环评工作方案
        
        阶段二：现状监测与调查
        - 布设监测点，开展环境质量现状监测
        - 收集当地气象、水文、地质等背景数据
        - 开展公众参与第一次信息公开
        
        阶段三：环境影响预测与评价
        - 进行工程分析，核算各类污染物排放量
        - 建立预测模型，计算环境影响
        - 评价是否符合环境功能区要求
        
        阶段四：污染防治措施
        - 提出各类污染物的防治措施
        - 论证措施的技术经济可行性
        - 制定环境管理与监测计划
        
        阶段五：报告编制
        - 按规范格式编制报告书（表）
        - 开展公众参与第二次信息公开
        - 提交审批
        
        环评报告书包含：
        1. 总论（评价目的、依据、内容、方法）
        2. 建设项目概况
        3. 工程分析（物料平衡、水平衡、污染物分析）
        4. 环境现状调查
        5. 环境影响预测
        6. 污染防治措施
        7. 清洁生产分析
        8. 总量控制
        9. 环境管理与监测计划
        10. 环境经济损益分析
        11. 公众参与
        12. 结论与建议
        """
    },
    {
        "id": "env_004",
        "title": "重点污染物监测与评价方法",
        "content": """
        重点污染物监测方法：
        
        一、大气污染物监测
        SO₂：碘量法（HJ/T56）、紫外荧光法
        NOₓ：化学发光法（HJ/T42）、盐酸萘乙二胺法
        PM₁₀/PM₂.₅：重量法（HJ618）、β射线法
        VOCs：气相色谱法（HJ38）、光离子化检测
        
        二、水污染物监测
        COD：重铬酸盐法（HJ828）、快速消解法
        氨氮：纳氏试剂法（HJ535）、水杨酸盐法
        总磷：钼酸铵分光光度法（GB11893）
        重金属：原子吸收法（各金属各有标准）
        
        三、评价标准
        大气质量：《环境空气质量标准》（GB3095-2012）
          - PM₂.₅年均浓度：一类区10μg/m³，二类区35μg/m³
          - SO₂年均浓度：一类区20μg/m³，二类区60μg/m³
        
        地表水质量：《地表水环境质量标准》（GB3838-2002）
          - I类：源头水，国家自然保护区
          - II类：饮用水二级保护区
          - III类：饮用水三级保护区，游泳区
          - IV类：工业用水，不接触人体娱乐用水
          - V类：农业用水及景观用水
        
        四、污染物超标判定
        污染物浓度超过相应功能区标准值即为超标。
        超标倍数 = （监测值 - 标准值）/ 标准值
        超标面积、范围、时间均为重要评价指标。
        """
    },
    {
        "id": "env_005",
        "title": "环境风险评价与应急预案",
        "content": """
        环境风险评价要点：
        
        一、风险识别
        识别建设项目存在的危险物质（危险化学品、有毒气体等），
        判断风险事故类型（爆炸、火灾、有毒气体泄漏、危废泄漏等）。
        
        二、源项分析
        确定最大可信事故场景，
        估算事故时有毒有害物质的释放量（最大泄漏量）。
        
        三、后果预测
        采用高斯烟团模型预测有毒气体事故泄漏扩散，
        确定毒害区（立即危险生命健康浓度IDLH范围）、
        危害区（阈值浓度ERCL范围）。
        
        四、风险评价
        将预测结果与可接受风险标准对比，
        判断项目环境风险是否可接受。
        
        五、环境应急预案
        包含：
        - 应急响应组织体系
        - 预警与报告程序
        - 应急处置程序（疏散、封堵、消防、救援）
        - 事后恢复程序
        - 应急资源保障（物资、人员、培训、演练）
        
        污染物事故排放控制：
        - 设置事故水池，收集消防废水和泄漏物
        - 设置雨水切换阀，防止含污染物雨水排出
        - 危险化学品储罐区设置防渗防漏措施
        """
    }
]

if kb is not None:
    print(f"  [i] 向知识库添加 {len(ENV_DOCS)} 份环评专业文档...")
    for doc in ENV_DOCS:
        try:
            kb.add_document(doc)
            print(f"  [OK] 已加入: [{doc['id']}] {doc['title']}")
        except Exception as e:
            print(f"  [WARN] 添加失败 [{doc['id']}]: {e}")
    print(f"  ✅ 知识库文档注入完成，共 {len(ENV_DOCS)} 份文档")
else:
    print("  [SKIP] 知识库未初始化，跳过文档注入")

# ═══════════════════════════════════════════════════════════
# STEP 3: 专家训练 - 环评报告编写（递归5层）
# ═══════════════════════════════════════════════════════════
print()
print("─" * 70)
print("【STEP 3】专家训练：环评报告编写（递归深度=5层）")
print("─" * 70)

# 环评报告编写专家训练文档
EXPERT_TRAINING_DOC = """
环评报告编写要点（训练文档）：

基于环境影响评价法，编写报告必须遵循技术规范。
首先确定评价等级，然后开展现状调查，通过数学模型进行影响预测。

工程分析是报告核心，需要核算所有污染物的产生量和排放量。
污染物包括：废气、废水、固废、噪声等四类。
废气中主要污染物包括颗粒物和气态污染物。

通过使用高斯扩散模型进行大气扩散预测，
通过使用Streeter-Phelps模型进行水体预测，
基于CALPUFF技术预测长距离传输影响。

报告结论必须明确：项目是否满足环境功能区标准，
总量控制指标是否在许可范围内，
污染防治措施是否技术可行。

注意：报告必须包含公众参与章节，参见相关公众参与规范。
"""

training_report = None
if dret is not None:
    print(f"  [i] 启动 DRET 专家训练，递归深度={dret.max_depth} 层")
    print(f"  [i] 训练主题: 环评报告编写")
    
    t0 = time.time()
    try:
        training_report = dret.learn_from_document(
            doc_content=EXPERT_TRAINING_DOC,
            doc_id="env_report_writing",
            session_id="env_expert_training_session",
            recursion_depth=5  # 明确指定5层
        )
        elapsed = time.time() - t0
        
        print()
        print(f"  ✅ 专家训练完成！耗时: {elapsed:.2f}s")
        print()
        print("  ┌─ 训练报告（DRET Learning Report）")
        print(f"  │  文档ID         : {training_report['doc_id']}")
        print(f"  │  最大递归深度   : {training_report['max_depth_used']} 层")
        print(f"  │  知识空白发现   : {training_report['gaps_found']} 个")
        print(f"  │  知识空白填充   : {training_report['gaps_filled']} 个")
        print(f"  │  矛盾点发现     : {training_report['conflicts_found']} 个")
        print(f"  │  矛盾点解决     : {training_report['conflicts_resolved']} 个")
        print(f"  │  辩论轮次       : {training_report['debate_rounds']} 轮")
        print(f"  │  知识图谱节点   : {training_report['knowledge_graph']['nodes']}")
        print(f"  │  知识图谱边数   : {training_report['knowledge_graph']['edges']}")
        print(f"  │  总耗时         : {training_report['total_time']:.2f}s")
        if training_report.get('expert_persona'):
            print(f"  │  专家人格       : {training_report['expert_persona']}")
        print(f"  └─ 完成")
        
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  [FAIL] 专家训练失败: {e}")
        import traceback
        traceback.print_exc()
else:
    print("  [SKIP] DRET 系统未初始化，跳过专家训练")

# ─── 专家人格匹配：环评 ───
print()
print("  ─── 专家角色匹配：环评报告编写 ───")
if dret and dret.expert_role_finder:
    try:
        best_persona = dret.expert_role_finder.find_best_persona(
            topic="环境影响评价报告编写",
            context="需要专业的环境工程知识，包括污染物分析、排放标准、防治措施"
        )
        print(f"  最佳匹配专家人格  : {best_persona.get('persona_name', 'N/A')}")
        print(f"  匹配度            : {best_persona.get('match_score', 0):.2f}")
        print(f"  专业领域          : {best_persona.get('domain', 'N/A')}")
        print(f"  描述              : {best_persona.get('persona_description', best_persona.get('description', 'N/A'))}")
        
        # 获取环境领域所有专家
        env_experts = dret.expert_role_finder.get_expert_by_domain("environment")
        if env_experts:
            print(f"\n  环境领域专家列表（{len(env_experts)} 位）:")
            for exp in env_experts:
                print(f"    ✦ {exp['persona_name']}: {exp['description']}")
    except Exception as e:
        print(f"  [WARN] 专家人格匹配失败: {e}")
else:
    # 使用内置 EXPERT_ROLES 展示
    from core.skill_evolution.dret_l04_integration import EXPERT_ROLES
    print("  内置专家角色（EXPERT_ROLES）:")
    for role_id, info in EXPERT_ROLES.items():
        if info.get("domain") in ("environment", "legal"):
            print(f"    ✦ [{role_id}] {info['name']}: {info['description']}")


# ═══════════════════════════════════════════════════════════
# STEP 4: 知识库搜索"污染物"
# ═══════════════════════════════════════════════════════════
print()
print("─" * 70)
print('【STEP 4】知识库搜索："污染物"')
print("─" * 70)

search_results = []

# 方法A：直接使用 KnowledgeBaseLayer
if kb is not None:
    print("  [i] 方法A：使用 KnowledgeBaseLayer 搜索...")
    t_search = time.time()
    try:
        results = kb.search("污染物", top_k=5)
        elapsed_search = time.time() - t_search
        
        print(f"  [OK] 搜索完成，耗时 {elapsed_search*1000:.1f}ms，找到 {len(results)} 条结果")
        print()
        print("  ╔══════════════════════════════════════════════════════════════╗")
        print("  ║          知识库搜索结果：污染物（TOP-5）                        ║")
        print("  ╠══════════════════════════════════════════════════════════════╣")
        
        for i, result in enumerate(results):
            doc_id = result.get("doc_id", result.get("id", "unknown"))
            title = result.get("title", "未知文档")
            score = result.get("score", 0)
            content = result.get("content", "").strip()[:200]
            source = result.get("source", "KB")
            
            print(f"  ║  #{i+1} 文档: {doc_id} | 标题: {title[:20]}")
            print(f"  ║     相关度: {score:.4f} | 来源: {source}")
            print(f"  ║     内容片段: {content[:120]}...")
            print(f"  ╠──────────────────────────────────────────────────────────╣")
            
            search_results.append({
                "rank": i + 1,
                "doc_id": doc_id,
                "title": title,
                "score": score,
                "content_preview": content[:200],
                "source": source
            })
        
        print("  ╚══════════════════════════════════════════════════════════════╝")
        
    except Exception as e:
        print(f"  [WARN] KnowledgeBaseLayer 搜索失败: {e}")
        import traceback
        traceback.print_exc()

# 方法B：使用 DRET 内部知识库（来自 GapDetector）
if dret is not None and dret.gap_detector.knowledge_base is not None:
    print()
    print("  [i] 方法B：使用 DRET 内嵌 KnowledgeBase 搜索...")
    t_search2 = time.time()
    try:
        results2 = dret.gap_detector.knowledge_base.search("污染物", top_k=3)
        elapsed2 = time.time() - t_search2
        
        print(f"  [OK] DRET内嵌KB搜索完成，耗时 {elapsed2*1000:.1f}ms，找到 {len(results2)} 条结果")
        
        if results2:
            print()
            print("  DRET 内嵌知识库搜索结果（TOP-3）:")
            for i, r in enumerate(results2):
                print(f"  [{i+1}] 文档: {r.get('doc_id', 'N/A')}")
                print(f"      分数: {r.get('score', 0):.4f}")
                print(f"      内容: {r.get('content', '')[:150]}...")
                print()
    except Exception as e:
        print(f"  [WARN] DRET内嵌KB搜索失败: {e}")

# 方法C：模拟专家搜索（使用关键词扩展）
print()
print("  [i] 方法C：专家关键词扩展搜索（环评相关）...")
POLLUTANT_KEYWORDS = ["污染物", "排放标准", "防治措施", "废气", "废水", "固废", "噪声"]
if kb is not None:
    for kw in POLLUTANT_KEYWORDS[:3]:
        try:
            r = kb.search(kw, top_k=2)
            if r:
                print(f"  搜索关键词 [{kw}]: {len(r)} 条, top1分数={r[0].get('score',0):.4f}, doc={r[0].get('doc_id','?')}")
        except:
            pass

# ═══════════════════════════════════════════════════════════
# STEP 5: 汇总输出结果
# ═══════════════════════════════════════════════════════════
print()
print("─" * 70)
print("【STEP 5】综合汇总结果")
print("─" * 70)

print()
print("  ▶ Agent 初始化状态")
for k, v in agent_config.items():
    status = "✓" if v == "OK" else "~"
    print(f"    {status} {k}: {v}")

print()
print("  ▶ 专家训练结果（环评报告编写，递归5层）")
if training_report:
    print(f"    · 知识空白发现: {training_report['gaps_found']} 个")
    print(f"    · 知识空白填充: {training_report['gaps_filled']} 个")
    fill_rate = training_report['gaps_filled'] / max(training_report['gaps_found'], 1) * 100
    print(f"    · 知识填充率  : {fill_rate:.1f}%")
    print(f"    · 矛盾发现    : {training_report['conflicts_found']} 个")
    print(f"    · 矛盾解决    : {training_report['conflicts_resolved']} 个")
    print(f"    · 最大递归深度: {training_report['max_depth_used']} 层")
    print(f"    · 知识图谱    : {training_report['knowledge_graph']['nodes']} 节点, {training_report['knowledge_graph']['edges']} 边")
    print(f"    · 总耗时      : {training_report['total_time']:.2f}s")
else:
    print("    [SKIP] 专家训练未执行")

print()
print('  ▶ 知识库搜索结果（查询词："污染物"）')
if search_results:
    print(f"    找到 {len(search_results)} 条相关文档片段：")
    for r in search_results:
        print(f"    #{r['rank']} [{r['doc_id']}] {r.get('title','')[:30]}")
        print(f"        相关度: {r['score']:.4f}")
        print(f"        摘要  : {r['content_preview'][:100]}...")
else:
    print("    [SKIP] 知识库搜索未执行或无结果")

print()
print("=" * 70)
print("  ✅ 所有步骤执行完成")
print("=" * 70)
