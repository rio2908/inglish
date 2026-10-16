"""Local named players, isolated saves and non-destructive import/migration."""

import copy
import uuid

from game_logic import new_game, normalize_game
from game_storage import PLAYERS_FORMAT, read_save_document, write_save_document


class StaleProfileError(ValueError):
    """The caller is trying to save an older in-memory copy of this player."""


def player_name(value):
    return " ".join("".join(c for c in value if c.isprintable()).split())[:20] if isinstance(value, str) else ""


class PlayerStore:
    def __init__(self, path=None):
        self.path = path
        self._revisions = {}

    def _write(self, document):
        write_save_document(document, self.path)

    def _read(self):
        raw = read_save_document(self.path)
        if raw is None:
            return {"format": PLAYERS_FORMAT, "version": 2, "last_player": None, "profiles": {}}
        if not isinstance(raw, dict):
            raise ValueError("Файл игроков повреждён; прежние данные не перезаписаны")
        if raw.get("format") != PLAYERS_FORMAT:
            if not any(key in raw for key in ("cards", "correct_answers", "session", "pet_name", "zoo")):
                raise ValueError("Неизвестный формат сохранения; данные не перезаписаны")
            identity = uuid.uuid4().hex
            raw = {"format": PLAYERS_FORMAT, "version": 2, "last_player": identity,
                   "profiles": {identity: {"name": "Сохранённая игра", "game": normalize_game(raw), "revision": 0}}}
            self._write(raw)
        if type(raw.get("version")) is not int or raw["version"] not in (1, 2) or not isinstance(raw.get("profiles"), dict):
            raise ValueError("Версия файла игроков не поддерживается")
        names = set()
        for identity, record in raw["profiles"].items():
            if (not isinstance(identity, str) or not identity or len(identity) > 64 or not isinstance(record, dict)
                    or not player_name(record.get("name")) or not isinstance(record.get("game"), dict)
                    or type(record.get("revision", 0)) is not int or record.get("revision", 0) < 0):
                raise ValueError("Профиль игрока повреждён; данные не перезаписаны")
            name = player_name(record["name"]).casefold()
            if name in names:
                raise ValueError("В сохранении повторяются имена игроков")
            names.add(name)
        if raw["version"] == 1:
            raw["version"] = 2
            for record in raw["profiles"].values():
                record.setdefault("revision", 0)
            # Old clients reject v2 instead of silently overwriting newer games.
            self._write(raw)
        return raw

    def list_players(self):
        document = self._read()
        players = [{"id": identity, "name": player_name(record["name"]), "game": normalize_game(record["game"])}
                   for identity, record in document["profiles"].items()]
        return sorted(players, key=lambda record: (record["id"] != document.get("last_player"), record["name"].casefold()))

    def _unique_name(self, document, name, except_id=None):
        name = player_name(name)
        if not name:
            raise ValueError("Напиши имя игрока")
        if any(identity != except_id and player_name(record["name"]).casefold() == name.casefold()
               for identity, record in document["profiles"].items()):
            raise ValueError("Такой игрок уже есть. Выбери его в списке.")
        return name

    def create_player(self, name, game=None, identity=None):
        document = self._read()
        name = self._unique_name(document, name)
        identity = identity or uuid.uuid4().hex
        if identity in document["profiles"]:
            raise ValueError("Этот игрок уже есть")
        document["profiles"][identity] = {"name": name, "game": normalize_game(game) if game is not None else new_game(), "revision": 0}
        document["last_player"] = identity
        self._write(document)
        self._revisions[identity] = 0
        return identity

    def metadata(self, identity):
        record = self._read()["profiles"][identity]
        return {"id": identity, "name": player_name(record["name"])}

    def revision(self, identity):
        return self._read()["profiles"][identity].get("revision", 0)

    def load_game(self, identity):
        return self.load_profile(identity)["game"]

    def load_profile(self, identity):
        record = self._read()["profiles"][identity]
        revision = record.get("revision", 0)
        self._revisions[identity] = revision
        return {"id": identity, "name": player_name(record["name"]), "revision": revision,
                "game": normalize_game(copy.deepcopy(record["game"]))}

    def save_game(self, identity, game, *, expected_revision=None, replace=False):
        document = self._read()
        if identity not in document["profiles"]:
            raise ValueError("Игрок не найден; выбери профиль заново")
        record = document["profiles"][identity]
        current = record.get("revision", 0)
        expected = self._revisions.get(identity) if expected_revision is None else expected_revision
        if not replace and expected != current:
            raise StaleProfileError("Профиль изменён в другом окне. Старый прогресс не перезаписал свежий.")
        document["profiles"][identity]["game"] = normalize_game(game)
        record["revision"] = current + 1
        document["last_player"] = identity
        self._write(document)
        self._revisions[identity] = current + 1
        return current + 1

    def select_player(self, identity):
        document = self._read()
        if identity not in document["profiles"]:
            raise ValueError("Игрок не найден")
        document["last_player"] = identity
        self._write(document)

    def rename_player(self, identity, name):
        document = self._read()
        name = self._unique_name(document, name, identity)
        if identity not in document["profiles"]:
            raise ValueError("Игрок не найден")
        document["profiles"][identity]["name"] = name
        self._write(document)
        return name

    def import_target(self, backup, current_id=None):
        document = self._read()
        owner = backup.get("player")
        if owner is None:
            if current_id not in document["profiles"]:
                return "register", None
            return "replace", current_id
        if owner["id"] in document["profiles"]:
            matching_id = owner["id"]
        else:
            matching_id = next((identity for identity, record in document["profiles"].items()
                                if player_name(record["name"]).casefold() == player_name(owner["name"]).casefold()), None)
        if matching_id is not None:
            if matching_id != current_id:
                name = document["profiles"][matching_id]["name"]
                raise ValueError(f"Игрок «{name}» уже есть. Сначала выбери его; чужой профиль не заменён.")
            return "replace", matching_id
        return "create", owner["name"]

    def restore_backup(self, backup, current_id=None):
        mode, target = self.import_target(backup, current_id)
        if mode == "replace":
            self.save_game(target, backup["game"], replace=True)
            return target
        if mode == "create":
            return self.create_player(target, backup["game"], backup["player"]["id"])
        raise ValueError("Сначала укажи имя игрока для этой копии")
