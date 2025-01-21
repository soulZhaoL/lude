import pandas as pd
import os
from glob import glob

# 指定当前目录下所有 CSV 文件的路径
csv_files = glob(os.path.join(os.getcwd(), "*.csv"))

# 排除名为 "merged_output.csv" 的文件
csv_files = [file for file in csv_files if os.path.basename(file) != "merged_output.csv"]

# 创建一个空的 DataFrame 用于存储合并后的数据
merged_df = pd.DataFrame()

# 遍历所有 CSV 文件并尝试不同编码读取
for file in csv_files:
    for encoding in ['utf-8', 'gbk', 'latin1', 'iso-8859-1']:
        try:
            df = pd.read_csv(file, encoding=encoding)
            print(f"{file} 成功使用编码 '{encoding}' 读取")
            break
        except Exception as e:
            continue
    else:
        print(f"{file} 无法读取")
        continue

    # 合并数据
    merged_df = pd.concat([merged_df, df], ignore_index=True)

# 去除重复行（以第一列为基础去重）
merged_df.drop_duplicates(subset=[merged_df.columns[0]], inplace=True)

# 计算权重并将第四列的值设置为权重，使其总和为 1
if merged_df.shape[1] >= 4:
    total_rows = len(merged_df)
    if total_rows > 0:
        weight = 1 / total_rows
        merged_df.iloc[:, 3] = weight

# 生成输出文件路径
output_file = "/Users/zhaolei/Downloads/result.csv"

# 将合并后的数据保存为新的 CSV 文件
merged_df.to_csv(output_file, index=False, encoding='utf-8-sig')

print(f"合并完成！已生成文件：{output_file}")