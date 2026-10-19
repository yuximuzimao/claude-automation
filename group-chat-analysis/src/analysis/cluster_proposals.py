"""全量高召回候选检索与保守簇提案；不生成或覆盖正式 Silver。

注意：这是可审计的 lexical baseline，不声称理解了每张卡的决策问题。
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


def normalize(value: str) -> str:
    value = str(value).lower()
    # 不消去数字或版本；数值差异可能正是不同问题的条件。
    return re.sub(r"\s+", " ", re.sub(r"[^\u3400-\u9fff0-9a-z%]+", " ", value)).strip()


def grams(value: str) -> collections.Counter[str]:
    text = normalize(value)
    # 对汉字使用 2/3-gram，英文也用 2/3-gram 兼容 WoW 黑话和别名。
    result: collections.Counter[str] = collections.Counter()
    for block in text.split(" "):
        for size in (2, 3):
            for i in range(max(0, len(block) - size + 1)):
                result[block[i:i+size]] += 1
    return result


def vectors(rows: list[dict], *, max_terms: int = 80, max_df: int = 95) -> list[dict[str, float]]:
    items = []
    df: collections.Counter[str] = collections.Counter()
    for row in rows:
        # title 比 summary 更接近问题表达；summary 只做补充召回。
        a = grams(row.get("title", ""))
        b = grams(row.get("semantic_summary", ""))
        combined = collections.Counter({x: v * 2 for x, v in a.items()})
        combined.update(b)
        items.append(combined)
        df.update(combined.keys())

    result: list[dict[str, float]] = []
    for item in items:
        tfidf = {
            k: (1 + math.log(v)) * (1 + math.log((len(rows) + 1) / (df[k] + 1)))
            for k, v in item.items()
            if 1 < df[k] <= max_df
        }
        selected = sorted(tfidf, key=lambda k: (-tfidf[k], k))[:max_terms]
        norm = math.sqrt(sum(tfidf[k] ** 2 for k in selected)) or 1.
        result.append({k: tfidf[k] / norm for k in selected})
    return result


def neighbors(rows: list[dict], vs: list[dict[str, float]], k: int = 10) -> list[list[tuple[int, float]]]:
    postings: dict[str, list[tuple[int, float]]] = collections.defaultdict(list)
    for i, v in enumerate(vs):
        for word, weight in v.items():
            postings[word].append((i, weight))

    output: list[list[tuple[int, float]]] = []
    for i, v in enumerate(vs):
        scores: collections.defaultdict[int, float] = collections.defaultdict(float)
        for word, weight in v.items():
            for j, other in postings[word]:
                if j != i:
                    scores[j] += weight * other
        ordered = sorted(scores.items(), key=lambda e: (-e[1], rows[e[0]]["card_id"]))
        output.append([(j, round(score, 5)) for j, score in ordered[:k]])
    return output


def evaluation(rows: list[dict], top: list[list[tuple[int, float]]], silver: dict) -> dict:
    # 自己已有的人工 Silver 是校准样本，而非独立 holdout。
    positive_groups: dict[str, set[str]] = collections.defaultdict(set)
    for unit in silver.get("units", []):
        for ref in unit.get("evidence_refs", []):
            if ref.get("card_id") and ref.get("coverage", "full") == "full":
                positive_groups[unit["knowledge_id"]].add(ref["card_id"])
    groups_by_card: dict[str, set[str]] = collections.defaultdict(set)
    for uid, ids in positive_groups.items():
        for cid in ids:
            groups_by_card[cid].add(uid)
    index = {row["card_id"]: i for i, row in enumerate(rows)}
    anchors = 0
    hit5 = 0
    hit10 = 0
    labeled_pairs = 0
    labeled_pair_same = 0
    for i, row in enumerate(rows):
        own = groups_by_card.get(row["card_id"], set())
        positives = set()
        for uid in own:
            positives.update(positive_groups[uid])
        positives.discard(row["card_id"])
        positives.intersection_update(index)
        if positives:
            anchors += 1
            if any(rows[j]["card_id"] in positives for j, _ in top[i][:5]):
                hit5 += 1
            if any(rows[j]["card_id"] in positives for j, _ in top[i][:10]):
                hit10 += 1
        for j, _ in top[i][:5]:
            other = groups_by_card.get(rows[j]["card_id"], set())
            if own and other:
                labeled_pairs += 1
                if own & other:
                    labeled_pair_same += 1
    return {
        "note": "历史人工 Silver 内部样本评测，不是独立留出集，不能据此宣称模型上线精确率。",
        "positive_anchors": anchors,
        "known_positive_recall_at_5": round(hit5 / anchors, 4) if anchors else None,
        "known_positive_recall_at_10": round(hit10 / anchors, 4) if anchors else None,
        "labeled_top5_pairs": labeled_pairs,
        "labeled_top5_agreement": round(labeled_pair_same / labeled_pairs, 4) if labeled_pairs else None,
    }


def proposals(rows: list[dict], top: list[list[tuple[int, float]]], *,
              threshold: float = 0.58, max_members: int = 5,
              quarantine_ids: set[str] | None = None) -> dict:
    # 只对尚未被 Silver / 动态档案完整吸收、且未被语义纠错隔离的来源生成聚类提案。
    # 已知抽取失真的旧 Topic Card 必须先从 canonical 原文重建原子命题，不能继续污染聚类。
    quarantine_ids = quarantine_ids or set()
    live = {
        i for i, row in enumerate(rows)
        if row.get("normalized_status", row["silver_status"]) != "full" and row["card_id"] not in quarantine_ids
    }
    by_index: list[dict[int, float]] = [{j: score for j, score in matches} for matches in top]
    edges = []
    for i in sorted(live):
        for j, score in top[i]:
            if j not in live or j <= i or score < threshold:
                continue
            a = set(rows[i].get("topics", []))
            b = set(rows[j].get("topics", []))
            if not a or not b or not (a & b):
                continue
            if by_index[j].get(i, 0) < threshold:  # 互为近邻，避免头部大簇吸附
                continue
            edges.append((min(score, by_index[j][i]), i, j))
    edges.sort(key=lambda x: (-x[0], rows[x[1]]["card_id"], rows[x[2]]["card_id"]))

    clusters: dict[int, set[int]] = {i: {i} for i in live}
    owner: dict[int, int] = {i: i for i in live}
    # complete-link: 扩簇时所有跨簇成员都需是强相似，不允许链式传递连成巨卡。
    for score, i, j in edges:
        a, b = owner[i], owner[j]
        if a == b:
            continue
        if len(clusters[a]) + len(clusters[b]) > max_members:
            continue
        if any(min(by_index[x].get(y, 0), by_index[y].get(x, 0)) < threshold
               for x in clusters[a] for y in clusters[b]):
            continue
        clusters[a].update(clusters[b])
        for x in clusters[b]:
            owner[x] = a
        del clusters[b]

    groups = []
    for values in clusters.values():
        members = sorted((rows[i]["card_id"] for i in values))
        digest = hashlib.sha1("|".join(members).encode()).hexdigest()[:12]
        group_rows = [rows[i] for i in sorted(values, key=lambda i: rows[i]["card_id"])]
        groups.append({
            "proposal_id": "P-" + digest,
            "status": "review_required",
            "members": members,
            "source_statuses": {r["card_id"]: r["silver_status"] for r in group_rows},
            "example_title": group_rows[0].get("title", ""),
            "shared_topics": sorted(set.intersection(*[set(r.get("topics", [])) for r in group_rows])) if group_rows else [],
            "note": "文本近似检索提案，未验证是否回答同一决策问题，不可直接当 Silver。",
        })
    groups.sort(key=lambda g: (-len(g["members"]), g["members"]))
    member_count = sum(len(g["members"]) for g in groups)
    assert member_count == len(live) and len(set(m for g in groups for m in g["members"])) == len(live)
    return {
        "algorithm": "title2_summary1_char_2_3gram_tfidf_complete_link_v1",
        "status": "proposal_only_not_published",
        "params": {"threshold": threshold, "top_k": len(top[0]) if top else 0, "max_members": max_members},
        "counts": {
            "candidate_total": len(rows),
            "non_full_candidates": len(live),
            "quarantined_semantic_errors": len(quarantine_ids),
            "groups": len(groups),
            "multi_source_groups": sum(len(g["members"]) > 1 for g in groups),
            "grouped_sources": sum(len(g["members"]) for g in groups if len(g["members"]) > 1),
            "singletons": sum(len(g["members"]) == 1 for g in groups),
        },
        "groups": groups,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", type=Path, default=WORK / "silver-candidates-v1.json")
    p.add_argument("--silver", type=Path, default=WORK / "silver-knowledge-v1.json")
    p.add_argument("--corrections", type=Path, default=WORK / "semantic-correction-queue-v1.json")
    p.add_argument("--out", type=Path, default=WORK / "silver-cluster-proposals-v1.json")
    args = p.parse_args()
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    silver = json.loads(args.silver.read_text(encoding="utf-8"))
    rows = candidates["candidates"]
    correction_ids: set[str] = set()
    if args.corrections.exists():
        correction_doc = json.loads(args.corrections.read_text(encoding="utf-8"))
        correction_ids = {x.get("card_id") for x in correction_doc.get("issues", []) if x.get("card_id")}
    vs = vectors(rows)
    top = neighbors(rows, vs, k=10)
    result = proposals(rows, top, quarantine_ids=correction_ids)
    # 召回列表才是这版 baseline 的主要产物：所有未 full 的来源均有可复核近邻。
    # 不把相似分数当成‘同一问题’概率。
    result["neighbor_suggestions"] = {
        row["card_id"]: [
            {"card_id": rows[j]["card_id"], "similarity": score, "silver_status": rows[j]["silver_status"]}
            for j, score in top[i]
        ]
        for i, row in enumerate(rows)
        if row.get("normalized_status", row["silver_status"]) != "full" and row["card_id"] not in correction_ids
    }
    result["calibration"] = evaluation(rows, top, silver)
    result["inputs"] = {
        "candidate_sha256": sha256_file(args.candidates),
        "silver_sha256": sha256_file(args.silver),
        "semantic_corrections_sha256": sha256_file(args.corrections) if args.corrections.exists() else None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "counts": result["counts"], "calibration": result["calibration"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
