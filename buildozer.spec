[app]
title = Русские шахматы
package.name = russianchess
package.domain = ru.vibeapps
source.dir = .
source.include_exts = py,png,wav,json,txt,md
source.exclude_dirs = tests,__pycache__,.pytest_cache,.git,.github
version = 0.1.0
requirements = python3,kivy==2.3.1
orientation = portrait
fullscreen = 0

android.minapi = 28
android.api = 35
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.copy_libs = 1
android.private_storage = True

[buildozer]
log_level = 2
warn_on_root = 1
bin_dir = bin
