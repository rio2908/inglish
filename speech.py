"""Offline word playback: Android system TTS, or optional pre-recorded WAVs."""

from pathlib import Path
import base64
import json
import logging
import os
import subprocess
import sys
import time
import weakref

import pygame


LOGGER = logging.getLogger(__name__)


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
        self.last_error = ""
        self.started = time.monotonic()
        self.process = None
        self.android = sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ
        self._engine_generation = 0
        self._utterance_generation = 0
        self._init_failed = False
        self._closed = False
        if self.android:
            self._init_android()

    def _init_android(self):
        self._engine_generation += 1
        generation = self._engine_generation
        self.started = time.monotonic()
        self.ready = False
        self._init_failed = False
        old_engine, self.tts = self.tts, None
        try:
            from jnius import PythonJavaClass, autoclass, java_method
            from android.runnable import run_on_ui_thread

            speech_ref = weakref.ref(self)

            class InitListener(PythonJavaClass):
                __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
                __javacontext__ = "app"

                @java_method("(I)V")
                def onInit(self, status):
                    speech = speech_ref()
                    if speech is None or speech._closed or generation != speech._engine_generation:
                        return
                    speech.ready = status == 0
                    speech._init_failed = status != 0
                    if status != 0:
                        speech._android_error("Не удалось запустить озвучку. Проверь настройки синтеза речи Android.", f"onInit status={status}")

            listener = InitListener()
            self.listener = listener
            # SDL runs Python on a worker thread. Create/use TTS on Android's UI thread.
            @run_on_ui_thread
            def initialize():
                try:
                    if old_engine is not None:
                        try:
                            old_engine.shutdown()
                        except Exception as shutdown_error:
                            LOGGER.debug("Android TTS old engine shutdown failed: %s", shutdown_error)
                    if self._closed or generation != self._engine_generation:
                        return
                    activity = autoclass("org.kivy.android.PythonActivity").mActivity
                    self.locale = autoclass("java.util.Locale")("en", "US")
                    engine = autoclass("android.speech.tts.TextToSpeech")(activity, listener)
                    if self._closed or generation != self._engine_generation:
                        engine.shutdown()
                        return
                    self.tts = engine
                except Exception as error:
                    if self._closed or generation != self._engine_generation:
                        return
                    self._init_failed = True
                    self._android_error("Озвучка Android недоступна. Проверь настройки синтеза речи.", error)
            initialize()
        except Exception as error:
            self.tts = None
            self._init_failed = True
            self._android_error("Не удалось включить озвучку Android. Попробуй перезапустить игру.", error)

    def _android_error(self, message, detail):
        self.error = message
        self.last_error = f"{type(detail).__name__}: {detail}" if isinstance(detail, Exception) else str(detail)
        if isinstance(detail, Exception):
            LOGGER.warning("Android TTS: %s", self.last_error, exc_info=True)
        else:
            LOGGER.info("Android TTS: %s", self.last_error)

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
        if self.pending and self.android and self._init_failed:
            self.pending = None
        elif self.pending and self.android and not self.ready and time.monotonic() - self.started > 15:
            self.pending = None
            self._init_failed = True
            self._android_error("Озвучка не запустилась. Проверь настройки синтеза речи Android.", "initialization timeout")
        if self.pending and self.tts and self.ready:
            word = self.pending
            self.pending = None
            self._speak_android(word)

    def _speak_android(self, word):
        engine = self.tts
        generation = self._utterance_generation

        def speak():
            if self._closed or generation != self._utterance_generation or engine is not self.tts or not self.ready:
                return
            try:
                language_status = engine.setLanguage(self.locale)
                if language_status < 0:
                    self.ready = False
                    self._init_failed = True
                    self._android_error("Скачайте английский голос в настройках озвучки Android.", f"setLanguage status={language_status}")
                    return
                from jnius import autoclass, cast
                java_text = autoclass("java.lang.String")(word)
                engine.setSpeechRate(0.82)
                try:
                    # Avoid ambiguous Python str/None conversion for CharSequence/Bundle.
                    params = autoclass("android.os.Bundle")()
                    result = engine.speak(cast("java.lang.CharSequence", java_text), 0, params, "sniffer-word")
                except Exception as binding_error:
                    LOGGER.debug("Android TTS modern overload failed: %s", binding_error)
                    params = autoclass("java.util.HashMap")()
                    params.put("utteranceId", "sniffer-word")
                    result = engine.speak(java_text, 0, params)
                if result < 0:
                    self.ready = False
                    self._init_failed = True
                    self._android_error("Не удалось озвучить слово. Проверь настройки синтеза речи Android.", f"speak status={result}")
                else:
                    self.last_error = ""
            except Exception as error:
                self.ready = False
                self._init_failed = True
                self._android_error("Не удалось озвучить слово. Попробуй ещё раз или перезапусти игру.", error)
        try:
            from android.runnable import run_on_ui_thread
            run_on_ui_thread(speak)()
        except Exception as error:
            self._android_error("Озвучка Android недоступна. Попробуй перезапустить игру.", error)

    def speak(self, word):
        self.error = ""
        if self._closed:
            return False
        self._utterance_generation += 1
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
            if self._init_failed or (not self.ready and time.monotonic() - self.started > 15):
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

    def stop(self):
        self._utterance_generation += 1
        self.pending = None
        self.error = ""
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
        self.process = None
        if self.tts:
            try:
                engine = self.tts
                if self.android:
                    from android.runnable import run_on_ui_thread
                    run_on_ui_thread(engine.stop)()
                else:
                    engine.stop()
            except Exception:
                pass

    def shutdown(self):
        self.stop()
        self._closed = True
        self.ready = False
        self._engine_generation += 1
        engine, self.tts = self.tts, None
        self.listener = None
        self.locale = None
        for sound in self.cache.values():
            sound.stop()
        self.cache.clear()
        if engine:
            try:
                if self.android:
                    from android.runnable import run_on_ui_thread
                    run_on_ui_thread(engine.shutdown)()
                else:
                    engine.shutdown()
            except Exception:
                pass
