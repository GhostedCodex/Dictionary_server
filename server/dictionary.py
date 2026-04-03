import json
import os
import threading
from datetime import datetime, timezone

from config import DICT_FILE, TS_ADDED, TS_UPDATED, TS_SEARCHED


def _now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


class Dictionary:
    """
    A thread-safe in memory dictionary backed by JSON file.

    All public methods acquire the lock before touching self._data,
    so multiple client threads can call them concurrently without
    race conditions.

    """

    def __init__(self, filepath: str = DICT_FILE):
        self._data: dict[str, dict] = {}  # in-memory dictionary
        self._lock = threading.Lock()  # mutex to protect access to self.data
        self._filepath = filepath
        self._load()

    # Private helpers or methods

    def _load(self) -> None:
        """Load entries from the JSON file into memory on startup."""
        if not os.path.exists(self._filepath):
            print(
                f"[Dictionary] No file found at {self._filepath}, starting empty.")
            return
        try:
            with open(self._filepath, 'r') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                print("[Dictionary] File format invalid — expected a JSON object.")
                return

            migrated = 0
            for k, v in data.items():
                key = k.lower()
                if isinstance(v, str):
                    # Migrate legacy flat format: "word": "definition"
                    now = _now()
                    self._data[key] = {
                        'definition': v,
                        TS_ADDED:    now,
                        TS_UPDATED:  now,
                        TS_SEARCHED: None,
                    }
                    migrated += 1
                elif isinstance(v, dict) and 'definition' in v:
                    self._data[key] = v
                else:
                    print(f"[Dictionary] Skipping malformed entry: '{k}'")

            msg = f"[Dictionary] Loaded {len(self._data)} entries from {self._filepath}"
            if migrated:
                msg += f" ({migrated} migrated from legacy format)"
            print(msg)

        except (json.JSONDecodeError, OSError) as e:
            print(f"[Dictionary] Failed to load file: {e}")

    def _save(self) -> None:
        """
        Persist current state to disk.
        Must only be called while self._lock is already held.
        """
        try:
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            with open(self._filepath, 'w') as f:
                json.dump(self._data, f, indent=2)
        except OSError as e:
            print(f"[Dictionary] Failed to save file: {e}")

    # PUBLIC API

    def search(self, word: str) -> str | None:
        """
        Return the definition string for word, or None if not found.
        Updates last_searched_at on every hit.
        """
        word = word.lower().strip()
        with self._lock:
            entry = self._data.get(word)
            if entry is None:
                return None
            entry[TS_SEARCHED] = _now()
            self._save()
            return entry['definition']

    def add(self, word: str, definition: str) -> bool:
        """
        Add or overwrite an entry, then persist to disk.
        - New word:      sets added_at and updated_at to now, last_searched_at to null.
        - Existing word: preserves added_at, updates updated_at to now.
        Returns True on success, False if inputs are blank.
        """
        word = word.lower().strip()
        definition = definition.strip()

        if not word or not definition:
            return False

        with self._lock:
            now = _now()
            existing = self._data.get(word)
            self._data[word] = {
                'definition': definition,
                TS_ADDED:    existing[TS_ADDED] if existing else now,
                TS_UPDATED:  now,
                TS_SEARCHED: existing.get(TS_SEARCHED) if existing else None,
            }
            self._save()
        return True

    def delete(self, word: str) -> bool:
        """
        Remove an entry if it exists, then persist to disk.
        Returns True if the entry was found and removed, False otherwise.
        """
        word = word.lower().strip()
        with self._lock:
            if word not in self._data:
                return False
            del self._data[word]
            self._save()
        return True

    def get_entry(self, word: str) -> dict | None:
        """
        Return the full entry dict (definition + all timestamps) for word,
        or None if not found. Does NOT update last_searched_at.
        Intended for the web UI, which needs metadata without side effects.
        """
        word = word.lower().strip()
        with self._lock:
            entry = self._data.get(word)
            return dict(entry) if entry else None

    def list_entries(self) -> list[dict]:
        """
        Return a list of all entries as dicts with a 'word' key added,
        sorted alphabetically. Used by the web UI to render the full table.
        """
        with self._lock:
            return sorted(
                [{'word': k, **v} for k, v in self._data.items()],
                key=lambda e: e['word']
            )

    def list_words(self) -> list[str]:
        """Return a sorted list of all words. Used by the TCP protocol LIST command."""
        with self._lock:
            return sorted(self._data.keys())

    def count(self) -> int:
        """Return the number of entries in the dictionary."""
        with self._lock:
            return len(self._data)
