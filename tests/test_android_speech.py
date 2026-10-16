import os
import gc
import weakref
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
if find_spec("pygame") is None:
    raise unittest.SkipTest("Speech integration needs pygame")

from speech import Speech


class JavaString:
    def __init__(self, value):
        self.value = value


class Bundle(dict):
    pass


class HashMap(dict):
    def put(self, key, value):
        self[key] = value


def java_modules(engine, run_on_ui_thread=lambda function: function):
    def create_engine(activity, listener):
        listener.onInit(0)
        return engine

    classes = {
        "org.kivy.android.PythonActivity": SimpleNamespace(mActivity="activity"),
        "java.util.Locale": lambda language, country: (language, country),
        "java.lang.String": JavaString,
        "android.os.Bundle": Bundle,
        "java.util.HashMap": HashMap,
        "android.speech.tts.TextToSpeech": create_engine,
    }
    return {"jnius": SimpleNamespace(PythonJavaClass=object, autoclass=lambda name: classes[name],
                                      cast=lambda name, value: value, java_method=lambda signature: lambda function: function),
            "android.runnable": SimpleNamespace(run_on_ui_thread=run_on_ui_thread)}


class AndroidSpeechTests(unittest.TestCase):
    def test_native_listener_does_not_keep_shutdown_speech_alive(self):
        engine = Mock()
        with patch.dict("sys.modules", java_modules(engine)), patch("speech.sys.platform", "android"):
            speech = Speech(Path("no-recordings"))
            listener = speech.listener  # Simulate a listener still owned by Java.
            reference = weakref.ref(speech)
            speech.shutdown()
            del speech
            gc.collect()
            self.assertIsNone(reference())
            listener.onInit(0)

    def test_shutdown_releases_cached_audio(self):
        speech = Speech(Path("no-recordings"))
        sound = Mock()
        reference = weakref.ref(sound)
        speech.cache["cat"] = sound
        del sound
        speech.shutdown()
        gc.collect()
        self.assertIsNone(reference())

    def create_ready(self, engine):
        speech = Speech(Path("no-recordings"))
        speech.android = True
        speech.ready = True
        speech.tts = engine
        speech.locale = "en-US"
        return speech

    def test_android_speak_uses_typed_java_arguments_instead_of_ambiguous_none(self):
        engine = Mock()
        engine.setLanguage.return_value = 0

        def speak(*args):
            if isinstance(args[0], str) or args[2] is None:
                raise TypeError("No matching Java overload for Python str/None")
            self.assertIsInstance(args[0], JavaString)
            self.assertEqual(args[0].value, "hello")
            self.assertIsInstance(args[2], Bundle)
            return 0

        engine.speak.side_effect = speak
        speech = self.create_ready(engine)
        with patch.dict("sys.modules", java_modules(engine)):
            self.assertTrue(speech.speak("hello"))
        self.assertEqual(speech.error, "")

    def test_legacy_android_overload_is_used_if_modern_binding_is_unavailable(self):
        engine = Mock()
        engine.setLanguage.return_value = 0

        def speak(*args):
            if len(args) == 4:
                raise TypeError("CharSequence overload unavailable in this binding")
            self.assertEqual(len(args), 3)
            self.assertIsInstance(args[2], HashMap)
            return 0

        engine.speak.side_effect = speak
        speech = self.create_ready(engine)
        with patch.dict("sys.modules", java_modules(engine)):
            self.assertTrue(speech.speak("hello"))
        self.assertEqual(engine.speak.call_count, 2)

    def test_android_exception_is_not_shown_as_program_text_to_the_child(self):
        engine = Mock()
        engine.setLanguage.return_value = 0
        engine.speak.side_effect = RuntimeError("org.jnius.JavaException: internal stack trace")
        speech = self.create_ready(engine)
        with patch.dict("sys.modules", java_modules(engine)), self.assertLogs("speech", level="WARNING"):
            self.assertFalse(speech.speak("hello"))
        self.assertNotIn("org.jnius", speech.error)
        self.assertNotIn("stack trace", speech.error)
        self.assertIn("org.jnius", speech.last_error)

    def test_stop_cancels_an_already_queued_android_ui_utterance(self):
        tasks = []

        def deferred(function):
            return lambda *args: tasks.append(lambda: function(*args))

        engine = Mock()
        engine.setLanguage.return_value = 0
        engine.speak.return_value = 0
        speech = self.create_ready(engine)
        with patch.dict("sys.modules", java_modules(engine, deferred)):
            self.assertTrue(speech.speak("hello"))
            speech.stop()
            for task in tasks[:]:
                task()
        engine.speak.assert_not_called()

    def test_failed_existing_engine_is_reinitialized_on_the_next_tap(self):
        old_engine = Mock()
        replacement = Mock()
        replacement.setLanguage.return_value = 0
        replacement.speak.return_value = 0
        speech = self.create_ready(old_engine)
        speech.ready = False
        speech._init_failed = True
        with patch.dict("sys.modules", java_modules(replacement)):
            self.assertTrue(speech.speak("hello"))
        self.assertIs(speech.tts, replacement)
        self.assertTrue(speech.ready)
        old_engine.shutdown.assert_called_once()
        replacement.speak.assert_called_once()

    def test_shutdown_ignores_delayed_initialization_and_callback(self):
        tasks = []

        def deferred(function):
            return lambda *args: tasks.append(lambda: function(*args))

        engine = Mock()
        with patch.dict("sys.modules", java_modules(engine, deferred)), patch("speech.sys.platform", "android"):
            speech = Speech(Path("no-recordings"))
            listener = speech.listener
            speech.shutdown()
            for task in tasks[:]:
                task()
            listener.onInit(0)
        self.assertIsNone(speech.tts)
        self.assertFalse(speech.ready)
        engine.speak.assert_not_called()


if __name__ == "__main__":
    unittest.main()
