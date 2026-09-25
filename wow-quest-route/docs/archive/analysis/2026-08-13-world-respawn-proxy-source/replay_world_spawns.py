#!/usr/bin/env python3
import ast
import gzip
import json
import re
import sqlite3
import sys
from pathlib import Path

TABLES = ("creature", "gameobject", "creature_spawn_entry", "gameobject_spawn_entry")
SPAWN_TABLES = ("creature", "gameobject")


def split_statements(text: str):
    out, buf = [], []
    quote = None
    line_comment = block_comment = False
    i = 0
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if c == "\n":
                line_comment = False
                buf.append(c)
            i += 1
            continue
        if block_comment:
            if c == "*" and n == "/":
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if quote:
            buf.append(c)
            if c == "\\" and quote in ("'", '"') and n:
                buf.append(n)
                i += 2
                continue
            if c == quote:
                if n == quote:
                    buf.append(n)
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if c in ("'", '"', "`"):
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "-" and n == "-" and (i + 2 == len(text) or text[i + 2].isspace()):
            line_comment = True
            i += 2
            continue
        if c == "#":
            line_comment = True
            i += 1
            continue
        if c == "/" and n == "*":
            block_comment = True
            i += 2
            continue
        if c == ";":
            statement = "".join(buf).strip()
            if statement:
                out.append(statement)
            buf = []
        else:
            buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def targets(profile: Path):
    data = json.loads(profile.read_text())
    result = {"creature": set(), "gameobject": set()}
    for quest in data["quests"].values():
        for component in quest.get("components", []):
            for source in component.get("sources", []):
                entry = source.get("entity_id")
                if not isinstance(entry, int):
                    continue
                if source.get("kind") == "npc":
                    result["creature"].add(entry)
                elif source.get("kind") == "object":
                    result["gameobject"].add(entry)
    return result


def parse_scalar(raw: str):
    raw = raw.strip()
    if raw.upper() == "NULL":
        return None
    if any(c in raw for c in ".eE"):
        return float(raw)
    return int(raw)


def create_tables(conn, schemas):
    for table in SPAWN_TABLES:
        defs = []
        for column in schemas[table]:
            kind = "REAL" if column.lower() in {"position_x", "position_y", "position_z", "orientation", "rotation0", "rotation1", "rotation2", "rotation3", "spawndist"} else "INTEGER"
            defs.append(f"`{column}` {kind}")
        defs.append("PRIMARY KEY (`guid`)")
        conn.execute(f"CREATE TABLE `{table}` ({','.join(defs)})")
        conn.execute(f"CREATE INDEX `idx_{table}_id` ON `{table}` (`id`)")
        conn.execute(f"CREATE INDEX `idx_{table}_map` ON `{table}` (`map`)")
    for table in ("creature_spawn_entry", "gameobject_spawn_entry"):
        conn.execute(f"CREATE TABLE `{table}` (`guid` INTEGER, `entry` INTEGER, PRIMARY KEY (`guid`,`entry`))")
        conn.execute(f"CREATE INDEX `idx_{table}_entry` ON `{table}` (`entry`)")


def load_base(conn, dump: Path):
    schemas = {table: [] for table in TABLES}
    creating = None
    create_re = re.compile(r"^CREATE TABLE `(creature|gameobject|creature_spawn_entry|gameobject_spawn_entry)`", re.I)
    insert_re = re.compile(r"^insert\s+(?:ignore\s+)?into\s+`(creature|gameobject|creature_spawn_entry|gameobject_spawn_entry)`(?:\s*\(([^)]*)\))?\s+values\s+", re.I)
    totals = {table: 0 for table in TABLES}
    with gzip.open(dump, "rt", encoding="utf-8", errors="strict") as stream:
        for line in stream:
            create_match = create_re.match(line)
            if create_match:
                creating = create_match.group(1).lower()
                continue
            if creating:
                column_match = re.match(r"\s*`([^`]+)`\s+", line)
                if column_match:
                    schemas[creating].append(column_match.group(1))
                if line.startswith(") ENGINE="):
                    creating = None
                continue
    if not all(schemas[t] for t in TABLES):
        raise RuntimeError(f"target schemas incomplete: {schemas}")
    create_tables(conn, schemas)
    with gzip.open(dump, "rt", encoding="utf-8", errors="strict") as stream:
        for line in stream:
            match = insert_re.match(line)
            if not match:
                continue
            table = match.group(1).lower()
            columns = ([part.strip().strip("`") for part in match.group(2).split(",")]
                       if match.group(2) else schemas[table])
            body = line[match.end():].strip()
            if body.endswith(";"):
                body = body[:-1]
            if not body.startswith("(") or not body.endswith(")"):
                raise ValueError(f"unexpected base VALUES framing for {table}")
            placeholders = ",".join("?" for _ in columns)
            sql = f"INSERT INTO `{table}` ({','.join('`'+c+'`' for c in columns)}) VALUES ({placeholders})"
            batch = []
            for tuple_raw in body[1:-1].split("),("):
                parts = tuple_raw.split(",")
                if len(parts) != len(columns):
                    raise ValueError(f"unexpected base value count in {table}: {len(parts)} != {len(columns)}")
                batch.append(tuple(map(parse_scalar, parts)))
                if len(batch) >= 10000:
                    conn.executemany(sql, batch)
                    totals[table] += len(batch)
                    batch.clear()
            if batch:
                conn.executemany(sql, batch)
                totals[table] += len(batch)
    conn.commit()
    return schemas, totals


def safe_number(expression: str, variables):
    expr = re.sub(r"@(\w+)", lambda m: str(variables[m.group(1).upper()]), expression.strip())
    tree = ast.parse(expr, mode="eval")
    allowed = (ast.Expression, ast.Constant, ast.UnaryOp, ast.UAdd, ast.USub, ast.BinOp,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
    if not all(isinstance(node, allowed) for node in ast.walk(tree)):
        raise ValueError(f"unsafe numeric expression: {expression}")
    value = eval(compile(tree, "<sql-number>", "eval"), {"__builtins__": {}}, {})
    return int(value) if isinstance(value, float) and value.is_integer() else value


def substitute_vars(sql: str, variables, unresolved=None, context=None):
    def repl(match):
        name = match.group(1).upper()
        if name not in variables:
            if unresolved is not None:
                unresolved.add((str(context), name))
            return "NULL"
        return str(variables[name])
    return re.sub(r"@(\w+)", repl, sql)


def target_fingerprint(conn, wanted):
    result = {}
    for table in SPAWN_TABLES:
        mapping = table + "_spawn_entry"
        ids = sorted(wanted[table])
        marks = ",".join("?" for _ in ids)
        sql = f"""
          SELECT q.entry, s.guid, s.id, s.map, s.position_x, s.position_y, s.position_z,
                 s.spawntimesecsmin, s.spawntimesecsmax
          FROM `{table}` s
          JOIN (
            SELECT id AS entry, guid FROM `{table}` WHERE id IN ({marks})
            UNION
            SELECT entry, guid FROM `{mapping}` WHERE entry IN ({marks})
          ) q ON q.guid=s.guid
          ORDER BY q.entry, s.guid
        """
        rows = conn.execute(sql, ids + ids).fetchall()
        result[table] = {int(entry): [] for entry in ids}
        for row in rows:
            result[table][int(row[0])].append(tuple(row[1:]))
    return result


def changed_entries(before, after):
    changed = {"creature": [], "gameobject": []}
    for table in SPAWN_TABLES:
        for entry in before[table]:
            if before[table][entry] != after[table][entry]:
                changed[table].append(entry)
    return changed


def direct_target_table(stmt: str):
    compact = re.sub(r"\s+", " ", stmt.strip())
    match = re.match(r"^(?:INSERT(?: IGNORE)? INTO|REPLACE INTO|DELETE FROM|UPDATE)\s+`?([A-Za-z0-9_]+)`?(?:\s|\(|$)", compact, re.I)
    return match.group(1).lower() if match else None


def replay(conn, repo: Path, wanted):
    files = sorted((repo / "Updates").glob("[0-9]*.sql")) + sorted((repo / "Updates/Instances").glob("[0-9]*.sql"))
    variables = {}
    changes = []
    executed = 0
    ignored_target_mentions = []
    unresolved_variables = set()
    for path in files:
        before = target_fingerprint(conn, wanted)
        for ordinal, stmt in enumerate(split_statements(path.read_text()), 1):
            compact = re.sub(r"\s+", " ", stmt.strip())
            set_match = re.match(r"^SET\s+@(\w+)\s*(?::=|=)\s*(.+)$", compact, re.I)
            if set_match:
                variables[set_match.group(1).upper()] = safe_number(set_match.group(2), variables)
                continue
            low = compact.lower()
            if low.startswith("create table tmp_creature (select") or low.startswith("create table tmp_gameobject (select"):
                sql = re.sub(r"(?i)^CREATE TABLE (tmp_(?:creature|gameobject))\s*\(SELECT", r"CREATE TABLE \1 AS SELECT", compact)
                if sql.endswith(")"):
                    sql = sql[:-1]
                conn.execute(substitute_vars(sql, variables, unresolved_variables, path.relative_to(repo)))
                executed += 1
                continue
            if re.match(r"^DROP TABLE(?: IF EXISTS)? tmp_(?:creature|gameobject)$", compact, re.I):
                conn.execute(compact)
                executed += 1
                continue
            table = direct_target_table(compact)
            if table not in TABLES:
                continue
            sql = substitute_vars(compact, variables, unresolved_variables, path.relative_to(repo))
            sql = re.sub(r"(?i)^INSERT IGNORE INTO", "INSERT OR IGNORE INTO", sql)
            try:
                conn.execute(sql)
            except Exception as exc:
                raise RuntimeError(f"{path.relative_to(repo)} statement {ordinal} failed: {exc}\n{sql[:2000]}") from exc
            executed += 1
        conn.commit()
        after = target_fingerprint(conn, wanted)
        changed = changed_entries(before, after)
        if changed["creature"] or changed["gameobject"]:
            changes.append({"file": str(path.relative_to(repo)), **changed})
    return changes, executed, len(files), ignored_target_mentions, sorted(unresolved_variables)


def export(conn, wanted):
    result = {"creature": {}, "gameobject": {}}
    for table in SPAWN_TABLES:
        mapping = table + "_spawn_entry"
        for entry in sorted(wanted[table]):
            rows = conn.execute(f"""
                SELECT s.* FROM `{table}` s
                WHERE s.id=? OR s.guid IN (SELECT guid FROM `{mapping}` WHERE entry=?)
                ORDER BY s.guid
            """, (entry, entry)).fetchall()
            result[table][str(entry)] = [dict(row) for row in rows]
    return result


def main():
    repo = Path(sys.argv[1])
    profile = Path(sys.argv[2])
    output = Path(sys.argv[3])
    audit_output = Path(sys.argv[4])
    db_path = Path(sys.argv[5])
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    wanted = targets(profile)
    dump = next((repo / "Full_DB").glob("*.sql.gz"))
    schemas, totals = load_base(conn, dump)
    base = target_fingerprint(conn, wanted)
    changes, executed, file_count, ignored, unresolved = replay(conn, repo, wanted)
    final = export(conn, wanted)
    output.write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    info = {
        "repo": str(repo),
        "revision": __import__("subprocess").check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(),
        "schemas": schemas,
        "base_row_totals": totals,
        "update_files": file_count,
        "executed_target_statements": executed,
        "target_changes_by_file": changes,
        "ignored_target_mentions": ignored,
        "undefined_mysql_variables_coerced_to_null": unresolved,
    }
    audit_output.write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    for table in SPAWN_TABLES:
        found = sum(bool(rows) for rows in final[table].values())
        row_count = sum(len(rows) for rows in final[table].values())
        range_rows = sum(r["spawntimesecsmin"] != r["spawntimesecsmax"] for rows in final[table].values() for r in rows)
        print(table, "requested", len(final[table]), "found", found, "rows", row_count, "range_rows", range_rows)
    print("update_files", file_count, "executed_target_statements", executed, "changed_files", len(changes))


if __name__ == "__main__":
    main()
