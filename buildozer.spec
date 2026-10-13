[app]
title = Sniffer Garden
package.name = sniffergarden
package.domain = org.game
source.dir = .
source.include_exts = py,png,jpg,json,txt,wav
source.exclude_dirs = previews,tests,assets/concepts,assets/sprites-prototype
version = 0.1
requirements = python3,pygame-ce,pyjnius
orientation = landscape
fullscreen = 1
android.archs = arm64-v8a
android.allow_backup = True
android.api = 34
android.minapi = 24
android.ndk = 26b
android.enable_androidx = True
android.extra_manifest_xml = android_config/tts_queries.xml
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1
