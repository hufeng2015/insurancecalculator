-- 数据库结构升级脚本：从旧版本迁移到版本控制系统

-- 1. 创建新版本表
CREATE TABLE IF NOT EXISTS rule_versions_new (
    id INT AUTO_INCREMENT PRIMARY KEY,
    start_date DATE NOT NULL,          -- 开始时间
    end_date DATE NULL,                -- 结束时间，NULL表示当前活跃版本
    remarks VARCHAR(255),              -- 备注
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) COMMENT='规则版本表';

-- 2. 创建新佣金规则表
CREATE TABLE IF NOT EXISTS commission_rules_new (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version_id INT NOT NULL,           -- 关联版本ID
    level VARCHAR(10) NOT NULL,        -- 等级：S, A, B, C, ES...
    base_rate DECIMAL(10, 4) DEFAULT 0,      -- 基础佣金点
    bonus_rate DECIMAL(10, 4) DEFAULT 0,     -- 加投红包点
    compulsory_rate DECIMAL(10, 4) DEFAULT 0,-- 交强险点
    driver_rate DECIMAL(10, 4) DEFAULT 0,    -- 驾意险点
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (version_id) REFERENCES rule_versions_new(id),
    UNIQUE KEY unique_version_level (version_id, level) -- 确保同一版本同一个等级只有一条规则
) COMMENT='佣金规则表';

-- 3. 插入默认版本记录
INSERT INTO rule_versions_new (id, start_date, end_date, remarks) VALUES 
(1, '2026-01-01', '2026-01-14', '系统默认版本');

-- 4. 将现有规则迁移到新结构
-- 注意：这需要先将现有commission_rules表按月份转换为版本ID
-- 这里我们把最新的月份作为当前版本

-- 5. 将现有规则复制到新表中
-- 假设我们要将最新月份的数据复制为版本1
INSERT INTO commission_rules_new (version_id, level, base_rate, bonus_rate, compulsory_rate, driver_rate)
SELECT 
    1 as version_id,
    level,
    MAX(base_rate) as base_rate,
    MAX(bonus_rate) as bonus_rate,
    MAX(compulsory_rate) as compulsory_rate,
    MAX(driver_rate) as driver_rate
FROM (
    SELECT 
        level,
        base_rate,
        bonus_rate,
        compulsory_rate,
        driver_rate,
        ROW_NUMBER() OVER (PARTITION BY level ORDER BY rule_month DESC) as rn
    FROM commission_rules
) t
WHERE rn = 1;

-- 6. 重命名表
ALTER TABLE commission_rules RENAME TO commission_rules_backup;
ALTER TABLE rule_versions_new RENAME TO rule_versions;
ALTER TABLE commission_rules_new RENAME TO commission_rules;

-- 7. 验证迁移是否成功
SELECT COUNT(*) as total_rules FROM commission_rules;
SELECT * FROM rule_versions;