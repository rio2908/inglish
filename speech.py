"""Offline word playback: Android system TTS, or optional pre-recorded WAVs."""

from pathlib import Path
import os
import sys

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
        if sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ:
            self._init_android()

    def _init_android(self):
        try:
            from jnius import PythonJavaClass, autoclass, java_method

            speech = self

            class InitListener(PythonJavaClass):
                __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
                __javacontext__ = "app"

                @java_method("(I)V")
                def onInit(self, status):
                    speech.ready = status == 0

            self.listener = InitListener()
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            self.tts = autoclass("android.speech.tts.TextToSpeech")(activity, self.listener)
            self.locale = autoclass("java.util.Locale").US
        except Exception:
            self.tts = None

    def tick(self):
        if self.pending and self.tts and self.ready:
            word = self.pending
            self.pending = None
            try:
                self.tts.setLanguage(self.locale)
                self.tts.setSpeechRate(0.82)
                self.tts.speak(word, self.tts.QUEUE_FLUSH, None, word)
            except Exception:
                self.ready = False

    def speak(self, word):
        path = self.audio_dir / f"{word}.wav"
        if path.is_file() and pygame.mixer.get_init():
            try:
                if word not in self.cache:
                    self.cache[word] = pygame.mixer.Sound(str(path))
                self.cache[word].play()
                return True
            except pygame.error:
                pass
        if self.tts:
            self.pending = word
            self.tick()
            return True
        if sys.platform == "emscripten":
            try:
                import platform
                window = platform.window
                try:
                    utterance = window.SpeechSynthesisUtterance.new(word)
                except AttributeError:
                    utterance = window.SpeechSynthesisUtterance(word)
                utterance.lang = "en-US"
                utterance.rate = 0.82
                window.speechSynthesis.cancel()
                window.speechSynthesis.speak(utterance)
                return True
            except Exception:
                pass
        return False

    def shutdown(self):
        if self.tts:
            try:
                self.tts.shutdown()
            except Exception:
                pass
