"""Portable profiles: MathCraft-style Android picker, browser, desktop dialogs."""

import json
import os
from pathlib import Path
import sys

from game_storage import MAX_BACKUP_BYTES, make_backup_bytes, read_backup_bytes


EXPORT_REQUEST = 4101
IMPORT_REQUEST = 4102


class ProfilePicker:
    def __init__(self, decoder=read_backup_bytes):
        self.pending = None
        self.result = None
        self._bound = False
        self._activity = None
        self.web_pending = False
        self.decoder = decoder
        self.request_code = None

    @property
    def busy(self):
        return self.pending is not None or self.web_pending or self.result is not None

    def _android(self):
        from android import activity
        from jnius import autoclass
        return activity, autoclass("org.kivy.android.PythonActivity").mActivity, autoclass("android.content.Intent")

    def _on_activity_result(self, request_code, result_code, intent):
        if self.pending is not None and request_code == self.request_code and self.result is None:
            self.result = (request_code, result_code, intent)

    def start(self, export, game, player=None):
        if self.busy:
            return False
        payload = make_backup_bytes(game, player) if export else None
        if sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ:
            activity, current, Intent = self._android()
            if not self._bound:
                activity.bind(on_activity_result=self._on_activity_result)
                self._bound = True
                self._activity = activity
            intent = Intent(Intent.ACTION_CREATE_DOCUMENT if export else Intent.ACTION_OPEN_DOCUMENT)
            intent.setType("application/json")
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            if export:
                intent.putExtra(Intent.EXTRA_TITLE, "EnglishCraft-profile.json")
            self.pending = payload if export else True
            self.request_code = EXPORT_REQUEST if export else IMPORT_REQUEST
            try:
                current.startActivityForResult(intent, self.request_code)
            except Exception:
                self.pending = None
                self.request_code = None
                raise
        elif sys.platform == "emscripten":
            import platform
            if export:
                platform.window.eval("""(() => {
                    const blob = new Blob([%s], {type:'application/json'});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a'); a.href = url;
                    a.download = 'EnglishCraft-profile.json';
                    document.body.appendChild(a); a.click(); a.remove();
                    setTimeout(() => URL.revokeObjectURL(url), 10000);
                })()""" % json.dumps(payload.decode("utf-8")))
                self.result = ("Профиль отправлен в загрузки браузера.", None)
            else:
                self.web_pending = True
                try:
                    platform.window.eval("""(() => {
                    window.snifferProfileResult = null;
                    const input = document.createElement('input');
                    input.type = 'file'; input.accept = '.json,application/json';
                    input.style.display = 'none'; document.body.appendChild(input);
                    input.oncancel = () => { window.snifferProfileResult = JSON.stringify({cancel:true}); input.remove(); };
                    input.onchange = async () => {
                        try {
                            const file = input.files[0];
                            if (!file) { window.snifferProfileResult = JSON.stringify({cancel:true}); return; }
                            if (file.size > %d) throw new Error('Файл профиля слишком большой');
                            window.snifferProfileResult = JSON.stringify({content:await file.text()});
                        } catch(e) { window.snifferProfileResult = JSON.stringify({error:String(e)}); }
                        finally { input.remove(); }
                    };
                    input.click();
                    })()""" % MAX_BACKUP_BYTES)
                except Exception:
                    self.web_pending = False
                    raise
        else:
            from tkinter import Tk, filedialog
            root = Tk()
            root.withdraw()
            try:
                if export:
                    path = filedialog.asksaveasfilename(title="Выгрузить профиль", initialfile="EnglishCraft-profile.json",
                                                      defaultextension=".json", filetypes=[("JSON", "*.json")])
                    if path:
                        Path(path).write_bytes(payload)
                        self.result = ("Профиль сохранён в выбранный файл.", None)
                    else:
                        self.result = ("Выбор файла отменён.", None)
                else:
                    path = filedialog.askopenfilename(title="Загрузить профиль", filetypes=[("JSON", "*.json")])
                    if path:
                        with Path(path).open("rb") as file:
                            content = file.read(MAX_BACKUP_BYTES + 1)
                        self.result = ("Профиль прочитан.", self.decoder(content))
                    else:
                        self.result = ("Выбор файла отменён.", None)
            finally:
                root.destroy()
        return True

    def poll(self):
        if self.web_pending:
            import platform
            value = platform.window.snifferProfileResult
            if not value:
                return None
            self.web_pending = False
            platform.window.snifferProfileResult = None
            try:
                result = json.loads(str(value))
                if result.get("cancel"):
                    return "Выбор файла отменён.", None
                if result.get("error"):
                    raise ValueError(result["error"])
                return "Профиль прочитан.", self.decoder(result["content"].encode("utf-8"))
            except Exception as error:
                return f"Ошибка профиля: {error}", None
        if self.result is None:
            return None
        result, self.result = self.result, None
        if len(result) == 2:
            return result
        request_code, result_code, intent = result
        payload, self.pending = self.pending, None
        self.request_code = None
        if result_code != -1 or intent is None:
            return "Выбор файла отменён.", None
        try:
            _, current, _ = self._android()
            uri = intent.getData()
            if uri is None:
                raise ValueError("Файл не выбран")
            resolver = current.getContentResolver()
            descriptor = resolver.openFileDescriptor(uri, "wt" if request_code == EXPORT_REQUEST else "r")
            if descriptor is None:
                raise OSError("Не удалось открыть файл")
            fd = descriptor.detachFd()
            if request_code == EXPORT_REQUEST:
                with os.fdopen(fd, "wb") as file:
                    file.write(payload)
                    # fdopen does not itself truncate an already-open descriptor.
                    # Also handle seekable providers that ignore the mode's 't'.
                    if file.seekable():
                        file.truncate()
                return "Профиль сохранён. Сохраните файл перед удалением игры.", None
            with os.fdopen(fd, "rb") as file:
                content = file.read(MAX_BACKUP_BYTES + 1)
            return "Профиль прочитан.", self.decoder(content)
        except Exception as error:
            return f"Ошибка профиля: {error}", None

    def close(self):
        """Release the Activity's reference and any unfinished transfer payload."""
        if self._bound:
            self._activity.unbind(on_activity_result=self._on_activity_result)
            self._bound = False
            self._activity = None
        self.pending = self.result = self.request_code = None
        self.web_pending = False
