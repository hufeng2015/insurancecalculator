-- 1. 版本控制表：用于管理规则的不同版本
CREATE TABLE IF NOT EXISTS rule_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    start_date DATE NOT NULL,          -- 开始时间
    end_date DATE NULL,                -- 结束时间，NULL表示当前活跃版本
    remarks VARCHAR(255),              -- 备注
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) COMMENT='规则版本表';

-- 2. 修改佣金规则表：关联版本ID
CREATE TABLE IF NOT EXISTS commission_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version_id INT NOT NULL,           -- 关联版本ID
    level VARCHAR(10) NOT NULL,        -- 等级：S, A, B, C, ES...
    base_rate DECIMAL(10, 4) DEFAULT 0,      -- 基础佣金点
    bonus_rate DECIMAL(10, 4) DEFAULT 0,     -- 加投红包点
    compulsory_rate DECIMAL(10, 4) DEFAULT 0,-- 交强险点
    driver_rate DECIMAL(10, 4) DEFAULT 0,    -- 驾意险点
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (version_id) REFERENCES rule_versions(id),
    UNIQUE KEY unique_version_level (version_id, level) -- 确保同一版本同一个等级只有一条规则
) COMMENT='佣金规则表';

-- 3. 创建报价记录表（可选，用于留痕）
CREATE TABLE IF NOT EXISTS quote_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    quote_date DATE NOT NULL,          -- 报价日期
    license_plate VARCHAR(20),         -- 车牌号
    salesperson VARCHAR(50),           -- 业务员
    level VARCHAR(10),                 -- 等级
    compulsory_fee DECIMAL(12, 2),     -- 交强险保费
    commercial_fee DECIMAL(12, 2),     -- 商业险保费
    driver_fee DECIMAL(12, 2),         -- 驾意险保费
    car_damage_coverage DECIMAL(12, 2),-- 车辆损失保额（用于判断 20-100万）
    
    -- 以下字段用于存储计算后的结果
    calc_base_comm DECIMAL(12, 2),     -- 算出的基础佣金
    calc_bonus_comm DECIMAL(12, 2),    -- 算出的加投红包
    calc_compulsory_comm DECIMAL(12, 2), -- 算出的交强佣金
    calc_driver_comm DECIMAL(12, 2),   -- 算出的驾意佣金
    total_commission DECIMAL(12, 2),   -- 总佣金
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) COMMENT='车险报价与佣金记录表';

-- 4. 插入默认版本记录
INSERT INTO rule_versions (id, start_date, end_date, remarks) VALUES 
(1, '2026-01-01', '2026-01-14', '第一次');

-- 5. 插入示例规则（基于第一个版本）
INSERT INTO commission_rules (version_id, level, base_rate, bonus_rate, compulsory_rate, driver_rate) VALUES 
(1, 'S', 0.12, 0.22, 0.037, 0.3),
(1, 'A', 0.12, 0.20, 0.037, 0.3),
(1, 'B', 0.12, 0.10, 0.037, 0.4),
(1, 'C', 0.08, 0.00, 0.037, 0.4),
(1, 'ES', 0.045, 0.23, 0.037, 0.3),
(1, 'EA', 0.045, 0.21, 0.037, 0.3),
(1, 'EB', 0.045, 0.15, 0.037, 0.3),
(1, 'EC', 0.045, 0.015, 0.037, 0.3);

CREATE TABLE IF NOT EXISTS renewal_clients (
    license_plate VARCHAR(20) NOT NULL COMMENT '车牌号-主键',
    policy_end_date DATE COMMENT '终保日期',
    last_quote_time DATETIME COMMENT '末次报价时间',
    policy_holder VARCHAR(50) COMMENT '投保人',
    vin_code VARCHAR(50) COMMENT '车架号',
    sales_code VARCHAR(50) COMMENT '销售员代码',
    sales_name VARCHAR(50) COMMENT '销售员名称',
    branch_company VARCHAR(50) COMMENT '支公司名称',
    department_name VARCHAR(50) COMMENT '营销服务部名称',
    agent_phone VARCHAR(20) COMMENT '寿险营销员电话',
    agent_resign_date DATE COMMENT '营销员离职日期',
    vip_level VARCHAR(20) COMMENT '高客等级',
    filter_flag VARCHAR(20) COMMENT '续保过滤标识',
    wechat_added VARCHAR(10) COMMENT '是否加微',
    track_status VARCHAR(20) DEFAULT '待跟进' COMMENT '跟踪状态',
    remark TEXT COMMENT '备注',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '系统更新时间',
    PRIMARY KEY (license_plate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='续保客户清单';