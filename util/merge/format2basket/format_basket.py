import csv

# 原始 CSV 文件名
input_file = '禄得可转债行情表.csv'
# 输出 CSV 文件名
output_file = 'basket_strategy.csv'

# 读取原始文件
with open(input_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print("表头解析后的列名：", rows[0].keys())
# 或者：
print("第一行数据对应的键值对：", rows[0])

# 准备新 CSV 需要的表头
fieldnames = ["代码", "市场", "数量", "相对权重", "方向", "转债名称"]

new_rows = []

# 只取前5条记录（假设原始数据首行为表头，从第二行开始为数据）
for i in range(min(5, len(rows))):
    # 取得转债代码和转债名称
    bond_code = rows[i]["转债代码"]  # 原 CSV 中对应的列名
    bond_name = rows[i]["转债名称"]  # 原 CSV 中对应的列名

    # 按 '.' 进行分割
    code_part, market_part = bond_code.split(".")

    # 构造新行
    new_rows.append({
        "代码": code_part,
        "市场": market_part,
        "数量": 0,
        "相对权重": 0,
        "方向": 0,
        "转债名称": bond_name
    })

# 将处理结果写入新的CSV文件
with open(output_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in new_rows:
        writer.writerow(row)