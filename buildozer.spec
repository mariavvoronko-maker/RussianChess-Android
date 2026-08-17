[app]
title = Русские шахматы
package.name = russianchess
package.domain = ru.vibeapps
source.dir = .
source.include_exts = py,png,wav,json,txt,md
source.exclude_dirs = tests,__pycache__,.pytest_cache,.git,.github
version = 0.1.2
requirements = python3,kivy==2.3.0
orientation = portrait
fullscreen = 0

# Stable Android toolchain for the first sideload APK.
# Android 9 is API 28; target API may be higher than the device API.
android.minapi = 28
android.ndk_api = 28
android.api = 33
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.copy_libs = 1
android.private_storage = True

# Freeze python-for-android to v2024.01.21.
# That release uses the Python 3.11.5 recipe and recommends NDK 25b.
p4a.branch = v2024.01.21
p4a.commit = 957a3e5f8c270f7aa648ba185e5a68c1077a798d

[buildozer]
log_level = 2
warn_on_root = 1
bin_dir = bin
