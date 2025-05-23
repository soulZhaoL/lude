import json
from bs4 import BeautifulSoup

# 示例 HTML 字符串，注意多行字符串要用三个引号包裹
# html_content = """
# <ul class="ant-menu ant-menu-sub ant-menu-vertical" role="menu" id="factor-menu-tmp_key-0-popup" data-menu-list="true"><li role="presentation" icon="[object Object]" class="ant-menu-item-group"><div role="presentation" class="ant-menu-item-group-title" title="基础因子">基础因子</div><ul role="group" class="ant-menu-item-group-list"><li title="转股溢价率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-conv_prem" class="ant-menu-item"><span class="ant-menu-title-content">转股溢价率</span></li><li title="理论溢价率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-theory_conv_prem" class="ant-menu-item"><span class="ant-menu-title-content">理论溢价率</span></li><li title="修正溢价率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-mod_conv_prem" class="ant-menu-item"><span class="ant-menu-title-content">修正溢价率</span></li><li title="收盘价" role="menuitem" tabindex="-1" data-menu-id="factor-menu-close" class="ant-menu-item"><span class="ant-menu-title-content">收盘价</span></li><li title="双低" role="menuitem" tabindex="-1" data-menu-id="factor-menu-dblow" class="ant-menu-item"><span class="ant-menu-title-content">双低</span></li><li title="纯债价值" role="menuitem" tabindex="-1" data-menu-id="factor-menu-pure_value" class="ant-menu-item"><span class="ant-menu-title-content">纯债价值</span></li><li title="纯债溢价率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-bond_prem" class="ant-menu-item"><span class="ant-menu-title-content">纯债溢价率</span></li><li title="发行规模(亿)" role="menuitem" tabindex="-1" data-menu-id="factor-menu-issue_size" class="ant-menu-item"><span class="ant-menu-title-content">发行规模(亿)</span></li><li title="剩余规模(亿)" role="menuitem" tabindex="-1" data-menu-id="factor-menu-remain_size" class="ant-menu-item"><span class="ant-menu-title-content">剩余规模(亿)</span></li><li title="剩余市值(亿)" role="menuitem" tabindex="-1" data-menu-id="factor-menu-remain_cap" class="ant-menu-item"><span class="ant-menu-title-content">剩余市值(亿)</span></li><li title="前收盘价" role="menuitem" tabindex="-1" data-menu-id="factor-menu-pre_close" class="ant-menu-item"><span class="ant-menu-title-content">前收盘价</span></li><li title="开盘价" role="menuitem" tabindex="-1" data-menu-id="factor-menu-open" class="ant-menu-item"><span class="ant-menu-title-content">开盘价</span></li><li title="最高价" role="menuitem" tabindex="-1" data-menu-id="factor-menu-high" class="ant-menu-item"><span class="ant-menu-title-content">最高价</span></li><li title="最低价" role="menuitem" tabindex="-1" data-menu-id="factor-menu-low" class="ant-menu-item"><span class="ant-menu-title-content">最低价</span></li><li title="成交额(万)" role="menuitem" tabindex="-1" data-menu-id="factor-menu-amount" class="ant-menu-item"><span class="ant-menu-title-content">成交额(万)</span></li><li title="成交量(手)" role="menuitem" tabindex="-1" data-menu-id="factor-menu-vol" class="ant-menu-item"><span class="ant-menu-title-content">成交量(手)</span></li><li title="转股价格" role="menuitem" tabindex="-1" data-menu-id="factor-menu-conv_price" class="ant-menu-item"><span class="ant-menu-title-content">转股价格</span></li><li title="转股价值" role="menuitem" tabindex="-1" data-menu-id="factor-menu-conv_value" class="ant-menu-item"><span class="ant-menu-title-content">转股价值</span></li><li title="期权价值" role="menuitem" tabindex="-1" data-menu-id="factor-menu-option_value" class="ant-menu-item"><span class="ant-menu-title-content">期权价值</span></li><li title="理论价值" role="menuitem" tabindex="-1" data-menu-id="factor-menu-theory_value" class="ant-menu-item"><span class="ant-menu-title-content">理论价值</span></li><li title="理论偏离度" role="menuitem" tabindex="-1" data-menu-id="factor-menu-theory_bias" class="ant-menu-item"><span class="ant-menu-title-content">理论偏离度</span></li><li title="涨跌幅" role="menuitem" tabindex="-1" data-menu-id="factor-menu-pct_chg" class="ant-menu-item"><span class="ant-menu-title-content">涨跌幅</span></li><li title="换手率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-turnover" class="ant-menu-item"><span class="ant-menu-title-content">换手率</span></li><li title="转债市占比" role="menuitem" tabindex="-1" data-menu-id="factor-menu-cap_mv_rate" class="ant-menu-item"><span class="ant-menu-title-content">转债市占比</span></li><li title="上市天数" role="menuitem" tabindex="-1" data-menu-id="factor-menu-list_days" class="ant-menu-item"><span class="ant-menu-title-content">上市天数</span></li><li title="剩余年限" role="menuitem" tabindex="-1" data-menu-id="factor-menu-left_years" class="ant-menu-item"><span class="ant-menu-title-content">剩余年限</span></li><li title="到期收益率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-ytm" class="ant-menu-item"><span class="ant-menu-title-content">到期收益率</span></li><li title="强赎触发价比率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-redeem_price_rate" class="ant-menu-item"><span class="ant-menu-title-content">强赎触发价比率</span></li><li title="强赎剩余计数" role="menuitem" tabindex="-1" data-menu-id="factor-menu-redeem_remain_days" class="ant-menu-item"><span class="ant-menu-title-content">强赎剩余计数</span></li></ul></li></ul>
# """

# html_content = """
# <ul role="group" class="ant-menu-item-group-list"><li title="5日涨跌幅" role="menuitem" tabindex="-1" data-menu-id="factor-menu-pct_chg_5" class="ant-menu-item"><span class="ant-menu-title-content">5日涨跌幅</span></li><li title="正股5日涨跌幅" role="menuitem" tabindex="-1" data-menu-id="factor-menu-pct_chg_5_stk" class="ant-menu-item"><span class="ant-menu-title-content">正股5日涨跌幅</span></li><li title="5日乖离率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-bias_5" class="ant-menu-item"><span class="ant-menu-title-content">5日乖离率</span></li><li title="5日均价" role="menuitem" tabindex="-1" data-menu-id="factor-menu-close_ma_5" class="ant-menu-item"><span class="ant-menu-title-content">5日均价</span></li><li title="5日超额涨跌幅" role="menuitem" tabindex="-1" data-menu-id="factor-menu-alpha_pct_chg_5" class="ant-menu-item"><span class="ant-menu-title-content">5日超额涨跌幅</span></li><li title="5日成交量" role="menuitem" tabindex="-1" data-menu-id="factor-menu-vol_5" class="ant-menu-item"><span class="ant-menu-title-content">5日成交量</span></li><li title="5日成交额" role="menuitem" tabindex="-1" data-menu-id="factor-menu-amount_5" class="ant-menu-item"><span class="ant-menu-title-content">5日成交额</span></li><li title="5日换手率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-turnover_5" class="ant-menu-item"><span class="ant-menu-title-content">5日换手率</span></li><li title="年化波动率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-volatility" class="ant-menu-item"><span class="ant-menu-title-content">年化波动率</span></li><li title="正股年化波动率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-volatility_stk" class="ant-menu-item"><span class="ant-menu-title-content">正股年化波动率</span></li></ul>
# """

html_content = """
<ul role="group" class="ant-menu-item-group-list"><li title="正股收盘价" role="menuitem" tabindex="-1" data-menu-id="factor-menu-close_stk" class="ant-menu-item"><span class="ant-menu-title-content">正股收盘价</span></li><li title="正股涨跌幅" role="menuitem" tabindex="-1" data-menu-id="factor-menu-pct_chg_stk" class="ant-menu-item"><span class="ant-menu-title-content">正股涨跌幅</span></li><li title="正股成交额(万)" role="menuitem" tabindex="-1" data-menu-id="factor-menu-amount_stk" class="ant-menu-item"><span class="ant-menu-title-content">正股成交额(万)</span></li><li title="正股成交量" role="menuitem" tabindex="-1" data-menu-id="factor-menu-vol_stk" class="ant-menu-item"><span class="ant-menu-title-content">正股成交量</span></li><li title="正股总市值(亿)" role="menuitem" tabindex="-1" data-menu-id="factor-menu-total_mv" class="ant-menu-item"><span class="ant-menu-title-content">正股总市值(亿)</span></li><li title="正股流通市值(亿)" role="menuitem" tabindex="-1" data-menu-id="factor-menu-circ_mv" class="ant-menu-item"><span class="ant-menu-title-content">正股流通市值(亿)</span></li><li title="市净率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-pb" class="ant-menu-item"><span class="ant-menu-title-content">市净率</span></li><li title="市盈率TTM" role="menuitem" tabindex="-1" data-menu-id="factor-menu-pe_ttm" class="ant-menu-item"><span class="ant-menu-title-content">市盈率TTM</span></li><li title="市销率TTM" role="menuitem" tabindex="-1" data-menu-id="factor-menu-ps_ttm" class="ant-menu-item"><span class="ant-menu-title-content">市销率TTM</span></li><li title="资产负债率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-debt_to_assets" class="ant-menu-item"><span class="ant-menu-title-content">资产负债率</span></li><li title="股息率" role="menuitem" tabindex="-1" data-menu-id="factor-menu-dv_ratio" class="ant-menu-item"><span class="ant-menu-title-content">股息率</span></li></ul>
"""

# 使用 BeautifulSoup 解析 HTML 内容
soup = BeautifulSoup(html_content, 'html.parser')

# 定义空字典用于存储映射关系
mapping = {}

# 查找所有符合条件的 li 标签
for li in soup.find_all('li'):
    data_menu_id = li.get('data-menu-id', '')
    # 判断 data-menu-id 是否以 "factor-menu-" 开头
    if data_menu_id.startswith("factor-menu-"):
        # 提取 key，并去掉前缀 "factor-menu-"
        key = data_menu_id.replace("factor-menu-", "")
        # 获取文本内容，strip() 用于去除多余空白字符
        text = li.get_text(strip=True)
        mapping[key] = text

# 输出映射关系
print(mapping)

# 输出键列表
print("\n键列表:")
for key, value in mapping.items():
    print(f"'{key}',")

# 将映射转换成 JSON 格式
json_str = json.dumps(mapping, ensure_ascii=False, indent=4)
print("\nJSON 格式:")
print(json_str)

# # 保存到文件
# output_file = "../factor_mapping.json"
# with open(output_file, 'w', encoding='utf-8') as f:
#     f.write(json_str)
# print(f"\n已保存到文件: {output_file}")