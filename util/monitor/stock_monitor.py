# -*- coding: gbk -*-
"""
【迅投（ThinkTrader）内置 Python 脚本示例】
功能：每 1 分钟监控持仓，若持仓单只证券收益率 > 5%，则通过企业微信机器人推送提醒
支持模拟模式：可在没有实际交易环境的情况下测试脚本功能
"""

import requests
import traceback
import time
import random
import datetime
import sys
import json

# ============ 1. 配置参数与全局变量 ==============

WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=5f19c101-363f-4c8e-a5c9-db57ba4513af"  # 企业微信机器人Webhook
THRESHOLD = 0.05  # 收益率阈值: 5%
MONITOR_INTERVAL = 10  # 监控间隔: 1分钟 (秒)
DEBUG_MODE = True  # 调试模式: 打印详细日志

# 用于避免短时间内重复提醒
notified_dict = {}  # key: symbol, value: bool

# 模拟模式配置
SIMULATION_MODE = False  # 设置为True启用模拟模式
SIM_POSITIONS = [
    # 股票持仓 - 成本价设置较低，使其更容易触发收益率阈值
    {"code": "600519", "name": "贵州茅台", "cost": 1700.0, "volume": 100},  # 成本价设低一些
    {"code": "000858", "name": "五粮液", "cost": 130.0, "volume": 200},      # 成本价设低一些
    # 可转债持仓 - 成本价设置较低，使其更容易触发收益率阈值
    {"code": "113009", "name": "广汽转债", "cost": 95.0, "volume": 10, "is_cb": True},  # 成本价设低一些
    {"code": "123111", "name": "东财转3", "cost": 90.0, "volume": 10, "is_cb": True},   # 成本价设低一些
]

# ============ 2. 企业微信发送函数 ==============

def log_message(level, message):
    """
    统一的日志记录函数
    
    :param level: 日志级别 (INFO, ERROR, WARNING)
    :param message: 日志消息
    """
    if DEBUG_MODE or level != "DEBUG":
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

def send_wecom_notification(title, content):
    """
    发送企业微信通知
    """
    try:
        # 检查WEBHOOK_URL是否配置
        if not WEBHOOK_URL or WEBHOOK_URL == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY_HERE":
            log_message("ERROR", "企业微信Webhook URL未正确配置，请设置正确的WEBHOOK_URL")
            return False
            
        # 构建请求数据
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {title}\n{content}\n\n> 发送时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
        
        # 记录发送前的日志
        log_message("INFO", f"正在发送企业微信通知: {title}")
        
        # 发送请求
        headers = {'Content-Type': 'application/json'}
        response = requests.post(WEBHOOK_URL, headers=headers, data=json.dumps(data), timeout=5)
        
        # 检查响应
        response_json = response.json()
        if response.status_code == 200 and response_json.get('errcode') == 0:
            log_message("INFO", f"企业微信通知发送成功: {title}")
            return True
        else:
            log_message("ERROR", f"企业微信通知发送失败: 状态码={response.status_code}, 错误信息={response_json}")
            return False
            
    except requests.RequestException as e:
        log_message("ERROR", f"企业微信通知网络请求异常: {str(e)}")
        return False
    except Exception as e:
        log_message("ERROR", f"企业微信通知发送异常: {str(e)}\n{traceback.format_exc()}")
        return False

# ============ 3. 模拟持仓类 ==============

class SimulationPosition:
    """模拟持仓类，用于模拟模式"""
    def __init__(self, code, name, cost, volume, is_cb=False):
        self.m_strInstrumentID = code
        self.m_strInstrumentName = name
        self.m_nVolume = volume
        self.m_dOpenPrice = cost
        self.m_dLastPrice = cost  # 初始价格等于成本价
        self.is_convertible_bond = is_cb
        
        # 随机生成一个波动范围，模拟不同股票的波动特性
        self.volatility = random.uniform(0.005, 0.02)  # 0.5%-2%的波动
        self.trend = random.choice([-1, 1, 1])  # 有更大概率上涨
        self.last_update = time.time()
    
    def update_price(self):
        """更新模拟价格"""
        now = time.time()
        # 计算自上次更新以来的时间（秒）
        elapsed = now - self.last_update
        
        # 根据时间流逝更新价格，模拟市场波动
        if elapsed > 0:
            # 生成随机波动
            change_pct = random.normalvariate(0.0001 * self.trend, self.volatility) * min(elapsed, 300) / 60
            
            # 应用价格变化
            self.m_dLastPrice *= (1 + change_pct)
            
            # 确保价格不会过低或过高（相对于成本）
            if self.is_convertible_bond:
                # 可转债价格通常在80-150之间波动
                self.m_dLastPrice = max(min(self.m_dLastPrice, self.m_dOpenPrice * 1.5), self.m_dOpenPrice * 0.8)
            else:
                # 股票价格波动范围更大
                self.m_dLastPrice = max(min(self.m_dLastPrice, self.m_dOpenPrice * 2.0), self.m_dOpenPrice * 0.7)
                
            self.last_update = now
        
        return self.m_dLastPrice

# ============ 4. 模拟账户类 ==============

class SimulationAccount:
    """模拟账户类，用于模拟模式"""
    def __init__(self, positions_data):
        self._positions = []
        
        # 初始化模拟持仓
        for pos_data in positions_data:
            pos = SimulationPosition(
                pos_data["code"], 
                pos_data["name"], 
                pos_data["cost"], 
                pos_data["volume"],
                pos_data.get("is_cb", False)
            )
            self._positions.append(pos)
    
    def positions(self):
        """返回持仓列表，模拟QMT API的positions方法"""
        # 更新所有持仓的价格
        for pos in self._positions:
            pos.update_price()
        
        return self._positions

# ============ 5. 模拟上下文类 ==============

class SimulationContext:
    """模拟上下文类，用于模拟模式"""
    def __init__(self):
        self._account = SimulationAccount(SIM_POSITIONS)
        self._scheduled_tasks = {}
    
    def account(self):
        """返回账户对象，模拟QMT API的account方法"""
        return self._account
    
    def schedule(self, schedule_name, schedule_func, interval):
        """模拟调度方法"""
        self._scheduled_tasks[schedule_name] = {
            "func": schedule_func,
            "interval": interval,
            "last_run": 0
        }
        log_message("INFO", f"已注册定时任务: {schedule_name}, 间隔: {interval}秒")
        return True
    
    def run_scheduled_tasks(self):
        """运行所有到期的定时任务"""
        now = time.time()
        for name, task in self._scheduled_tasks.items():
            if now - task["last_run"] >= task["interval"]:
                log_message("INFO", f"执行定时任务: {name}")
                task["func"](self)
                task["last_run"] = now

# ============ 6. 持仓监控函数 ==============

def monitor_positions(context):
    """
    1. 获取当前持仓
    2. 判断是否超过阈值
    3. 推送企业微信
    """
    global notified_dict

    try:
        # 获取当前账户对象
        account = context.account()
        
        # 获取持仓信息 - 使用迅投QMT API
        positions = account.positions()  # 直接调用positions()方法获取持仓列表
        
        if not positions:
            log_message("INFO", "当前没有持仓或持仓数据为空。")
            return
        
        # 遍历每只持仓
        for pos in positions:
            # 获取持仓信息，根据QMT API文档中position对象的属性
            symbol = pos.m_strInstrumentID  # 证券代码
            name = pos.m_strInstrumentName  # 证券名称
            volume = pos.m_nVolume  # 持仓数量
            cost_price = pos.m_dOpenPrice  # 成本价
            last_price = pos.m_dLastPrice  # 当前价
            
            # 检查是否为可转债
            is_convertible_bond = getattr(pos, 'is_convertible_bond', 
                                        symbol.startswith('11') or symbol.startswith('12'))
            
            if cost_price <= 0:
                continue
            
            # 计算收益率 / 涨跌幅
            profit_rate = (last_price - cost_price) / cost_price
            
            # 判断是否超过阈值
            if profit_rate >= THRESHOLD and not notified_dict.get(symbol, False):
                # 发送企业微信通知
                security_type = "可转债" if is_convertible_bond else "股票"
                title = f"[提醒] {symbol} {name}({security_type})收益率达 {(profit_rate*100):.2f}%"
                content = f"当前价: {last_price:.2f}, 成本价: {cost_price:.2f}, 持仓: {volume}"
                
                if SIMULATION_MODE:
                    log_message("INFO", f"\n{'-'*50}\n{title}\n{content}\n{'-'*50}")
                    send_wecom_notification(title, content)
                else:
                    log_message("INFO", f"\n{'-'*50}\n{title}\n{content}\n{'-'*50}")
                    send_wecom_notification(title, content)
                
                # 标记已提醒
                notified_dict[symbol] = True
            
            # 如果收益率又低于阈值，则重置(若需在再次突破时继续提醒)
            elif profit_rate < THRESHOLD and notified_dict.get(symbol, False):
                notified_dict[symbol] = False
                log_message("INFO", f"{symbol} {name} 收益率回落至 {(profit_rate*100):.2f}%，低于阈值 {(THRESHOLD*100):.2f}%")

    except Exception as ex:
        err_msg = f"监控持仓异常: {ex}\n{traceback.format_exc()}"
        log_message("ERROR", err_msg)

# ============ 7. 启动及调度 ==============

def on_start(context):
    """
    迅投(ThinkTrader) 常见的启动函数之一，脚本启动时自动执行。
    在此处注册定时任务，每 1 分钟执行一次 monitor_positions。
    """
    log_message("INFO", f"【脚本启动】开始注册 {MONITOR_INTERVAL//60} 分钟调度任务...")

    try:
        # 使用迅投QMT的schedule方法注册定时任务
        context.schedule(schedule_name="monitor_positions_task", 
                        schedule_func=monitor_positions, 
                        interval=MONITOR_INTERVAL)  # 1分钟 = 60秒
        
        log_message("INFO", f"【脚本启动】成功注册 {MONITOR_INTERVAL//60} 分钟调度任务")
    except AttributeError:
        # 如果没有 schedule 方法，尝试其他方式
        try:
            # 尝试使用run_time方法
            context.run_time(monitor_positions, MONITOR_INTERVAL)
            log_message("INFO", f"【脚本启动】使用run_time方法注册 {MONITOR_INTERVAL//60} 分钟调度任务")
        except AttributeError:
            log_message("WARNING", "检测到 context.schedule() 和 context.run_time() 方法不可用，请改用其他方式调度。")
    
    # 脚本启动时立即执行一次监控
    monitor_positions(context)

# 如果文档或平台要求使用 `start_now()` 而不是 `on_start(context)`，可改为：
def start_now(context):
    """
    迅投(ThinkTrader) 的另一种启动函数，某些版本可能使用此函数作为入口。
    """
    on_start(context)

# ============ 8. 模拟模式运行函数 ==============

def run_simulation():
    """
    在模拟模式下运行脚本
    """
    global SIMULATION_MODE
    SIMULATION_MODE = True
    
    print(f"{'='*20} 模拟模式启动 {'='*20}")
    print(f"当前时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"收益率阈值: {THRESHOLD*100}%")
    print(f"监控间隔: {MONITOR_INTERVAL}秒")
    print(f"模拟持仓数量: {len(SIM_POSITIONS)}")
    print(f"{'='*50}\n")
    
    # 创建模拟上下文
    context = SimulationContext()
    
    # 启动脚本
    on_start(context)
    
    # 模拟运行，每秒检查一次是否有定时任务需要执行
    try:
        print("模拟运行中，按Ctrl+C终止...")
        while True:
            context.run_scheduled_tasks()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n模拟运行已终止")

# 快速测试模式 - 加速价格波动以快速触发通知
def run_quick_test():
    """
    快速测试模式 - 加速价格波动以快速触发通知
    """
    global SIMULATION_MODE, SIM_POSITIONS
    SIMULATION_MODE = True
    
    # 修改模拟持仓，使其更容易触发通知
    SIM_POSITIONS = [
        # 股票持仓 - 成本价设置更低，使其立即触发收益率阈值
        {"code": "600519", "name": "贵州茅台", "cost": 1600.0, "volume": 100},  # 成本价设更低
        {"code": "000858", "name": "五粮液", "cost": 120.0, "volume": 200},      # 成本价设更低
        # 可转债持仓 - 成本价设置更低，使其立即触发收益率阈值
        {"code": "113009", "name": "广汽转债", "cost": 90.0, "volume": 10, "is_cb": True},  # 成本价设更低
        {"code": "123111", "name": "东财转3", "cost": 85.0, "volume": 10, "is_cb": True},   # 成本价设更低
    ]
    
    print(f"{'='*20} 快速测试模式启动 {'='*20}")
    print(f"当前时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"收益率阈值: {THRESHOLD*100}%")
    print(f"监控间隔: {MONITOR_INTERVAL}秒")
    print(f"模拟持仓数量: {len(SIM_POSITIONS)}")
    print(f"{'='*50}\n")
    
    # 创建模拟上下文
    context = SimulationContext()
    
    # 增加价格波动速度和上涨趋势
    for pos in context.account()._positions:
        pos.volatility = 0.05  # 设置更大的波动率，5%
        pos.trend = 2  # 强制更强的上涨趋势
        # 直接设置初始价格高于成本价的5%以上，确保立即触发通知
        pos.m_dLastPrice = pos.m_dOpenPrice * (1 + THRESHOLD + 0.01)
    
    # 启动脚本
    on_start(context)
    
    # 模拟运行，每秒检查一次是否有定时任务需要执行
    try:
        print("快速测试模式运行中，按Ctrl+C终止...")
        while True:
            context.run_scheduled_tasks()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n快速测试已终止")

# ============ 9. 测试函数 ==============

def test_send_notification():
    """
    测试企业微信通知发送
    """
    title = "测试通知"
    content = f"这是一条测试通知，发送时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    print(f"正在发送测试通知...")
    print(f"WEBHOOK_URL: {WEBHOOK_URL}")
    
    # 尝试发送通知
    result = send_wecom_notification(title, content)
    
    if result:
        print("测试通知发送成功！")
    else:
        print("测试通知发送失败，请检查日志和配置。")

# 如果直接运行此脚本，则启动模拟模式
if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "quick":
            run_quick_test()
        elif sys.argv[1] == "test_notification":
            test_send_notification()
    else:
        run_simulation()