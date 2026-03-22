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
requirements = python3,kivy==2.2.0,requests

# (list) Supported orientations
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# Android specific
android.permissions = INTERNET,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 30
android.minapi = 21
android.sdk = 30
android.build_tools = 30.0.3
android.ndk = 25b
android.python_version = 3
