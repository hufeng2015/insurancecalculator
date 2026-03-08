import pandas as pd
import time
from playwright.sync_api import sync_playwright

def test_form_fill():
    # 1. 读取 Excel 数据
    try:
        df = pd.read_excel("待报价.xlsx", dtype=str)
        # 提取第一条数据作为本次的测试对象
        test_row = df.iloc[0]
        car_no = str(test_row.get('车牌号', '')).strip()
        agent_code = str(test_row.get('销售员代码', '')).strip()
        agent_name = str(test_row.get('销售员名称', '')).strip()
        leave_date = str(test_row.get('营销员离职日期', '')).strip()
        print(f"✅ 成功加载数据。当前测试车辆：{car_no}，销售员代码：{agent_code}")
    except Exception as e:
        print(f"❌ Excel 读取失败：{e}")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context(viewport={'width': 1366, 'height': 768})
        page = context.new_page()
        
        # =================【阶段一：自动登录与导航】=================
        print("正在打开泰康系统并尝试自动登录...")
        page.goto("https://car.tk.cn/offwebNew/#/framework")
        
        # 尝试自动定位账号密码框 (使用常见的选择器，如果报错请告诉我登录页的截图或源码)
        try:
            # 匹配 type 为 text 或 password 的输入框
            page.locator("input[type='text']").first.fill("Thubei01")
            page.locator("input[type='password']").first.fill("Qwer987654")
            
            # 点击登录按钮（匹配包含“登录”文字的按钮或常见 class）
            login_btn = page.locator("button:has-text('登录'), .login-btn, input[value='登录']").first
            login_btn.click()
            print("✅ 已提交登录信息！")
        except Exception as e:
            print(f"⚠️ 自动登录遇到一点问题，可能输入框特征不匹配。请在 60 秒内手动补充登录...")
        
        # 等待菜单并进入
        menu_item = page.locator("li.el-menu-item").filter(has=page.locator("span:has-text('车险报价')"))
        menu_item.wait_for(state="visible", timeout=60000)
        menu_item.click()
        page.wait_for_timeout(10000)
        
        # 穿透 iframe 点击 goNext
        iframe = page.frame_locator("iframe").first
        iframe.locator("#goNext").click(force=True, timeout=10000)
        page.wait_for_timeout(10000)
        
        # =================【阶段二：表单数据联动注入】=================
        print("🚀 开始注入表单数据...")
        
        try:
            # 判断“营销员离职日期”是否为空 ('nan' 是 pandas 读取空单元格的默认字符串转化)
            if leave_date.lower() == 'nan' or not leave_date:
                print("👉 营销员离职日期为空，开始选择渠道...")
                channel_input = iframe.locator("#channelName")
                
                # 1. 终极方案：模拟真人逐字输入（故意少输入最后一个“)”）
                channel_input.click() # 先点击聚焦
                channel_input.clear() # 清空已有的内容
                print("⌨️ 正在模拟真人逐字打字...")
                # delay=150 表示每个字符输入间隔 0.15 秒，完美触发 Vue 的 input 监听器
                channel_input.press_sequentially("泰康人寿（个险）(64827", delay=150) 
                
                # 2. 显式等待那个隐藏的下拉框出现
                print("⏳ 等待下拉联想菜单弹出...")
                dropdown_item = iframe.locator("input[intermediarycode='000000000004']")
                dropdown_item.wait_for(state="visible", timeout=10000)
                
                # 3. 点击联想出来的选项
                dropdown_item.click()
                print("✅ 渠道选择完成！")

            # 填写销售员代码
            agent_input = iframe.locator("#angetCode")
            agent_input.fill(agent_code)
            # 点击页面空白处触发 blur 数据联动
            iframe.locator("body").click() 
            print("✅ 销售员代码填写完毕，已触发联动！")
            page.wait_for_timeout(2000) # 等待联动接口请求返回

            # 填写车牌号
            car_input = iframe.locator("#carLicenseNo3")
            car_input.fill(car_no)
            # 再次点击页面空白处触发 blur 数据联动
            iframe.locator("body").click()
            print("✅ 车牌号填写完毕，已触发联动！")
            page.wait_for_timeout(2000)

            # ... 前面第四步的代码 ...
            # 点击下一步
            print("正在点击『下一步』...")
            iframe.locator("#a_nextpage").click()
            
           # =================【阶段三：险种计算与下载】=================
            print("⏳ 等待险种选择对话框出现...")
            page.wait_for_timeout(2000) # 给对话框一点弹出的时间
            
            # 10. 选择：交强险+商业险
            # 破解障眼法：直接点击绑定了该 radio 的 label 标签，或者直接点击文字
            print("👉 正在勾选『交强险+商业险』...")
            iframe.locator("label[for='kindLimitBZAndCI']").click()
            print("✅ 已选择交强险+商业险")
            
            # 11. 点击确认
            print("👉 正在点击对话框的『确认』按钮...")
            # 增加 [value='确认'] 属性选择器，精准定位目标按钮，解决严格模式报错
            iframe.locator("input.trafficBtn2[value='确认']").click()
            print("✅ 已确认险种大类，等待详细险种页面加载...")
            page.wait_for_timeout(3000) # 等待页面完全渲染
            
            # 12. 取消勾选“泰乐途”
            print("正在检查并取消勾选『泰乐途』...")
            tat_checkbox = iframe.locator("#check_TAT")
            # 确保如果它是勾选状态，才去取消它
            if tat_checkbox.is_checked():
                tat_checkbox.uncheck(force=True)
                print("✅ 泰乐途已取消勾选")
            else:
                print("👉 泰乐途已经是未勾选状态")
            
            # 13. 点击保费计算
            print("🧮 正在提交保费计算，请稍候...")
            iframe.locator("#premiumCalculate_btn").first.click()
            
            # 14. 点击查看报价单
            print("⏳ 等待系统计算出结果 (可能耗时较长)...")
            make_price_list_btn = iframe.locator("#makePriceList")
            # 保费计算通常需要调用后台接口，这里设置 30 秒超时等待按钮出现
            make_price_list_btn.wait_for(state="visible", timeout=30000) 
            make_price_list_btn.click()
            print("✅ 已生成报价单预览！")
            page.wait_for_timeout(2000)
            
            # 15. 点击并拦截下载报价单
            print("📥 准备下载报价单文件...")
            # Playwright 的特定语法：预期会发生一个下载事件
            with page.expect_download() as download_info:
                iframe.locator("button.btnDown").click()
            
            # 获取下载对象并保存到本地
            download = download_info.value
            # 使用车牌号动态命名文件，防止覆盖
            download_path = f"{agent_name}_报价单_{car_no}.png" 
            download.save_as(download_path)
            
            print(f"🎉 第五步大功告成！报价单已成功保存到当前目录：{download_path}")
            
            # 16. 刷新页面，准备下一次循环 (我们在最后一步再套入 for 循环)
            # page.reload() 
            
            page.pause() # 调试用，确认下载完成后可关闭
            
        except Exception as e:
            print(f"❌ 流程中断，错误信息: {e}")
            page.pause()
            
        finally:
            browser.close()

if __name__ == "__main__":
    test_form_fill()