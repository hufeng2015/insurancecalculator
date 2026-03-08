import pymysql
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),          
    'password': os.getenv('DB_PASSWORD', '95938'),  
    'database': os.getenv('DB_NAME', 'car_insurance_db'), 
    'charset': os.getenv('DB_CHARSET', 'utf8mb4')
}

def init_database():
    """初始化数据库表结构"""
    conn = None
    try:
        # 连接到数据库
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 创建版本控制表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS rule_versions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            start_date DATE NOT NULL,          
            end_date DATE NULL,                
            remarks VARCHAR(255),              
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) COMMENT='规则版本表';
        """)
        
        # 创建佣金规则表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS commission_rules (
            id INT AUTO_INCREMENT PRIMARY KEY,
            version_id INT NOT NULL,           
            level VARCHAR(10) NOT NULL,        
            base_rate DECIMAL(10, 4) DEFAULT 0,      
            bonus_rate DECIMAL(10, 4) DEFAULT 0,     
            compulsory_rate DECIMAL(10, 4) DEFAULT 0,
            driver_rate DECIMAL(10, 4) DEFAULT 0,    
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (version_id) REFERENCES rule_versions(id),
            UNIQUE KEY unique_version_level (version_id, level)
        ) COMMENT='佣金规则表';
        """)
        
        # 创建报价记录表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS quote_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            quote_date DATE NOT NULL,          
            license_plate VARCHAR(20),         
            salesperson VARCHAR(50),           
            level VARCHAR(10),                 
            compulsory_fee DECIMAL(12, 2),     
            commercial_fee DECIMAL(12, 2),     
            driver_fee DECIMAL(12, 2),         
            car_damage_coverage DECIMAL(12, 2),
            
            calc_base_comm DECIMAL(12, 2),     
            calc_bonus_comm DECIMAL(12, 2),    
            calc_compulsory_comm DECIMAL(12, 2),
            calc_driver_comm DECIMAL(12, 2),   
            total_commission DECIMAL(12, 2),   
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) COMMENT='车险报价与佣金记录表';
        """)
        
        # 检查是否已有版本数据
        cursor.execute("SELECT COUNT(*) FROM rule_versions WHERE id = 1")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # 插入默认版本记录
            cursor.execute("""
            INSERT INTO rule_versions (id, start_date, end_date, remarks) 
            VALUES (1, '2026-01-01', NULL, '第一次')
            """)
            
            # 插入示例规则数据
            rules_data = [
                (1, 'S', 0.12, 0.22, 0.037, 0.3),
                (1, 'A', 0.12, 0.20, 0.037, 0.3),
                (1, 'B', 0.12, 0.10, 0.037, 0.4),
                (1, 'C', 0.08, 0.00, 0.037, 0.4),
                (1, 'ES', 0.045, 0.23, 0.037, 0.3),
                (1, 'EA', 0.045, 0.21, 0.037, 0.3),
                (1, 'EB', 0.045, 0.15, 0.037, 0.3),
                (1, 'EC', 0.045, 0.015, 0.037, 0.3)
            ]
            
            cursor.executemany("""
            INSERT INTO commission_rules (version_id, level, base_rate, bonus_rate, compulsory_rate, driver_rate) 
            VALUES (%s, %s, %s, %s, %s, %s)
            """, rules_data)
        
        conn.commit()
        print("数据库初始化完成！")
        
    except Exception as e:
        print(f"数据库初始化过程中出现错误: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    init_database()