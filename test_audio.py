import pygame
import time
import array
import math

print("1. 初始化 pygame 音频...")
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.mixer.init()
print(f"✅ 初始化成功，设备参数: {pygame.mixer.get_init()}")

print("2. 生成测试音...")
sample_rate = 44100
duration = 1.0
frequency = 440.0

samples = []
for i in range(int(sample_rate * duration)):
    samples.append(int(32767.0 * math.sin(2.0 * math.pi * frequency * i / sample_rate)))

sound = pygame.mixer.Sound(array.array('h', samples))
print("3. 播放测试音...")
sound.play()
time.sleep(2)
print("✅ 测试完成")