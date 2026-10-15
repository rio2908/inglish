"""Offline word playback: Android system TTS, or optional pre-recorded WAVs."""

from pathlib import Path
import base64
import json
import os
import subprocess
import sys
import time

import pygame


class Speech:
    def __init__(self, audio_dir: Path):
        self.audio_dir = audio_dir
        self.cache = {}
        self.pending = None
        self.ready = False
        self.tts = None
        self.locale = None
        self.listener = None
        self.error = ""
        self.started = time.monotonic()
        self.process = None
        self.android = sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ
        if self.android:
            self._init_android()

    def _init_android(self):
        try:
            from jnius import PythonJavaClass, autoclass, java_method
            from android.runnable import run_on_ui_thread

            speech = self

            class InitListener(PythonJavaClass):
                __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
                __javacontext__ = "app"

                @java_method("(I)V")
                def onInit(self, status):
                    speech.ready = status == 0
                    if status != 0:
                        speech.error = "Не удалось запустить озвучку Android. Проверьте настройки TTS."

            self.listener = InitListener()
            # SDL runs Python on a worker thread. Create/use TTS on Android's UI thread.
            @run_on_ui_thread
            def initialize():
                try:
                    activity = autoclass("org.kivy.android.PythonActivity").mActivity
                    self.locale = autoclass("java.util.Locale").US
                    self.tts = autoclass("android.speech.tts.TextToSpeech")(activity, self.listener)
                except Exception as error:
                    self.error = f"Не удалось включить озвучку Android: {error}"
            initialize()
        except Exception as error:
            self.tts = None
            self.error = f"Не удалось включить озвучку Android: {error}"

    def tick(self):
        if self.process is not None and self.process.poll() is not None:
            if self.process.returncode:
                self.error = "Озвучка недоступна. Установите английский голос в настройках Windows."
            self.process = None
        if sys.platform == "emscripten":
            try:
                import platform
                error = platform.window.snifferSpeechError
                if error:
                    self.error = "Озвучка браузера недоступна: " + str(error)
                    platform.window.snifferSpeechError = ""
            except Exception:
                pass
        if self.pending and self.android and not self.ready and time.monotonic() - self.started > 15:
            self.pending = None
            self.error = "Озвучка не запустилась. Включите TTS и скачайте английский голос."
        if self.pending and self.tts and self.ready:
            word = self.pending
            self.pending = None
            self._speak_android(word)

    def _speak_android(self, word):
        from android.runnable import run_on_ui_thread

        @run_on_ui_thread
        def speak():
            try:
                if self.tts.setLanguage(self.locale) < 0:
                    self.error = "Скачайте английский голос в настройках озвучки Android."
                    return
                self.tts.setSpeechRate(0.82)
                result = self.tts.speak(word, 0, None, "sniffer-word")
                if result < 0:
                    self.error = "Android не смог произнести слово. Проверьте настройки TTS."
            except Exception as error:
                self.error = f"Ошибка озвучки Android: {error}"
        speak()

    def speak(self, word):
        self.error = ""
        path = self.audio_dir / f"{word}.wav"
        if path.is_file() and pygame.mixer.get_init():
            try:
                if word not in self.cache:
                    self.cache[word] = pygame.mixer.Sound(str(path))
                self.cache[word].play()
                return True
            except pygame.error:
                pass
        if self.android:
            if not self.tts and time.monotonic() - self.started > 15:
                self.started = time.monotonic()
                self._init_android()
            self.pending = word
            self.tick()
            return not bool(self.error)
        if sys.platform == "emscripten":
            try:
                import platform
                platform.window.eval("""(() => {
                    window.snifferSpeechError = '';
                    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
                        window.snifferSpeechError = 'В этом браузере нет синтеза речи'; return;
                    }
                    const u = new SpeechSynthesisUtterance(%s);
                    u.lang = 'en-US'; u.rate = 0.82;
                    const voices = speechSynthesis.getVoices();
                    const voice = voices.find(v => v.lang === 'en-US') || voices.find(v => v.lang.startsWith('en'));
                    if (voice) u.voice = voice;
                    u.onerror = e => { if (!['canceled','interrupted'].includes(e.error)) window.snifferSpeechError = e.error; };
                    window.snifferUtterance = u;
                    speechSynthesis.cancel(); speechSynthesis.resume(); speechSynthesis.speak(u);
                })()""" % json.dumps(word))
                return True
            except Exception as error:
                self.error = f"Ошибка озвучки браузера: {error}"
        elif sys.platform == "win32":
            try:
                if self.process is not None and self.process.poll() is None:
                    self.process.terminate()
                script = """$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'en-*' } | Select-Object -First 1
if (-not $voice) { throw 'No English voice installed' }
$s.SelectVoice($voice.VoiceInfo.Name)
$s.Rate = -2
$s.Speak('%s')
$s.Dispose()
""" % word.replace("'", "''")
                encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
                self.process = subprocess.Popen(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                    creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except OSError as error:
                self.error = f"Ошибка озвучки Windows: {error}"
        else:
            self.error = "Нет записи слова или доступного синтезатора английской речи."
        return False

    def shutdown(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
        if self.tts:
            try:
                self.tts.shutdown()
            except Exception:
                pass
