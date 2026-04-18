"""
数据库迁移管理
Database Migration Manager

支持版本化的数据库迁移
"""

import sqlite3
import time
import json
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass


@dataclass
class Migration:
    """迁移记录"""
    version: int
    name: str
    description: str
    up: str  # 升级SQL
    down: str  # 降级SQL


# 定义所有迁移
MIGRATIONS = []


def register_migration(version: int, name: str, description: str):
    """注册迁移装饰器"""
    def decorator(func: Callable[[sqlite3.Connection], None]):
        MIGRATIONS.append(Migration(
            version=version,
            name=name,
            description=description,
            up=func.__doc__ or "",
            down=""
        ))
        return func
    return decorator


# v7: 添加 MCP Server 相关表
@register_migration(7, "add_mcp_tables", "添加 MCP Server 管理相关表")
def migrate_v7(conn: sqlite3.Connection):
    """-- MCP Servers 表
    CREATE TABLE IF NOT EXISTS mcp_servers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        url TEXT,
        protocol TEXT DEFAULT 'sse',
        status TEXT DEFAULT 'offline',
        source TEXT DEFAULT 'local',
        capabilities TEXT,
        tags TEXT,
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now')),
        last_connected REAL
    );

    -- MCP 订阅表
    CREATE TABLE IF NOT EXISTS mcp_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id TEXT NOT NULL,
        user_id TEXT,
        status TEXT DEFAULT 'active',
        auto_connect INTEGER DEFAULT 1,
        last_error TEXT,
        FOREIGN KEY (server_id) REFERENCES mcp_servers(id)
    );

    -- MCP 工具表
    CREATE TABLE IF NOT EXISTS mcp_tools (
        id TEXT PRIMARY KEY,
        server_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        input_schema TEXT,
        FOREIGN KEY (server_id) REFERENCES mcp_servers(id)
    );
    """


# v8: 添加 Skill Market 相关表
@register_migration(8, "add_skills_market_tables", "添加 Skill 市场相关表")
def migrate_v8(conn: sqlite3.Connection):
    """-- Skills 表
    CREATE TABLE IF NOT EXISTS skills (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT,
        version TEXT DEFAULT '1.0.0',
        source TEXT DEFAULT 'local',
        manifest_url TEXT,
        local_path TEXT,
        status TEXT DEFAULT 'installed',
        dependencies TEXT,
        config_schema TEXT,
        installed_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now')),
        rating REAL DEFAULT 0.0,
        downloads INTEGER DEFAULT 0
    );

    -- Skill 触发词表
    CREATE TABLE IF NOT EXISTS skill_triggers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        skill_id TEXT NOT NULL,
        trigger TEXT NOT NULL,
        FOREIGN KEY (skill_id) REFERENCES skills(id)
    );
    """


# v9: 添加 LAN Chat 相关表
@register_migration(9, "add_lan_chat_tables", "添加 LAN 聊天相关表")
def migrate_v9(conn: sqlite3.Connection):
    """-- LAN Users 表
    CREATE TABLE IF NOT EXISTS lan_users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        ip_address TEXT,
        port INTEGER DEFAULT 45679,
        status TEXT DEFAULT 'offline',
        last_seen REAL,
        avatar TEXT
    );

    -- Chat Messages 表
    CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        sender_id TEXT NOT NULL,
        sender_name TEXT,
        receiver_id TEXT NOT NULL,
        content TEXT,
        timestamp REAL DEFAULT (julianday('now')),
        read INTEGER DEFAULT 0,
        ai_generated INTEGER DEFAULT 0
    );

    -- 创建索引
    CREATE INDEX IF NOT EXISTS idx_messages_sender ON chat_messages(sender_id);
    CREATE INDEX IF NOT EXISTS idx_messages_receiver ON chat_messages(receiver_id);
    CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON chat_messages(timestamp);
    """


# v10: 添加 Digital Avatar 相关表
@register_migration(10, "add_avatars_tables", "添加数字分身相关表")
def migrate_v10(conn: sqlite3.Connection):
    """-- Avatars 表
    CREATE TABLE IF NOT EXISTS avatars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT UNIQUE NOT NULL,
        
        -- 核心层
        core_identity TEXT DEFAULT '{}',
        declared_interests TEXT DEFAULT '[]',
        
        -- 行为层
        behavioral_patterns TEXT DEFAULT '{}',
        inferred_roles TEXT DEFAULT '{}',
        decision_biases TEXT DEFAULT '{}',
        
        -- 记忆层
        conversation_milestones TEXT DEFAULT '[]',
        learned_concepts TEXT DEFAULT '{}',
        knowledge_gaps TEXT DEFAULT '[]',
        
        -- 成长系统
        experience INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        unlocked_features TEXT DEFAULT '[]',
        
        -- 时间戳
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- Avatar 快照表
    CREATE TABLE IF NOT EXISTS avatar_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        avatar_id INTEGER NOT NULL,
        snapshot_data TEXT NOT NULL,
        created_at REAL DEFAULT (julianday('now')),
        FOREIGN KEY (avatar_id) REFERENCES avatars(id)
    );

    -- Avatar 交互记录表
    CREATE TABLE IF NOT EXISTS avatar_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        avatar_id INTEGER NOT NULL,
        interaction_type TEXT NOT NULL,
        content TEXT,
        reward INTEGER DEFAULT 0,
        created_at REAL DEFAULT (julianday('now')),
        FOREIGN KEY (avatar_id) REFERENCES avatars(id)
    );
    """


# v11: 添加 Learning World 相关表
@register_migration(11, "add_learning_world_tables", "添加学习世界相关表")
def migrate_v11(conn: sqlite3.Connection):
    """-- Learning Profiles 表
    CREATE TABLE IF NOT EXISTS learning_profiles (
        id INTEGER PRIMARY KEY,
        profile_data TEXT NOT NULL,
        graph_data TEXT NOT NULL,
        updated_at REAL NOT NULL
    );

    -- Learning Sessions 表
    CREATE TABLE IF NOT EXISTS learning_sessions (
        id TEXT PRIMARY KEY,
        initial_query TEXT NOT NULL,
        current_query TEXT,
        path_data TEXT,
        visited_topics TEXT DEFAULT '[]',
        tag_click_stats TEXT DEFAULT '{}',
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- Exploration History 表
    CREATE TABLE IF NOT EXISTS exploration_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        from_topic TEXT,
        to_topic TEXT NOT NULL,
        via_tag TEXT,
        tag_type TEXT,
        duration REAL DEFAULT 0,
        created_at REAL DEFAULT (julianday('now')),
        FOREIGN KEY (session_id) REFERENCES learning_sessions(id)
    );

    -- 创建索引
    CREATE INDEX IF NOT EXISTS idx_sessions_created ON learning_sessions(created_at);
    CREATE INDEX IF NOT EXISTS idx_exploration_session ON exploration_history(session_id);
    """


# v12: 添加智能记忆与决策支持相关表
@register_migration(12, "add_memory_and_decision_tables", "添加智能记忆与决策支持相关表")
def migrate_v12(conn: sqlite3.Connection):
    """-- 智能记忆表
    CREATE TABLE IF NOT EXISTS qa_pairs (
        id TEXT PRIMARY KEY,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        question_keywords TEXT DEFAULT '[]',
        answer_entities TEXT DEFAULT '[]',
        quality_score REAL DEFAULT 1.0,
        usage_count INTEGER DEFAULT 0,
        last_used REAL DEFAULT 0,
        created_at REAL DEFAULT (julianday('now')),
        is_verified INTEGER DEFAULT 0,
        tags TEXT DEFAULT '[]'
    );

    -- 实体表
    CREATE TABLE IF NOT EXISTS entities (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        entity_type TEXT DEFAULT '',
        aliases TEXT DEFAULT '[]',
        description TEXT DEFAULT '',
        attributes TEXT DEFAULT '{}',
        confidence REAL DEFAULT 1.0,
        created_at REAL DEFAULT (julianday('now')),
        last_updated REAL DEFAULT (julianday('now'))
    );

    -- 关系表
    CREATE TABLE IF NOT EXISTS relations (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        relation_type TEXT NOT NULL,
        confidence REAL DEFAULT 1.0,
        context TEXT DEFAULT '',
        created_at REAL DEFAULT (julianday('now'))
    );

    -- 事实表
    CREATE TABLE IF NOT EXISTS facts (
        id TEXT PRIMARY KEY,
        subject TEXT NOT NULL,
        predicate TEXT NOT NULL,
        object TEXT NOT NULL,
        context TEXT DEFAULT '',
        confidence REAL DEFAULT 1.0,
        source TEXT DEFAULT '',
        created_at REAL DEFAULT (julianday('now')),
        last_verified REAL DEFAULT (julianday('now')),
        value_level INTEGER DEFAULT 2
    );

    -- 用户偏好表
    CREATE TABLE IF NOT EXISTS user_preferences (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- 投资画像表
    CREATE TABLE IF NOT EXISTS investment_profiles (
        user_id TEXT PRIMARY KEY,
        risk_tolerance REAL DEFAULT 0.5,
        investment_experience TEXT DEFAULT 'beginner',
        capital_size TEXT DEFAULT 'small',
        investment_horizon TEXT DEFAULT 'short',
        preferred_sectors TEXT DEFAULT '[]',
        excluded_sectors TEXT DEFAULT '[]',
        has_stop_loss_experience INTEGER DEFAULT 0,
        has_margin_experience INTEGER DEFAULT 0,
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- 决策记录表
    CREATE TABLE IF NOT EXISTS decision_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        symbol TEXT,
        report_data TEXT NOT NULL,
        selected_strategy TEXT,
        execution_status TEXT DEFAULT 'pending',
        outcome TEXT,
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- 情景分析历史表
    CREATE TABLE IF NOT EXISTS scenario_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        symbol TEXT,
        scenario_type TEXT,
        probability REAL,
        price_target_low REAL,
        price_target_high REAL,
        trigger_conditions TEXT,
        created_at REAL DEFAULT (julianday('now'))
    );

    -- 策略回测表
    CREATE TABLE IF NOT EXISTS strategy_backtests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        symbol TEXT,
        strategy_type TEXT,
        entry_price REAL,
        exit_price REAL,
        return_pct REAL,
        holding_days INTEGER,
        created_at REAL DEFAULT (julianday('now'))
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_qa_question ON qa_pairs(question);
    CREATE INDEX IF NOT EXISTS idx_qa_usage ON qa_pairs(usage_count DESC);
    CREATE INDEX IF NOT EXISTS idx_entity_name ON entities(name);
    CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject);
    CREATE INDEX IF NOT EXISTS idx_decision_user ON decision_records(user_id);
    CREATE INDEX IF NOT EXISTS idx_decision_symbol ON decision_records(symbol);
    """


# v13: 添加文档审核与生命周期管理相关表
@register_migration(13, "add_doc_lifecycle_tables", "添加文档审核与生命周期管理相关表")
def migrate_v13(conn: sqlite3.Connection):
    """-- 文档信息表
    CREATE TABLE IF NOT EXISTS documents (
        doc_id TEXT PRIMARY KEY,
        file_path TEXT UNIQUE NOT NULL,
        file_name TEXT NOT NULL,
        file_type TEXT DEFAULT 'unknown',
        file_size INTEGER DEFAULT 0,
        hash_value TEXT,
        metadata TEXT DEFAULT '{}',
        created_at REAL,
        modified_at REAL,
        accessed_at REAL
    );

    -- 审核任务表
    CREATE TABLE IF NOT EXISTS review_tasks (
        task_id TEXT PRIMARY KEY,
        doc_id TEXT NOT NULL,
        review_level TEXT DEFAULT 'standard',
        status TEXT DEFAULT 'pending',
        priority INTEGER DEFAULT 5,
        progress REAL DEFAULT 0,
        error_message TEXT,
        result TEXT,
        retry_count INTEGER DEFAULT 0,
        max_retries INTEGER DEFAULT 3,
        created_at REAL,
        started_at REAL,
        completed_at REAL
    );

    -- 审核结果表
    CREATE TABLE IF NOT EXISTS review_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL,
        doc_id TEXT NOT NULL,
        quality_score REAL DEFAULT 0,
        accuracy_score REAL DEFAULT 0,
        completeness_score REAL DEFAULT 0,
        consistency_score REAL DEFAULT 0,
        clarity_score REAL DEFAULT 0,
        professionalism_score REAL DEFAULT 0,
        innovation_score REAL DEFAULT 0,
        issues TEXT DEFAULT '[]',
        suggestions TEXT DEFAULT '[]',
        category TEXT DEFAULT '',
        tags TEXT DEFAULT '[]',
        summary TEXT DEFAULT '',
        processing_time REAL DEFAULT 0,
        sensitive_words_found TEXT DEFAULT '[]',
        risk_level TEXT DEFAULT 'low',
        created_at REAL
    );

    -- 报告表
    CREATE TABLE IF NOT EXISTS reports (
        report_id TEXT PRIMARY KEY,
        task_id TEXT,
        doc_id TEXT,
        report_type TEXT DEFAULT 'single',
        report_format TEXT DEFAULT 'html',
        file_path TEXT NOT NULL,
        file_size INTEGER DEFAULT 0,
        title TEXT,
        download_count INTEGER DEFAULT 0,
        active_score REAL DEFAULT 100,
        retention_policy TEXT DEFAULT 'default',
        clean_status TEXT DEFAULT 'normal',
        created_at REAL,
        last_access REAL
    );

    -- 清理规则表
    CREATE TABLE IF NOT EXISTS cleanup_rules (
        rule_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        enabled INTEGER DEFAULT 1,
        min_activity_score REAL DEFAULT 0,
        max_activity_score REAL DEFAULT 100,
        min_file_age_days INTEGER DEFAULT 0,
        max_file_size INTEGER DEFAULT 0,
        allowed_extensions TEXT DEFAULT '[]',
        excluded_extensions TEXT DEFAULT '[]',
        excluded_paths TEXT DEFAULT '[]',
        action TEXT DEFAULT 'archive',
        require_confirmation INTEGER DEFAULT 1,
        notification_enabled INTEGER DEFAULT 1,
        schedule_type TEXT DEFAULT 'daily',
        schedule_time TEXT DEFAULT '02:00',
        notification_before_days INTEGER DEFAULT 7,
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- 清理任务表
    CREATE TABLE IF NOT EXISTS cleanup_tasks (
        task_id TEXT PRIMARY KEY,
        file_path TEXT NOT NULL,
        action TEXT DEFAULT 'archive',
        status TEXT DEFAULT 'pending',
        result TEXT,
        space_freed INTEGER DEFAULT 0,
        executed_at REAL,
        created_at REAL DEFAULT (julianday('now')),
        approved_by TEXT,
        approved_at REAL
    );

    -- 清理历史表
    CREATE TABLE IF NOT EXISTS cleanup_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL,
        action TEXT NOT NULL,
        status TEXT NOT NULL,
        file_size INTEGER,
        space_freed INTEGER,
        executed_at REAL DEFAULT (julianday('now')),
        error_message TEXT
    );

    -- 文件访问记录表
    CREATE TABLE IF NOT EXISTS file_access_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL,
        access_type TEXT DEFAULT 'read',
        accessed_at REAL DEFAULT (julianday('now')),
        UNIQUE(file_path, accessed_at)
    );

    -- 用户文件标记表
    CREATE TABLE IF NOT EXISTS user_file_marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT UNIQUE NOT NULL,
        is_starred INTEGER DEFAULT 0,
        is_critical INTEGER DEFAULT 0,
        tags TEXT DEFAULT '[]',
        marked_at REAL DEFAULT (julianday('now'))
    );

    -- 文件引用表
    CREATE TABLE IF NOT EXISTS file_references (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_file TEXT NOT NULL,
        target_file TEXT NOT NULL,
        reference_type TEXT DEFAULT 'link',
        created_at REAL DEFAULT (julianday('now')),
        UNIQUE(source_file, target_file)
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_docs_path ON documents(file_path);
    CREATE INDEX IF NOT EXISTS idx_tasks_status ON review_tasks(status);
    CREATE INDEX IF NOT EXISTS idx_tasks_doc ON review_tasks(doc_id);
    CREATE INDEX IF NOT EXISTS idx_results_task ON review_results(task_id);
    CREATE INDEX IF NOT EXISTS idx_reports_doc ON reports(doc_id);
    CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at);
    CREATE INDEX IF NOT EXISTS idx_access_file ON file_access_logs(file_path);
    CREATE INDEX IF NOT EXISTS idx_access_time ON file_access_logs(accessed_at);
    """


# v14: 添加强容错分布式任务处理系统相关表
@register_migration(14, "add_fault_tolerance_tables", "添加强容错分布式任务处理系统相关表")
def migrate_v14(conn: sqlite3.Connection):
    """-- 分布式任务表
    CREATE TABLE IF NOT EXISTS ft_tasks (
        task_id TEXT PRIMARY KEY,
        task_type TEXT DEFAULT 'batch',
        status TEXT DEFAULT 'pending',
        priority INTEGER DEFAULT 5,
        payload TEXT DEFAULT '{}',
        result TEXT,
        assigned_node TEXT,
        backup_node TEXT,
        progress REAL DEFAULT 0,
        retry_count INTEGER DEFAULT 0,
        max_retries INTEGER DEFAULT 3,
        checkpoint_id TEXT,
        error_message TEXT,
        fault_history TEXT DEFAULT '[]',
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now')),
        started_at REAL,
        completed_at REAL
    );

    -- 分布式节点表
    CREATE TABLE IF NOT EXISTS ft_nodes (
        node_id TEXT PRIMARY KEY,
        node_name TEXT NOT NULL,
        role TEXT DEFAULT 'worker',
        status TEXT DEFAULT 'active',
        cpu_cores INTEGER DEFAULT 4,
        memory_gb REAL DEFAULT 8,
        storage_gb REAL DEFAULT 100,
        network_bandwidth_mbps INTEGER DEFAULT 100,
        cpu_usage REAL DEFAULT 0,
        memory_usage REAL DEFAULT 0,
        active_tasks INTEGER DEFAULT 0,
        host TEXT,
        port INTEGER DEFAULT 8766,
        last_heartbeat REAL,
        reliability_score REAL DEFAULT 100,
        total_tasks INTEGER DEFAULT 0,
        failed_tasks INTEGER DEFAULT 0,
        avg_response_time REAL DEFAULT 0,
        election_term INTEGER DEFAULT 0,
        is_leader INTEGER DEFAULT 0,
        voted_for TEXT,
        tags TEXT DEFAULT '[]',
        metadata TEXT DEFAULT '{}',
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- 故障记录表
    CREATE TABLE IF NOT EXISTS ft_faults (
        fault_id TEXT PRIMARY KEY,
        fault_type TEXT NOT NULL,
        severity TEXT DEFAULT 'low',
        node_id TEXT,
        task_id TEXT,
        description TEXT,
        error_code TEXT,
        stack_trace TEXT,
        affected_tasks TEXT DEFAULT '[]',
        affected_nodes TEXT DEFAULT '[]',
        is_resolved INTEGER DEFAULT 0,
        resolution TEXT,
        resolved_at REAL,
        detected_at REAL DEFAULT (julianday('now')),
        created_at REAL DEFAULT (julianday('now'))
    );

    -- 检查点表
    CREATE TABLE IF NOT EXISTS ft_checkpoints (
        checkpoint_id TEXT PRIMARY KEY,
        checkpoint_type TEXT DEFAULT 'incremental',
        task_id TEXT NOT NULL,
        node_id TEXT,
        state_data TEXT DEFAULT '{}',
        state_size INTEGER DEFAULT 0,
        storage_path TEXT,
        storage_type TEXT DEFAULT 'local',
        sequence_number INTEGER DEFAULT 0,
        is_valid INTEGER DEFAULT 1,
        parent_checkpoint_id TEXT,
        created_at REAL DEFAULT (julianday('now')),
        expires_at REAL
    );

    -- 恢复记录表
    CREATE TABLE IF NOT EXISTS ft_recovery_records (
        record_id TEXT PRIMARY KEY,
        fault_id TEXT,
        fault_type TEXT NOT NULL,
        strategy TEXT DEFAULT 'auto_retry',
        source_node TEXT,
        target_node TEXT,
        recovered_task_id TEXT,
        checkpoint_id TEXT,
        is_success INTEGER DEFAULT 0,
        recovery_time_ms INTEGER DEFAULT 0,
        data_loss INTEGER DEFAULT 0,
        details TEXT DEFAULT '{}',
        started_at REAL DEFAULT (julianday('now')),
        completed_at REAL
    );

    -- 网络分区表
    CREATE TABLE IF NOT EXISTS ft_network_partitions (
        partition_id TEXT PRIMARY KEY,
        primary_nodes TEXT DEFAULT '[]',
        secondary_nodes TEXT DEFAULT '[]',
        is_active INTEGER DEFAULT 1,
        is_resolved INTEGER DEFAULT 0,
        detected_at REAL DEFAULT (julianday('now')),
        resolved_at REAL
    );

    -- 告警表
    CREATE TABLE IF NOT EXISTS ft_alerts (
        alert_id TEXT PRIMARY KEY,
        level TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT,
        source TEXT,
        acknowledged INTEGER DEFAULT 0,
        resolved INTEGER DEFAULT 0,
        metadata TEXT DEFAULT '{}',
        created_at REAL DEFAULT (julianday('now'))
    );

    -- 任务指标表
    CREATE TABLE IF NOT EXISTS ft_task_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL,
        scheduled_at REAL,
        started_at REAL,
        completed_at REAL,
        execution_time_ms INTEGER DEFAULT 0,
        wait_time_ms INTEGER DEFAULT 0,
        retries INTEGER DEFAULT 0,
        node_id TEXT,
        UNIQUE(task_id)
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_ft_tasks_status ON ft_tasks(status);
    CREATE INDEX IF NOT EXISTS idx_ft_tasks_node ON ft_tasks(assigned_node);
    CREATE INDEX IF NOT EXISTS idx_ft_nodes_status ON ft_nodes(status);
    CREATE INDEX IF NOT EXISTS idx_ft_nodes_role ON ft_nodes(role);
    CREATE INDEX IF NOT EXISTS idx_ft_faults_resolved ON ft_faults(is_resolved);
    CREATE INDEX IF NOT EXISTS idx_ft_faults_node ON ft_faults(node_id);
    CREATE INDEX IF NOT EXISTS idx_ft_checkpoints_task ON ft_checkpoints(task_id);
    CREATE INDEX IF NOT EXISTS idx_ft_recovery_task ON ft_recovery_records(recovered_task_id);
    CREATE INDEX IF NOT EXISTS idx_ft_alerts_level ON ft_alerts(level);
    """


# v15: 添加去中心化电商 (DeCommerce) 相关表
@register_migration(15, "add_decommerce_tables", "添加去中心化电商相关表")
def migrate_v15(conn: sqlite3.Connection):
    """-- 卖家表
    CREATE TABLE IF NOT EXISTS decommerce_sellers (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        avatar_url TEXT,
        bio TEXT DEFAULT '',
        connectivity TEXT DEFAULT 'poor',
        endpoint TEXT,
        has_ai_service INTEGER DEFAULT 0,
        ai_models TEXT DEFAULT '[]',
        total_services INTEGER DEFAULT 0,
        total_orders INTEGER DEFAULT 0,
        rating REAL DEFAULT 0.0,
        is_online INTEGER DEFAULT 0,
        last_seen_at REAL,
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- 商品/服务表
    CREATE TABLE IF NOT EXISTS decommerce_listings (
        id TEXT PRIMARY KEY,
        seller_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        price INTEGER DEFAULT 0,
        currency TEXT DEFAULT 'CNY',
        service_type TEXT DEFAULT 'physical_product',
        delivery_type TEXT DEFAULT 'instant',
        endpoint TEXT,
        thumbnail_url TEXT,
        media_urls TEXT DEFAULT '[]',
        ai_model TEXT,
        ai_capabilities TEXT DEFAULT '[]',
        is_live_available INTEGER DEFAULT 0,
        max_concurrent INTEGER DEFAULT 1,
        status TEXT DEFAULT 'draft',
        view_count INTEGER DEFAULT 0,
        order_count INTEGER DEFAULT 0,
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now')),
        last_live_at REAL,
        FOREIGN KEY (seller_id) REFERENCES decommerce_sellers(id)
    );

    -- 服务会话表
    CREATE TABLE IF NOT EXISTS decommerce_sessions (
        id TEXT PRIMARY KEY,
        listing_id TEXT NOT NULL,
        seller_id TEXT NOT NULL,
        buyer_id TEXT NOT NULL,
        session_type TEXT DEFAULT 'remote_live_view',
        room_id TEXT,
        room_password TEXT,
        status TEXT DEFAULT 'pending',
        billing_start REAL,
        billing_end REAL,
        billing_duration_seconds INTEGER DEFAULT 0,
        billing_amount INTEGER DEFAULT 0,
        last_heartbeat_seller REAL DEFAULT 0,
        last_heartbeat_buyer REAL DEFAULT 0,
        access_token TEXT,
        token_expires_at REAL,
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now')),
        FOREIGN KEY (listing_id) REFERENCES decommerce_listings(id)
    );

    -- AI任务表
    CREATE TABLE IF NOT EXISTS decommerce_ai_jobs (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        task_type TEXT DEFAULT 'chat',
        prompt TEXT,
        model TEXT,
        parameters TEXT DEFAULT '{}',
        result TEXT,
        error TEXT,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        status TEXT DEFAULT 'queued',
        queued_at REAL DEFAULT (julianday('now')),
        started_at REAL,
        completed_at REAL,
        FOREIGN KEY (session_id) REFERENCES decommerce_sessions(id)
    );

    -- 订单表
    CREATE TABLE IF NOT EXISTS decommerce_orders (
        id TEXT PRIMARY KEY,
        listing_id TEXT,
        session_id TEXT,
        seller_id TEXT NOT NULL,
        buyer_id TEXT NOT NULL,
        total_amount INTEGER DEFAULT 0,
        commission_fee INTEGER DEFAULT 0,
        net_amount INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        payment_method TEXT DEFAULT '',
        payment_id TEXT,
        created_at REAL DEFAULT (julianday('now')),
        paid_at REAL,
        completed_at REAL
    );

    -- 支付记录表
    CREATE TABLE IF NOT EXISTS decommerce_payments (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        payment_type TEXT DEFAULT 'frozen',
        amount INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        transaction_id TEXT,
        metadata TEXT DEFAULT '{}',
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now')),
        FOREIGN KEY (order_id) REFERENCES decommerce_orders(id)
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_sellers_user ON decommerce_sellers(user_id);
    CREATE INDEX IF NOT EXISTS idx_sellers_online ON decommerce_sellers(is_online);
    CREATE INDEX IF NOT EXISTS idx_listings_seller ON decommerce_listings(seller_id);
    CREATE INDEX IF NOT EXISTS idx_listings_status ON decommerce_listings(status);
    CREATE INDEX IF NOT EXISTS idx_listings_type ON decommerce_listings(service_type);
    CREATE INDEX IF NOT EXISTS idx_sessions_listing ON decommerce_sessions(listing_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_seller ON decommerce_sessions(seller_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_buyer ON decommerce_sessions(buyer_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_status ON decommerce_sessions(status);
    CREATE INDEX IF NOT EXISTS idx_ai_jobs_session ON decommerce_ai_jobs(session_id);
    CREATE INDEX IF NOT EXISTS idx_ai_jobs_status ON decommerce_ai_jobs(status);
    CREATE INDEX IF NOT EXISTS idx_orders_seller ON decommerce_orders(seller_id);
    CREATE INDEX IF NOT EXISTS idx_orders_buyer ON decommerce_orders(buyer_id);
    CREATE INDEX IF NOT EXISTS idx_orders_status ON decommerce_orders(status);
    CREATE INDEX IF NOT EXISTS idx_payments_order ON decommerce_payments(order_id);
    """


# v16: 添加 AI 算力仪表盘相关表
@register_migration(16, "add_ai_capability_tables", "添加 AI 算力仪表盘相关表")
def migrate_v16(conn: sqlite3.Connection):
    """-- AI 能力画像表
    CREATE TABLE IF NOT EXISTS ai_capability_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_hash TEXT UNIQUE NOT NULL,
        cpu_model TEXT,
        cpu_cores INTEGER,
        cpu_threads INTEGER,
        cpu_arch TEXT,
        ram_total_gb REAL,
        ram_available_gb REAL,
        ram_type TEXT,
        gpu_renderer TEXT,
        gpu_vram_gb REAL,
        gpu_vendor TEXT,
        has_webgl INTEGER DEFAULT 0,
        has_gpu INTEGER DEFAULT 0,
        os_platform TEXT,
        best_model TEXT,
        best_speed INTEGER DEFAULT 0,
        model_count INTEGER DEFAULT 0,
        profile_data TEXT,
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- AI 能力共享记录表
    CREATE TABLE IF NOT EXISTS ai_capability_shares (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_hash TEXT NOT NULL,
        shared_with_peer TEXT,
        share_method TEXT DEFAULT 'p2p',
        shared_at REAL DEFAULT (julianday('now')),
        note TEXT,
        FOREIGN KEY (profile_hash) REFERENCES ai_capability_profiles(profile_hash)
    );

    -- AI 模型兼容性记录表
    CREATE TABLE IF NOT EXISTS ai_model_compatibility (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_hash TEXT NOT NULL,
        model_name TEXT NOT NULL,
        provider TEXT,
        params TEXT,
        vram_required_gb REAL,
        compatibility TEXT DEFAULT 'unknown',
        estimated_speed INTEGER DEFAULT 0,
        tested_at REAL DEFAULT (julianday('now')),
        FOREIGN KEY (profile_hash) REFERENCES ai_capability_profiles(profile_hash)
    );

    -- AI 服务发布记录表
    CREATE TABLE IF NOT EXISTS ai_service_listings (
        id TEXT PRIMARY KEY,
        profile_hash TEXT NOT NULL,
        service_name TEXT NOT NULL,
        service_type TEXT DEFAULT 'text_chat',
        model_name TEXT,
        price_per_hour REAL DEFAULT 1.0,
        description TEXT,
        listing_data TEXT,
        status TEXT DEFAULT 'active',
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now')),
        FOREIGN KEY (profile_hash) REFERENCES ai_capability_profiles(profile_hash)
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_profiles_hash ON ai_capability_profiles(profile_hash);
    CREATE INDEX IF NOT EXISTS idx_shares_profile ON ai_capability_shares(profile_hash);
    CREATE INDEX IF NOT EXISTS idx_compat_profile ON ai_model_compatibility(profile_hash);
    CREATE INDEX IF NOT EXISTS idx_services_profile ON ai_service_listings(profile_hash);
    CREATE INDEX IF NOT EXISTS idx_services_status ON ai_service_listings(status);
    """


# v17: 添加根系同步 (Root Sync) 相关表
@register_migration(17, "add_root_sync_tables", "添加根系同步去中心化文件同步相关表")
def migrate_v17(conn: sqlite3.Connection):
    """-- 设备注册表
    CREATE TABLE IF NOT EXISTS rs_devices (
        device_id TEXT PRIMARY KEY,
        device_name TEXT NOT NULL,
        public_key TEXT,
        address TEXT,
        port INTEGER DEFAULT 22000,
        status TEXT DEFAULT 'offline',
        last_seen REAL,
        cert_fingerprint TEXT,
        is_self INTEGER DEFAULT 0,
        compression TEXT DEFAULT 'always',
        introducer INTEGER DEFAULT 0,
        auto_accept_folders INTEGER DEFAULT 0,
        max_send_rate INTEGER DEFAULT 0,
        max_recv_rate INTEGER DEFAULT 0,
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- 同步文件夹表
    CREATE TABLE IF NOT EXISTS rs_folders (
        folder_id TEXT PRIMARY KEY,
        label TEXT,
        path TEXT NOT NULL,
        folder_type TEXT DEFAULT 'sendreceive',
        rescan_interval INTEGER DEFAULT 60,
        fs_watcher_enabled INTEGER DEFAULT 1,
        fs_watcher_delay INTEGER DEFAULT 10,
        ignore_patterns TEXT DEFAULT '[]',
        versioning_type TEXT DEFAULT 'simple',
        versioning_params TEXT DEFAULT '{}',
        max_version_count INTEGER DEFAULT 5,
        copiers INTEGER DEFAULT 1,
        puller_pause INTEGER DEFAULT 0,
        puller_pending_kib INTEGER DEFAULT 512,
        weak_hash_threshold_pct INTEGER DEFAULT 25,
        scan_progress_interval INTEGER DEFAULT 0,
        status TEXT DEFAULT 'idle',
        local_files INTEGER DEFAULT 0,
        local_size INTEGER DEFAULT 0,
        need_files INTEGER DEFAULT 0,
        need_size INTEGER DEFAULT 0,
        last_scan REAL,
        last_sync REAL,
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- 文件夹-设备关联表
    CREATE TABLE IF NOT EXISTS rs_folder_devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        folder_id TEXT NOT NULL,
        device_id TEXT NOT NULL,
        share_type TEXT DEFAULT 'sendreceive',
        index_id TEXT,
        local_deleted INTEGER DEFAULT 0,
        remote_deleted INTEGER DEFAULT 0,
        last_seen_remote INTEGER DEFAULT 0,
        created_at REAL DEFAULT (julianday('now')),
        UNIQUE(folder_id, device_id),
        FOREIGN KEY (folder_id) REFERENCES rs_folders(folder_id),
        FOREIGN KEY (device_id) REFERENCES rs_devices(device_id)
    );

    -- 文件索引表
    CREATE TABLE IF NOT EXISTS rs_file_index (
        file_id TEXT PRIMARY KEY,
        folder_id TEXT NOT NULL,
        path TEXT NOT NULL,
        file_type TEXT DEFAULT 'file',
        size INTEGER DEFAULT 0,
        mtime REAL,
        permissions TEXT DEFAULT '0644',
        chunk_count INTEGER DEFAULT 0,
        root_hash TEXT,
        local_version INTEGER DEFAULT 0,
        deleted INTEGER DEFAULT 0,
        invalid INTEGER DEFAULT 0,
        device_id TEXT,
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now')),
        UNIQUE(folder_id, path),
        FOREIGN KEY (folder_id) REFERENCES rs_folders(folder_id)
    );

    -- 块索引表
    CREATE TABLE IF NOT EXISTS rs_chunk_index (
        chunk_id TEXT PRIMARY KEY,
        file_id TEXT NOT NULL,
        offset INTEGER DEFAULT 0,
        size INTEGER DEFAULT 0,
        hash TEXT NOT NULL,
        compressed_hash TEXT,
        is_compressed INTEGER DEFAULT 0,
        created_at REAL DEFAULT (julianday('now')),
        FOREIGN KEY (file_id) REFERENCES rs_file_index(file_id)
    );

    -- 文件版本表
    CREATE TABLE IF NOT EXISTS rs_file_versions (
        version_id TEXT PRIMARY KEY,
        file_id TEXT NOT NULL,
        version_type TEXT DEFAULT 'simple',
        version_num INTEGER DEFAULT 1,
        source_path TEXT,
        version_path TEXT,
        size INTEGER DEFAULT 0,
        mtime REAL,
        device_id TEXT,
        metadata TEXT DEFAULT '{}',
        created_at REAL DEFAULT (julianday('now')),
        expires_at REAL,
        FOREIGN KEY (file_id) REFERENCES rs_file_index(file_id)
    );

    -- 同步历史表
    CREATE TABLE IF NOT EXISTS rs_sync_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        folder_id TEXT NOT NULL,
        file_path TEXT NOT NULL,
        action TEXT NOT NULL,
        direction TEXT DEFAULT 'download',
        size INTEGER DEFAULT 0,
        duration_ms INTEGER DEFAULT 0,
        status TEXT DEFAULT 'completed',
        error_message TEXT,
        device_id TEXT,
        chunk_count INTEGER DEFAULT 0,
        bytes_transferred INTEGER DEFAULT 0,
        started_at REAL DEFAULT (julianday('now')),
        completed_at REAL,
        FOREIGN KEY (folder_id) REFERENCES rs_folders(folder_id)
    );

    -- 冲突记录表
    CREATE TABLE IF NOT EXISTS rs_conflicts (
        conflict_id TEXT PRIMARY KEY,
        folder_id TEXT NOT NULL,
        file_path TEXT NOT NULL,
        local_version TEXT,
        remote_version TEXT,
        local_device_id TEXT,
        remote_device_id TEXT,
        resolution_strategy TEXT,
        resolution TEXT,
        local_size INTEGER DEFAULT 0,
        remote_size INTEGER DEFAULT 0,
        local_mtime REAL,
        remote_mtime REAL,
        is_resolved INTEGER DEFAULT 0,
        resolved_at REAL,
        created_at REAL DEFAULT (julianday('now')),
        FOREIGN KEY (folder_id) REFERENCES rs_folders(folder_id)
    );

    -- 中继连接表
    CREATE TABLE IF NOT EXISTS rs_relay_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        relay_url TEXT NOT NULL,
        peer_device_id TEXT NOT NULL,
        connection_id TEXT,
        bytes_sent INTEGER DEFAULT 0,
        bytes_received INTEGER DEFAULT 0,
        latency_ms INTEGER DEFAULT 0,
        status TEXT DEFAULT 'connected',
        connected_at REAL DEFAULT (julianday('now')),
        disconnected_at REAL
    );

    -- 全局发现记录表
    CREATE TABLE IF NOT EXISTS rs_discovery_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT NOT NULL,
        discovery_type TEXT DEFAULT 'local',
        address TEXT NOT NULL,
        port INTEGER DEFAULT 22000,
        is_reachable INTEGER DEFAULT 0,
        last_check REAL DEFAULT (julianday('now')),
        UNIQUE(device_id, discovery_type, address)
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_rs_devices_status ON rs_devices(status);
    CREATE INDEX IF NOT EXISTS idx_rs_folders_status ON rs_folders(status);
    CREATE INDEX IF NOT EXISTS idx_rs_folder_devices_folder ON rs_folder_devices(folder_id);
    CREATE INDEX IF NOT EXISTS idx_rs_folder_devices_device ON rs_folder_devices(device_id);
    CREATE INDEX IF NOT EXISTS idx_rs_file_index_folder ON rs_file_index(folder_id);
    CREATE INDEX IF NOT EXISTS idx_rs_file_index_path ON rs_file_index(path);
    CREATE INDEX IF NOT EXISTS idx_rs_file_index_deleted ON rs_file_index(deleted);
    CREATE INDEX IF NOT EXISTS idx_rs_chunk_index_file ON rs_chunk_index(file_id);
    CREATE INDEX IF NOT EXISTS idx_rs_chunk_index_hash ON rs_chunk_index(hash);
    CREATE INDEX IF NOT EXISTS idx_rs_versions_file ON rs_file_versions(file_id);
    CREATE INDEX IF NOT EXISTS idx_rs_history_folder ON rs_sync_history(folder_id);
    CREATE INDEX IF NOT EXISTS idx_rs_history_status ON rs_sync_history(status);
    CREATE INDEX IF NOT EXISTS idx_rs_history_time ON rs_sync_history(started_at);
    CREATE INDEX IF NOT EXISTS idx_rs_conflicts_folder ON rs_conflicts(folder_id);
    CREATE INDEX IF NOT EXISTS idx_rs_conflicts_resolved ON rs_conflicts(is_resolved);
    CREATE INDEX IF NOT EXISTS idx_rs_relay_status ON rs_relay_connections(status);
    CREATE INDEX IF NOT EXISTS idx_rs_discovery_device ON rs_discovery_records(device_id);
    """


# v18: GitHub Store 桌面代码仓库
@register_migration(18, "add_github_store_tables", "添加 GitHub Store 桌面代码仓库相关表")
def migrate_v18(conn: sqlite3.Connection):
    """
    -- GitHub Token 配置
    CREATE TABLE IF NOT EXISTS gs_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_name TEXT DEFAULT 'default',
        token_hash TEXT NOT NULL,
        rate_limit_remaining INTEGER DEFAULT 60,
        rate_limit_reset REAL,
        created_at REAL DEFAULT (julianday('now')),
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- 缓存的仓库信息
    CREATE TABLE IF NOT EXISTS gs_repo_cache (
        repo_id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        owner TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        html_url TEXT,
        stars INTEGER DEFAULT 0,
        forks INTEGER DEFAULT 0,
        language TEXT,
        topics TEXT DEFAULT '[]',
        license TEXT,
        latest_release_version TEXT,
        latest_release_date REAL,
        is_installable INTEGER DEFAULT 0,
        last_checked REAL DEFAULT (julianday('now')),
        created_at REAL DEFAULT (julianday('now')),
        UNIQUE(full_name)
    );

    -- 已安装应用
    CREATE TABLE IF NOT EXISTS gs_installed_apps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_id TEXT NOT NULL,
        full_name TEXT NOT NULL,
        installed_version TEXT NOT NULL,
        installed_at REAL DEFAULT (julianday('now')),
        install_path TEXT,
        asset_name TEXT,
        asset_size INTEGER DEFAULT 0,
        platform TEXT,
        architecture TEXT,
        current_version TEXT,
        update_available INTEGER DEFAULT 0,
        download_url TEXT,
        notes TEXT,
        UNIQUE(full_name)
    );

    -- 收藏列表
    CREATE TABLE IF NOT EXISTS gs_favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL UNIQUE,
        added_at REAL DEFAULT (julianday('now'))
    );

    -- 星标列表 (GitHub 星标同步)
    CREATE TABLE IF NOT EXISTS gs_starred (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL UNIQUE,
        starred_at REAL DEFAULT (julianday('now'))
    );

    -- 最近浏览
    CREATE TABLE IF NOT EXISTS gs_recent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL UNIQUE,
        viewed_at REAL DEFAULT (julianday('now'))
    );

    -- 下载任务
    CREATE TABLE IF NOT EXISTS gs_download_tasks (
        task_id TEXT PRIMARY KEY,
        repo_full_name TEXT NOT NULL,
        version TEXT,
        asset_name TEXT NOT NULL,
        download_url TEXT NOT NULL,
        file_size INTEGER DEFAULT 0,
        downloaded_size INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        progress REAL DEFAULT 0,
        download_path TEXT,
        started_at REAL,
        completed_at REAL,
        error_message TEXT,
        retry_count INTEGER DEFAULT 0
    );

    -- 安装历史
    CREATE TABLE IF NOT EXISTS gs_install_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        action TEXT NOT NULL,
        version TEXT,
        timestamp REAL DEFAULT (julianday('now'))
    );

    -- 分类信息缓存
    CREATE TABLE IF NOT EXISTS gs_category_cache (
        category_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        icon TEXT,
        topics TEXT DEFAULT '[]',
        repo_count INTEGER DEFAULT 0,
        last_updated REAL DEFAULT (julianday('now'))
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_gs_repo_cache_stars ON gs_repo_cache(stars DESC);
    CREATE INDEX IF NOT EXISTS idx_gs_repo_cache_installable ON gs_repo_cache(is_installable);
    CREATE INDEX IF NOT EXISTS idx_gs_repo_cache_last_checked ON gs_repo_cache(last_checked);
    CREATE INDEX IF NOT EXISTS idx_gs_installed_update ON gs_installed_apps(update_available);
    CREATE INDEX IF NOT EXISTS idx_gs_installed_platform ON gs_installed_apps(platform);
    CREATE INDEX IF NOT EXISTS idx_gs_download_status ON gs_download_tasks(status);
    CREATE INDEX IF NOT EXISTS idx_gs_history_time ON gs_install_history(timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_gs_favorites_added ON gs_favorites(added_at DESC);
    CREATE INDEX IF NOT EXISTS idx_gs_starred_time ON gs_starred(starred_at DESC);
    CREATE INDEX IF NOT EXISTS idx_gs_recent_viewed ON gs_recent(viewed_at DESC);
    """


# v19: Database Browser 桌面数据库管理 (onetcli 风格)
@register_migration(19, "add_database_browser_tables", "添加数据库浏览器相关表")
def migrate_v19(conn: sqlite3.Connection):
    """
    -- 数据库连接配置 (由 DatabaseBrowser 内部管理，存储在独立 db)
    -- 查询历史表
    CREATE TABLE IF NOT EXISTS db_query_history (
        id TEXT PRIMARY KEY,
        connection_id TEXT,
        sql TEXT NOT NULL,
        execution_time REAL,
        row_count INTEGER,
        is_error INTEGER DEFAULT 0,
        timestamp REAL DEFAULT (julianday('now'))
    );

    -- 收藏查询
    CREATE TABLE IF NOT EXISTS db_favorite_queries (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        sql TEXT NOT NULL,
        connection_id TEXT,
        description TEXT,
        created_at REAL DEFAULT (julianday('now'))
    );

    -- 查询模板
    CREATE TABLE IF NOT EXISTS db_query_templates (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        sql TEXT NOT NULL,
        description TEXT,
        db_types TEXT DEFAULT '[]',
        created_at REAL DEFAULT (julianday('now'))
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_db_history_timestamp ON db_query_history(timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_db_history_connection ON db_query_history(connection_id);
    CREATE INDEX IF NOT EXISTS idx_db_favorites_created ON db_favorite_queries(created_at DESC);
    """


# v20: Preview Panel 文档预览与编辑
@register_migration(20, "add_preview_panel_tables", "添加文档预览面板相关表")
def migrate_v20(conn: sqlite3.Connection):
    """
    -- 预览历史
    CREATE TABLE IF NOT EXISTS pp_preview_history (
        id TEXT PRIMARY KEY,
        file_path TEXT NOT NULL,
        preview_count INTEGER DEFAULT 1,
        last_preview_time REAL DEFAULT (julianday('now')),
        favorite INTEGER DEFAULT 0,
        tags TEXT DEFAULT '[]',
        file_type TEXT,
        UNIQUE(file_path)
    );

    -- 收藏文件
    CREATE TABLE IF NOT EXISTS pp_favorites (
        id TEXT PRIMARY KEY,
        file_path TEXT NOT NULL UNIQUE,
        added_at REAL DEFAULT (julianday('now')),
        notes TEXT
    );

    -- 打开的标签页记录
    CREATE TABLE IF NOT EXISTS pp_open_tabs (
        tab_id TEXT PRIMARY KEY,
        file_path TEXT NOT NULL,
        editor_mode TEXT DEFAULT 'preview_only',
        scroll_position REAL DEFAULT 0,
        cursor_position INTEGER DEFAULT 0,
        last_opened REAL DEFAULT (julianday('now'))
    );

    -- 最近打开的文件
    CREATE TABLE IF NOT EXISTS pp_recent_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL UNIQUE,
        last_opened REAL DEFAULT (julianday('now')),
        open_count INTEGER DEFAULT 1
    );

    -- 预览配置
    CREATE TABLE IF NOT EXISTS pp_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at REAL DEFAULT (julianday('now'))
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_pp_history_preview ON pp_preview_history(preview_count DESC);
    CREATE INDEX IF NOT EXISTS idx_pp_history_favorite ON pp_preview_history(favorite);
    CREATE INDEX IF NOT EXISTS idx_pp_recent_opened ON pp_recent_files(last_opened DESC);
    CREATE INDEX IF NOT EXISTS idx_pp_open_tabs_recent ON pp_open_tabs(last_opened DESC);
    """


class MigrationManager:

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row

            # 启用 WAL 模式
            self._conn.execute("PRAGMA journal_mode=WAL")

        return self._conn

    def _init_schema_table(self):
        """初始化迁移记录表"""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at REAL DEFAULT (julianday('now'))
            )
        """)

    def get_current_version(self) -> int:
        """获取当前版本"""
        conn = self._get_connection()
        self._init_schema_table()

        cursor = conn.execute("SELECT MAX(version) as version FROM schema_migrations")
        row = cursor.fetchone()
        return row["version"] or 0 if row else 0

    def get_applied_migrations(self) -> List[int]:
        """获取已应用的迁移"""
        conn = self._get_connection()
        self._init_schema_table()

        cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version")
        return [row["version"] for row in cursor.fetchall()]

    def migrate(self, target_version: int = None) -> Dict[str, Any]:
        """
        执行迁移

        Args:
            target_version: 目标版本，None 表示迁移到最新

        Returns:
            迁移结果
        """
        conn = self._get_connection()
        self._init_schema_table()

        current_version = self.get_current_version()

        if target_version is None:
            target_version = max(m.version for m in MIGRATIONS) if MIGRATIONS else 0

        if target_version <= current_version:
            return {
                "success": True,
                "message": "Already at target version",
                "migrations_applied": []
            }

        applied = []

        for migration in sorted(MIGRATIONS, key=lambda m: m.version):
            if migration.version <= current_version:
                continue

            if migration.version > target_version:
                break

            try:
                # 执行迁移SQL
                if migration.up:
                    conn.executescript(migration.up)

                # 记录迁移
                conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                    (migration.version, migration.name)
                )

                conn.commit()
                applied.append({
                    "version": migration.version,
                    "name": migration.name,
                    "success": True
                })

            except Exception as e:
                conn.rollback()
                return {
                    "success": False,
                    "message": f"Migration {migration.version} failed: {str(e)}",
                    "migrations_applied": applied,
                    "failed_at": migration.version
                }

        return {
            "success": True,
            "message": f"Migrated to version {target_version}",
            "migrations_applied": applied
        }

    def rollback(self, steps: int = 1) -> Dict[str, Any]:
        """
        回滚迁移

        Args:
            steps: 回滚步数

        Returns:
            回滚结果
        """
        conn = self._get_connection()

        current_version = self.get_current_version()
        rolled_back = []

        # 获取最近的迁移
        for migration in sorted(MIGRATIONS, key=lambda m: m.version, reverse=True):
            if len(rolled_back) >= steps:
                break

            if migration.version > current_version:
                continue

            try:
                if migration.down:
                    conn.executescript(migration.down)

                conn.execute(
                    "DELETE FROM schema_migrations WHERE version = ?",
                    (migration.version,)
                )

                conn.commit()
                rolled_back.append({
                    "version": migration.version,
                    "name": migration.name,
                    "success": True
                })

            except Exception as e:
                conn.rollback()
                return {
                    "success": False,
                    "message": f"Rollback {migration.version} failed: {str(e)}",
                    "rolled_back": rolled_back,
                    "failed_at": migration.version
                }

        return {
            "success": True,
            "message": f"Rolled back {len(rolled_back)} migrations",
            "rolled_back": rolled_back
        }

    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
            self._conn = None


def get_migration_manager(db_path: str) -> MigrationManager:
    """获取迁移管理器"""
    return MigrationManager(db_path)


def run_all_migrations(db_path: str) -> Dict[str, Any]:
    """运行所有迁移"""
    manager = get_migration_manager(db_path)
    try:
        result = manager.migrate()
        return result
    finally:
        manager.close()
