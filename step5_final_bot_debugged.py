import pandas as pd
import time
import os
import re
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()


class ExcelLogger:
    """Excel日志管理器"""
    
    def __init__(self, log_file="执行日志.xlsx"):
        self.log_file = log_file
        self.current_car_logs = []
        self.all_logs = []
        
        if os.path.exists(log_file):
            try:
                self.all_logs = pd.read_excel(log_file).to_dict('records')
            except:
                self.all_logs = []
    
    def start_car(self, car_no, index, total):
        """开始处理一辆车"""
        self.current_car_logs = [{
            '处理时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '车牌号': car_no,
            '序号': f"{index + 1}/{total}",
            '步骤': '开始处理',
            '状态': '进行中',
            '详细信息': '',
            '错误信息': '',
            '文件路径': ''
        }]
    
    def log_step(self, step_name, status, detail='', error=''):
        """记录处理步骤"""
        self.current_car_logs.append({
            '处理时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '车牌号': self.current_car_logs[0]['车牌号'] if self.current_car_logs else '',
            '序号': self.current_car_logs[0]['序号'] if self.current_car_logs else '',
            '步骤': step_name,
            '状态': status,
            '详细信息': detail,
            '错误信息': error,
            '文件路径': ''
        })
    
    def finish_car(self, success=True, file_path='', error_msg=''):
        """完成一辆车的处理"""
        final_status = '成功' if success else '失败'
        self.current_car_logs.append({
            '处理时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '车牌号': self.current_car_logs[0]['车牌号'] if self.current_car_logs else '',
            '序号': self.current_car_logs[0]['序号'] if self.current_car_logs else '',
            '步骤': '处理完成',
            '状态': final_status,
            '详细信息': '',
            '错误信息': error_msg,
            '文件路径': file_path
        })
        
        self.all_logs.extend(self.current_car_logs)
        self.save_to_excel()
    
    def save_to_excel(self):
        """保存日志到Excel文件"""
        df = pd.DataFrame(self.all_logs)
        df.to_excel(self.log_file, index=False, engine='openpyxl')
    
    def get_summary(self):
        """获取统计摘要"""
        if not self.all_logs:
            return {'成功': 0, '失败': 0, '跳过': 0}
        
        completed = [log for log in self.all_logs if log['步骤'] == '处理完成']
        success = sum(1 for log in completed if log['状态'] == '成功')
        failed = sum(1 for log in completed if log['状态'] == '失败')
        
        return {'成功': success, '失败': failed, '跳过': 0}


def sanitize_folder_name(name):
    """清理文件夹名称，移除非法字符"""
    if not name or name.lower() == 'nan':
        return "未命名"
    # 移除或替换Windows文件系统中的非法字符
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        name = name.replace(char, '_')
    # 移除前后空格
    name = name.strip()
    # 限制长度
    return name[:50] if name else "未命名"


def is_valid_date(date_str):
    """检查字符串是否为有效的日期格式"""
    if not date_str or pd.isna(date_str):
        return False
    date_str = str(date_str).strip()
    if date_str.lower() == 'nan':
        return False
    # 简单的日期格式检查（支持 YYYY-MM-DD, YYYY/MM/DD 等）
    date_pattern = r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}$'
    return bool(re.match(date_pattern, date_str))


def safe_get_value(row, possible_columns, default=''):
    """安全地从DataFrame行中获取值，支持多个可能的列名"""
    for col in possible_columns:
        if col in row.index:
            value = row[col]
            if pd.notna(value):
                return str(value).strip()
    return default


def run_batch_automation():
    # =================【一、数据准备】=================
    print("=" * 60)
    print("🚀 泰康车险批量报价机器人启动")
    print("=" * 60)
    
    # 初始化Excel日志管理器
    logger = ExcelLogger("执行日志.xlsx")
    print("✅ Excel日志管理器已初始化")
    
    # 检查待报价.xlsx是否存在
    excel_file = "待报价.xlsx"
    if not os.path.exists(excel_file):
        print(f"❌ 错误：找不到文件 '{excel_file}'")
        print(f"   请确保文件位于当前目录: {os.getcwd()}")
        return

    try:
        df = pd.read_excel(excel_file, dtype=str)
        print(f"✅ 成功加载《{excel_file}》，共 {len(df)} 条数据准备执行批量任务！\n")
        
        # 调试：显示列名
        print(f"📋 Excel列名: {list(df.columns)}")
        print(f"📋 前3行数据预览:")
        print(df.head(3).to_string())
        print()
    except Exception as e:
        print(f"❌ Excel 读取失败，请检查文件：{e}")
        import traceback
        traceback.print_exc()
        return

    with sync_playwright() as p:
        # headless=False: 显示浏览器界面; slow_mo=300: 操作间隔300毫秒，模拟真人节奏
        try:
            browser = p.chromium.launch(headless=False, slow_mo=300)
            context = browser.new_context(viewport={'width': 1366, 'height': 768}, accept_downloads=True)
            page = context.new_page()
            print("✅ 浏览器启动成功")
        except Exception as e:
            print(f"❌ 浏览器启动失败: {e}")
            print("   请确保已安装 Playwright: pip install playwright")
            print("   并运行: playwright install chromium")
            return
        
        # =================【二、全局只登录一次】=================
        print("\n正在打开泰康系统并自动登录...")
        try:
            page.goto("https://car.tk.cn/offwebNew/#/framework")
            print("✅ 页面加载成功")
        except Exception as e:
            print(f"❌ 页面加载失败: {e}")
            browser.close()
            return
        
        try:
            # 从环境变量获取账号和密码
            username = os.getenv('TK_USERNAME', 'Thubei01')
            password = os.getenv('TK_PASSWORD', 'Qwer987654')
            
            # 填入指定的账号和密码
            print("   正在填写登录信息...")
            page.locator("input[type='text']").first.fill(username)
            page.locator("input[type='password']").first.fill(password)
            print("   登录信息已填写，请在5秒内手动输入验证码...")
            # 停顿 5 秒，等待输入验证码
            page.wait_for_timeout(5000)
            page.locator("button:has-text('登录'), .login-btn, input[value='登录']").first.click()
            print("✅ 全局登录成功！准备开始循环打单...\n")
            
        except Exception as e:
            print(f"⚠️ 自动登录未完全触发: {e}")
            print("   如果页面停留在了登录页，请您在 5 秒内手动点一下...")
            page.wait_for_timeout(5000)
        
        # =================【三、核心：Excel 数据大循环】=================
        success_count = 0
        fail_count = 0
        skip_count = 0
        
        for index, row in df.iterrows():
            print(f"\n{'='*60}")
            print(f"▶️ 正在处理第 {index + 1}/{len(df)} 条数据")
            print(f"{'='*60}")
            
            # 提取当前行的关键字段
            car_no = safe_get_value(row, ['车牌号', '车牌', 'car_no', 'license_plate'])
            agent_code_excel = safe_get_value(row, ['销售员代码', 'agent_code', 'sales_code', '业务员代码'])
            leave_date = safe_get_value(row, ['营销员离职日期', '离职日期', 'leave_date'])
            agent_name = safe_get_value(row, ['销售员名称', '业务员名称', 'agent_name', 'sales_name'])
            department_name = safe_get_value(row, ['营销服务部名称', '服务部名称', 'department', 'dept_name'])
            branch_company_name = safe_get_value(row, ['支公司名称', '分公司名称', 'branch', 'branch_name'])
            
            # 开始记录这辆车的日志
            logger.start_car(car_no, index, len(df))
            logger.log_step('数据提取', '成功', f"车牌:{car_no}, 销售员:{agent_name}")
            
            # 调试输出
            print(f"   📊 原始数据:")
            print(f"      - 车牌号: '{car_no}'")
            print(f"      - 销售员代码: '{agent_code_excel}'")
            print(f"      - 离职日期: '{leave_date}'")
            print(f"      - 销售员名称: '{agent_name}'")
            print(f"      - 营销服务部: '{department_name}'")
            print(f"      - 支公司: '{branch_company_name}'")
            
            # 如果车牌号为空，则直接跳过
            if not car_no or car_no.lower() == 'nan':
                print(f"   ⚠️ 第 {index + 1} 行车牌号为空，跳过")
                logger.log_step('数据验证', '跳过', '车牌号为空')
                logger.finish_car(success=False, error_msg='车牌号为空')
                skip_count += 1
                continue

            try:
                # 2. 定位并点击"车险报价"菜单
                print("   🔄 正在点击'车险报价'菜单...")
                logger.log_step('点击菜单', '进行中', '车险报价')
                menu_item = page.locator("li.el-menu-item").filter(has=page.locator("span:has-text('车险报价')"))
                menu_item.wait_for(state="visible", timeout=30000)
                menu_item.click()
                print("   ✅ 已点击'车险报价'菜单，等待iframe渲染...")
                logger.log_step('点击菜单', '成功', '等待iframe渲染')
                page.wait_for_timeout(10000)
                
                # 3. 穿透进入工作区 iframe
                print("   🔄 正在进入iframe...")
                logger.log_step('进入iframe', '进行中')
                iframe = page.frame_locator("iframe").first
                
                # 4. 点击 goNext
                print("   🔄 正在点击'goNext'按钮...")
                logger.log_step('点击goNext', '进行中')
                iframe.locator("#goNext").click(force=True, timeout=10000)
                print("   ✅ 已点击'goNext'，等待数据加载...")
                logger.log_step('点击goNext', '成功', '等待数据加载')
                page.wait_for_timeout(10000)
                
                # =================【四、动态表单注入与联动】=================
                # 5. 动态判断渠道和销售员代码
                print("   🔄 正在判断渠道类型...")
                logger.log_step('渠道判断', '进行中')
                
                has_leave_date = is_valid_date(leave_date)
                
                if not has_leave_date:
                    if agent_code_excel.upper().startswith('2Z'):
                        channel_keyword = "泰康人寿（综拓）(71391"
                        full_channel_name = "泰康人寿（综拓）(71391)"
                        current_agent_code = agent_code_excel
                        channel_type = "综拓渠道"
                        print(f"   👉 离职日期为空但销售员代码以 2Z 开头，走综拓渠道")
                        print(f"      销售员代码：{current_agent_code}")
                    else:
                        channel_keyword = "泰康人寿（个险）(64827"
                        full_channel_name = "泰康人寿（个险）(64827)"
                        current_agent_code = agent_code_excel
                        channel_type = "个险渠道"
                        print(f"   👉 离职日期为空，走个险渠道")
                        print(f"      销售员代码：{current_agent_code}")
                else:
                    channel_keyword = "泰康人寿（综拓）(71391"
                    full_channel_name = "泰康人寿（综拓）(71391)"
                    current_agent_code = "2Z2000066"
                    channel_type = "综拓渠道(孤儿单)"
                    print(f"   👉 离职日期已存在({leave_date})，走综拓渠道")
                    print(f"      使用默认销售员代码：{current_agent_code}")
                
                logger.log_step('渠道判断', '成功', f'{channel_type}, 代码:{current_agent_code}')

                # 模拟逐字打字唤醒 Vue 监听器
                print("   🔄 正在填写渠道信息...")
                logger.log_step('填写渠道', '进行中', full_channel_name)
                channel_input = iframe.locator("#channelName")
                channel_input.click() 
                channel_input.clear() 
                channel_input.press_sequentially(channel_keyword, delay=150) 
                
                # 匹配联想出来的选项并点击
                print("   🔄 正在选择渠道选项...")
                dropdown_item = iframe.locator(f"input[value='{full_channel_name}']")
                dropdown_item.wait_for(state="visible", timeout=10000)
                dropdown_item.click()
                print("   ✅ 渠道选择完成！")
                logger.log_step('填写渠道', '成功', full_channel_name)

                # 6. 填写销售员代码
                print(f"   🔄 正在填写销售员代码: {current_agent_code}")
                logger.log_step('填写销售员代码', '进行中', current_agent_code)
                agent_input = iframe.locator("#angetCode")
                agent_input.fill(current_agent_code)
                iframe.locator("body").click()
                page.wait_for_timeout(1500) 

                # 7. 填写车牌号
                print(f"   🔄 正在填写车牌号: {car_no}")
                logger.log_step('填写车牌号', '进行中', car_no)
                car_input = iframe.locator("#carLicenseNo3")
                car_input.fill(car_no)
                iframe.locator("body").click()
                print("   ✅ 销售员和车牌号填写完毕，触发联动！")
                logger.log_step('填写车牌号', '成功', '数据联动完成')
                page.wait_for_timeout(2000)

                # 8. 点击下一步
                print("   🔄 正在点击'下一步'...")
                logger.log_step('点击下一步', '进行中')
                iframe.locator("#a_nextpage").click()
                page.wait_for_timeout(5000) 

                # 此处点击确认按钮
                confirm_btn = iframe.locator("input.btn-confirm1[value='确认']")
                if confirm_btn.is_visible():
                    print("   ⚠️ 检测到弹窗，正在点击『确认』...")
                    logger.log_step('处理弹窗', '进行中', '车型确认弹窗')
                    confirm_btn.click()
                    page.wait_for_timeout(2000)
                    logger.log_step('处理弹窗', '成功', '已确认')
                else:
                    print("   ✅ 无需处理弹窗，继续执行下一步...")
                    logger.log_step('处理弹窗', '跳过', '无弹窗')
                
                # =================【五、险种选择与下载】=================
                # 9. 险种选择对话框
                print("   🔄 正在选择险种...")
                logger.log_step('选择险种', '进行中')
                page.wait_for_timeout(2000) 
                kind_label = iframe.locator("label[for='kindLimitBZAndCI']")
                kind_label.wait_for(state="visible", timeout=10000)
                kind_label.click()
                
                # 10. 点击确认
                print("   🔄 正在确认险种选择...")
                iframe.locator("input.trafficBtn2[value='确认']").click()
                print("   ✅ 已确认险种大类，等待详细页面加载...")
                logger.log_step('选择险种', '成功', '交强险+商业险')
                page.wait_for_timeout(10000)

                # 此处检测错误弹窗
                error_dialog = iframe.locator("input.confirmCheck[value='确定']")
                if error_dialog.is_visible():
                    print("   ⚠️ 检测到错误弹窗，正在获取错误信息...")
                    logger.log_step('检测错误', '失败', '发现错误弹窗')
                    try:
                        error_div = iframe.locator("#div_dialogSureMess")
                        if error_div.is_visible():
                            error_message = error_div.inner_text()
                            print(f"   ❌ 错误信息：{error_message}")
                            logger.log_step('获取错误详情', '失败', '', error_message)
                            raise Exception(f"保费计算失败：{error_message}")
                        else:
                            dialog = error_dialog.locator('xpath=../..')
                            if dialog.is_visible():
                                dialog_text = dialog.inner_text()
                                if dialog_text and dialog_text != '确定':
                                    print(f"   ❌ 详细错误：{dialog_text}")
                                    logger.log_step('获取错误详情', '失败', '', dialog_text)
                                    raise Exception(f"保费计算失败：{dialog_text}")
                            
                            print("   ❌ 无法获取具体错误信息")
                            logger.log_step('获取错误详情', '失败', '', '未知错误')
                            raise Exception("保费计算失败，检测到错误弹窗")
                    except Exception as e:
                        if "保费计算失败" in str(e):
                            raise e
                        else:
                            raise Exception(f"处理错误弹窗时发生异常: {str(e)}")
                else:
                    print("   ✅ 无错误弹窗，继续执行下一步...")
                    logger.log_step('检测错误', '成功', '无错误')

                page.wait_for_timeout(2000)
                
                # 11. 取消勾选"泰乐途"
                print("   🔄 正在处理'泰乐途'选项...")
                logger.log_step('处理泰乐途', '进行中')
                tat_checkbox = iframe.locator("#check_TAT")
                if tat_checkbox.is_visible() and tat_checkbox.is_checked():
                    tat_checkbox.uncheck(force=True)
                    print("   ✅ 泰乐途已取消勾选")
                    logger.log_step('处理泰乐途', '成功', '已取消勾选')
                else:
                    print("   ℹ️ 泰乐途未勾选或不可见")
                    logger.log_step('处理泰乐途', '跳过', '未勾选或不可见')
                
                # 12. 点击保费计算
                print("   🧮 正在提交保费计算，请耐心等待...")
                logger.log_step('保费计算', '进行中')
                iframe.locator("#premiumCalculate_btn").first.click()
                page.wait_for_timeout(10000)

                # 此处点击确定按钮
                confirm_check = iframe.locator("input.confirmCheck[value='确定']")
                if confirm_check.is_visible():
                    print("   ⚠️ 检测到弹窗，正在点击『确定』...")
                    logger.log_step('处理计算弹窗', '进行中')
                    confirm_check.click()
                    logger.log_step('处理计算弹窗', '成功')
                else:
                    print("   ✅ 无需处理弹窗，继续执行下一步...")
                    logger.log_step('处理计算弹窗', '跳过', '无弹窗')

                page.wait_for_timeout(2000)
                
                # 13. 点击查看报价单
                print("   🔄 正在点击查看报价单...")
                logger.log_step('查看报价单', '进行中')
                make_price_list_btn = iframe.locator("#makePriceList")
                make_price_list_btn.wait_for(state="visible", timeout=45000) 
                make_price_list_btn.click()
                logger.log_step('查看报价单', '成功')
                page.wait_for_timeout(2000)
                
                # 14. 点击并拦截下载报价单
                print("   📥 准备下载报价单文件...")
                logger.log_step('下载报价单', '进行中')
                with page.expect_download(timeout=30000) as download_info:
                    iframe.locator("button.btnDown").click()
                
                download = download_info.value
                
                # 按照指定规则组合文件名
                if not agent_name or agent_name.lower() == 'nan':
                    agent_name = "未知销售员"
                
                # 根据离职日期判断是否为孤儿单
                file_prefix = ""
                if has_leave_date:
                    file_prefix = "孤儿单_"
                
                # 清理文件夹名称
                safe_branch_name = sanitize_folder_name(branch_company_name)
                safe_department_name = sanitize_folder_name(department_name)
                
                # 确保文件夹存在
                if not os.path.exists(safe_branch_name):
                    os.makedirs(safe_branch_name)
                    print(f"   📁 已创建支公司文件夹：{safe_branch_name}")
                
                department_path = os.path.join(safe_branch_name, safe_department_name)
                if not os.path.exists(department_path):
                    os.makedirs(department_path)
                    print(f"   📁 已创建部门子文件夹：{department_path}")
                
                # 构建完整的保存路径
                safe_agent_name = sanitize_folder_name(agent_name)
                download_path = os.path.join(department_path, f"{file_prefix}{safe_agent_name}_报价单_{car_no}.png")
                
                download.save_as(download_path)
                print(f"   🎉 第 {index + 1} 单完成！")
                print(f"      文件已保存至：{download_path}")
                logger.log_step('下载报价单', '成功', '', '', download_path)
                logger.finish_car(success=True, file_path=download_path)
                success_count += 1
                
            except Exception as e:
                error_msg = str(e)
                print(f"   ❌ 车牌 {car_no} 处理失败！")
                print(f"   错误详情: {error_msg}")
                logger.log_step('处理失败', '失败', '', error_msg)
                logger.finish_car(success=False, error_msg=error_msg)
                fail_count += 1
                continue

        # =================【六、执行完成统计】=================
        summary = logger.get_summary()
        print(f"\n{'='*60}")
        print("🎊 执行完成统计")
        print(f"{'='*60}")
        print(f"   ✅ 成功: {summary['成功']} 单")
        print(f"   ❌ 失败: {summary['失败']} 单")
        print(f"   ⏭️  跳过: {skip_count} 单")
        print(f"   📊 总计: {len(df)} 单")
        print(f"\n📄 详细日志已保存至：执行日志.xlsx")
        print(f"\n您的 泰康车险AI员工 已完成使命！")
        
        page.pause()  # 跑完后暂停一下，方便您确认成果


if __name__ == "__main__":
    run_batch_automation()
