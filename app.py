import streamlit as st
import pymysql
import pandas as pd
import datetime
from decimal import Decimal, ROUND_HALF_UP
from dotenv import load_dotenv
import os

# 加载环境变量
# conda activate agiclass
# streamlit run app.py
load_dotenv()

# ================= 1. 数据库配置与公共函数 =================
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),          
    'password': os.getenv('DB_PASSWORD', '95938'),  
    'database': os.getenv('DB_NAME', 'car_insurance_db'), 
    'charset': os.getenv('DB_CHARSET', 'utf8mb4')
}

def get_connection():
    return pymysql.connect(**DB_CONFIG)

def get_version_id_by_date(date):
    """根据日期获取对应的版本ID"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
            SELECT id FROM rule_versions 
            WHERE start_date <= %s AND (end_date IS NULL OR end_date >= %s)
            ORDER BY start_date DESC LIMIT 1
            """
            cursor.execute(sql, (date, date))
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        st.error(f"获取版本ID时数据库连接失败: {e}")
        return None
    finally:
        conn.close()

def get_rules(date, level):
    """根据日期和等级从数据库获取规则"""
    version_id = get_version_id_by_date(date)
    if not version_id: return None
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT base_rate, bonus_rate, compulsory_rate, driver_rate FROM commission_rules WHERE version_id = %s AND level = %s"
            cursor.execute(sql, (version_id, level))
            return cursor.fetchone()
    except Exception: return None
    finally: conn.close()

def save_record(data, result):
    """保存记录到数据库"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            check_sql = "SELECT id FROM quote_records WHERE quote_date = %s AND salesperson = %s AND license_plate = %s"
            cursor.execute(check_sql, (data['date'], data['sales'], data['plate']))
            existing = cursor.fetchone()
            
            if existing:
                update_sql = """
                UPDATE quote_records SET level=%s, compulsory_fee=%s, commercial_fee=%s, driver_fee=%s, car_damage_coverage=%s,
                calc_base_comm=%s, calc_bonus_comm=%s, calc_compulsory_comm=%s, calc_driver_comm=%s, total_commission=%s
                WHERE quote_date=%s AND salesperson=%s AND license_plate=%s
                """
                cursor.execute(update_sql, (
                    data['level'], data['comp_fee'], data['comm_fee'], data['driver_fee'], data['damage_cov'],
                    result['base_val'], result['bonus_val'], result['comp_val'], result['driver_val'], result['total'],
                    data['date'], data['sales'], data['plate']
                ))
                conn.commit()
                return True, "更新"
            else:
                insert_sql = """
                INSERT INTO quote_records (quote_date, license_plate, salesperson, level, compulsory_fee, commercial_fee, driver_fee, car_damage_coverage,
                 calc_base_comm, calc_bonus_comm, calc_compulsory_comm, calc_driver_comm, total_commission)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_sql, (
                    data['date'], data['plate'], data['sales'], data['level'], data['comp_fee'], data['comm_fee'], data['driver_fee'], data['damage_cov'],
                    result['base_val'], result['bonus_val'], result['comp_val'], result['driver_val'], result['total']
                ))
                conn.commit()
                return True, "新增"
    except Exception as e:
        st.error(f"保存失败: {e}")
        return False, None
    finally:
        conn.close()

def calculate_logic(data, rules):
    """核心计算逻辑"""
    base_rate, bonus_rate, comp_rate, driver_rate = [Decimal(str(r)) for r in rules]
    comm_fee, comp_fee, driver_fee, damage_cov = [Decimal(str(x)) for x in [data['comm_fee'], data['comp_fee'], data['driver_fee'], data['damage_cov']]]
    
    # 1. 基础佣金
    curr_base = base_rate
    base_txt = f"基础点位({base_rate})"
    if driver_fee <= 0:
        curr_base -= Decimal('0.04')
        base_txt += " - 0.04(无驾意)"
    if data['level'] in ['ES', 'EA', 'EB', 'EC'] and Decimal('200000') <= damage_cov <= Decimal('1000000'):
        curr_base += Decimal('0.04')
        base_txt += " + 0.04(车损达标)"
    if curr_base < 0: curr_base = Decimal('0')
    base_val = (comm_fee * curr_base).quantize(Decimal('0.01'))
    
    # 2. 加投
    bonus_val = (comm_fee * bonus_rate).quantize(Decimal('0.01'))
    
    # 3. 交强
    curr_comp = comp_rate
    comp_txt = f"交强点位({comp_rate})"
    if data['level'] in ['C', 'EC']:
        if comp_fee > 0 and comm_fee > 0:
            curr_comp = Decimal('0.037')
            comp_txt = "特殊点位(0.037)"
        else:
            curr_comp = Decimal('0')
            comp_txt = "不满足条件(0)"
    comp_val = (comp_fee * curr_comp).quantize(Decimal('0.01'))
    
    # 4. 驾意
    driver_val = (driver_fee * driver_rate).quantize(Decimal('0.01'))
    
    return {
        "base_val": base_val, "base_str": f"商业险({comm_fee})×[{base_txt}={curr_base}]={base_val}",
        "bonus_val": bonus_val, "bonus_str": f"商业险({comm_fee})×加投({bonus_rate})={bonus_val}",
        "comp_val": comp_val, "comp_str": f"交强险({comp_fee})×{comp_txt}={comp_val}",
        "driver_val": driver_val, "driver_str": f"驾意险({driver_fee})×驾意({driver_rate})={driver_val}",
        "total": base_val + bonus_val + comp_val + driver_val
    }

# ================= 2. 页面函数定义 =================

def page_calculator():
    st.header("📋 佣金计算器")
    
    # 显示规则
    with st.expander("查看当前规则", expanded=False):
        try:
            conn = get_connection()
            ver_id = get_version_id_by_date(datetime.date.today())
            if ver_id:
                df = pd.read_sql("SELECT level as 等级, base_rate as 基础, bonus_rate as 加投, compulsory_rate as 交强, driver_rate as 驾意 FROM commission_rules WHERE version_id=%s ORDER BY level", conn, params=(ver_id,))
                st.dataframe(df, hide_index=True, use_container_width=True)
            else: st.warning("暂无今日规则")
            conn.close()
        except Exception: st.warning("无法连接数据库")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. 报价信息")
        i_date = st.date_input("报价日期", datetime.date.today())
        i_plate = st.text_input("车牌号")
        i_sales = st.text_input("业务员")
        i_level = st.selectbox("等级", ["", "S", "A", "B", "C", "D", "ES", "EA", "EB", "EC", "ED"])
    with col2:
        st.subheader("2. 保费金额")
        v_comp = st.number_input("交强险", step=100.0)
        v_comm = st.number_input("商业险", step=100.0)
        v_driver = st.number_input("驾意险", step=50.0)
        v_dmg = st.number_input("车损额度", step=10000.0)

    # 计算与保存
    if 'calc_res' not in st.session_state: st.session_state.calc_res = None
    if 'calc_data' not in st.session_state: st.session_state.calc_data = None

    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("计算", type="primary", use_container_width=True):
            if not (i_plate and i_sales and i_level):
                st.warning("请补全信息"); st.stop()
            rules = get_rules(i_date, i_level)
            if not rules: st.error("找不到对应规则"); st.stop()
            
            data = {'date': i_date, 'plate': i_plate, 'sales': i_sales, 'level': i_level,
                    'comp_fee': v_comp, 'comm_fee': v_comm, 'driver_fee': v_driver, 'damage_cov': v_dmg}
            res = calculate_logic(data, rules)
            st.session_state.calc_res = res
            st.session_state.calc_data = data
            st.rerun()

    with c_btn2:
        if st.button("保存", type="secondary", use_container_width=True):
            if not st.session_state.calc_res: st.warning("请先计算"); st.stop()
            ok, act = save_record(st.session_state.calc_data, st.session_state.calc_res)
            if ok: st.success(f"已{act}！")

    # 结果展示
    if st.session_state.calc_res:
        r = st.session_state.calc_res
        st.divider()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("基础", f"¥{r['base_val']}")
        k2.metric("加投", f"¥{r['bonus_val']}")
        k3.metric("交强", f"¥{r['comp_val']}")
        k4.metric("驾意", f"¥{r['driver_val']}")
        st.metric("总佣金", f"¥{r['total']}", delta_color="normal")
        with st.expander("计算过程", expanded=True):
            st.write(r['base_str'])
            st.write(r['bonus_str'])
            st.write(r['comp_str'])
            st.write(r['driver_str'])

def page_rules_query():
    st.header("🔍 规则查询")
    q_date = st.date_input("查询日期", datetime.date.today())
    try:
        conn = get_connection()
        vid = get_version_id_by_date(q_date)
        if vid:
            df = pd.read_sql("SELECT level, base_rate, bonus_rate, compulsory_rate, driver_rate FROM commission_rules WHERE version_id=%s ORDER BY level", conn, params=(vid,))
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("该日期无规则")
        conn.close()
    except Exception as e: st.error(str(e))

def page_history():
    st.header("📝 历史记录")
    
    conn = get_connection()
    try:
        # 1. 查摘要列表
        df_history = pd.read_sql(
            "SELECT quote_date AS 报价日期, salesperson AS 业务员, license_plate AS 车牌号, "
            "level AS 等级, (compulsory_fee + commercial_fee + driver_fee) AS 总保费, "
            "total_commission AS 总佣金, id AS 记录ID "
            "FROM quote_records ORDER BY id DESC LIMIT 20",
            conn
        )
        
        if df_history.empty:
            st.info("暂无历史记录")
        else:
            # 2. 手动构建表格头部
            cols = st.columns([1.2, 1.2, 1.2, 0.8, 1.1, 1.1, 0.8])
            headers = ["报价日期", "业务员", "车牌号", "等级", "总保费", "总佣金", "操作"]
            for col, h in zip(cols, headers): 
                col.markdown(f"**{h}**")

            # 3. 循环渲染行
            for idx, row in df_history.iterrows():
                c1, c2, c3, c4, c5, c6, c7 = st.columns([1.2, 1.2, 1.2, 0.8, 1.1, 1.1, 0.8])
                c1.write(str(row['报价日期']))
                c2.write(str(row['业务员']))
                c3.write(str(row['车牌号']))
                c4.write(str(row['等级']))
                c5.write(f"¥ {row['总保费']:.2f}")
                c6.write(f"¥ {row['总佣金']:.2f}")

                # 4. 详情按钮逻辑
                if c7.button("详情", key=f"btn_hist_{row['记录ID']}"):
                    # 获取详细数据（用于重算）
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT compulsory_fee, commercial_fee, driver_fee, car_damage_coverage,
                                   calc_base_comm, calc_bonus_comm, calc_compulsory_comm, calc_driver_comm,
                                   total_commission
                            FROM quote_records WHERE id = %s
                        """, (row['记录ID'],))
                        rec = cursor.fetchone()
                    
                    if rec:
                        (comp_f, comm_f, driv_f, dam_f, base_c, bonus_c, comp_c, driv_c, total_c) = rec
                        
                        # 重新计算逻辑过程
                        rules_h = get_rules(row['报价日期'], row['等级'])
                        calc_display = None
                        if rules_h:
                            data_pack = {
                                'date': row['报价日期'], 'plate': row['车牌号'], 'sales': row['业务员'], 'level': row['等级'],
                                'comp_fee': comp_f, 'comm_fee': comm_f, 'driver_fee': driv_f, 'damage_cov': dam_f
                            }
                            # 复用核心计算函数，生成过程字符串
                            calc_display = calculate_logic(data_pack, rules_h)

                        # 在下方展示详情 Expander
                        with st.expander(f"🧾 详情: {row['车牌号']} - {row['业务员']}", expanded=True):
                            k1, k2, k3, k4 = st.columns(4)
                            k1.metric("基础佣金", f"¥ {base_c}")
                            k2.metric("加投红包", f"¥ {bonus_c}")
                            k3.metric("交强险佣金", f"¥ {comp_c}")
                            k4.metric("驾意险佣金", f"¥ {driv_c}")
                            
                            st.markdown("---")
                            st.markdown("##### 🧮 历史计算逻辑还原")
                            if calc_display:
                                st.code(f"1. 基础: {calc_display['base_str']}\n"
                                        f"2. 加投: {calc_display['bonus_str']}\n"
                                        f"3. 交强: {calc_display['comp_str']}\n"
                                        f"4. 驾意: {calc_display['driver_str']}", language="text")
                            else:
                                st.warning("⚠️ 无法找到当时的规则版本，仅显示存储的数值。")
                            
                            st.caption(f"保费明细：商业险 {comm_f} | 交强险 {comp_f} | 驾意险 {driv_f} | 车损额度 {dam_f}")

    except Exception as e:
        st.error(f"加载历史记录失败: {e}")
    finally:
        conn.close()
# ================= 新增：数据处理辅助函数 =================

def clean_date(val):
    """清洗日期格式，兼容 2026/3/4 23:59:59 和 Pandas Timestamp"""
    if pd.isna(val) or val == '' or str(val).strip() == '':
        return None
    try:
        # 尝试转为 datetime 对象
        dt = pd.to_datetime(val, errors='coerce')
        if pd.isna(dt):
            return None
        return dt.date()
    except:
        return None

def clean_datetime(val):
    """清洗时间格式"""
    if pd.isna(val) or val == '' or str(val).strip() == '':
        return None
    try:
        dt = pd.to_datetime(val, errors='coerce')
        if pd.isna(dt):
            return None
        return dt
    except:
        return None

def sync_excel_to_db(uploaded_file):
    """
    核心同步逻辑
    """
    # 1. 读取 Excel
    try:
        df = pd.read_excel(uploaded_file)
        # 简单清洗列名空格
        df.columns = [c.strip() for c in df.columns]
    except Exception as e:
        return False, f"读取Excel失败: {e}"

    # 2. 必要的列名映射检查
    required_cols = {
        '车牌号': 'license_plate',
        '终保日期': 'policy_end_date',
        '末次报价时间': 'last_quote_time',
        '续保过滤标识': 'filter_flag'
    }
    # 检查Excel是否包含所有必要列
    missing_cols = [col for col in required_cols.keys() if col not in df.columns]
    if missing_cols:
        return False, f"Excel缺少必要列: {', '.join(missing_cols)}"

    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 3. 获取数据库现有数据 (构建字典以便快速比对)
        # 我们只查关键字段用于逻辑判断: 车牌号, 末次报价时间, 续保过滤标识, 跟踪状态
        cursor.execute("SELECT license_plate, last_quote_time, filter_flag, track_status FROM renewal_clients")
        existing_records = {}
        for row in cursor.fetchall():
            # row[0] is license_plate
            existing_records[row[0]] = {
                'last_quote': row[1],
                'filter_flag': row[2],
                'status': row[3]
            }
        
        insert_list = []
        update_list = []
        excel_plates = set()
        
        # 4. 遍历 Excel 数据
        for _, row in df.iterrows():
            plate = str(row['车牌号']).strip()
            if not plate or plate.lower() == 'nan':
                continue
            
            excel_plates.add(plate)
            
            # 数据清洗准备
            new_quote_time = clean_datetime(row.get('末次报价时间'))
            new_filter_flag = str(row.get('续保过滤标识', ''))
            
            # 基础字段数据包 (用于 Insert 和 Update)
            # 注意：这里不包含 track_status，因为 Update 时它是计算出来的
            base_data = (
                clean_date(row.get('终保日期')),
                new_quote_time,
                str(row.get('投保人', '')),
                str(row.get('车架号', '')),
                str(row.get('销售员代码', '')),
                str(row.get('销售员名称', '')),
                str(row.get('支公司名称', '')),
                str(row.get('营销服务部名称', '')),
                str(row.get('寿险营销员电话', '')),
                clean_date(row.get('营销员离职日期')),
                str(row.get('高客等级', '')),
                new_filter_flag,
                str(row.get('是否加微', '')),
                # 最后一个占位符是 plate，用于 WHERE 或 INSERT
                plate 
            )

            # --- 逻辑判断开始 ---
            if plate not in existing_records:
                # === 场景 1: 新增 ===
                # 默认状态：待跟进，备注：空
                # SQL Insert 顺序: dates..., info..., status, remark, plate
                # 这里为了方便，我们把 plate 放在 VALUES 的对应位置
                final_insert_data = (plate,) + base_data[:-1] + ('待跟进', '') 
                insert_list.append(final_insert_data)
                
            else:
                # === 场景 2: 更新 ===
                old_data = existing_records[plate]
                old_status = old_data['status']
                old_quote = old_data['last_quote']
                old_flag = old_data['filter_flag']
                
                new_status = old_status # 默认状态不变
                
                # 逻辑 A: 报价时间变化 (数据库为空 -> Excel不为空)
                # 注意：Pandas 读取空时间可能是 NaT 或 None
                db_quote_is_empty = (old_quote is None)
                excel_quote_is_valid = (new_quote_time is not None)
                
                if db_quote_is_empty and excel_quote_is_valid:
                    if old_status == '待跟进':
                        new_status = '已报价'
                
                # 逻辑 B: 拒保/转保逻辑
                # 数据库不是(拒保/转保) -> Excel是(拒保/转保)
                reject_keywords = ['拒保', '已转保']
                db_flag_safe = old_flag not in reject_keywords
                excel_flag_reject = new_filter_flag in reject_keywords
                
                if db_flag_safe and excel_flag_reject:
                    if old_status != '已流失':
                        new_status = '已流失'
                
                # 组装 Update 数据: 
                # SQL: SET ..., track_status=%s WHERE license_plate=%s
                # base_data[:-1] 是除了plate以外的所有字段值
                # 最后加上 new_status 和 plate
                final_update_data = base_data[:-1] + (new_status, plate)
                update_list.append(final_update_data)

        # 5. 执行数据库操作
        # 5.1 批量插入
        if insert_list:
            insert_sql = """
            INSERT INTO renewal_clients 
            (license_plate, policy_end_date, last_quote_time, policy_holder, vin_code, 
             sales_code, sales_name, branch_company, department_name, agent_phone, 
             agent_resign_date, vip_level, filter_flag, wechat_added, track_status, remark)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.executemany(insert_sql, insert_list)
            
        # 5.2 批量更新
        if update_list:
            update_sql = """
            UPDATE renewal_clients SET
                policy_end_date=%s, last_quote_time=%s, policy_holder=%s, vin_code=%s,
                sales_code=%s, sales_name=%s, branch_company=%s, department_name=%s,
                agent_phone=%s, agent_resign_date=%s, vip_level=%s, filter_flag=%s,
                wechat_added=%s, track_status=%s
            WHERE license_plate=%s
            """
            # 注意：这里没有更新 remark，符合需求“备注不变”
            cursor.executemany(update_sql, update_list)
            
        # 6. === 场景 3: 处理消失的数据 (已签约) ===
        # 数据库中存在，但 Excel (excel_plates) 中不存在的车牌
        db_plates = set(existing_records.keys())
        missing_plates = list(db_plates - excel_plates)
        
        signed_count = 0
        if missing_plates:
            # 只有当当前状态不是 '已签约' 时才更新，避免重复更新（虽然更新了也没事，但为了统计准确）
            # 简单起见，直接批量更新所有不在 Excel 里的为 '已签约'
            # 更好的做法：WHERE license_plate IN (...) AND track_status != '已签约'
            
            format_strings = ','.join(['%s'] * len(missing_plates))
            mark_signed_sql = f"""
            UPDATE renewal_clients 
            SET track_status = '已签约' 
            WHERE license_plate IN ({format_strings}) AND track_status != '已签约' AND remark IS NULL
            """
            cursor.execute(mark_signed_sql, missing_plates)
            signed_count = cursor.rowcount

        conn.commit()
        return True, f"同步成功！\n新增: {len(insert_list)} 条\n更新: {len(update_list)} 条\n标记已签约(Excel中消失): {signed_count} 条"

    except Exception as e:
        conn.rollback()
        return False, f"数据库操作失败: {e}"
    finally:
        conn.close()

# ================= 新增：数据回传处理函数 =================

def process_feedback_excel(uploaded_file):
    """
    处理业务员回传的 Excel，更新状态和备注
    逻辑：严格校验状态、智能覆盖备注、忽略不存在的车牌
    """
    # 0. 定义合法状态白名单
    VALID_STATUS = {'待跟进', '已报价', '有意向', '已签约', '已流失'}
    
    # 1. 读取 Excel
    try:
        df = pd.read_excel(uploaded_file)
        # 清洗列名：去除空格
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as e:
        return False, f"读取Excel失败: {e}", None

    # 2. 列名映射与检查
    # 允许用户列名为 "车牌" 或 "车牌号"
    plate_col = None
    if '车牌' in df.columns: plate_col = '车牌'
    elif '车牌号' in df.columns: plate_col = '车牌号'
    
    if not plate_col:
        return False, "Excel中缺少【车牌】列，请检查。", None
    
    # 检查是否有需要更新的内容列
    has_status = '跟踪状态' in df.columns
    has_remark = '备注' in df.columns
    
    if not (has_status or has_remark):
        return False, "Excel中缺少【跟踪状态】或【备注】列，无法进行更新。", None

    # 3. 开始处理
    conn = get_connection()
    stats = {
        'success': 0,      # 成功更新
        'skipped_not_found': 0, # 车牌不存在（忽略）
        'skipped_empty': 0,     # Excel里这行全是空的
        'error_invalid_status': [] # 状态不合法列表
    }
    
    try:
        cursor = conn.cursor()
        
        for index, row in df.iterrows():
            plate = str(row[plate_col]).strip()
            if not plate or plate.lower() == 'nan':
                continue
                
            # 获取 Excel 中的值
            # 状态处理：去除空格，如果是 NaN 则为 None
            raw_status = row.get('跟踪状态')
            new_status = str(raw_status).strip() if pd.notna(raw_status) and str(raw_status).strip() != '' else None
            
            # 备注处理：去除空格，如果是 NaN 则为 None
            raw_remark = row.get('备注')
            new_remark = str(raw_remark).strip() if pd.notna(raw_remark) and str(raw_remark).strip() != '' else None
            
            # === 逻辑 1: 空值处理 (部分更新) ===
            # 如果两个都是空的，直接跳过
            if not new_status and not new_remark:
                stats['skipped_empty'] += 1
                continue
                
            # === 逻辑 2: 跟踪状态合法性校验 (严格模式) ===
            if new_status:
                if new_status not in VALID_STATUS:
                    # 记录错误，不更新这一行（或者你可以选择只更新备注，但通常为了警示，整行跳过）
                    stats['error_invalid_status'].append(f"行{index+2} 车牌{plate}: 状态'{new_status}'非法")
                    continue
            
            # === 逻辑 3: 动态构建 SQL (智能覆盖) ===
            update_clauses = []
            params = []
            
            if new_status:
                update_clauses.append("track_status = %s")
                params.append(new_status)
                
            if new_remark:
                update_clauses.append("remark = %s")
                params.append(new_remark)
            
            # 加上 WHERE 条件
            sql = f"UPDATE renewal_clients SET {', '.join(update_clauses)} WHERE license_plate = %s"
            params.append(plate)
            
            # 执行更新
            cursor.execute(sql, params)
            
            # === 逻辑 4: 检查是否更新成功 (忽略不存在的车牌) ===
            if cursor.rowcount > 0:
                stats['success'] += 1
            else:
                stats['skipped_not_found'] += 1
                
        conn.commit()
        return True, "处理完成", stats
        
    except Exception as e:
        conn.rollback()
        return False, f"数据库执行错误: {e}", None
    finally:
        conn.close()

def page_data_postback():
    st.header("📥 数据回传 (更新状态)")
    
    st.info("""
    **功能说明**：此功能用于批量回传业务员的跟进结果。
    
    **Excel 要求**：
    1. 必须包含列：
    `车牌` 、`车牌号`
    2. 可选更新列：
    `跟踪状态`、`备注`
    
    **处理规则**：
    - **严格校验**：跟踪状态必须为 `待跟进`、`已报价`、`有意向`、`已签约`、`已流失` 之一，否则该行报错。
    - **智能覆盖**：只有 Excel 中填写了内容的单元格才会更新数据库；留空则保持数据库原样。
    - **安全忽略**：系统里找不到的车牌会自动忽略。
    """)
    
    uploaded_file = st.file_uploader("上传回传 Excel 文件", type=['xlsx', 'xls'], key="postback_uploader")
    
    if uploaded_file:
        if st.button("开始回传更新", type="primary", key="btn_postback_start"):
            with st.spinner("正在逐行比对并更新数据库..."):
                success, msg, stats = process_feedback_excel(uploaded_file)
                
                if not success:
                    st.error(msg)
                else:
                    # 展示结果统计
                    st.success(f"✅ 处理完毕！成功更新 {stats['success']} 条数据。")
                    
                    # 使用 3 列展示详细统计
                    c1, c2, c3 = st.columns(3)
                    c1.metric("成功更新", stats['success'], border=True)
                    c2.metric("忽略 (车牌不存在)", stats['skipped_not_found'], border=True)
                    c3.metric("跳过 (空内容)", stats['skipped_empty'], border=True)
                    
                    # 如果有非法状态错误，展示出来
                    if stats['error_invalid_status']:
                        st.error(f"⚠️ 发现 {len(stats['error_invalid_status'])} 条非法状态数据，已跳过更新：")
                        with st.expander("查看错误详情"):
                            for err in stats['error_invalid_status']:
                                st.write(err)



def page_sync():
    st.header("🔄 续保数据同步")
    
    st.markdown("""
    ### 📤 上传续保清单 Excel
    请上传包含以下列的 Excel 文件：
    `车牌号`, `终保日期`, `末次报价时间`, `投保人`, `续保过滤标识` 等...
    
    **同步逻辑说明：**
    1. **新增**：Excel 有但系统无 -> 新增记录，状态为"待跟进"。
    2. **更新**：系统有且 Excel 也有 -> 更新基础信息，保留备注。
       - 若有了新报价 -> 自动变更为"已报价"。
       - 若变为拒保/转保 -> 自动变更为"已流失"。
    3. **已签约**：系统有但 Excel 无 -> 自动变更为"已签约"。
    """)
    
    uploaded_file = st.file_uploader("选择 Excel 文件", type=['xlsx', 'xls'])
    
    if uploaded_file is not None:
        if st.button("开始同步数据", type="primary"):
            with st.spinner("正在分析数据并同步数据库..."):
                success, msg = sync_excel_to_db(uploaded_file)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)

def get_filter_options():
    """从数据库获取动态筛选项"""
    conn = get_connection()
    options = {
        'depts': [],
        'flags': []
    }
    try:
        with conn.cursor() as cursor:
            # 1. 获取营业部 (去重, 非空)
            cursor.execute("SELECT DISTINCT department_name FROM renewal_clients WHERE department_name IS NOT NULL AND department_name != ''")
            options['depts'] = [row[0] for row in cursor.fetchall()]
            
            # 2. 获取续保过滤标识 (去重, 非空)
            cursor.execute("SELECT DISTINCT filter_flag FROM renewal_clients WHERE filter_flag IS NOT NULL AND filter_flag != ''")
            options['flags'] = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        st.error(f"获取筛选项失败: {e}")
    finally:
        conn.close()
    return options

def page_export():
    st.header("📤 续保数据导出")
    
    # 1. 获取动态选项
    options = get_filter_options()
    
    # 定义静态选项
    status_options = ['待跟进', '已报价', '有意向', '已签约', '已流失']
    
    # --- 筛选条件区域 ---
    with st.container():
        st.subheader("🛠️ 数据筛选条件")
        
        col1, col2 = st.columns(2)
        with col1:
            # 2. 营业部服务名称 (🔴 修复点：添加 key="export_dept")
            dept_choices = ["所有营业部"] + options['depts']
            selected_dept = st.selectbox("营业部服务名称", dept_choices, key="export_dept")
            
            # 3. 跟踪状态 (🔴 修复点：添加 key="export_status")
            selected_status = st.multiselect("跟踪状态", status_options, default=status_options, key="export_status")

            # 6. 营销员离职日期 (🔴 修复点：添加 key="export_resign_date")
            resign_date_option = st.radio("营销员离职日期", ["不限", "为空 (在职)", "非空 (已离职)"], horizontal=True, key="export_resign_date")

        with col2:
            # 5. 末次报价时间 (🔴 修复点：添加 key="export_quote_time")
            quote_time_option = st.radio("末次报价时间", ["不限", "为空 (未报价)", "非空 (已报价)"], horizontal=True, key="export_quote_time")

            # 4. 续保过滤标识 (🔴 修复点：添加 key="export_flags")
            if not options['flags']:
                st.info("数据库中暂无续保过滤标识数据")
                selected_flags = []
            else:
                selected_flags = st.multiselect("续保过滤标识", options['flags'], default=options['flags'], key="export_flags")

    st.markdown("---")

    # --- 导出按钮逻辑 ---
    if st.button("🔍 查询并生成导出文件", type="primary", use_container_width=True, key="export_btn_search"):
        if not selected_status:
            st.warning("请至少选择一个跟踪状态")
            return
        
        # 构建 SQL 语句
        sql = "SELECT * FROM renewal_clients WHERE 1=1"
        params = []
        
        # 1. 营业部筛选
        if selected_dept != "所有营业部":
            sql += " AND department_name = %s"
            params.append(selected_dept)
            
        # 2. 跟踪状态筛选
        if selected_status:
            placeholders = ','.join(['%s'] * len(selected_status))
            sql += f" AND track_status IN ({placeholders})"
            params.extend(selected_status)
            
        # 3. 续保过滤标识筛选
        if options['flags']:
            if selected_flags:
                placeholders = ','.join(['%s'] * len(selected_flags))
                sql += f" AND filter_flag IN ({placeholders})"
                params.extend(selected_flags)
            else:
                st.warning("未选择任何续保过滤标识，可能查询不到结果")
                sql += " AND 1=0" 

        # 4. 末次报价时间筛选
        if quote_time_option == "为空 (未报价)":
            sql += " AND last_quote_time IS NULL"
        elif quote_time_option == "非空 (已报价)":
            sql += " AND last_quote_time IS NOT NULL"
            
        # 5. 营销员离职日期筛选
        if resign_date_option == "为空 (在职)":
            sql += " AND agent_resign_date IS NULL"
        elif resign_date_option == "非空 (已离职)":
            sql += " AND agent_resign_date IS NOT NULL"

        # 按终保日期升序排列 (最早到期的在前面)
        sql += " ORDER BY policy_end_date ASC"

        # 执行查询
        try:
            conn = get_connection()
            df_result = pd.read_sql(sql, conn, params=params)
            conn.close()
            
            if df_result.empty:
                st.warning("⚠️ 没有查询到符合条件的数据。")
            else:
                # ================= 列映射与排序 =================
                col_mapping = {
                    'license_plate': '车牌号',
                    'policy_end_date': '终保日期',
                    'last_quote_time': '末次报价时间',
                    'policy_holder': '投保人',
                    'vin_code': '车架号',
                    'sales_code': '销售员代码',
                    'sales_name': '销售员名称',
                    'branch_company': '支公司名称',
                    'department_name': '营销服务部名称',
                    'agent_phone': '寿险营销员电话',
                    'agent_resign_date': '营销员离职日期',
                    'vip_level': '高客等级',
                    'filter_flag': '续保过滤标识',
                    'wechat_added': '是否加微',
                    'track_status': '跟踪状态',
                    'remark': '跟踪备注'
                }
                
                target_cols = list(col_mapping.keys())
                available_cols = [c for c in target_cols if c in df_result.columns]
                df_export = df_result[available_cols].rename(columns=col_mapping)
                
                st.success(f"✅ 查询成功！共找到 {len(df_export)} 条数据。")
                
                # 生成 Excel
                import io
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='续保数据')
                
                # 下载按钮
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="📥 点击下载 Excel 文件",
                    data=output.getvalue(),
                    file_name=f"续保数据导出_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    key="export_btn_download"  # 🔴 修复点：添加 key
                )
                
                # 预览数据
                with st.expander("数据预览 (前10条)"):
                    st.dataframe(df_export.head(10))
                    
        except Exception as e:
            st.error(f"查询或导出失败: {e}")

# ================= 3. 导航配置 =================

pages = {
    "佣金计算": [
        st.Page(page_calculator, title="计算器", icon="🧮"),
        st.Page(page_rules_query, title="规则查询", icon="🔍"),
        st.Page(page_history, title="历史记录", icon="📝"),
    ],
    "续保管理": [
        st.Page(page_sync, title="数据同步", icon="🔄"),
        st.Page(page_export, title="数据导出", icon="📤"),
        st.Page(page_data_postback, title="数据回传", icon="📥"),
    ]
}

pg = st.navigation(pages)
pg.run()