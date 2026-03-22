[app]

# (str) Title of your application
title = 智能导购小X

# (str) Package name
package.name = shopagent

# (str) Package domain (needed for android/ios packaging)
package.domain = com.xiaox.shop

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,txt,mp3,conf,fst,mdl,int,wav,csv,ttf,ttc

# (list) List of inclusions using pattern matching
source.include_patterns = images/*,fonts/*,products.csv

# (str) Application versioning (method 1)
version = 1.0.0

# (list) Application requirements
# 精简 requirements，移除不必要的包
requirements = python3,kivy==2.2.0,requests

# (list) Supported orientations
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# Android specific
android.permissions = INTERNET,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# 添加中文字体支持
android.add_src = fonts/

# 使用 Python 3.8（更稳定）
android.python_version = 3

# Android API 配置
android.api = 30
android.minapi = 21
android.ndk = 25b
