"""Local named players, isolated saves and non-destructive import/migration."""

import copy
import uuid

from game_logic import new_game, normalize_game
from game_storage import PLAYERS_FORMAT, read_save_document, write_save_document


def player_name(value):
    return " ".join("".join(c for c in value if c.isprintable()).split())[:20] if isinstance(value, str) else ""


class PlayerStore:
    def __init__(self, path=None):
        self.path = path

    def _write(self, document):
        write_save_document(document, self.path)

    def _read(self):
        raw = read_save_document(self.path)
        if raw is None:
            return {"format": PLAYERS_FORMAT, "version": 1, "last_player": None, "profiles": {}}
        if not isinstance(raw, dict):
            raise ValueError("Файл игроков повреждён; прежние данные не перезаписаны")
        if raw.get("format") != PLAYERS_FORMAT:
            if not any(key in raw for key in ("cards", "correct_answers", "session", "pet_name", "zoo")):
                raise ValueError("Неизвестный формат сохранения; данные не перезаписаны")
            identity = uuid.uuid4().hex
            raw = {"format": PLAYERS_FORMAT, "version": 1, "last_player": identity,
                   "profiles": {identity: {"name": "Сохранённая игра", "game": normalize_game(raw)}}}
            self._write(raw)
        if raw.get("version") != 1 or not isinstance(raw.get("profiles"), dict):
            raise ValueError("Версия файла игроков не поддерживается")
        names = set()
        for identity, record in raw["profiles"].items():
            if (not isinstance(identity, str) or not identity or len(identity) > 64 or not isinstance(record, dict)
                    or not player_name(record.get("name")) or not isinstance(record.get("game"), dict)):
                raise ValueError("Профиль игрока повреждён; данные не перезаписаны")
            name = player_name(record["name"]).casefold()
            if name in names:
                raise ValueError("В сохранении повторяются имена игроков")
            names.add(name)
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
        document["profiles"][identity] = {"name": name, "game": normalize_game(game) if game is not None else new_game()}
        document["last_player"] = identity
        self._write(document)
        return identity

    def metadata(self, identity):
        record = self._read()["profiles"][identity]
        return {"id": identity, "name": player_name(record["name"])}

    def load_game(self, identity):
        return normalize_game(copy.deepcopy(self._read()["profiles"][identity]["game"]))

    def save_game(self, identity, game):
        document = self._read()
        if identity not in document["profiles"]:
            raise ValueError("Игрок не найден; выбери профиль заново")
        document["profiles"][identity]["game"] = normalize_game(game)
        document["last_player"] = identity
        self._write(document)

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
            self.save_game(target, backup["game"])
            return target
        if mode == "create":
            return self.create_player(target, backup["game"], backup["player"]["id"])
        raise ValueError("Сначала укажи имя игрока для этой копии")
