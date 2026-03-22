import sys
import threading
import queue
import time
import random
import asyncio
import csv
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# 语音相关库
try:
    import vosk
    import pyaudio
    import json
    import edge_tts
    import pygame
    VOICE_AVAILABLE = True
except ImportError as e:
    print(f"语音模块导入失败: {e}，将仅支持文字交互")
    VOICE_AVAILABLE = False


class ShopAgentUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🤖 智能导购小X · 无人店铺")
        self.setGeometry(100, 100, 800, 1200)

        # 加载商品数据
        self.products = []
        self.load_products()

        # 智能体配置
        self.agent_name = "小X"
        self.wake_words = ["小x", "你好", "有人吗", "在吗"]

        # 语音相关状态
        self.is_awake = False
        self.is_listening = False
        self.wakeup_detected = False

        # 初始化 Pygame 混音器
        if VOICE_AVAILABLE:
            try:
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
                print("✅ Pygame 混音器初始化成功")
            except Exception as e:
                print(f"⚠️ Pygame 初始化失败: {e}，语音播报可能不可用")

        # 初始化UI
        self.initUI()

        # 启动时主动打招呼
        QTimer.singleShot(1000, self.greet_customer)

        # 启动关键词监听线程
        if VOICE_AVAILABLE:
            self.start_wake_word_listener()
        else:
            self.status_bar.showMessage("⚠️ 语音模块未安装，仅支持点击交互")

    # === 把 update_status 移到前面 ===
    def update_status(self, msg):
        """更新状态栏"""
        self.status_bar.showMessage(msg)

    def initUI(self):
        """初始化界面"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        main_widget.setLayout(layout)

        # 1. 状态指示区
        self.status_indicator = QLabel("⚪ 待机中")
        self.status_indicator.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #7f8c8d;
                background-color: #ecf0f1;
                padding: 10px;
                border-radius: 10px;
                margin: 10px;
            }
        """)
        self.status_indicator.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_indicator)

        # 2. 欢迎语区域
        self.welcome_label = QLabel("👋 您好！欢迎光临")
        self.welcome_label.setStyleSheet("""
            QLabel {
                font-size: 36px;
                font-weight: bold;
                color: #2c3e50;
                background-color: #ecf0f1;
                padding: 20px;
                border-radius: 15px;
                margin: 10px;
            }
        """)
        self.welcome_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.welcome_label)

        # 3. 唤醒词提示
        wake_hint = QLabel(f"💬 可以对我说“{self.agent_name}”或“你好”唤醒我")
        wake_hint.setStyleSheet("font-size: 16px; color: #3498db; margin: 5px;")
        wake_hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(wake_hint)

        # 4. 对话历史显示区
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                font-size: 20px;
                background-color: white;
                border: 2px solid #bdc3c7;
                border-radius: 15px;
                padding: 15px;
                margin: 10px;
                min-height: 250px;
            }
        """)
        layout.addWidget(self.chat_display)
        self.chat_display.append(f"✨ 我是智能导购{self.agent_name}")
        self.chat_display.append(f"💡 您可以点击下方🎤按钮，或直接对我说“{self.agent_name}”唤醒我")

        # 5. 语音按钮
        self.mic_button = QPushButton("🎤 点击说话")
        self.mic_button.setStyleSheet("""
            QPushButton {
                font-size: 32px;
                font-weight: bold;
                background-color: #e74c3c;
                color: white;
                padding: 25px;
                border-radius: 20px;
                margin: 10px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a8231a;
            }
        """)
        self.mic_button.clicked.connect(self.on_mic_clicked)
        layout.addWidget(self.mic_button)

        # 6. 快捷商品按钮区
        products_widget = QWidget()
        products_layout = QGridLayout()
        products_widget.setLayout(products_layout)

        row, col = 0, 0
        for i, product in enumerate(self.products[:6]):
            btn = QPushButton(f"{product['商品名称']}\n¥{product['价格']}")
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 18px;
                    background-color: #3498db;
                    color: white;
                    padding: 15px;
                    border-radius: 10px;
                    margin: 5px;
                    min-width: 150px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            btn.clicked.connect(lambda checked, p=product: self.show_product(p))
            products_layout.addWidget(btn, row, col)

            col += 1
            if col > 2:
                col = 0
                row += 1

        layout.addWidget(products_widget)

        # 7. 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("⚡ 待机中，等待唤醒")

    def greet_customer(self):
        """主动打招呼"""
        if self.is_awake:
            return

        greetings = [
            "👋 您好！欢迎光临！",
            "✨ 欢迎光临，需要我帮忙吗？",
            f"🎉 我是{self.agent_name}，有什么可以帮您？",
            "🌟 下午好！今天想找点什么？"
        ]
        msg = random.choice(greetings)
        self.welcome_label.setText(msg)
        self.chat_display.append(f"🤖 {self.agent_name}: {msg}")

        if VOICE_AVAILABLE:
            self.speak_text(msg)

    def on_mic_clicked(self):
        """点击按钮唤醒"""
        self.wake_up(source="button")
        self.start_listening()

    def wake_up(self, source="voice"):
        """唤醒智能体"""
        if self.is_awake:
            return

        self.is_awake = True
        self.update_status("✨ 已唤醒")

        self.status_indicator.setText("🔵 聆听中...")
        self.status_indicator.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2980b9;
                background-color: #3498db;
                padding: 10px;
                border-radius: 10px;
                margin: 10px;
            }
        """)

        greetings = [
            f"👋 您好！我是{self.agent_name}，有什么可以帮您？",
            f"✨ {self.agent_name}为您服务，请说～",
            f"🎤 在呢，您想了解什么商品？"
        ]
        welcome_msg = random.choice(greetings)
        self.welcome_label.setText(welcome_msg)
        self.chat_display.append(f"🤖 {self.agent_name}: {welcome_msg}")

        if VOICE_AVAILABLE and source == "voice":
            self.speak_text(welcome_msg)

        if source == "voice":
            self.start_listening()

    def start_listening(self):
        """开始聆听顾客指令"""
        if self.is_listening:
            return

        self.is_listening = True
        self.mic_button.setText("🎤 正在聆听...")
        self.mic_button.setStyleSheet(self.mic_button.styleSheet() +
                                      "background-color: #f39c12;")
        self.update_status("🎤 请说话...")

        if VOICE_AVAILABLE:
            threading.Thread(target=self.recognize_command).start()
        else:
            QTimer.singleShot(2000, self.mock_command_result)

    def recognize_command(self):
        """识别用户指令（模拟版本）"""
        time.sleep(2)
        QMetaObject.invokeMethod(self, "process_command",
                                 Qt.QueuedConnection,
                                 Q_ARG(str, "这个耳机多少钱"))

    def mock_command_result(self):
        """模拟指令识别结果"""
        self.process_command("这个耳机多少钱")

    def process_command(self, text):
        """处理识别到的指令"""
        self.chat_display.append(f"👤 顾客: {text}")
        self.update_status("🤔 思考中...")

        response = None
        mentioned_product = None

        for product in self.products:
            if product['商品名称'] in text:
                mentioned_product = product
                break

        if "价格" in text or "多少钱" in text or "怎么卖" in text:
            for product in self.products:
                if product['商品名称'] in text:
                    response = f"{product['商品名称']} 是 {product['价格']} 元。{product['核心卖点']}"
                    if product['库存'] < 10:
                        response += f" 库存只剩{product['库存']}件了。"
                    break

        if not response:
            if mentioned_product:
                response = f"{mentioned_product['商品名称']} 是 {mentioned_product['价格']} 元。{mentioned_product['核心卖点']}"
            else:
                response = "抱歉，我没完全理解。您可以点击下方商品按钮查看详情，或者再说一遍？"

        self.chat_display.append(f"🤖 {self.agent_name}: {response}")

        if VOICE_AVAILABLE:
            self.speak_text(response)

        self.reset_after_interaction()

    def show_product(self, product):
        """点击商品按钮"""
        self.chat_display.append(f"👤 顾客: 介绍一下{product['商品名称']}")
        response = f"{product['商品名称']} 是 {product['价格']} 元。{product['核心卖点']}"
        if product['库存'] > 0:
            response += f" 目前库存 {product['库存']} 件。"
        else:
            response += " 暂时缺货，需要帮您留意补货吗？"

        self.chat_display.append(f"🤖 {self.agent_name}: {response}")

        if VOICE_AVAILABLE:
            self.speak_text(response)

        self.update_status("✨ 已唤醒，可以继续提问")

    def reset_after_interaction(self):
        """交互结束后重置状态"""
        self.is_listening = False
        self.is_awake = False
        self.mic_button.setText("🎤 点击说话")
        self.mic_button.setStyleSheet("""
            QPushButton {
                font-size: 32px;
                font-weight: bold;
                background-color: #e74c3c;
                color: white;
                padding: 25px;
                border-radius: 20px;
                margin: 10px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a8231a;
            }
        """)
        self.update_status("⚡ 待机中，等待唤醒")
        self.status_indicator.setText("⚪ 待机中")
        self.status_indicator.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #7f8c8d;
                background-color: #ecf0f1;
                padding: 10px;
                border-radius: 10px;
                margin: 10px;
            }
        """)
        self.welcome_label.setText("👋 欢迎再次光临")

    def start_wake_word_listener(self):
        """启动唤醒词监听线程"""

        def wake_word_loop():
            try:
                small_model_path = "models/vosk-zh-small"
                model = vosk.Model(small_model_path)
                recognizer = vosk.KaldiRecognizer(model, 16000)

                p = pyaudio.PyAudio()
                stream = p.open(format=pyaudio.paInt16,
                                channels=1,
                                rate=16000,
                                input=True,
                                frames_per_buffer=8000)

                print("✅ 唤醒词监听已启动...")

                while True:
                    data = stream.read(4000, exception_on_overflow=False)

                    if self.is_awake:
                        time.sleep(0.5)
                        continue

                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").lower()

                        if text:
                            print(f"听到: {text}")

                        for wake_word in self.wake_words:
                            if wake_word in text:
                                print(f"🎯 检测到唤醒词: {wake_word}")
                                QMetaObject.invokeMethod(self, "wake_up",
                                                         Qt.QueuedConnection,
                                                         Q_ARG(str, "voice"))
                                break
            except Exception as e:
                print(f"❌ 唤醒词监听错误: {e}")

        threading.Thread(target=wake_word_loop, daemon=True).start()

    def speak_text(self, text):
        """语音合成播报（使用Pygame）"""

        async def _speak():
            filename = "temp_output.mp3"
            try:
                communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
                await communicate.save(filename)

                sound = pygame.mixer.Sound(filename)
                channel = sound.play()

                if channel:
                    while channel.get_busy():
                        QApplication.processEvents()
                        time.sleep(0.1)

                print(f"🔊 语音播报: {text}")

            except Exception as e:
                print(f"语音播放失败: {e}")

        threading.Thread(target=lambda: asyncio.run(_speak()), daemon=True).start()

    def load_products(self):
        """加载商品数据（自动检测编码）"""
        self.products = []

        # 方法1：尝试读取CSV（多种编码）
        try:
            import csv
            # 使用相对路径（兼容电脑和手机）
            csv_path = "products.csv"
            encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig', 'ansi']

            for enc in encodings:
                try:
                    with open(csv_path, "r", encoding=enc) as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            # 把价格和库存转成整数
                            try:
                                row["价格"] = int(row["价格"])
                            except:
                                row["价格"] = 0
                            try:
                                row["库存"] = int(row["库存"])
                            except:
                                row["库存"] = 0
                            self.products.append(row)
                    print(f"✅ 已加载 {len(self.products)} 个商品 (来自CSV，编码{enc})")
                    return
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"CSV读取失败（编码{enc}）: {e}")
                    continue
        except Exception as e:
            print(f"CSV模块导入失败: {e}")

        # 方法2：尝试读取Excel（备选）
        try:
            import openpyxl
            workbook = openpyxl.load_workbook("products.xlsx")
            sheet = workbook.active

            headers = [cell.value for cell in sheet[1]]
            self.products = []
            for row in sheet.iter_rows(min_row=2, values_only=True):
                product = {}
                for i, value in enumerate(row):
                    if headers[i] and value is not None:
                        product[headers[i]] = value
                if product:
                    self.products.append(product)
            print(f"✅ 已加载 {len(self.products)} 个商品 (来自Excel)")
            return
        except Exception as e:
            print(f"Excel读取失败: {e}")

        # 方法3：使用默认数据
        print("使用默认商品数据")
        self.products = [
            {"商品名称": "无线耳机", "价格": 299, "核心卖点": "40dB主动降噪，30小时续航", "库存": 50},
            {"商品名称": "充电宝", "价格": 89, "核心卖点": "20000mAh，支持快充", "库存": 120},
            {"商品名称": "智能手环", "价格": 159, "核心卖点": "心率监测，睡眠分析", "库存": 35},
        ]


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ShopAgentUI()
    window.show()
    sys.exit(app.exec_())