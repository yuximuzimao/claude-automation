from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LuaParseError(ValueError):
    pass


@dataclass
class LuaTableParser:
    text: str
    pos: int = 0

    def parse(self) -> Any:
        self._skip_ws()
        if self.text.startswith("return", self.pos):
            self.pos += len("return")
        value = self._parse_value()
        self._skip_ws()
        return value

    def _peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def _skip_ws(self) -> None:
        while self.pos < len(self.text):
            if self.text[self.pos].isspace():
                self.pos += 1
                continue
            if self.text.startswith("--", self.pos):
                end = self.text.find("\n", self.pos)
                self.pos = len(self.text) if end == -1 else end + 1
                continue
            break

    def _parse_value(self) -> Any:
        self._skip_ws()
        char = self._peek()
        if char == "{":
            return self._parse_table()
        if char in {'"', "'"}:
            return self._parse_string()
        if char == "[" and self.text.startswith("[[", self.pos):
            return self._parse_long_string()
        if char in "+-" or char.isdigit():
            return self._parse_number()
        ident = self._parse_identifier()
        if ident == "nil":
            return None
        if ident == "true":
            return True
        if ident == "false":
            return False
        raise LuaParseError(f"Unsupported identifier {ident!r} at {self.pos}")

    def _parse_identifier(self) -> str:
        start = self.pos
        while self.pos < len(self.text) and (
            self.text[self.pos].isalnum() or self.text[self.pos] in "_.$"
        ):
            self.pos += 1
        if self.pos == start:
            raise LuaParseError(f"Expected identifier at {self.pos}: {self.text[self.pos:self.pos+40]!r}")
        return self.text[start:self.pos]

    def _parse_number(self) -> int | float:
        start = self.pos
        if self._peek() in "+-":
            self.pos += 1
        while self.pos < len(self.text) and self.text[self.pos].isdigit():
            self.pos += 1
        if self.pos < len(self.text) and self.text[self.pos] == ".":
            self.pos += 1
            while self.pos < len(self.text) and self.text[self.pos].isdigit():
                self.pos += 1
        if self.pos < len(self.text) and self.text[self.pos] in "eE":
            self.pos += 1
            if self._peek() in "+-":
                self.pos += 1
            while self.pos < len(self.text) and self.text[self.pos].isdigit():
                self.pos += 1
        raw = self.text[start:self.pos]
        return float(raw) if any(c in raw for c in ".eE") else int(raw)

    def _parse_string(self) -> str:
        quote = self._peek()
        self.pos += 1
        chars: list[str] = []
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == quote:
                return "".join(chars)
            if char != "\\":
                chars.append(char)
                continue
            if self.pos >= len(self.text):
                raise LuaParseError("Unterminated escape")
            esc = self.text[self.pos]
            self.pos += 1
            mapping = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}
            if esc in mapping:
                chars.append(mapping[esc])
            elif esc in "\\\"'":
                chars.append(esc)
            elif esc.isdigit():
                digits = esc
                for _ in range(2):
                    if self.pos < len(self.text) and self.text[self.pos].isdigit():
                        digits += self.text[self.pos]
                        self.pos += 1
                chars.append(chr(int(digits)))
            elif esc == "z":
                self._skip_ws()
            else:
                chars.append(esc)
        raise LuaParseError("Unterminated string")

    def _parse_long_string(self) -> str:
        self.pos += 2
        end = self.text.find("]]", self.pos)
        if end == -1:
            raise LuaParseError("Unterminated long string")
        value = self.text[self.pos:end]
        self.pos = end + 2
        return value

    def _parse_table(self) -> dict[Any, Any]:
        if self._peek() != "{":
            raise LuaParseError(f"Expected table at {self.pos}")
        self.pos += 1
        result: dict[Any, Any] = {}
        next_index = 1
        while True:
            self._skip_ws()
            if self._peek() == "}":
                self.pos += 1
                return result
            if self._peek() == "[":
                self.pos += 1
                key = self._parse_value()
                self._skip_ws()
                if self._peek() != "]":
                    raise LuaParseError(f"Expected ] at {self.pos}")
                self.pos += 1
                self._skip_ws()
                if self._peek() != "=":
                    raise LuaParseError(f"Expected = at {self.pos}")
                self.pos += 1
                value = self._parse_value()
                result[key] = value
            else:
                saved = self.pos
                key: Any | None = None
                if self._peek().isalpha() or self._peek() == "_":
                    ident = self._parse_identifier()
                    self._skip_ws()
                    if self._peek() == "=":
                        self.pos += 1
                        key = ident
                        value = self._parse_value()
                    else:
                        self.pos = saved
                        value = self._parse_value()
                else:
                    value = self._parse_value()
                if key is None:
                    while next_index in result:
                        next_index += 1
                    result[next_index] = value
                    next_index += 1
                else:
                    result[key] = value
            self._skip_ws()
            if self._peek() in ",;":
                self.pos += 1


def parse_embedded_table_text(text: str, source: str = "<memory>") -> dict[Any, Any]:
    start = text.find("[[return")
    if start == -1:
        start = text.find("[[\nreturn")
    if start == -1:
        raise LuaParseError(f"No embedded return table found in {source}")
    start += 2
    end = text.rfind("]]" )
    if end == -1 or end <= start:
        raise LuaParseError(f"No closing long string found in {source}")
    parsed = LuaTableParser(text[start:end]).parse()
    if not isinstance(parsed, dict):
        raise LuaParseError(f"Expected top-level table in {source}")
    return parsed


def extract_embedded_table(path: Path) -> dict[Any, Any]:
    return parse_embedded_table_text(
        path.read_text(encoding="utf-8", errors="strict"),
        str(path),
    )


def seq(table: Any) -> list[Any]:
    if not isinstance(table, dict):
        return []
    return [table[index] for index in sorted(k for k in table if isinstance(k, int) and k >= 1)]
