import pandas as pd

def test_read_excel():
    file_path = "待报价.xlsx" # 替换为你的实际文件名
    
    try:
        # 使用 dtype=str 强制将所有列读取为字符串，防止类似“000000000004”这样的代码前面的0被抹除
        df = pd.read_excel(file_path, dtype=str)
        
        # 过滤掉表头中的空白字符
        df.columns = df.columns.str.strip()
        
        print("✅ Excel 读取成功！一共包含 {} 条数据。".format(len(df)))
        print("-" * 30)
        
        # 提取第一条数据进行展示
        first_row = df.iloc[0]
        print("第一条测试数据如下：")
        print(f"车牌号: {first_row.get('车牌号', '未找到对应列')}")
        print(f"销售员代码: {first_row.get('销售员代码', '未找到对应列')}")
        print(f"离职日期: {first_row.get('营销员离职日期', '未找到对应列')}")
        
    except Exception as e:
        print(f"❌ 读取失败，错误信息: {e}")

if __name__ == "__main__":
    test_read_excel()