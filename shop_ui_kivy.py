"""
智能导购小X - Kivy安卓版（最终稳定版）
适配 Windows 编辑 + WSL 运行 + 安卓打包
"""

import os
import sys
import threading
import time
import random
import csv
import asyncio
import json
import subprocess
from functools import partial

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import get_color_from_hex, platform
from kivy.metrics import dp
from kivy.core.text import LabelBase
from kivy.graphics import Color, Rectangle

# ==================== 平台相关路径处理 ====================
if platform == 'android':
    # 安卓平台：使用应用私有目录
    from android.storage import app_storage_path
    from android.permissions import request_permissions, Permission

    request_permissions([
        Permission.RECORD_AUDIO,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.READ_EXTERNAL_STORAGE
    ])

    DATA_DIR = app_storage_path()
    TMP_DIR = DATA_DIR
else:
    # 桌面平台（Windows/WSL）：使用当前目录
    DATA_DIR = '.'
    TMP_DIR = '.'

print(f"📁 数据目录: {DATA_DIR}")

# ==================== 字体设置（兼容 Windows 和 Linux）====================
font_registered = False

# 根据平台选择字体路径
if platform == 'win':
    # Windows 字体路径（用于 PyCharm 测试）
    FONT_PATHS = [
        'C:/Windows/Fonts/msyh.ttc',      # 微软雅黑
        'C:/Windows/Fonts/simhei.ttf',    # 黑体
        'C:/Windows/Fonts/msyhbd.ttc',    # 微软雅黑粗体
    ]
    for font_path in FONT_PATHS:
        if os.path.exists(font_path):
            try:
                LabelBase.register(name='ChineseFont', fn_regular=font_path)
                print(f"✅ Windows 字体加载成功: {font_path}")
                font_registered = True
                break
            except:
                continue
else:
    # Linux/WSL 字体名（从 fc-list 获取）
    try:
        LabelBase.register(name='ChineseFont', fn_regular='WenQuanYi Micro Hei')
        print("✅ Linux 字体注册成功: WenQuanYi Micro Hei")
        font_registered = True
    except:
        # 备选字体名
        fallback_fonts = [
            'Noto Sans CJK SC',
            'Noto Sans CJK JP',
            'WenQuanYi Zen Hei',
            'DejaVu Sans'
        ]
        for font_name in fallback_fonts:
            try:
                LabelBase.register(name='ChineseFont', fn_regular=font_name)
                print(f"✅ Linux 使用备选字体: {font_name}")
                font_registered = True
                break
            except:
                continue

if not font_registered:
    print("⚠️ 未找到中文字体，使用Kivy默认字体")

# ==================== 语音模块导入 ====================
VOICE_AVAILABLE = False
try:
    import edge_tts
    import pygame
    import pygame.mixer
    VOICE_AVAILABLE = True
    print("✅ 语音模块加载成功")
except ImportError as e:
    print(f"⚠️ 语音模块未安装: {e}")

try:
    import vosk
    VOSK_AVAILABLE = True
    print("✅ Vosk模块加载成功")
except ImportError as e:
    VOSK_AVAILABLE = False
    print(f"⚠️ Vosk模块未安装: {e}")

# ==================== 窗口设置 ====================
Window.size = (400, 800)
Window.clearcolor = (0.95, 0.95, 0.95, 1)


class ProductButton(Button):
    """商品按钮"""
    def __init__(self, product, callback, **kwargs):
        super().__init__(**kwargs)
        self.product = product
        self.callback = callback
        self.text = f"{product['商品名称']}\n¥{product['价格']}"
        self.font_name = 'ChineseFont' if font_registered else 'Roboto'
        self.font_size = dp(18)
        self.size_hint_y = None
        self.height = dp(100)
        self.background_normal = ''
        self.background_color = get_color_from_hex('#3498db')
        self.color = (1, 1, 1, 1)
        self.bold = True

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.background_color = get_color_from_hex('#2980b9')
            self.callback(self.product)
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        self.background_color = get_color_from_hex('#3498db')
        return super().on_touch_up(touch)


class VoiceButton(Button):
    """语音按钮"""
    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.text = '🎤 点击说话'
        self.font_name = 'ChineseFont' if font_registered else 'Roboto'
        self.font_size = dp(24)
        self.size_hint_y = None
        self.height = dp(70)
        self.background_normal = ''
        self.background_color = get_color_from_hex('#e74c3c')
        self.color = (1, 1, 1, 1)
        self.bold = True
        self.voice_callback = callback

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.background_color = get_color_from_hex('#c0392b')
            self.voice_callback()
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        self.background_color = get_color_from_hex('#e74c3c')
        return super().on_touch_up(touch)

    def start_listening(self):
        self.text = '🎤 聆听中...'
        self.background_color = get_color_from_hex('#f39c12')

    def stop_listening(self):
        self.text = '🎤 点击说话'
        self.background_color = get_color_from_hex('#e74c3c')


class ShopAgentUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = [dp(10), dp(5)]
        self.spacing = dp(5)

        # 加载商品数据
        self.products = []
        self.load_products()

        # 状态变量
        self.is_awake = False
        self.is_listening = False
        self.is_processing = False
        self.agent_name = "小X"
        self.wake_words = ["小x", "你好", "在吗"]

        # 设置背景
        with self.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
            self.bind(pos=lambda inst, val: setattr(self.bg_rect, 'pos', val),
                      size=lambda inst, val: setattr(self.bg_rect, 'size', val))

        # 线程
        self.voice_thread = None
        self.wake_thread = None

        # 构建UI
        self.build_ui()

        # 初始化Pygame
        if VOICE_AVAILABLE:
            try:
                pygame.mixer.init(frequency=22050, size=-16, channels=2)
                print("✅ Pygame混音器初始化成功")
            except Exception as e:
                print(f"⚠️ Pygame初始化失败: {e}")

        # 启动时打招呼
        Clock.schedule_once(self.greet_customer, 1)

        # 启动唤醒监听
        if VOSK_AVAILABLE:
            self.start_wake_word_listener()
        else:
            self.start_simulated_wake()
            print("⚠️ 使用模拟唤醒模式")

    def build_ui(self):
        """构建UI"""
        # 顶部状态栏
        status_bar = BoxLayout(size_hint_y=None, height=dp(40))

        self.status_label = Label(
            text='⚪ 待机',
            font_name='ChineseFont' if font_registered else 'Roboto',
            font_size=dp(16),
            color=get_color_from_hex('#2c3e50'),
            size_hint_x=0.3,
            halign='left'
        )
        status_bar.add_widget(self.status_label)

        shop_name = Label(
            text='智能导购小X',
            font_name='ChineseFont' if font_registered else 'Roboto',
            font_size=dp(18),
            color=get_color_from_hex('#2c3e50'),
            size_hint_x=0.4,
            bold=True,
            halign='center'
        )
        status_bar.add_widget(shop_name)

        self.time_label = Label(
            text=self.get_current_time(),
            font_name='ChineseFont' if font_registered else 'Roboto',
            font_size=dp(16),
            color=get_color_from_hex('#7f8c8d'),
            size_hint_x=0.3,
            halign='right'
        )
        status_bar.add_widget(self.time_label)
        self.add_widget(status_bar)

        Clock.schedule_interval(lambda dt: setattr(
            self.time_label, 'text', self.get_current_time()
        ), 1)

        # 欢迎语区域
        welcome_box = BoxLayout(
            size_hint_y=None,
            height=dp(50),
            padding=[dp(10), dp(5)]
        )
        with welcome_box.canvas.before:
            Color(0.9, 0.95, 1, 1)
            welcome_rect = Rectangle(pos=welcome_box.pos, size=welcome_box.size)
            welcome_box.bind(pos=lambda inst, val: setattr(welcome_rect, 'pos', val),
                             size=lambda inst, val: setattr(welcome_rect, 'size', val))

        self.welcome_label = Label(
            text='您好！欢迎光临',
            font_name='ChineseFont' if font_registered else 'Roboto',
            font_size=dp(20),
            color=get_color_from_hex('#2c3e50'),
            bold=True,
            halign='center'
        )
        welcome_box.add_widget(self.welcome_label)
        self.add_widget(welcome_box)

        # 唤醒提示
        hint_box = BoxLayout(
            size_hint_y=None,
            height=dp(30),
            padding=[dp(10), 0]
        )
        wake_hint = Label(
            text=f'可以说“{self.agent_name}”或“你好”唤醒我',
            font_name='ChineseFont' if font_registered else 'Roboto',
            font_size=dp(14),
            color=get_color_from_hex('#3498db'),
            halign='center'
        )
        hint_box.add_widget(wake_hint)
        self.add_widget(hint_box)

        # 对话区域
        scroll_view = ScrollView(size_hint_y=0.3)
        with scroll_view.canvas.before:
            Color(1, 1, 1, 1)
            scroll_bg = Rectangle(pos=scroll_view.pos, size=scroll_view.size)
            scroll_view.bind(pos=lambda inst, val: setattr(scroll_bg, 'pos', val),
                             size=lambda inst, val: setattr(scroll_bg, 'size', val))

        self.chat_container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(3),
            padding=[dp(8)]
        )
        self.chat_container.bind(minimum_height=self.chat_container.setter('height'))
        scroll_view.add_widget(self.chat_container)
        self.add_widget(scroll_view)

        # 语音按钮
        self.voice_btn = VoiceButton(self.on_voice_click)
        self.add_widget(self.voice_btn)

        # 商品按钮
        grid_box = BoxLayout(
            size_hint_y=0.25,
            padding=[dp(5), dp(5)]
        )
        product_grid = GridLayout(
            cols=2,
            spacing=dp(8),
            size_hint_y=None,
            height=dp(200)
        )

        for product in self.products[:4]:
            btn = ProductButton(product, self.on_product_click)
            product_grid.add_widget(btn)

        grid_box.add_widget(product_grid)
        self.add_widget(grid_box)

        # 底部状态
        footer_box = BoxLayout(
            size_hint_y=None,
            height=dp(25),
            padding=[dp(10), 0]
        )
        self.footer_label = Label(
            text='待机中，等待唤醒',
            font_name='ChineseFont' if font_registered else 'Roboto',
            font_size=dp(12),
            color=get_color_from_hex('#7f8c8d'),
            halign='left'
        )
        footer_box.add_widget(self.footer_label)
        self.add_widget(footer_box)

    def get_current_time(self):
        return time.strftime('%H:%M')

    def get_data_path(self, filename):
        return os.path.join(DATA_DIR, filename)

    def get_temp_path(self, filename):
        return os.path.join(TMP_DIR, filename)

    def greet_customer(self, dt=None):
        if self.is_processing:
            return
        greetings = [
            f"您好！我是{self.agent_name}，有什么可以帮您？",
            f"欢迎光临，需要我帮忙吗？",
            f"下午好！今天想找点什么？"
        ]
        msg = random.choice(greetings)
        self.add_message(msg, False)
        self.welcome_label.text = msg
        if VOICE_AVAILABLE:
            self.speak_text(msg)

    def on_voice_click(self):
        if self.is_processing:
            return
        self.is_processing = True
        self.is_listening = True
        self.voice_btn.start_listening()
        self.update_status("聆听中...", is_listening=True)
        Clock.schedule_once(lambda dt: self.process_voice_input("这个耳机多少钱"), 2)

    def process_voice_input(self, text):
        self.is_listening = False
        self.add_message(f"顾客: {text}", True)
        self.update_status("思考中...")
        response = self.find_product_response(text)
        Clock.schedule_once(lambda dt: self.add_message(f"小X: {response}", False), 0.5)
        if VOICE_AVAILABLE:
            Clock.schedule_once(lambda dt: self.speak_text(response), 0.6)
        Clock.schedule_once(lambda dt: self.finish_processing(), 2)

    def on_product_click(self, product):
        if self.is_processing:
            return
        self.is_processing = True
        self.add_message(f"顾客: 介绍一下{product['商品名称']}", True)
        self.update_status("思考中...")
        response = f"{product['商品名称']} 是 {product['价格']} 元。{product['核心卖点']}"
        if product['库存'] > 0:
            response += f" 目前库存 {product['库存']} 件。"
        else:
            response += " 暂时缺货。"
        Clock.schedule_once(lambda dt: self.add_message(f"小X: {response}", False), 0.5)
        if VOICE_AVAILABLE:
            Clock.schedule_once(lambda dt: self.speak_text(response), 0.6)
        Clock.schedule_once(lambda dt: self.finish_processing(), 2)
        self.update_status("已唤醒")

    def find_product_response(self, text):
        text_lower = text.lower()
        best_match = None
        for product in self.products:
            if product['商品名称'] in text:
                best_match = product
                break
        if "多少钱" in text_lower or "价格" in text_lower or "怎么卖" in text_lower:
            for product in self.products:
                if product['商品名称'] in text:
                    response = f"{product['商品名称']} 是 {product['价格']} 元。"
                    if product['库存'] < 10:
                        response += f" 库存只剩{product['库存']}件了。"
                    return response
        if best_match:
            return f"{best_match['商品名称']} 是 {best_match['价格']} 元。{best_match['核心卖点']}"
        return "抱歉，我没完全理解。您可以点击下方商品按钮查看详情。"

    def finish_processing(self):
        self.is_processing = False
        self.is_listening = False
        self.voice_btn.stop_listening()
        self.update_status("待机中")

    def add_message(self, text, is_user):
        msg_box = BoxLayout(
            size_hint_y=None,
            height=dp(35),
            spacing=dp(5)
        )
        msg_label = Label(
            text=text,
            font_name='ChineseFont' if font_registered else 'Roboto',
            font_size=dp(14),
            size_hint_x=1,
            halign='left',
            valign='middle',
            color=get_color_from_hex('#2c3e50'),
            text_size=(Window.width * 0.9, None)
        )
        msg_box.add_widget(msg_label)
        self.chat_container.add_widget(msg_box)
        Clock.schedule_once(lambda dt: setattr(
            self.chat_container.parent, 'scroll_y', 0
        ), 0.1)

    def speak_text(self, text):
        """语音播报（使用 subprocess，兼容 Windows 和 Linux）"""
        if not VOICE_AVAILABLE:
            return

        def _play():
            try:
                # 直接调用 edge-tts 命令行
                cmd = ["edge-tts", "--text", text, "--voice", "zh-CN-XiaoxiaoNeural"]
                subprocess.run(cmd, capture_output=True, timeout=10)
                print(f"🔊 语音播报: {text}")
            except subprocess.TimeoutExpired:
                print("⚠️ edge-tts 超时")
            except Exception as e:
                print(f"语音播放失败: {e}")

        threading.Thread(target=_play, daemon=True).start()

    def update_status(self, status, is_listening=False):
        self.footer_label.text = status
        if is_listening:
            self.status_label.text = '🔵 聆听'
            self.status_label.color = get_color_from_hex('#2980b9')
        elif "思考" in status or "唤醒" in status:
            self.status_label.text = '🔵 忙碌'
            self.status_label.color = get_color_from_hex('#2980b9')
        else:
            self.status_label.text = '⚪ 待机'
            self.status_label.color = get_color_from_hex('#7f8c8d')

    def load_products(self):
        """加载商品数据（从CSV）"""
        self.products = []
        encodings = ['utf-8', 'gbk', 'gb2312']

        csv_path = self.get_data_path("products.csv")
        if not os.path.exists(csv_path):
            csv_path = "products.csv"

        if not os.path.exists(csv_path):
            print("⚠️ 未找到products.csv，使用默认商品数据")
            self.use_default_products()
            return

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
                        self.products.append(row)
                print(f"✅ 已加载 {len(self.products)} 个商品 (编码:{enc})")
                return
            except Exception as e:
                print(f"尝试编码 {enc} 失败: {e}")
                continue

        print("❌ 所有编码尝试失败，使用默认商品数据")
        self.use_default_products()

    def use_default_products(self):
        self.products = [
            {"商品名称": "无线耳机", "价格": 299, "核心卖点": "40dB主动降噪，30小时续航", "库存": 50},
            {"商品名称": "充电宝", "价格": 89, "核心卖点": "20000mAh，支持快充", "库存": 120},
            {"商品名称": "智能手环", "价格": 159, "核心卖点": "心率监测，睡眠分析", "库存": 35},
            {"商品名称": "小玩偶", "价格": 28, "核心卖点": "可爱，手感柔软", "库存": 100}
        ]

    def start_wake_word_listener(self):
        """启动Vosk唤醒监听"""
        if not VOSK_AVAILABLE:
            self.start_simulated_wake()
            return

        def wake_loop():
            try:
                model_path = self.get_data_path("models/vosk-zh-small")
                if not os.path.exists(model_path):
                    model_path = "models/vosk-zh-small"

                if not os.path.exists(model_path):
                    print("❌ 未找到Vosk模型，使用模拟唤醒模式")
                    self.start_simulated_wake()
                    return

                import pyaudio
                import vosk

                model = vosk.Model(model_path)
                recognizer = vosk.KaldiRecognizer(model, 16000)
                p = pyaudio.PyAudio()

                # 查找输入设备
                input_device = None
                for i in range(p.get_device_count()):
                    info = p.get_device_info_by_index(i)
                    if info.get('maxInputChannels', 0) > 0:
                        input_device = i
                        print(f"✅ 找到输入设备 {i}: {info.get('name', '未知')}")
                        break

                if input_device is None:
                    print("⚠️ 未找到麦克风设备，使用模拟唤醒模式")
                    self.start_simulated_wake()
                    return

                stream = p.open(format=pyaudio.paInt16,
                              channels=1,
                              rate=16000,
                              input=True,
                              input_device_index=input_device,
                              frames_per_buffer=4000)
                print("✅ 唤醒词监听已启动")

                while True:
                    if self.is_processing:
                        time.sleep(0.5)
                        continue

                    data = stream.read(4000, exception_on_overflow=False)

                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").lower()

                        if text:
                            print(f"听到: {text}")
                            for word in self.wake_words:
                                if word in text:
                                    print(f"🎯 检测到唤醒词: {word}")
                                    Clock.schedule_once(lambda dt: self.wake_up(), 0)
                                    break

            except Exception as e:
                print(f"❌ 唤醒监听错误: {e}，切换到模拟唤醒")
                self.start_simulated_wake()

        self.wake_thread = threading.Thread(target=wake_loop, daemon=True)
        self.wake_thread.start()

    def start_simulated_wake(self):
        """模拟唤醒"""
        def wake_loop():
            while True:
                time.sleep(20)
                if not self.is_processing and not self.is_awake:
                    Clock.schedule_once(lambda dt: self.wake_up(), 0)
        threading.Thread(target=wake_loop, daemon=True).start()
        print("✅ 模拟唤醒线程已启动")

    def wake_up(self):
        if self.is_processing:
            return
        self.is_awake = True
        self.update_status("已唤醒")
        welcome_msgs = [
            f"您好！我是{self.agent_name}，有什么可以帮您？",
            f"{self.agent_name}为您服务，请说～",
            f"在呢，您想了解什么商品？"
        ]
        msg = random.choice(welcome_msgs)
        self.welcome_label.text = msg
        self.add_message(msg, False)
        if VOICE_AVAILABLE:
            self.speak_text(msg)
        Clock.schedule_once(lambda dt: self.go_to_sleep(), 10)

    def go_to_sleep(self):
        self.is_awake = False
        self.update_status("待机中")
        self.welcome_label.text = "您好！欢迎光临"


class ShopAgentApp(App):
    def build(self):
        self.title = '智能导购小X'
        return ShopAgentUI()

    def on_stop(self):
        print("👋 应用退出，清理临时文件")
        try:
            for file in os.listdir(TMP_DIR):
                if file.startswith("temp_") and file.endswith(".mp3"):
                    try:
                        os.remove(os.path.join(TMP_DIR, file))
                        print(f"🧹 已清理: {file}")
                    except:
                        pass
        except Exception as e:
            print(f"清理临时文件时出错: {e}")


if __name__ == '__main__':
    ShopAgentApp().run()