import pymysql
from decimal import Decimal, ROUND_HALF_UP

class InsuranceCalculator:
    def __init__(self, db_config):
        """
        初始化数据库连接
        :param db_config: 数据库配置字典
        """
        self.db_config = db_config

    def _get_connection(self):
        return pymysql.connect(**self.db_config)

    def _get_rules(self, month, level):
        """
        根据月份和等级从数据库获取佣金点位
        """
        sql = """
        SELECT base_rate, bonus_rate, compulsory_rate, driver_rate 
        FROM commission_rules 
        WHERE rule_month = %s AND level = %s
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, (month, level))
                result = cursor.fetchone()
                if result:
                    return {
                        'base': Decimal(result[0]),
                        'bonus': Decimal(result[1]),
                        'compulsory': Decimal(result[2]),
                        'driver': Decimal(result[3])
                    }
                return None
        finally:
            conn.close()

    def calculate(self, data, save_to_db=False):
        """
        核心计算逻辑
        :param data: 包含报价信息的字典
        :param save_to_db: 是否将结果保存到数据库
        :return: 包含各项佣金详情的字典
        """
        # 1. 解析输入数据，并将金额转为 Decimal 防止精度丢失
        quote_date = data['quote_date'] # 格式 'YYYY-MM-DD'
        month_key = quote_date[:7]      # 提取 'YYYY-MM'
        level = data['level']
        
        compulsory_fee = Decimal(str(data['compulsory_fee']))      # 交强险保费
        commercial_fee = Decimal(str(data['commercial_fee']))      # 商业险保费
        driver_fee = Decimal(str(data['driver_fee']))              # 驾意险保费
        car_damage_coverage = Decimal(str(data['car_damage_coverage'])) # 车损保额

        # 2. 获取规则
        rules = self._get_rules(month_key, level)
        
        # 初始化结果
        result = {
            "base_commission": Decimal(0),
            "bonus_commission": Decimal(0),
            "compulsory_commission": Decimal(0),
            "driver_commission": Decimal(0),
            "total_commission": Decimal(0),
            "error": None
        }

        if not rules:
            result['error'] = f"未找到 {month_key} 月份等级为 {level} 的规则"
            return result

        # ==================== 逻辑开始 ====================

        # --- A. 基础佣金计算逻辑 ---
        # 逻辑：如果没有驾意险(<=0)，点位-0.04
        current_base_rate = rules['base']
        if driver_fee <= 0:
            current_base_rate -= Decimal('0.04')
        
        # 逻辑：特殊等级且车损在 [20万, 100万] 之间，点位+0.04
        special_levels = ['ES', 'EA', 'EB', 'EC']
        if level in special_levels and Decimal('200000') <= car_damage_coverage <= Decimal('1000000'):
            current_base_rate += Decimal('0.04')

        # 计算基础佣金 = 商业险 * 最终点位
        # 保护逻辑：如果点位计算后小于0，通常按0处理，防止倒扣钱（除非你允许负佣金）
        if current_base_rate < 0: current_base_rate = 0 
        result['base_commission'] = commercial_fee * current_base_rate

        # --- B. 加投红包计算逻辑 ---
        # 逻辑：直接查表计算
        result['bonus_commission'] = commercial_fee * rules['bonus']

        # --- C. 交强险计算逻辑 ---
        # 逻辑：C/EC等级特殊判断
        current_comp_rate = rules['compulsory']
        
        if level in ['C', 'EC']:
            # 条件：交强险保费 > 0 且 商业险保费 > 0
            if compulsory_fee > 0 and commercial_fee > 0:
                current_comp_rate = Decimal('0.037')
            else:
                current_comp_rate = Decimal('0')
        
        result['compulsory_commission'] = compulsory_fee * current_comp_rate

        # --- D. 驾意险计算逻辑 ---
        # 逻辑：驾意险保费 * 驾意险点位
        result['driver_commission'] = driver_fee * rules['driver']

        # ==================== 逻辑结束 ====================

        # 汇总
        result['total_commission'] = (
            result['base_commission'] + 
            result['bonus_commission'] + 
            result['compulsory_commission'] + 
            result['driver_commission']
        )

        # 格式化输出（保留2位小数）
        final_output = {k: v.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP) 
                        if isinstance(v, Decimal) else v 
                        for k, v in result.items()}

        # 3. 可选：保存到数据库
        if save_to_db:
            self._save_record(data, final_output)

        return final_output

    def _save_record(self, input_data, res):
        conn = self._get_connection()
        sql = """
        INSERT INTO quote_records 
        (quote_date, license_plate, salesperson, level, compulsory_fee, commercial_fee, driver_fee, car_damage_coverage,
         calc_base_comm, calc_bonus_comm, calc_compulsory_comm, calc_driver_comm, total_commission)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            input_data['quote_date'], input_data['license_plate'], input_data['salesperson'], input_data['level'],
            input_data['compulsory_fee'], input_data['commercial_fee'], input_data['driver_fee'], input_data['car_damage_coverage'],
            res['base_commission'], res['bonus_commission'], res['compulsory_commission'], res['driver_commission'], res['total_commission']
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
            conn.commit()
        except Exception as e:
            print(f"保存数据库失败: {e}")
        finally:
            conn.close()

# --- 使用示例 ---

# 1. 配置数据库
db_config = {
    'host': 'localhost',
    'user': 'root',      # 替换你的用户名
    'password': '95938', # 替换你的密码
    'database': 'car_insurance_db', # 替换你的库名
    'charset': 'utf8mb4'
}

# 2. 实例化计算器
calculator = InsuranceCalculator(db_config)

# 3. 准备输入数据（模拟你的示例 A 等级）
input_data = {
    "quote_date": "2025-01-04",     # 报价日期，决定了使用 2025-01 的规则
    "license_plate": "粤B88888",
    "salesperson": "张三",
    "level": "A",
    "compulsory_fee": 665,          # 交强险
    "commercial_fee": 1367.57,      # 商业险
    "driver_fee": 298,              # 驾意险
    "car_damage_coverage": 287600   # 车损保额 (注意：这里我填了28.76万，而不是原来的28760，如果是2万8则填28760)
}

# 4. 调用计算
print(f"正在计算车牌: {input_data['license_plate']}...")
result = calculator.calculate(input_data, save_to_db=True)

# 5. 打印结果
if result['error']:
    print(f"计算出错: {result['error']}")
else:
    print("-" * 30)
    print(f"基础佣金: {result['base_commission']}") # 预期: 1367.57 * 0.12 = 164.11
    print(f"加投红包: {result['bonus_commission']}") # 预期: 1367.57 * 0.20 = 273.51
    print(f"交强险佣: {result['compulsory_commission']}") # 预期: 665 * 0.037 = 24.61
    print(f"驾意险佣: {result['driver_commission']}") # 预期: 298 * 0.30 = 89.40
    print("-" * 30)
    print(f"总 佣 金: {result['total_commission']}")