[app]
title = FunPay BRO
package.name = funpaybro
package.domain = org.lunavpn
source.dir = .
source.include_exts = py
version = 0.1
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,requests,urllib3,idna,charset-normalizer,certifi,beautifulsoup4==4.12.3,soupsieve,plyer,android
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,POST_NOTIFICATIONS,WAKE_LOCK
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
