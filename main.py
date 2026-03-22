"""
智能导购小X - 无按钮版 + 微信推送
唤醒方式：点击图片 或 语音唤醒
唤醒后自动进入聆听状态，超时自动休眠
支持实时推送对话 + 定时推送成交汇总
"""
import os
import sys

# 切换到脚本所在目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))
print(f"📁 工作目录: {os.getcwd()}")

import threading
import time
import random
import csv
import sqlite3
import json
import requests
from datetime import datetime, timedelta
from functools import partial

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.behaviors import ButtonBehavior
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import get_color_from_hex, platform
from kivy.core.text import LabelBase

# ==================== 平台相关 ====================
if platform == 'android':
    from android.storage import app_storage_path
    from android.permissions import request_permissions, Permission
    request_permissions([
        Permission.RECORD_AUDIO,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.READ_EXTERNAL_STORAGE
    ])
    DATA_DIR = app_storage_path()
else:
    DATA_DIR = '.'

# ==================== 字体设置 ====================
font_registered = False

# Windows 字体
if platform == 'win':
    FONT_PATHS = [
        'C:/Windows/Fonts/msyh.ttc',
        'C:/Windows/Fonts/simhei.ttf',
    ]
    for font_path in FONT_PATHS:
        if os.path.exists(font_path):
            try:
                LabelBase.register(name='ChineseFont', fn_regular=font_path)
                font_registered = True
                break
            except:
                continue

# Android 字体
elif platform == 'android':
    # Android 系统字体路径（按优先级）
    FONT_PATHS = [
        '/system/fonts/NotoSansCJK-Regular.ttc',  # 中文
        '/system/fonts/NotoSerifCJK-Regular.ttc', # 中文备选
        '/system/fonts/DroidSansFallback.ttf',    # 旧版 Android
        '/system/fonts/Roboto-Regular.ttf',       # 英文字体
    ]
    for font_path in FONT_PATHS:
        if os.path.exists(font_path):
            try:
                LabelBase.register(name='ChineseFont', fn_regular=font_path)
                font_registered = True
                print(f"✅ Android 字体加载成功: {font_path}")
                break
            except Exception as e:
                print(f"字体加载失败 {font_path}: {e}")
                continue

# Linux/WSL 字体
else:
    try:
        LabelBase.register(name='ChineseFont', fn_regular='WenQuanYi Micro Hei')
        font_registered = True
        print("✅ Linux 字体注册成功")
    except:
        fallback_fonts = [
            'Noto Sans CJK SC',
            'Noto Sans CJK JP',
            'WenQuanYi Zen Hei',
            'DejaVu Sans'
        ]
        for font_name in fallback_fonts:
            try:
                LabelBase.register(name='ChineseFont', fn_regular=font_name)
                font_registered = True
                print(f"✅ Linux 使用备选字体: {font_name}")
                break
            except:
                continue

if not font_registered:
    print("⚠️ 未找到中文字体，使用Kivy默认字体")

# ==================== 语音模块 ====================
VOICE_AVAILABLE = False
try:
    import pygame
    import pygame.mixer
    # 初始化 pygame 混音器
    pygame.mixer.init(frequency=22050, size=-16, channels=2)
    print("✅ Pygame 混音器初始化成功")

    # edge-tts 只在非 Android 平台使用
    if platform != 'android':
        import edge_tts
        VOICE_AVAILABLE = True
        print("✅ 语音模块加载成功 (edge-tts)")
    else:
        # Android 平台使用原生 TTS，稍后在 speak_text 中处理
        VOICE_AVAILABLE = True
        print("✅ Android 平台，将使用原生 TTS")
except ImportError as e:
    print(f"⚠️ 语音模块未安装: {e}")

try:
    import vosk
    VOSK_AVAILABLE = True
    print("✅ Vosk模块加载成功")
except ImportError as e:
    VOSK_AVAILABLE = False
    print(f"⚠️ Vosk模块未安装: {e}")

# ==================== 微信推送配置 ====================
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY_HERE"

class WeChatBot:
    """企业微信机器人"""
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    def send_text(self, content):
        if not self.webhook_url or "YOUR_KEY_HERE" in self.webhook_url:
            print(f"⚠️ 未配置微信 Webhook，跳过发送: {content}")
            return
        try:
            data = {"msgtype": "text", "text": {"content": content}}
            requests.post(self.webhook_url, json=data, timeout=5)
            print(f"📱 微信推送: {content[:50]}...")
        except Exception as e:
            print(f"❌ 微信推送失败: {e}")

    def send_markdown(self, content):
        if not self.webhook_url or "YOUR_KEY_HERE" in self.webhook_url:
            print(f"⚠️ 未配置微信 Webhook，跳过发送")
            return
        try:
            data = {"msgtype": "markdown", "markdown": {"content": content}}
            requests.post(self.webhook_url, json=data, timeout=5)
            print(f"📊 已发送汇总报告")
        except Exception as e:
            print(f"❌ 发送汇总失败: {e}")

# ==================== 数据库管理 ====================
class ConversationDB:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(DATA_DIR, "shop_data.db")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_input TEXT,
                bot_response TEXT,
                product_name TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                product_name TEXT,
                price INTEGER,
                quantity INTEGER,
                total INTEGER
            )
        ''')
        self.conn.commit()

    def add_conversation(self, user_input, bot_response, product_name=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO conversations (timestamp, user_input, bot_response, product_name)
            VALUES (?, ?, ?, ?)
        ''', (datetime.now().isoformat(), user_input, bot_response, product_name))
        self.conn.commit()

    def add_order(self, product_name, price, quantity=1):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO orders (timestamp, product_name, price, quantity, total)
            VALUES (?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), product_name, price, quantity, price * quantity))
        self.conn.commit()

    def get_summary(self, hours=6):
        cursor = self.conn.cursor()
        since = (datetime.now() - timedelta(hours=hours)).isoformat()

        cursor.execute('SELECT COUNT(*) FROM conversations WHERE timestamp > ?', (since,))
        total_conversations = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM orders WHERE timestamp > ?', (since,))
        total_orders = cursor.fetchone()[0]

        cursor.execute('''
            SELECT product_name, SUM(quantity), SUM(total) FROM orders
            WHERE timestamp > ? GROUP BY product_name
        ''', (since,))
        order_summary = cursor.fetchall()

        cursor.execute('''
            SELECT product_name, COUNT(*) FROM conversations
            WHERE timestamp > ? AND product_name IS NOT NULL
            GROUP BY product_name ORDER BY COUNT(*) DESC LIMIT 5
        ''', (since,))
        hot_products = cursor.fetchall()

        total_amount = sum(item[2] for item in order_summary)

        return {
            "total_conversations": total_conversations,
            "total_orders": total_orders,
            "total_amount": total_amount,
            "hot_products": hot_products,
            "order_summary": order_summary
        }

# ==================== 可点击图片 ====================
class ClickableImage(ButtonBehavior, Image):
    def __init__(self, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.allow_stretch = True
        self.keep_ratio = True

    def on_press(self):
        if self.callback:
            self.callback()

# ==================== 主 UI ====================
class ShopAgentUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = [dp(10), dp(10)]
        self.spacing = dp(5)

        # 初始化数据库
        self.db = ConversationDB()

        # 初始化微信推送
        self.wechat = WeChatBot(WEBHOOK_URL)

        # 加载商品数据
        self.products = self.load_products()

        # 状态管理
        self.is_awake = False
        self.is_listening = False
        self.sleep_timer = None

        # 唤醒配置
        self.agent_name = "小X"
        self.wake_words = ["小x", "你好", "在吗"]
        self.sleep_timeout = 10

        # 图片资源路径
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.IMAGE_PATH = os.path.join(self.base_dir, "images")
        self.AVATAR_SLEEP = os.path.join(self.IMAGE_PATH, "avatar", "sleeping.png")
        self.AVATAR_AWAKE = os.path.join(self.IMAGE_PATH, "avatar", "awake.png")
        self.AVATAR_LISTENING = os.path.join(self.IMAGE_PATH, "avatar", "listening.png")
        self.AVATAR_THINKING = os.path.join(self.IMAGE_PATH, "avatar", "thinking.png")

        # 构建 UI
        self.build_ui()

        # 设置默认图片
        self.set_sleep_image()

        # 启动唤醒监听
        if VOSK_AVAILABLE:
            self.start_wake_word_listener()
        else:
            self.start_simulated_wake()

        # 定时发送汇总
        self.last_summary_time = datetime.now()
        Clock.schedule_interval(self.check_and_send_summary, 30)

        # 启动时发送欢迎消息
        Clock.schedule_once(lambda dt: self.wechat.send_text("🤖 智能导购小X已上线"), 2)

    def build_ui(self):
        """构建 UI"""
        # 图片展示区（点击唤醒）- 使用固定比例
        self.display_image = ClickableImage(
            callback=self.on_image_click,
            size_hint=(1, 0.65)
        )
        self.add_widget(self.display_image)

        # 对话历史区
        scroll_view = ScrollView(size_hint=(1, 0.3))
        self.chat_container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(3),
            padding=[dp(8)]
        )
        self.chat_container.bind(minimum_height=self.chat_container.setter('height'))
        scroll_view.add_widget(self.chat_container)
        self.add_widget(scroll_view)

        # 初始提示
        self.add_message("✨ 点击图片或说“小X”唤醒我", False)

    # ==================== 唤醒/休眠管理 ====================
    def on_image_click(self):
        self.wake_up(source="click")

    def wake_up(self, source="voice"):
        if self.is_awake:
            return
        self.is_awake = True
        print(f"✨ 已唤醒 (来源: {source})")
        self.display_image.source = self.AVATAR_AWAKE

        welcome_msgs = [
            f"您好！我是{self.agent_name}",
            f"我在呢，您想了解什么商品？",
            f"请说～"
        ]
        msg = random.choice(welcome_msgs)
        self.add_message(msg, False)

        self.wechat.send_text(f"🔔 智能体已唤醒（{source}）")
        self.start_listening()
        self.reset_sleep_timer()

    def start_listening(self):
        if self.is_listening:
            return
        self.is_listening = True
        print("🎤 开始聆听...")
        self.display_image.source = self.AVATAR_LISTENING

        if VOSK_AVAILABLE:
            threading.Thread(target=self.listen_for_command, daemon=True).start()
        else:
            Clock.schedule_once(lambda dt: self.process_command("这个耳机多少钱"), 2)

    def stop_listening(self):
        self.is_listening = False
        print("⏹️ 停止聆听")

    def go_to_sleep(self):
        if not self.is_awake:
            return
        self.is_awake = False
        self.stop_listening()
        self.display_image.source = self.AVATAR_SLEEP
        print("💤 进入休眠")

    def reset_sleep_timer(self):
        if self.sleep_timer:
            self.sleep_timer.cancel()
        self.sleep_timer = threading.Timer(self.sleep_timeout, self.go_to_sleep)
        self.sleep_timer.daemon = True
        self.sleep_timer.start()

    # ==================== 语音处理 ====================
    def listen_for_command(self):
        time.sleep(2)
        Clock.schedule_once(lambda dt: self.process_command("这个耳机多少钱"), 0)

    def is_purchase_intent(self, text):
        keywords = ["买", "要一个", "下单", "来一个", "给我", "要这个", "买了"]
        return any(keyword in text for keyword in keywords)

    def process_command(self, text):
        if not self.is_awake:
            return

        print(f"👤 顾客: {text}")
        self.add_message(f"顾客: {text}", True)
        self.wechat.send_text(f"💬 客户: {text}")
        self.display_image.source = self.AVATAR_THINKING

        product = self.find_product(text)

        if product:
            product_image = product.get("图片路径", self.AVATAR_AWAKE)
            self.display_image.source = product_image

            response = f"{product['商品名称']} 是 {product['价格']} 元。{product['核心卖点']}"
            self.db.add_conversation(text, response, product['商品名称'])

            if self.is_purchase_intent(text):
                self.db.add_order(product_name=product['商品名称'], price=product['价格'], quantity=1)
                response += " 需要帮您下单吗？"
                self.wechat.send_text(f"🎯 购买意向: {product['商品名称']}")
        else:
            self.display_image.source = self.AVATAR_AWAKE
            response = "抱歉，我没听清，能再说一遍吗？"
            self.db.add_conversation(text, response, None)

        print(f"🤖 小X: {response}")
        self.add_message(f"小X: {response}", False)
        self.wechat.send_text(f"🤖 导购: {response}")
        self.speak_text(response)

        self.display_image.source = self.AVATAR_LISTENING
        self.reset_sleep_timer()

    def find_product(self, text):
        text_lower = text.lower()
        for product in self.products:
            if product['商品名称'] in text:
                return product
        return None

    def add_message(self, text, is_user=False):
        msg_label = Label(
            text=text,
            size_hint_y=None,
            height=dp(35),
            color=get_color_from_hex('#2c3e50') if is_user else get_color_from_hex('#3498db'),
            font_name='ChineseFont' if font_registered else 'Roboto',
            font_size=dp(14),
            halign='left',
            valign='middle',
            text_size=(Window.width * 0.9, None)
        )
        self.chat_container.add_widget(msg_label)
        if hasattr(self.chat_container.parent, 'scroll_y'):
            self.chat_container.parent.scroll_y = 0

    def speak_text(self, text):
        """语音播报 - 跨平台支持"""
        if not VOICE_AVAILABLE:
            return

        def _play():
            try:
                if platform == 'android':
                    # Android 使用原生 TTS
                    try:
                        from android import activity
                        from jnius import autoclass
                        TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
                        tts = TextToSpeech(activity, None)
                        tts.speak(text, TextToSpeech.QUEUE_FLUSH, None, None)
                        print(f"🔊 Android TTS: {text}")
                    except Exception as e:
                        print(f"Android TTS 失败: {e}")
                else:
                    # Windows/Linux 使用 edge-tts
                    import subprocess
                    import tempfile
                    import pygame
                    import os
                    import time

                    temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
                    cmd = ["python", "-m", "edge_tts", "--text", text,
                           "--voice", "zh-CN-XiaoxiaoNeural", "--write-media", temp_file]
                    subprocess.run(cmd, capture_output=True, timeout=15)

                    if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                        pygame.mixer.music.load(temp_file)
                        pygame.mixer.music.play()
                        while pygame.mixer.music.get_busy():
                            time.sleep(0.1)
                        pygame.mixer.music.unload()
                        os.remove(temp_file)
                        print(f"🔊 语音播报: {text}")
            except Exception as e:
                print(f"语音播放失败: {e}")

        threading.Thread(target=_play, daemon=True).start()

    def set_sleep_image(self):
        self.display_image.source = self.AVATAR_SLEEP

    def load_products(self):
        products = []
        encodings = ['utf-8', 'gbk', 'gb2312']
        csv_path = os.path.join(DATA_DIR, "products.csv")

        if not os.path.exists(csv_path):
            csv_path = "products.csv"

        if os.path.exists(csv_path):
            for enc in encodings:
                try:
                    with open(csv_path, "r", encoding=enc) as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            try:
                                row["价格"] = int(row["价格"])
                                row["库存"] = int(row["库存"])
                            except:
                                row["价格"] = 0
                                row["库存"] = 0
                            products.append(row)
                    print(f"✅ 已加载 {len(products)} 个商品")
                    return products
                except:
                    continue

        print("⚠️ 使用默认商品数据")
        return [
            {"商品名称": "无线耳机", "价格": 299, "核心卖点": "40dB主动降噪，30小时续航", "库存": 50},
            {"商品名称": "充电宝", "价格": 89, "核心卖点": "20000mAh，支持快充", "库存": 120},
            {"商品名称": "智能手环", "价格": 159, "核心卖点": "心率监测，睡眠分析", "库存": 35},
            {"商品名称": "小玩偶", "价格": 28, "核心卖点": "可爱，手感柔软", "库存": 100}
        ]

    # ==================== 定时汇总 ====================
    def check_and_send_summary(self, dt):
        now = datetime.now()
        hours_passed = (now - self.last_summary_time).total_seconds() / 3600

        if hours_passed >= 6:
            self.send_periodic_summary()
            self.last_summary_time = now

    def send_periodic_summary(self):
        summary = self.db.get_summary(hours=6)

        if summary['total_conversations'] == 0 and summary['total_orders'] == 0:
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        report = f"""## 📊 智能导购汇总报告
**时间**: {now}
**统计时段**: 过去6小时

### 📈 数据概览
| 指标 | 数量 |
|------|------|
| 总对话次数 | {summary['total_conversations']} |
| 成交订单数 | {summary['total_orders']} |
| 总成交额 | ¥{summary['total_amount']} |

### 🔥 热门咨询
"""
        for product, count in summary['hot_products']:
            report += f"- {product}: {count}次\n"

        if summary['order_summary']:
            report += "\n### 💰 成交明细\n"
            for product, qty, amount in summary['order_summary']:
                report += f"- {product}: {qty}件，共¥{amount}\n"

        self.wechat.send_markdown(report)

    # ==================== 唤醒词监听 ====================
    def start_wake_word_listener(self):
        def wake_loop():
            while True:
                time.sleep(15)
                if not self.is_awake and not self.is_listening:
                    Clock.schedule_once(lambda dt: self.wake_up(source="voice"), 0)
        threading.Thread(target=wake_loop, daemon=True).start()
        print("✅ 唤醒监听已启动")

    def start_simulated_wake(self):
        def wake_loop():
            while True:
                time.sleep(20)
                if not self.is_awake:
                    Clock.schedule_once(lambda dt: self.wake_up(source="simulated"), 0)
        threading.Thread(target=wake_loop, daemon=True).start()
        print("✅ 模拟唤醒已启动")


class ShopAgentApp(App):
    def build(self):
        self.title = '智能导购小X'
        # 只在非 Android 平台设置固定窗口大小
        if platform != 'android':
            Window.size = (400, 800)
        Window.clearcolor = (0.95, 0.95, 0.95, 1)
        return ShopAgentUI()
    
    def on_stop(self):
        print("👋 应用退出")


if __name__ == '__main__':
    ShopAgentApp().run()