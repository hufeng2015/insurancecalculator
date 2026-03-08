import pandas as pd
import time
from playwright.sync_api import sync_playwright

def run_batch_automation():
    # =================【一、数据准备】=================
    try:
        df = pd.read_excel("待报价.xlsx", dtype=str)
        print(f"✅ 成功加载《待报价.xlsx》，共 {len(df)} 条数据准备执行批量任务！\n")
    except Exception as e:
        print(f"❌ Excel 读取失败，请检查文件：{e}")
        return

    with sync_playwright() as p:
        # headless=False: 显示浏览器界面; slow_mo=300: 操作间隔300毫秒，模拟真人节奏
        browser = p.chromium.launch(headless=False, slow_mo=300)
        context = browser.new_context(viewport={'width': 1366, 'height': 768}, accept_downloads=True)
        page = context.new_page()
        
        # =================【二、全局只登录一次】=================
        print("正在打开泰康系统并自动登录...")
        page.goto("https://car.tk.cn/offwebNew/#/framework")
        
        try:
            # 填入指定的账号和密码
            page.locator("input[type='text']").first.fill("Thubei01")
            page.locator("input[type='password']").first.fill("Qwer987654")
            # 停顿 5 秒，等待输入验证码
            page.wait_for_timeout(5000)
            page.locator("button:has-text('登录'), .login-btn, input[value='登录']").first.click()
            print("✅ 全局登录成功！准备开始循环打单...\n")
            
        except Exception as e:
            print("⚠️ 自动登录未完全触发，如果页面停留在了登录页，请您在 5 秒内手动点一下...")
            page.wait_for_timeout(5000)
        
        # =================【三、核心：Excel 数据大循环】=================
        for index, row in df.iterrows():
            # 提取当前行的关键字段 - 兼容"车牌"和"车牌号"两种列名
            car_no = str(row.get('车牌号', row.get('车牌', ''))).strip()
            agent_code_excel = str(row.get('销售员代码', '')).strip()
            leave_date = str(row.get('营销员离职日期', '')).strip()
            agent_name = str(row.get('销售员名称', '')).strip()
            # 获取营销服务部名称，兼容多种可能的列名
            department_name = str(row.get('营销服务部名称', '')).strip()
            # 获取支公司名称，兼容多种可能的列名
            branch_company_name = str(row.get('支公司名称', '')).strip()
            
            # 如果车牌号为空（例如遇到了 Excel 末尾的空行），则直接跳过
            if car_no == 'nan' or not car_no:
                continue

            print(f"▶️ {'='*15} 正在处理第 {index + 1}/{len(df)} 条数据：车牌 {car_no} {'='*15}")
            
            try:
                # 1. 每次循环前，刷新或回到首页，重置系统状态
                # page.goto("https://car.tk.cn/offwebNew/#/framework")
                # page.wait_for_timeout(2000)

                # 2. 定位并点击“车险报价”菜单
                menu_item = page.locator("li.el-menu-item").filter(has=page.locator("span:has-text('车险报价')"))
                menu_item.wait_for(state="visible", timeout=30000)
                menu_item.click()
                page.wait_for_timeout(10000) # 等待 iframe 渲染 (要求等待10S)
                
                # 3. 穿透进入工作区 iframe
                iframe = page.frame_locator("iframe").first
                
                # 4. 点击 goNext
                iframe.locator("#goNext").click(force=True, timeout=10000)
                page.wait_for_timeout(10000) # 等待数据加载 (要求等待10S)
                
                # =================【四、动态表单注入与联动】=================
                # 5. 动态判断渠道和销售员代码
                if leave_date.lower() == 'nan' or not leave_date:
                    # 离职日期为空时，根据销售员代码前缀判断渠道
                    if agent_code_excel.upper().startswith('2Z'):
                        channel_keyword = "泰康人寿（综拓）(71391"
                        full_channel_name = "泰康人寿（综拓）(71391)"
                        current_agent_code = agent_code_excel
                        print(f"   👉 离职日期为空但销售员代码以 2Z 开头，走综拓渠道，销售员代码：{current_agent_code}")
                    else:
                        channel_keyword = "泰康人寿（个险）(64827"
                        full_channel_name = "泰康人寿（个险）(64827)"
                        current_agent_code = agent_code_excel
                        print(f"   👉 离职日期为空，走个险渠道，销售员代码：{current_agent_code}")
                else:
                    channel_keyword = "泰康人寿（综拓）(71391"
                    full_channel_name = "泰康人寿（综拓）(71391)"
                    current_agent_code = "2Z2000066"
                    print(f"   👉 离职日期已存在，走综拓渠道，销售员代码：{current_agent_code}")

                # 模拟逐字打字唤醒 Vue 监听器
                channel_input = iframe.locator("#channelName")
                channel_input.click() 
                channel_input.clear() 
                channel_input.press_sequentially(channel_keyword, delay=150) 
                
                # 匹配联想出来的选项并点击
                dropdown_item = iframe.locator(f"input[value='{full_channel_name}']")
                dropdown_item.wait_for(state="visible", timeout=10000)
                dropdown_item.click()
                print("   ✅ 渠道选择完成！")

                # 6. 填写销售员代码 (使用条件判断后的动态变量)
                agent_input = iframe.locator("#angetCode")
                agent_input.fill(current_agent_code)
                iframe.locator("body").click() # 触发 blur 数据联动
                page.wait_for_timeout(1500) 

                # 7. 填写车牌号
                car_input = iframe.locator("#carLicenseNo3")
                car_input.fill(car_no)
                iframe.locator("body").click() # 触发 blur 数据联动
                print("   ✅ 销售员和车牌号填写完毕，触发联动！")
                page.wait_for_timeout(2000)

                # 8. 点击下一步
                iframe.locator("#a_nextpage").click()

                page.wait_for_timeout(5000) 

                # 此处点击<input type="button" value="确认" class="btn-confirm1 confirm1-op8" id="btn_carModelConfirm1">
                # 先判断是否存在
                if iframe.locator("input.btn-confirm1[value='确认']").is_visible():
                    print("   ⚠️ 检测到弹窗，正在点击『确认』...")
                    iframe.locator("input.btn-confirm1[value='确认']").click()
                    page.wait_for_timeout(2000)
                else:
                    print("   ✅ 无需处理弹窗，继续执行下一步...")
                # # 此处可能会出现弹窗，需要处理，直接点击确认即可
                # if page.locator("body").text_content().find("确定") > -1:
                #     print("   ⚠️ 检测到弹窗，正在点击『确定』...")
                #     page.locator("body").click()
                #     page.wait_for_timeout(2000)
                
                # =================【五、险种选择与下载】=================
                # 9. 险种选择对话框：等待标签出现并点击
                page.wait_for_timeout(2000) 
                iframe.locator("label[for='kindLimitBZAndCI']").wait_for(state="visible", timeout=10000)
                iframe.locator("label[for='kindLimitBZAndCI']").click()
                
                # 10. 点击确认 (精准定位解决 Strict Mode 冲突)
                iframe.locator("input.trafficBtn2[value='确认']").click()
                print("   ✅ 已确认险种大类，等待详细页面加载...")
                # 等待页面完全渲染
                page.wait_for_timeout(10000)

                # 此处检测 <input type="button" id="btn_sure" value="确定" class="confirmCheck" data-role="none">
                if iframe.locator("input.confirmCheck[value='确定']").is_visible():
                    print("   ⚠️ 检测到错误弹窗，正在获取错误信息...")
                    try:
                        # 获取错误提示文本 - 从 div.tipsinfoCheck 中获取
                        error_div = iframe.locator("#div_dialogSureMess")
                        if error_div.is_visible():
                            error_message = error_div.inner_text()
                            print(f"   ❌ 错误信息：{error_message}")
                            # 不点击确定按钮，直接抛出异常
                            raise Exception(f"保费计算失败：{error_message}")
                        else:
                            # 如果找不到特定的 div，尝试从父级元素获取
                            dialog = iframe.locator("input.confirmCheck[value='确定']").locator('xpath=../..')
                            if dialog.is_visible():
                                dialog_text = dialog.inner_text()
                                if dialog_text and dialog_text != '确定':
                                    print(f"   ❌ 详细错误：{dialog_text}")
                                    raise Exception(f"保费计算失败：{dialog_text}")
                            
                            print("   ❌ 无法获取具体错误信息")
                            raise Exception("保费计算失败，检测到错误弹窗")
                    except Exception as e:
                        if str(e) != "保费计算失败，检测到错误弹窗":
                            raise e
                        else:
                            raise e
                else:
                    print("   ✅ 无需处理弹窗，继续执行下一步...")

                page.wait_for_timeout(2000)
                
                # 11. 取消勾选“泰乐途”
                tat_checkbox = iframe.locator("#check_TAT")
                if tat_checkbox.is_visible() and tat_checkbox.is_checked():
                    tat_checkbox.uncheck(force=True)
                    print("   ✅ 泰乐途已取消勾选")
                
                # 12. 点击保费计算
                print("   🧮 正在提交保费计算，请耐心等待...")
                iframe.locator("#premiumCalculate_btn").first.click()

                page.wait_for_timeout(10000)

                #此处点击 <input type="button" id="btn_sure" value="确定" class="confirmCheck" data-role="none">
                if iframe.locator("input.confirmCheck[value='确定']").is_visible():
                    print("   ⚠️ 检测到弹窗，正在点击『确定』...")
                    iframe.locator("input.confirmCheck[value='确定']").click()
                else:
                    print("   ✅ 无需处理弹窗，继续执行下一步...")

                page.wait_for_timeout(2000)
                
                # 13. 点击查看报价单 (保费计算需经过后台，可能较慢，给足 45 秒宽容度)
                make_price_list_btn = iframe.locator("#makePriceList")
                make_price_list_btn.wait_for(state="visible", timeout=45000) 
                make_price_list_btn.click()
                page.wait_for_timeout(2000)
                
                # 14. 点击并拦截下载报价单
                print("   📥 准备下载报价单文件...")
                with page.expect_download(timeout=30000) as download_info:
                    iframe.locator("button.btnDown").click()
                
                download = download_info.value
                
                # 🌟 按照指定规则组合文件名（注意：这里保存为 .png，实际文件底层依然是系统派发的格式，一般为 PDF）
                if agent_name == 'nan':
                    agent_name = "未知销售员"
                
                # 根据离职日期判断是否为孤儿单，并在文件名中标识
                file_prefix = ""
                if leave_date.lower() != 'nan' and leave_date:
                    file_prefix = "孤儿单_"
                
                # 处理支公司名称，作为第一级文件夹名称
                if branch_company_name == 'nan' or not branch_company_name:
                    branch_company_name = "未指定支公司"
                
                # 处理营销服务部名称，作为第二级文件夹名称
                if department_name == 'nan' or not department_name:
                    department_name = "未指定部门"
                
                # 确保文件夹存在，如果不存在则创建（两级目录）
                import os
                # 先创建支公司文件夹
                if not os.path.exists(branch_company_name):
                    os.makedirs(branch_company_name)
                    print(f"   📁 已创建支公司文件夹：{branch_company_name}")
                
                # 再创建营销服务部子文件夹（在支公司文件夹内）
                department_path = os.path.join(branch_company_name, department_name)
                if not os.path.exists(department_path):
                    os.makedirs(department_path)
                    print(f"   📁 已创建部门子文件夹：{department_path}")
                
                # 构建完整的保存路径：支公司/营销服务部/文件名
                download_path = os.path.join(department_path, f"{file_prefix}{agent_name}_报价单_{car_no}.png")
                
                download.save_as(download_path)
                print(f"   🎉 第 {index + 1} 单完成！文件已存为：{download_path}\n")
                
            except Exception as e:
                # 【容错机制】这辆车出错了？没关系，跳过这辆车，继续跑下一辆！
                print(f"   ❌ 车牌 {car_no} 处理失败，跳过该条。错误简述: {str(e)[:100]}...\n")
                continue

        print("🎊 大功告成！所有 Excel 数据处理完毕！您的 RPA 机器人已完成使命。")
        page.pause() # 跑完后暂停一下，方便您确认成果

if __name__ == "__main__":
    run_batch_automation()