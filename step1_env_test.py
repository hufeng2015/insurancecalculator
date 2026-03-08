from playwright.sync_api import sync_playwright

def test_environment():
    print("正在启动 Playwright...")
    with sync_playwright() as p:
        # headless=False 表示非无头模式，你可以看到浏览器弹出来
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.baidu.com")
        print(f"成功打开网页，当前页面标题为: {page.title()}")
        browser.close()
        print("第一步测试通过！")

if __name__ == "__main__":
    test_environment()