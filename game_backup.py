"""Portable profiles: MathCraft-style Android picker, browser, desktop dialogs."""

import json
import os
from pathlib import Path
import sys

from game_storage import MAX_BACKUP_BYTES, make_backup_bytes, read_backup_bytes


EXPORT_REQUEST = 4101
IMPORT_REQUEST = 4102


class ProfilePicker:
    def __init__(self):
        self.pending = None
        self.result = None
        self._bound = False
        self.web_pending = False

    def _android(self):
        from android import activity
        from jnius import autoclass
        return activity, autoclass("org.kivy.android.PythonActivity").mActivity, autoclass("android.content.Intent")

    def _on_activity_result(self, request_code, result_code, intent):
        if request_code in (EXPORT_REQUEST, IMPORT_REQUEST):
            self.result = (request_code, result_code, intent)

    def start(self, export, game):
        if self.pending is not None or self.web_pending:
            return
        payload = make_backup_bytes(game) if export else None
        if sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ:
            activity, current, Intent = self._android()
            if not self._bound:
                activity.bind(on_activity_result=self._on_activity_result)
                self._bound = True
            intent = Intent(Intent.ACTION_CREATE_DOCUMENT if export else Intent.ACTION_OPEN_DOCUMENT)
            intent.setType("application/json")
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            if export:
                intent.putExtra(Intent.EXTRA_TITLE, "Inglish-profile.json")
            self.pending = payload if export else True
            try:
                current.startActivityForResult(intent, EXPORT_REQUEST if export else IMPORT_REQUEST)
            except Exception:
                self.pending = None
                raise
        elif sys.platform == "emscripten":
            import platform
            if export:
                platform.window.eval("""(() => {
                    const blob = new Blob([%s], {type:'application/json'});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a'); a.href = url;
                    a.download = 'Inglish-profile.json';
                    document.body.appendChild(a); a.click(); a.remove();
                    setTimeout(() => URL.revokeObjectURL(url), 10000);
                })()""" % json.dumps(payload.decode("utf-8")))
                self.result = ("Профиль отправлен в загрузки браузера.", None)
            else:
                self.web_pending = True
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
        else:
            from tkinter import Tk, filedialog
            root = Tk()
            root.withdraw()
            try:
                if export:
                    path = filedialog.asksaveasfilename(title="Выгрузить профиль", initialfile="Inglish-profile.json",
                                                      defaultextension=".json", filetypes=[("JSON", "*.json")])
                    if path:
                        Path(path).write_bytes(payload)
                        self.result = ("Профиль сохранён в выбранный файл.", None)
                else:
                    path = filedialog.askopenfilename(title="Загрузить профиль", filetypes=[("JSON", "*.json")])
                    if path:
                        with Path(path).open("rb") as file:
                            content = file.read(MAX_BACKUP_BYTES + 1)
                        self.result = ("Профиль прочитан.", read_backup_bytes(content))
            finally:
                root.destroy()

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
                return "Профиль прочитан.", read_backup_bytes(result["content"].encode("utf-8"))
            except Exception as error:
                return f"Ошибка профиля: {error}", None
        if self.result is None:
            return None
        result, self.result = self.result, None
        if len(result) == 2:
            return result
        request_code, result_code, intent = result
        payload, self.pending = self.pending, None
        if result_code != -1 or intent is None:
            return "Выбор файла отменён.", None
        try:
            _, current, _ = self._android()
            uri = intent.getData()
            if uri is None:
                raise ValueError("Файл не выбран")
            resolver = current.getContentResolver()
            descriptor = resolver.openFileDescriptor(uri, "w" if request_code == EXPORT_REQUEST else "r")
            if descriptor is None:
                raise OSError("Не удалось открыть файл")
            fd = descriptor.detachFd()
            if request_code == EXPORT_REQUEST:
                with os.fdopen(fd, "wb") as file:
                    file.write(payload)
                return "Профиль сохранён. Сохраните файл перед удалением игры.", None
            with os.fdopen(fd, "rb") as file:
                content = file.read(MAX_BACKUP_BYTES + 1)
            return "Профиль прочитан.", read_backup_bytes(content)
        except Exception as error:
            return f"Ошибка профиля: {error}", None
