# -*- coding: utf-8 -*-
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

# ============ 1. 配置参数与全局变量 ==============

WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=5f19c101-363f-4c8e-a5c9-db57ba4513af"  # 企业微信机器人Webhook
THRESHOLD = 0.05  # 收益率阈值: 5%
MONITOR_INTERVAL = 60  # 监控间隔: 1分钟 (秒)
DEBUG_MODE = True  # 调试模式: 打印详细日志

# 用于避免短时间内重复提醒
notified_dict = {}  # key: symbol, value: bool

# 模拟模式配置
SIMULATION_MODE = True  # 设置为True启用模拟模式
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
    使用企业微信Webhook发送text类型通知

    :param title: 通知标题
    :param content: 通知正文
    """
    data = {
        "msgtype": "text",
        "text": {
            "content": f"{title}\n{content}"
        }
    }
    
    try:
        # 记录尝试发送通知
        log_message("INFO", f"尝试发送企业微信通知: {title}")
        print(f"[STOCK_MONITOR]尝试发送企业微信通知: {title}")
            
        r = requests.post(WEBHOOK_URL, json=data, timeout=5)
        if r.status_code != 200:
            err_msg = f"发送企业微信失败: code={r.status_code}, response={r.text}"
            log_message("ERROR", err_msg)
            print(f"[STOCK_MONITOR]ERROR: {err_msg}")
        else:
            success_msg = f"已发送通知: {title} - {content}"
            log_message("INFO", success_msg)
            print(f"[STOCK_MONITOR]成功: {success_msg}")
            return True
    except Exception as e:
        err_msg = f"通知异常: {e}\n{traceback.format_exc()}"
        log_message("ERROR", err_msg)
        print(f"[STOCK_MONITOR]ERROR: {err_msg}")
    
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

    print("[STOCK_MONITOR]开始监控持仓...")
    print("[STOCK_MONITOR]模拟模式: " + ("已启用" if SIMULATION_MODE else "未启用"))
    print("[STOCK_MONITOR]阈值设置: " + str(THRESHOLD * 100) + "%")
    
    try:
        # 获取当前账户对象
        account = context.account()
        print("[STOCK_MONITOR]成功获取账户对象")
        
        # 获取持仓信息 - 使用迅投QMT API
        positions = account.positions()  # 直接调用positions()方法获取持仓列表
        
        pos_count = len(positions) if positions else 0
        print(f"[STOCK_MONITOR]成功获取持仓列表，持仓数量: {pos_count}")
        
        # 打印所有持仓的基本信息
        if pos_count > 0:
            print("[STOCK_MONITOR]持仓概览:")
            for i, pos in enumerate(positions):
                try:
                    symbol = getattr(pos, 'm_strInstrumentID', '未知代码')
                    name = getattr(pos, 'm_strInstrumentName', '未知名称')
                    print(f"[STOCK_MONITOR]  {i+1}. {symbol} {name}")
                except:
                    print(f"[STOCK_MONITOR]  {i+1}. 无法获取持仓信息")
        
        if not positions:
            log_message("INFO", "当前没有持仓或持仓数据为空。")
            print("[STOCK_MONITOR]当前没有持仓或持仓数据为空")
            print("[STOCK_MONITOR]监控持仓结束")
            return
        
        # 遍历每只持仓
        for pos in positions:
            # 获取持仓信息，根据QMT API文档中position对象的属性
            symbol = pos.m_strInstrumentID  # 证券代码
            name = pos.m_strInstrumentName  # 证券名称
            volume = pos.m_nVolume  # 持仓数量
            cost_price = pos.m_dOpenPrice  # 成本价
            last_price = pos.m_dLastPrice  # 当前价
            
            print(f"[STOCK_MONITOR]分析持仓: {symbol} {name}, 成本价: {cost_price}, 现价: {last_price}")
            
            # 检查是否为可转债
            is_convertible_bond = getattr(pos, 'is_convertible_bond', 
                                        symbol.startswith('11') or symbol.startswith('12'))
            
            if cost_price <= 0:
                print(f"[STOCK_MONITOR]跳过 {symbol} {name}，成本价无效: {cost_price}")
                continue
            
            # 计算收益率 / 涨跌幅
            profit_rate = (last_price - cost_price) / cost_price
            print(f"[STOCK_MONITOR]{symbol} {name} 收益率: {(profit_rate*100):.2f}%，阈值: {(THRESHOLD*100):.2f}%")
            
            # 明确输出判断结果
            if profit_rate >= THRESHOLD:
                print(f"[STOCK_MONITOR]>>> {symbol} {name} 收益率 {(profit_rate*100):.2f}% 超过阈值 {(THRESHOLD*100):.2f}% <<<")
            else:
                print(f"[STOCK_MONITOR]{symbol} {name} 收益率未达到阈值")
            
            # 判断是否超过阈值
            if profit_rate >= THRESHOLD and not notified_dict.get(symbol, False):
                # 发送企业微信通知
                security_type = "可转债" if is_convertible_bond else "股票"
                title = f"[提醒] {symbol} {name}({security_type})收益率达 {(profit_rate*100):.2f}%"
                content = f"当前价: {last_price:.2f}, 成本价: {cost_price:.2f}, 持仓: {volume}"
                
                print(f"[STOCK_MONITOR]准备发送通知: {title}")
                
                if SIMULATION_MODE:
                    log_message("INFO", f"\n{'-'*50}\n{title}\n{content}\n{'-'*50}")
                    print(f"[STOCK_MONITOR]模拟模式下发送真实通知")
                    send_wecom_notification(title, content)
                else:
                    send_wecom_notification(title, content)
                
                # 标记已提醒
                notified_dict[symbol] = True
                print(f"[STOCK_MONITOR]已将 {symbol} 标记为已通知")
            
            # 如果收益率又低于阈值，则重置(若需在再次突破时继续提醒)
            elif profit_rate < THRESHOLD and notified_dict.get(symbol, False):
                notified_dict[symbol] = False
                log_message("INFO", f"{symbol} {name} 收益率回落至 {(profit_rate*100):.2f}%，低于阈值 {(THRESHOLD*100):.2f}%")
                print(f"[STOCK_MONITOR]重置通知状态: {symbol} {name} 收益率回落至 {(profit_rate*100):.2f}%，低于阈值 {(THRESHOLD*100):.2f}%")
            
            # 如果收益率超过阈值但已经通知过，提示已通知
            elif profit_rate >= THRESHOLD and notified_dict.get(symbol, False):
                print(f"[STOCK_MONITOR]{symbol} {name} 收益率 {(profit_rate*100):.2f}% 超过阈值，但已经通知过，不再重复通知")
    
    except Exception as ex:
        err_msg = f"监控持仓异常: {ex}\n{traceback.format_exc()}"
        log_message("ERROR", err_msg)
        print(f"[STOCK_MONITOR]监控持仓异常: {ex}")
    
    print("[STOCK_MONITOR]监控持仓结束")

# ============ 7. 启动及调度 ==============

def on_start(context):
    """
    迅投(ThinkTrader) 常见的启动函数之一，脚本启动时自动执行。
    在此处注册定时任务，每 1 分钟执行一次 monitor_positions。
    """
    log_message("INFO", f"【脚本启动】开始注册 {MONITOR_INTERVAL//60} 分钟调度任务...")
    print(f"[STOCK_MONITOR]【脚本启动】开始注册 {MONITOR_INTERVAL//60} 分钟调度任务...")

    # 国金证券QMT可能不使用log_message，添加直接输出
    print("[STOCK_MONITOR]尝试注册定时任务...")
    
    success = False
    
    try:
        # 使用迅投QMT的schedule方法注册定时任务
        context.schedule(schedule_name="monitor_positions_task", 
                        schedule_func=monitor_positions, 
                        interval=MONITOR_INTERVAL)  # 1分钟 = 60秒
        
        log_message("INFO", f"【脚本启动】成功注册 {MONITOR_INTERVAL//60} 分钟调度任务")
        print(f"[STOCK_MONITOR]成功使用schedule方法注册任务")
        success = True
    except AttributeError:
        print("[STOCK_MONITOR]schedule方法不可用，尝试其他方法...")
        # 如果没有 schedule 方法，尝试其他方式
        try:
            # 尝试使用run_time方法
            context.run_time(monitor_positions, MONITOR_INTERVAL)
            log_message("INFO", f"【脚本启动】使用run_time方法注册 {MONITOR_INTERVAL//60} 分钟调度任务")
            print(f"[STOCK_MONITOR]成功使用run_time方法注册任务")
            success = True
        except AttributeError:
            print("[STOCK_MONITOR]run_time方法不可用，尝试其他方法...")
            try:
                # 尝试国金证券QMT可能的方法
                context.run_daily(monitor_positions, MONITOR_INTERVAL)
                print(f"[STOCK_MONITOR]成功使用run_daily方法注册任务")
                success = True
            except AttributeError:
                try:
                    # 尝试国金证券QMT可能的方法
                    context.set_timer(monitor_positions, MONITOR_INTERVAL)
                    print(f"[STOCK_MONITOR]成功使用set_timer方法注册任务")
                    success = True
                except AttributeError:
                    log_message("WARNING", "检测到 context.schedule()、context.run_time()等方法不可用，请改用其他方式调度。")
                    print("[STOCK_MONITOR]所有尝试的定时方法都不可用，请手动调用函数")
    
    if not success:
        print("[STOCK_MONITOR]无法注册定时任务，将仅执行一次监控")
    
    # 脚本启动时立即执行一次监控
    print("[STOCK_MONITOR]立即执行一次监控...")
    monitor_positions(context)
    print("[STOCK_MONITOR]首次监控执行完毕")

# 如果文档或平台要求使用 `start_now()` 而不是 `on_start(context)`，可改为：
def start_now(context):
    """
    迅投(ThinkTrader) 的另一种启动函数，某些版本可能使用此函数作为入口。
    """
    on_start(context)

# 添加国金证券QMT平台常用的入口函数
def initialize(context):
    """
    国金证券QMT平台可能使用的入口函数
    """
    global SIMULATION_MODE
    
    print("[STOCK_MONITOR]开始运行")
    print("[STOCK_MONITOR]检测环境...")
    
    # 尝试获取持仓，判断是否需要切换到模拟模式
    try:
        account = context.account()
        positions = account.positions()
        if positions and len(positions) > 0:
            SIMULATION_MODE = False
            print(f"[STOCK_MONITOR]检测到真实持仓 {len(positions)} 个，使用真实模式")
        else:
            SIMULATION_MODE = True
            print("[STOCK_MONITOR]未检测到真实持仓，切换到模拟模式")
    except Exception as e:
        SIMULATION_MODE = True
        print(f"[STOCK_MONITOR]获取持仓出错: {e}，切换到模拟模式")
    
    # 测试企业微信通知功能
    print("[STOCK_MONITOR]测试企业微信通知功能...")
    test_send_notification()
    
    print("[STOCK_MONITOR]启动持仓监控...")
    
    if SIMULATION_MODE:
        print("[STOCK_MONITOR]使用模拟持仓进行测试")
        # 替换context为模拟context
        sim_context = SimulationContext()
        # 若原context有需要的方法，尝试保留
        for attr_name in ['schedule', 'run_time', 'run_daily', 'set_timer']:
            if hasattr(context, attr_name) and callable(getattr(context, attr_name)):
                setattr(sim_context, attr_name, getattr(context, attr_name))
        
        # 使用模拟context替代真实context
        context = sim_context
    
    # 先执行一次监控
    monitor_positions(context)
    
    # 然后尝试注册定时任务
    on_start(context)
    
    print("[STOCK_MONITOR]持仓监控任务已启动，将定期检查持仓")

def init(context):
    """
    国金证券QMT平台可能使用的另一个入口函数
    """
    # 使用initialize函数的实现
    initialize(context)

def main(context=None):
    """
    国金证券QMT平台可能直接调用的主函数
    """
    print("[STOCK_MONITOR]main函数被调用")
    
    if context is None:
        print("[STOCK_MONITOR]未提供context，创建模拟context")
        context = SimulationContext()
        SIMULATION_MODE = True
    else:
        # 尝试检测是否为QMT环境
        try:
            # 检查context是否有QMT特定方法
            is_qmt = hasattr(context, 'account') and callable(getattr(context, 'account'))
            if is_qmt:
                print("[STOCK_MONITOR]检测到QMT环境")
                # 委托给initialize处理
                initialize(context)
                return
            else:
                print("[STOCK_MONITOR]非QMT环境，使用模拟模式")
                context = SimulationContext()
                SIMULATION_MODE = True
        except:
            print("[STOCK_MONITOR]环境检测出错，使用模拟模式")
            context = SimulationContext()
            SIMULATION_MODE = True
    
    # 测试通知功能
    print("[STOCK_MONITOR]测试企业微信通知功能...")
    test_send_notification()
    
    # 启动持仓监控
    print("[STOCK_MONITOR]启动持仓监控...")
    monitor_positions(context)
    
    # 注册定时任务
    on_start(context)
    
    print("[STOCK_MONITOR]持仓监控任务已启动")

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
    测试企业微信通知功能
    """
    print("开始测试企业微信通知功能...")
    
    # 测试发送通知
    print("\n测试: 发送企业微信通知")
    result = send_wecom_notification("测试标题", "这是一条测试内容")
    
    if result:
        print("通知发送成功！")
    else:
        print("通知发送失败！")
    
    print("\n企业微信通知测试完成")
    print("[STOCK_MONITOR]结束运行")
    print("[STOCK_MONITOR]注意：现在应该运行自动执行部分...")

def test_notification_trigger():
    """
    手动触发通知测试，模拟一个收益率超过阈值的持仓
    """
    print("[STOCK_MONITOR]开始测试通知触发...")
    
    # 创建模拟上下文和持仓
    context = SimulationContext()
    
    # 修改一个持仓，使其收益率超过阈值
    positions = context.account()._positions
    if positions:
        # 选第一个持仓修改价格
        pos = positions[0]
        original_price = pos.m_dLastPrice
        
        # 设置价格使其超过阈值
        pos.m_dLastPrice = pos.m_dOpenPrice * (1 + THRESHOLD + 0.02)
        
        print(f"[STOCK_MONITOR]已修改持仓 {pos.m_strInstrumentID} {pos.m_strInstrumentName} 价格:")
        print(f"[STOCK_MONITOR]原价: {original_price:.2f}, 新价: {pos.m_dLastPrice:.2f}, 成本价: {pos.m_dOpenPrice:.2f}")
        print(f"[STOCK_MONITOR]新收益率: {((pos.m_dLastPrice/pos.m_dOpenPrice)-1)*100:.2f}%, 阈值: {THRESHOLD*100:.2f}%")
        
        # 执行监控
        monitor_positions(context)
        
        # 恢复原价
        pos.m_dLastPrice = original_price
    else:
        print("[STOCK_MONITOR]没有模拟持仓可供测试")
    
    print("[STOCK_MONITOR]通知触发测试完成")

# 如果直接运行此脚本，则启动模拟模式
if __name__ == "__main__":
    # 直接测试通知功能
    print("[STOCK_MONITOR]直接测试企业微信通知功能...")
    test_send_notification()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "quick":
            run_quick_test()
        elif sys.argv[1] == "test_notification":
            test_send_notification()
    else:
        run_simulation()

# 添加自动执行的代码，确保在QMT平台上自动运行，不依赖入口函数
print("[STOCK_MONITOR]====== 脚本自动执行部分 ======")
print("[STOCK_MONITOR]当前时间：" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# 标记自动执行状态，避免重复执行
AUTO_RUNNING = False

try:
    # 检查是否已经在运行，避免重复执行
    if 'AUTO_RUNNING' in globals() and AUTO_RUNNING:
        print("[STOCK_MONITOR]脚本已经在运行中，避免重复执行")
    else:
        # 设置运行标记
        AUTO_RUNNING = True
        
        # 创建模拟上下文
        auto_context = SimulationContext()
        print("[STOCK_MONITOR]已创建模拟上下文")
        
        # 打印模拟持仓
        print("[STOCK_MONITOR]模拟持仓列表：")
        positions = auto_context.account().positions()
        for i, pos in enumerate(positions):
            print(f"[STOCK_MONITOR]  {i+1}. {pos.m_strInstrumentID} {pos.m_strInstrumentName}")
        
        print(f"[STOCK_MONITOR]开始循环监控，间隔: {MONITOR_INTERVAL}秒")
        print(f"[STOCK_MONITOR]按Ctrl+C或关闭控制台可停止监控")
        print(f"[STOCK_MONITOR]脚本使用说明:")
        print(f"[STOCK_MONITOR]1. 当前模式是自动每{MONITOR_INTERVAL}秒监控一次持仓")
        print(f"[STOCK_MONITOR]2. 如果需要手动测试通知功能，可以在QMT控制台执行:")
        print(f"[STOCK_MONITOR]   import stock_monitor")
        print(f"[STOCK_MONITOR]   stock_monitor.test_notification_trigger()")
        print(f"[STOCK_MONITOR]3. 这将模拟一个持仓收益率超过{THRESHOLD*100:.2f}%的情况，并触发通知")
        
        # 循环执行监控，模拟定时任务
        counter = 1
        while True:
            print(f"[STOCK_MONITOR]======= 第{counter}次监控 =======")
            print("[STOCK_MONITOR]当前时间：" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            # 执行持仓监控
            monitor_positions(auto_context)
            
            counter += 1
            
            # 更新模拟持仓价格，使其有所变动
            for pos in auto_context.account()._positions:
                # 随机价格波动
                pos.m_dLastPrice = pos.m_dLastPrice * (1 + random.uniform(-0.01, 0.03))
                # 每几次监控就让一个持仓超过阈值，便于测试通知功能
                if counter % 3 == 0 and random.random() > 0.5:
                    pos.m_dLastPrice = pos.m_dOpenPrice * (1 + THRESHOLD + 0.01)
                
            print(f"[STOCK_MONITOR]等待{MONITOR_INTERVAL}秒后执行下一次监控...")
            time.sleep(MONITOR_INTERVAL)

except KeyboardInterrupt:
    print("[STOCK_MONITOR]监控被用户中断")
except Exception as e:
    print(f"[STOCK_MONITOR]自动执行出错: {e}")
    import traceback
    print(traceback.format_exc())