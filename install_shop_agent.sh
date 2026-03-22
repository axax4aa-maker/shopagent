#!/bin/bash
# =============================================
# 智能导购小X - 完整环境安装脚本
# 适用于 Ubuntu 22.04 WSL2
# 保存位置: D:\project\shop_agent\Open-AutoGLM\install_shop_agent.sh
# =============================================

set -e  # 遇到错误立即停止

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的信息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否以普通用户运行（不能用root）
check_user() {
    if [ "$EUID" -eq 0 ]; then 
        print_error "请不要以root用户运行此脚本"
        print_info "请用普通用户运行: ./install_shop_agent.sh"
        exit 1
    fi
    print_success "当前用户: $(whoami)"
}

# 更新系统
update_system() {
    print_info "正在更新系统软件源..."
    sudo apt update
    print_success "系统更新完成"
}

# 安装系统依赖
install_system_deps() {
    print_info "正在安装系统依赖包（这可能需要几分钟）..."
    
    # 基础工具
    sudo apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        git \
        curl \
        wget \
        unzip \
        build-essential
        
    # 音频依赖（关键！）
    sudo apt install -y \
        pulseaudio \
        pulseaudio-utils \
        alsa-utils \
        libasound2-plugins \
        libportaudio2 \
        portaudio19-dev
        
    # 图形界面依赖
    sudo apt install -y \
        libsdl2-dev \
        libsdl2-image-dev \
        libsdl2-mixer-dev \
        libsdl2-ttf-dev \
        libgl1-mesa-dev \
        libgles2-mesa-dev \
        libdrm-dev \
        libgbm-dev \
        libudev-dev \
        libasound2-dev \
        liblzma-dev \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev \
        libxv-dev \
        libxi-dev \
        libxxf86vm-dev \
        libglu1-mesa-dev
        
    # 中文字体
    sudo apt install -y \
        fonts-wqy-microhei \
        fonts-wqy-zenhei \
        fonts-noto-cjk
        
    print_success "系统依赖安装完成"
}

# 配置音频环境
configure_audio() {
    print_info "正在配置音频环境..."
    
    # 创建 PulseAudio 客户端配置
    mkdir -p ~/.config/pulse
    cat > ~/.config/pulse/client.conf << EOF
default-server = unix:/mnt/wslg/PulseServer
autospawn = no
enable-shm = no
EOF
    
    # 创建 ALSA 配置文件
    sudo tee /etc/asound.conf > /dev/null << EOF
pcm.!default {
    type pulse
    hint.description "Default Audio Device"
}
ctl.!default {
    type pulse
}
EOF
    
    # 用户级别的 ALSA 配置
    cp /etc/asound.conf ~/.asoundrc 2>/dev/null || sudo cp /etc/asound.conf ~/.asoundrc
    
    # 设置环境变量
    echo 'export PULSE_SERVER=unix:/mnt/wslg/PulseServer' >> ~/.bashrc
    echo 'export SDL_AUDIODRIVER=pulseaudio' >> ~/.bashrc
    
    # 立即生效
    export PULSE_SERVER=unix:/mnt/wslg/PulseServer
    export SDL_AUDIODRIVER=pulseaudio
    
    print_success "音频配置完成"
}

# 安装 Python 包
install_python_packages() {
    print_info "正在安装 Python 包（这可能需要几分钟）..."
    
    # 升级 pip
    pip3 install --upgrade pip
    
    # 核心包
    pip3 install \
        kivy==2.3.1 \
        pygame==2.6.1 \
        edge-tts \
        vosk \
        pandas \
        numpy \
        pyaudio \
        openpyxl \
        pillow
        
    print_success "Python 包安装完成"
}

# 测试音频
test_audio() {
    print_info "正在测试音频..."
    
    # 检查 PulseAudio 连接
    if pactl info > /dev/null 2>&1; then
        print_success "PulseAudio 连接成功"
        print_info "播放测试音（1秒）..."
        speaker-test -t sine -f 1000 -l 1
    else
        print_warning "PulseAudio 连接失败，检查配置"
        print_info "尝试手动连接..."
        export PULSE_SERVER=unix:/mnt/wslg/PulseServer
        pactl info
    fi
}

# 创建验证脚本
create_test_script() {
    print_info "创建验证脚本..."
    
    cat > ~/test_audio.py << 'EOF'
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
EOF

    chmod +x ~/test_audio.py
    print_success "验证脚本创建完成: ~/test_audio.py"
}

# 复制项目文件
copy_project() {
    print_info "正在复制项目文件..."
    
    # 获取脚本所在目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # 创建目标目录
    mkdir -p ~/kivy_projects
    
    # 复制整个项目
    cp -r "$SCRIPT_DIR" ~/kivy_projects/
    
    print_success "项目文件复制完成到: ~/kivy_projects/Open-AutoGLM"
}

# 主函数
main() {
    print_info "开始安装智能导购小X环境"
    echo "========================================="
    
    check_user
    update_system
    install_system_deps
    configure_audio
    install_python_packages
    copy_project
    create_test_script
    
    echo "========================================="
    print_success "环境安装完成！"
    echo ""
    print_info "下一步操作："
    echo "1. 测试音频: python3 ~/test_audio.py"
    echo "2. 进入项目: cd ~/kivy_projects/Open-AutoGLM"
    echo "3. 运行程序: python3 shop_ui_kivy.py"
    echo ""
    print_info "如果音频测试不成功，可以手动运行:"
    echo "   export PULSE_SERVER=unix:/mnt/wslg/PulseServer"
    echo "   pactl info"
    echo ""
}

# 执行主函数
main