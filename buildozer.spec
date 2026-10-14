[app]
title = Sniffer Garden
package.name = sniffergarden
package.domain = org.game
source.dir = .
source.include_exts = py,png,jpg,json,txt,wav
source.exclude_dirs = .git,.github,.venv,.web-test-venv,build,bin,.buildozer,previews,tests,assets/concepts,assets/sprites-prototype
source.exclude_patterns = __pycache__/*,*.pyc
version = 0.1
requirements = python3==3.10.11,hostpython3==3.10.11,pygame,pyjnius
orientation = landscape
fullscreen = 1
android.archs = arm64-v8a
android.allow_backup = True
android.api = 34
android.minapi = 24
android.numeric_version = 10000
android.release_artifact = apk
android.ndk = 25b
android.enable_androidx = True
android.extra_manifest_xml = android_config/tts_queries.xml
p4a.bootstrap = sdl2
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
