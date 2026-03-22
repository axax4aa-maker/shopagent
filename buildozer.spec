[app]
title = 智能导购小X
package.name = shopagent
package.domain = com.xiaox.shop
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt,mp3,conf,fst,mdl,int,wav,csv,ttf,ttc
source.include_patterns = images/*,fonts/*,products.csv
version = 1.0.0
requirements = python3,kivy==2.2.0,requests
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 30
android.minapi = 21
android.sdk = 30
android.ndk = 25b
android.python_version = 3
