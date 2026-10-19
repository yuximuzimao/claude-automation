"""为缺少原文定位的 Topic Card 生成可审计回填候选。

仅生成 proposal。不得直接修改 topic card、Silver、已阅状态或页面来源真值。
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
from pathlib import Path

from .quality import WORK, sha256_file

TOPIC_DIR = WORK / "topic-cards-v1"
SOURCE_DIR = WORK / "full-history-chunks"
CARD_RE = re.compile(r"^## (T-\d{8}-\d+) — ([^\n]*)\n(.*?)(?=^## T-|\Z)", re.M | re.S)
TIME_FIELD_RE = re.compile(r"^- time_range:\s*(.+)$", re.M)
SUMMARY_RE = re.compile(r"^- semantic_summary:\s*(.+)$", re.M)
CLOCK_RE = re.compile(r"\[(\d{1,2}):(\d{2})\]")
RANGE_RE = re.compile(r"(\d{1,2}):(\d{2})(?:\s*[–—-]\s*(\d{1,2}):(\d{2}))?")

WINDOW_SIZE = 28
WINDOW_STEP = 7
HIGH_SCORE = 0.07
HIGH_MARGIN = 0.005


def normalize(value: str) -> str:
    return re.sub(r"[^\u3400-\u9fff0-9a-z%]+", "", str(value).lower())


def grams(value: str) -> collections.Counter[str]:
    text = normalize(value)
    result: collections.Counter[str] = collections.Counter()
    for size in (2, 3, 4):
        for i in range(max(0, len(text) - size + 1)):
            result[text[i:i + size]] += 1
    return result


def parse_range(value: str) -> tuple[int, int] | None:
    m = RANGE_RE.search(value or "")
    if not m:
        return None
    start = int(m.group(1)) * 60 + int(m.group(2))
    end = int(m.group(3)) * 60 + int(m.group(4)) if m.group(3) else start
    return start, end


def clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def parse_cards(date: str) -> list[dict]:
    path = TOPIC_DIR / f"{date}.md"
    if not path.exists():
        return []
    result = []
    for m in CARD_RE.finditer(path.read_text(encoding="utf-8")):
        body = m.group(3)
        tm = TIME_FIELD_RE.search(body)
        sm = SUMMARY_RE.search(body)
        result.append({
            "card_id": m.group(1),
            "date": date,
            "title": m.group(2).strip(),
            "semantic_summary": sm.group(1).strip() if sm else "",
            "saved_time_range": tm.group(1).strip() if tm else "",
            "truth": parse_range(tm.group(1)) if tm else None,
        })
    return result


def source_lines(date: str) -> list[dict]:
    result = []
    for path in sorted((SOURCE_DIR / date).glob("part-*.md")):
        for line_no, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            m = CLOCK_RE.match(text)
            result.append({
                "file": path.name,
                "line": line_no,
                "text": text,
                "minute": int(m.group(1)) * 60 + int(m.group(2)) if m else None,
            })
    return result


def segments(chunk: list[dict]) -> list[dict]:
    out = []
    for row in chunk:
        if out and out[-1]["file"] == row["file"] and out[-1]["end_line"] + 1 == row["line"]:
            out[-1]["end_line"] = row["line"]
        else:
            out.append({"file": row["file"], "start_line": row["line"], "end_line": row["line"]})
    return out


def windows(lines: list[dict]) -> list[dict]:
    out = []
    if len(lines) < WINDOW_SIZE:
        starts = [0]
    else:
        starts = range(0, len(lines) - WINDOW_SIZE + 1, WINDOW_STEP)
    for start in starts:
        chunk = lines[start:start + WINDOW_SIZE]
        times = [row["minute"] for row in chunk if row["minute"] is not None]
        if not times:
            continue
        out.append({
            "index": start,
            "lo": min(times),
            "hi": max(times),
            "segments": segments(chunk),
            "text": " ".join(row["text"] for row in chunk),
        })
    return out


def tfidf(texts: list[str]) -> list[dict[str, float]]:
    counters = [grams(text) for text in texts]
    df: collections.Counter[str] = collections.Counter()
    for item in counters:
        df.update(item.keys())
    n_docs = len(counters)
    vectors = []
    for item in counters:
        values = {
            key: (1 + math.log(count)) * (1 + math.log((n_docs + 1) / (df[key] + 1)))
            for key, count in item.items()
            if df[key] <= max(3, int(n_docs * .8))
        }
        length = math.sqrt(sum(value * value for value in values.values())) or 1.0
        vectors.append({key: value / length for key, value in values.items()})
    return vectors


def rank_day(cards: list[dict], source_windows: list[dict]) -> dict[str, list[dict]]:
    if not cards or not source_windows:
        return {}
    queries = [card["title"] + " " + card["title"] + " " + card["semantic_summary"] for card in cards]
    vectors = tfidf(queries + [window["text"] for window in source_windows])
    query_vectors = vectors[:len(cards)]
    window_vectors = vectors[len(cards):]
    postings: dict[str, list[tuple[int, float]]] = collections.defaultdict(list)
    for j, vector in enumerate(window_vectors):
        for key, value in vector.items():
            postings[key].append((j, value))
    result = {}
    for i, card in enumerate(cards):
        scores: collections.defaultdict[int, float] = collections.defaultdict(float)
        for key, value in query_vectors[i].items():
            for j, other in postings.get(key, []):
                scores[j] += value * other
        top = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:3]
        rows = []
        second = top[1][1] if len(top) > 1 else 0.0
        for rank, (j, score) in enumerate(top, start=1):
            window = source_windows[j]
            rows.append({
                "rank": rank,
                "score": round(score, 6),
                "margin_from_second": round(score - second, 6) if rank == 1 else None,
                "time_range": f"{clock(window['lo'])}–{clock(window['hi'])}",
                "segments": window["segments"],
            })
        result[card["card_id"]] = rows
    return result


def distance(candidate: dict, truth: tuple[int, int]) -> int:
    found = parse_range(candidate["time_range"])
    assert found is not None
    lo, hi = found
    start, end = truth
    if not (hi < start or lo > end):
        return 0
    return min(abs(hi - start), abs(lo - end))


def evaluate(cards_by_date: dict[str, list[dict]], ranked: dict[str, dict[str, list[dict]]],
             first_date: str, last_date: str) -> dict:
    values = []
    for date, cards in cards_by_date.items():
        if not (first_date <= date <= last_date):
            continue
        for card in cards:
            if not card["truth"] or not ranked.get(date, {}).get(card["card_id"]):
                continue
            first = ranked[date][card["card_id"]][0]
            values.append({
                "score": first["score"],
                "margin": first["margin_from_second"] or 0.0,
                "distance": distance(first, card["truth"]),
            })
    high = [v for v in values if v["score"] >= HIGH_SCORE and v["margin"] >= HIGH_MARGIN]
    def ratio(items: list[dict], limit: int) -> float | None:
        return round(sum(v["distance"] <= limit for v in items) / len(items), 4) if items else None
    return {
        "date_range": [first_date, last_date],
        "samples": len(values),
        "top1_overlap": ratio(values, 0),
        "top1_within_5m": ratio(values, 5),
        "high_confidence_samples": len(high),
        "high_confidence_overlap": ratio(high, 0),
        "high_confidence_within_5m": ratio(high, 5),
    }


def source_manifest_hash() -> str:
    h = hashlib.sha256()
    for path in sorted(SOURCE_DIR.glob("2026-*/part-*.md")):
        h.update(str(path.relative_to(SOURCE_DIR)).encode())
        h.update(sha256_file(path).encode())
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=WORK / "silver-candidates-v1.json")
    parser.add_argument("--out", type=Path, default=WORK / "source-anchor-backfill-proposals-v1.json")
    args = parser.parse_args()

    candidate_doc = json.loads(args.candidates.read_text(encoding="utf-8"))
    candidate_map = {row["card_id"]: row for row in candidate_doc["candidates"]}
    dates = sorted({row["date"] for row in candidate_doc["candidates"] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["date"])})
    cards_by_date = {date: parse_cards(date) for date in dates}
    ranked: dict[str, dict[str, list[dict]]] = {}
    for date in dates:
        ranked[date] = rank_day(cards_by_date[date], windows(source_lines(date)))

    proposals = []
    for card_id, candidate in sorted(candidate_map.items()):
        if candidate.get("source_anchor_confidence", "none") != "none":
            continue
        day = candidate.get("date", "")
        top = ranked.get(day, {}).get(card_id, [])
        first = top[0] if top else None
        status = "no_candidate"
        if first:
            if first["score"] >= HIGH_SCORE and (first["margin_from_second"] or 0) >= HIGH_MARGIN:
                status = "high_confidence_candidate"
            else:
                status = "review_required"
        proposals.append({
            "card_id": card_id,
            "date": day,
            "silver_status": candidate.get("silver_status"),
            "status": status,
            "reason": candidate.get("source_anchor_reason", ""),
            "candidates": top,
        })

    result = {
        "schema_version": 1,
        "status": "proposal_only_not_applied",
        "method": {
            "name": "day_local_char_ngram_tfidf_window_retrieval_v1",
            "window_lines": WINDOW_SIZE,
            "window_step": WINDOW_STEP,
            "title_weight": 2,
            "ngrams": [2, 3, 4],
            "high_confidence_threshold": {"score": HIGH_SCORE, "margin": HIGH_MARGIN},
            "warning": "high_confidence_candidate 仍是回填候选，不得自动写为正式来源。",
        },
        "validation": {
            "calibration": evaluate(cards_by_date, ranked, "2026-09-25", "2026-10-04"),
            "holdout": evaluate(cards_by_date, ranked, "2026-10-05", "2026-10-12"),
        },
        "counts": {
            "missing_anchor_candidates": len(proposals),
            "high_confidence_candidates": sum(p["status"] == "high_confidence_candidate" for p in proposals),
            "review_required": sum(p["status"] == "review_required" for p in proposals),
            "no_candidate": sum(p["status"] == "no_candidate" for p in proposals),
            "unabsorbed_or_partial_missing": sum(p["silver_status"] != "full" for p in proposals),
            "full_missing": sum(p["silver_status"] == "full" for p in proposals),
        },
        "inputs": {
            "candidate_sha256": sha256_file(args.candidates),
            "source_manifest_sha256": source_manifest_hash(),
        },
        "proposals": proposals,
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "validation": result["validation"], "counts": result["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
