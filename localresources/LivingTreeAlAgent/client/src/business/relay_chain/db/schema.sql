-- 中继链数据库 Schema V2.1
-- 用于存储链式账本、账户快照、节点信息等
-- 设计参考：无币无挖矿的分布式积分记账系统 + 事件驱动扩展

-- =====================================================
-- 交易账本表（核心真相源，不可修改）
-- =====================================================
CREATE TABLE IF NOT EXISTS tx_ledger (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- 链式结构
    tx_hash VARCHAR(64) NOT NULL UNIQUE COMMENT '本交易Hash(SHA256)',
    prev_tx_hash VARCHAR(64) NOT NULL DEFAULT '' COMMENT '用户上一笔交易Hash',
    user_id VARCHAR(64) NOT NULL COMMENT '用户ID',

    -- 交易内容
    -- 积分类
    -- RECHARGE, CONSUME, TRANSFER_IN, TRANSFER_OUT, GRANT, IN, OUT
    -- 任务类
    -- TASK_DISPATCH, TASK_EXECUTE, TASK_COMPLETE, TASK_CANCEL, TASK_RETRY
    -- 租户类
    -- CROSS_TENANT_MSG, TENANT_NOTIFY, TENANT_RECEIPT
    -- 资产类
    -- ASSET_GRANT, ASSET_TRANSFER, ASSET_CONSUME, ASSET_FREEZE, ASSET_UNFREEZE
    -- 政务类
    -- GOV_CHECKIN, GOV_CHECKOUT, GOV_VERIFY, GOV_REVOKE, GOV_TRANSFER
    -- 隐私类
    -- ZK_PROOF_SUBMIT, ZK_PROOF_VERIFY, ZK_RANGE_PROOF
    -- IM消息类
    -- MSG_SEND, MSG_RECEIPT, MSG_EDIT, MSG_DELETE, MSG_REACTION, MSG_REPLY, MSG_FORWARD
    -- 文件分享类
    -- FILE_SHARE, FILE_REQUEST, FILE_SLICE_HASH
    op_type ENUM(
        -- 积分类
        'IN', 'OUT', 'RECHARGE', 'CONSUME', 'TRANSFER_IN', 'TRANSFER_OUT', 'GRANT',
        -- 任务类
        'TASK_DISPATCH', 'TASK_EXECUTE', 'TASK_COMPLETE', 'TASK_CANCEL', 'TASK_RETRY',
        -- 租户类
        'CROSS_TENANT_MSG', 'TENANT_NOTIFY', 'TENANT_RECEIPT',
        -- 资产类
        'ASSET_GRANT', 'ASSET_TRANSFER', 'ASSET_CONSUME', 'ASSET_FREEZE', 'ASSET_UNFREEZE',
        -- 政务类
        'GOV_CHECKIN', 'GOV_CHECKOUT', 'GOV_VERIFY', 'GOV_REVOKE', 'GOV_TRANSFER',
        -- 隐私类
        'ZK_PROOF_SUBMIT', 'ZK_PROOF_VERIFY', 'ZK_RANGE_PROOF',
        -- IM消息类
        'MSG_SEND', 'MSG_RECEIPT', 'MSG_EDIT', 'MSG_DELETE', 'MSG_REACTION', 'MSG_REPLY', 'MSG_FORWARD',
        -- 文件分享类
        'FILE_SHARE', 'FILE_REQUEST', 'FILE_SLICE_HASH'
    ) NOT NULL COMMENT '操作类型',
    amount DECIMAL(12,2) NOT NULL DEFAULT 1 COMMENT '交易金额/数量',

    -- 业务标识（任务ID/消息ID/资产ID）
    biz_id VARCHAR(128) DEFAULT NULL COMMENT '业务ID(支付单号/订单号/任务ID/消息ID/资产ID)',
    to_user_id VARCHAR(64) DEFAULT NULL COMMENT '目标用户ID',

    -- 扩展标识
    tenant_id VARCHAR(64) DEFAULT NULL COMMENT '租户ID（多租户场景）',
    asset_type VARCHAR(32) DEFAULT NULL COMMENT '资产类型（游戏资产场景）',

    -- 防重放
    nonce INT NOT NULL COMMENT '用户级交易序号',

    -- 节点信息
    creator_node VARCHAR(32) DEFAULT NULL COMMENT '创建节点',
    confirmer_count INT DEFAULT 1 COMMENT '确认节点数',

    -- 元数据（JSON格式）
    metadata JSON DEFAULT NULL COMMENT '扩展元数据',

    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    -- 索引
    INDEX idx_user_chain (user_id, prev_tx_hash),
    INDEX idx_user_nonce (user_id, nonce),
    INDEX idx_biz_id (biz_id),
    INDEX idx_tenant (tenant_id),
    INDEX idx_asset_type (asset_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='链式账本，不可修改';

-- =====================================================
-- 交易状态表（异步处理）
-- =====================================================
CREATE TABLE IF NOT EXISTS tx_pending (
    tx_hash VARCHAR(64) PRIMARY KEY COMMENT '交易哈希',
    user_id VARCHAR(64) NOT NULL COMMENT '用户ID',
    op_type ENUM(
        'IN', 'OUT', 'RECHARGE', 'CONSUME', 'TRANSFER_IN', 'TRANSFER_OUT', 'GRANT',
        'TASK_DISPATCH', 'TASK_EXECUTE', 'TASK_COMPLETE', 'TASK_CANCEL', 'TASK_RETRY',
        'CROSS_TENANT_MSG', 'TENANT_NOTIFY', 'TENANT_RECEIPT',
        'ASSET_GRANT', 'ASSET_TRANSFER', 'ASSET_CONSUME', 'ASSET_FREEZE', 'ASSET_UNFREEZE',
        'GOV_CHECKIN', 'GOV_CHECKOUT', 'GOV_VERIFY', 'GOV_REVOKE', 'GOV_TRANSFER',
        'ZK_PROOF_SUBMIT', 'ZK_PROOF_VERIFY', 'ZK_RANGE_PROOF',
        'MSG_SEND', 'MSG_RECEIPT', 'MSG_EDIT', 'MSG_DELETE', 'MSG_REACTION', 'MSG_REPLY', 'MSG_FORWARD',
        'FILE_SHARE', 'FILE_REQUEST', 'FILE_SLICE_HASH'
    ) NOT NULL COMMENT '操作类型',
    amount DECIMAL(12,2) NOT NULL DEFAULT 1 COMMENT '交易金额',
    biz_id VARCHAR(128) DEFAULT NULL COMMENT '业务ID',

    status ENUM('PENDING', 'CONFIRMED', 'FAILED', 'EXPIRED') NOT NULL DEFAULT 'PENDING' COMMENT '状态',
    confirm_nodes JSON DEFAULT NULL COMMENT '已确认节点列表',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    confirmed_at TIMESTAMP NULL COMMENT '确认时间',
    expired_at TIMESTAMP NOT NULL COMMENT '过期时间',

    INDEX idx_status_created (status, created_at),
    INDEX idx_user_id (user_id),
    INDEX idx_expired_at (expired_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='待确认交易状态表';

-- =====================================================
-- 账户快照表（缓存优化，仅加速查询）
-- =====================================================
CREATE TABLE IF NOT EXISTS account_snapshot (
    user_id VARCHAR(64) PRIMARY KEY COMMENT '用户ID',
    balance DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '当前余额',

    -- 防双花关键字段
    last_nonce INT NOT NULL DEFAULT -1 COMMENT '最后一笔nonce',
    last_tx_hash VARCHAR(64) NOT NULL DEFAULT '' COMMENT '最后一笔交易哈希',

    -- 统计
    total_recharge DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '累计充值',
    total_consume DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '累计消费',
    total_transfer_in DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '累计转入',
    total_transfer_out DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '累计转出',
    total_task_count INT NOT NULL DEFAULT 0 COMMENT '累计任务数',
    total_asset_ops INT NOT NULL DEFAULT 0 COMMENT '累计资产操作数',
    total_msg_count INT NOT NULL DEFAULT 0 COMMENT '累计消息数',

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_balance (balance)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账户快照表（缓存层）';

-- =====================================================
-- 对账记录表
-- =====================================================
CREATE TABLE IF NOT EXISTS reconciliation_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    reconciliation_type ENUM('DAILY', 'MANUAL', 'AUTO_CHECK') NOT NULL DEFAULT 'DAILY' COMMENT '对账类型',
    check_date DATE NOT NULL COMMENT '对账日期',

    -- 内部一致性检查
    total_users INT DEFAULT 0 COMMENT '检查用户数',
    inconsistent_users INT DEFAULT 0 COMMENT '不一致用户数',
    total_amount_diff DECIMAL(12,2) DEFAULT 0 COMMENT '总金额差异',

    -- 外部对账（支付网关）
    total_recharges DECIMAL(12,2) DEFAULT 0 COMMENT '账本充值总额',
    gateway_total DECIMAL(12,2) DEFAULT 0 COMMENT '支付网关总额',
    gateway_diff DECIMAL(12,2) DEFAULT 0 COMMENT '差异',

    status ENUM('PENDING', 'PASSED', 'FAILED', 'MANUAL_REVIEW') NOT NULL DEFAULT 'PENDING' COMMENT '状态',
    error_details TEXT DEFAULT NULL COMMENT '错误详情',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    completed_at TIMESTAMP NULL COMMENT '完成时间',

    INDEX idx_check_date (check_date),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对账记录表';

-- =====================================================
-- 审计日志表
-- =====================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    event_type VARCHAR(50) NOT NULL COMMENT '事件类型',
    user_id BIGINT DEFAULT NULL COMMENT '用户ID',
    tx_hash VARCHAR(64) DEFAULT NULL COMMENT '关联交易',

    details JSON DEFAULT NULL COMMENT '事件详情',

    ip_address VARCHAR(45) DEFAULT NULL COMMENT 'IP地址',
    user_agent VARCHAR(255) DEFAULT NULL COMMENT '用户代理',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX idx_user_id (user_id),
    INDEX idx_event_type (event_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='审计日志表';

-- =====================================================
-- 交易池表（内存+持久化）
-- =====================================================
CREATE TABLE IF NOT EXISTS mempool (
    tx_hash VARCHAR(64) PRIMARY KEY COMMENT '交易哈希',
    tx_data TEXT NOT NULL COMMENT '交易JSON数据',
    relay_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '来源中继ID',
    confirmed_by TEXT DEFAULT '' COMMENT '已确认的中继ID列表，逗号分隔',
    received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '接收时间',
    expires_at TIMESTAMP NOT NULL COMMENT '过期时间',

    INDEX idx_received_at (received_at),
    INDEX idx_expires_at (expires_at),
    INDEX idx_relay_id (relay_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='交易池表';

-- =====================================================
-- 共识投票表
-- =====================================================
CREATE TABLE IF NOT EXISTS consensus_votes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tx_hash VARCHAR(64) NOT NULL COMMENT '交易哈希',
    relay_id VARCHAR(64) NOT NULL COMMENT '投票中继ID',
    valid BOOLEAN NOT NULL COMMENT '是否有效',
    reason VARCHAR(255) DEFAULT '' COMMENT '原因',
    voted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '投票时间',

    UNIQUE INDEX idx_tx_relay (tx_hash, relay_id),
    INDEX idx_tx_hash (tx_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='共识投票表';

-- =====================================================
-- 节点注册表
-- =====================================================
CREATE TABLE IF NOT EXISTS relay_nodes (
    relay_id VARCHAR(64) PRIMARY KEY COMMENT '中继ID',
    node_type ENUM('registry', 'core', 'edge') NOT NULL DEFAULT 'edge' COMMENT '节点类型',
    host VARCHAR(255) NOT NULL COMMENT '主机地址',
    port INT NOT NULL DEFAULT 8080 COMMENT '端口',
    region VARCHAR(50) NOT NULL DEFAULT 'unknown' COMMENT '地区',

    state ENUM('online', 'offline', 'suspect', 'maintenance') NOT NULL DEFAULT 'online' COMMENT '状态',
    capabilities TEXT DEFAULT 'read,write,sync' COMMENT '能力标签，逗号分隔',

    last_heartbeat TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后心跳时间',
    current_load INT NOT NULL DEFAULT 0 COMMENT '当前负载',
    max_load INT NOT NULL DEFAULT 100 COMMENT '最大负载',

    registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',

    INDEX idx_state (state),
    INDEX idx_node_type (node_type),
    INDEX idx_region (region),
    INDEX idx_last_heartbeat (last_heartbeat)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='节点注册表';

-- =====================================================
-- 同步历史表
-- =====================================================
CREATE TABLE IF NOT EXISTS sync_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sync_type VARCHAR(20) NOT NULL COMMENT '同步类型: full_sync/catch_up/tx_broadcast',
    source_relay VARCHAR(64) NOT NULL COMMENT '源中继ID',
    target_relay VARCHAR(64) NOT NULL COMMENT '目标中继ID',
    success_count INT NOT NULL DEFAULT 0 COMMENT '成功数量',
    fail_count INT NOT NULL DEFAULT 0 COMMENT '失败数量',
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
    completed_at TIMESTAMP NULL COMMENT '完成时间',
    error_message TEXT DEFAULT NULL COMMENT '错误信息',

    INDEX idx_sync_type (sync_type),
    INDEX idx_started_at (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='同步历史表';

-- =====================================================
-- IM 会话表（分布式 IM）
-- =====================================================
CREATE TABLE IF NOT EXISTS im_conversations (
    conv_id VARCHAR(64) PRIMARY KEY COMMENT '会话ID',
    conv_type ENUM('PRIVATE', 'GROUP', 'CHANNEL', 'BROADCAST') NOT NULL DEFAULT 'PRIVATE' COMMENT '会话类型',
    name VARCHAR(255) NOT NULL COMMENT '会话名称',
    owner VARCHAR(64) NOT NULL COMMENT '创建者',

    -- 设置
    is_encrypted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否端到端加密',
    max_members INT NOT NULL DEFAULT 500 COMMENT '最大成员数',

    -- 统计
    msg_count INT NOT NULL DEFAULT 0 COMMENT '消息数',

    -- 元数据
    metadata JSON DEFAULT NULL COMMENT '扩展元数据',

    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    INDEX idx_owner (owner),
    INDEX idx_conv_type (conv_type),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='IM会话表';

-- =====================================================
-- IM 会话成员表
-- =====================================================
CREATE TABLE IF NOT EXISTS im_conversation_members (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    conv_id VARCHAR(64) NOT NULL COMMENT '会话ID',
    user_id VARCHAR(64) NOT NULL COMMENT '用户ID',

    -- 成员链状态（用于消息同步）
    last_read_tx VARCHAR(64) DEFAULT NULL COMMENT '最后已读交易哈希',
    last_read_nonce INT NOT NULL DEFAULT -1 COMMENT '最后已读nonce',

    -- 角色
    role ENUM('owner', 'admin', 'member') NOT NULL DEFAULT 'member' COMMENT '角色',

    -- 时间戳
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '加入时间',
    left_at TIMESTAMP NULL COMMENT '离开时间',

    UNIQUE INDEX idx_conv_user (conv_id, user_id),
    INDEX idx_user (user_id),
    INDEX idx_conv (conv_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='IM会话成员表';

-- =====================================================
-- IM 消息索引表（用于快速查询）
-- =====================================================
CREATE TABLE IF NOT EXISTS im_message_index (
    msg_id VARCHAR(64) PRIMARY KEY COMMENT '消息ID（biz_id）',
    conv_id VARCHAR(64) NOT NULL COMMENT '会话ID',
    sender VARCHAR(64) NOT NULL COMMENT '发送者',
    msg_type ENUM('TEXT', 'IMAGE', 'FILE', 'AUDIO', 'VIDEO', 'LOCATION', 'CARD', 'SYSTEM') NOT NULL DEFAULT 'TEXT' COMMENT '消息类型',

    -- 引用
    reply_to VARCHAR(64) DEFAULT NULL COMMENT '回复的消息ID',

    -- 状态
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否已删除',
    is_edited BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否已编辑',

    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX idx_conv (conv_id),
    INDEX idx_sender (sender),
    INDEX idx_conv_created (conv_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='IM消息索引表';

-- =====================================================
-- Gossip 节点表
-- =====================================================
CREATE TABLE IF NOT EXISTS gossip_nodes (
    node_id VARCHAR(64) PRIMARY KEY COMMENT '节点ID',
    node_type ENUM('super', 'micro') NOT NULL DEFAULT 'micro' COMMENT '节点类型：super=超级节点，micro=微中继',

    -- 连接信息
    addr VARCHAR(255) NOT NULL COMMENT '地址',
    port INT NOT NULL DEFAULT 0 COMMENT '端口',

    -- 邻居关系
    neighbors JSON DEFAULT NULL COMMENT '邻居节点列表',

    -- 状态
    state ENUM('online', 'offline', 'suspect') NOT NULL DEFAULT 'online' COMMENT '状态',
    score DECIMAL(5,2) NOT NULL DEFAULT 1.00 COMMENT '信誉评分',

    -- 统计
    messages_sent INT NOT NULL DEFAULT 0 COMMENT '发送消息数',
    messages_received INT NOT NULL DEFAULT 0 COMMENT '接收消息数',

    -- 时间戳
    last_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后活跃时间',
    registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',

    INDEX idx_state (state),
    INDEX idx_type (node_type),
    INDEX idx_score (score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Gossip节点表';

-- =====================================================
-- Gossip 消息传播表（防重放）
-- =====================================================
CREATE TABLE IF NOT EXISTS gossip_seen (
    tx_hash VARCHAR(64) NOT NULL COMMENT '交易哈希',
    node_id VARCHAR(64) NOT NULL COMMENT '节点ID',
    seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '收到时间',

    UNIQUE INDEX idx_tx_node (tx_hash, node_id),
    INDEX idx_tx_hash (tx_hash),
    INDEX idx_node (node_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Gossip消息已见表（防重放）';

-- =====================================================
-- 触发器：自动更新账户快照
-- =====================================================
DELIMITER //

CREATE TRIGGER IF NOT EXISTS tr_after_tx_insert
AFTER INSERT ON tx_ledger
FOR EACH ROW
BEGIN
    DECLARE v_balance DECIMAL(12,2);
    DECLARE v_total_recharge DECIMAL(12,2);
    DECLARE v_total_consume DECIMAL(12,2);
    DECLARE v_total_transfer_in DECIMAL(12,2);
    DECLARE v_total_transfer_out DECIMAL(12,2);

    -- 计算新余额和统计
    IF NEW.op_type = 'RECHARGE' OR NEW.op_type = 'GRANT' THEN
        SELECT COALESCE(balance, 0) + NEW.amount,
               COALESCE(total_recharge, 0) + NEW.amount,
               COALESCE(total_consume, 0),
               COALESCE(total_transfer_in, 0),
               COALESCE(total_transfer_out, 0)
        INTO v_balance, v_total_recharge, v_total_consume, v_total_transfer_in, v_total_transfer_out
        FROM account_snapshot
        WHERE user_id = NEW.user_id;

        INSERT INTO account_snapshot (user_id, balance, last_nonce, last_tx_hash,
                                      total_recharge, total_consume, total_transfer_in, total_transfer_out)
        VALUES (NEW.user_id, v_balance, NEW.nonce, NEW.tx_hash,
                v_total_recharge, v_total_consume, v_total_transfer_in, v_total_transfer_out)
        ON DUPLICATE KEY UPDATE
            balance = v_balance,
            last_nonce = NEW.nonce,
            last_tx_hash = NEW.tx_hash,
            total_recharge = v_total_recharge,
            total_consume = v_total_consume,
            total_transfer_in = v_total_transfer_in,
            total_transfer_out = v_total_transfer_out;

    ELSEIF NEW.op_type = 'CONSUME' THEN
        SELECT COALESCE(balance, 0) - NEW.amount,
               COALESCE(total_recharge, 0),
               COALESCE(total_consume, 0) + NEW.amount,
               COALESCE(total_transfer_in, 0),
               COALESCE(total_transfer_out, 0)
        INTO v_balance, v_total_recharge, v_total_consume, v_total_transfer_in, v_total_transfer_out
        FROM account_snapshot
        WHERE user_id = NEW.user_id;

        INSERT INTO account_snapshot (user_id, balance, last_nonce, last_tx_hash,
                                      total_recharge, total_consume, total_transfer_in, total_transfer_out)
        VALUES (NEW.user_id, v_balance, NEW.nonce, NEW.tx_hash,
                v_total_recharge, v_total_consume, v_total_transfer_in, v_total_transfer_out)
        ON DUPLICATE KEY UPDATE
            balance = v_balance,
            last_nonce = NEW.nonce,
            last_tx_hash = NEW.tx_hash,
            total_recharge = v_total_recharge,
            total_consume = v_total_consume,
            total_transfer_in = v_total_transfer_in,
            total_transfer_out = v_total_transfer_out;

    ELSEIF NEW.op_type = 'TRANSFER_OUT' THEN
        SELECT COALESCE(balance, 0) - NEW.amount,
               COALESCE(total_recharge, 0),
               COALESCE(total_consume, 0),
               COALESCE(total_transfer_in, 0),
               COALESCE(total_transfer_out, 0) + NEW.amount
        INTO v_balance, v_total_recharge, v_total_consume, v_total_transfer_in, v_total_transfer_out
        FROM account_snapshot
        WHERE user_id = NEW.user_id;

        INSERT INTO account_snapshot (user_id, balance, last_nonce, last_tx_hash,
                                      total_recharge, total_consume, total_transfer_in, total_transfer_out)
        VALUES (NEW.user_id, v_balance, NEW.nonce, NEW.tx_hash,
                v_total_recharge, v_total_consume, v_total_transfer_in, v_total_transfer_out)
        ON DUPLICATE KEY UPDATE
            balance = v_balance,
            last_nonce = NEW.nonce,
            last_tx_hash = NEW.tx_hash,
            total_recharge = v_total_recharge,
            total_consume = v_total_consume,
            total_transfer_in = v_total_transfer_in,
            total_transfer_out = v_total_transfer_out;

        -- 如果是转账，同时更新目标用户
        IF NEW.to_user_id IS NOT NULL THEN
            SELECT COALESCE(balance, 0) + NEW.amount,
                   COALESCE(total_recharge, 0),
                   COALESCE(total_consume, 0),
                   COALESCE(total_transfer_in, 0) + NEW.amount,
                   COALESCE(total_transfer_out, 0)
            INTO v_balance, v_total_recharge, v_total_consume, v_total_transfer_in, v_total_transfer_out
            FROM account_snapshot
            WHERE user_id = NEW.to_user_id;

            INSERT INTO account_snapshot (user_id, balance, last_nonce, last_tx_hash,
                                          total_recharge, total_consume, total_transfer_in, total_transfer_out)
            VALUES (NEW.to_user_id, v_balance, NEW.nonce, NEW.tx_hash,
                    v_total_recharge, v_total_consume, v_total_transfer_in, v_total_transfer_out)
            ON DUPLICATE KEY UPDATE
                balance = v_balance,
                total_transfer_in = v_total_transfer_in;
        END IF;
    END IF;
END//

DELIMITER ;
