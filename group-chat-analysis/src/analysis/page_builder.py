#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from src.analysis.page_renderer import build_page_v3, dossier_evidence_index

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.first_read_projection import build_first_read_projection
from src.analysis.quality import sha256_file
from src.analysis.reviewed_semantic_state import build_reviewed_semantic_state
from src.analysis.semantic_fingerprint import semantic_fingerprint

WORK = ROOT / "runtime" / "analysis-work"
CARDS_DIR = WORK / "topic-cards-v1"
CHUNKS_DIR = WORK / "full-history-chunks"
COLLECTION_DIR = WORK / "normalized-v1" / "collections"
BLACKWORD_FILE = WORK / "normalized-v1" / "blackword-dictionary-v1.md"
REORG_TRIAGE = WORK / "reorg-v2" / "card-triage.json"
INFINITE_DOSSIER = WORK / "infinite-dossier-v1.json"
SILVER_KNOWLEDGE = WORK / "silver-knowledge-v1.json"
SILVER_CANDIDATES = WORK / "silver-candidates-v1.json"
FIRST_READ_PROJECTION = WORK / "first-read-projection-v1.json"
REVIEWED_SEMANTIC_DECISIONS = WORK / "reviewed-semantic-decisions-v1.json"
REVIEWED_SEMANTIC_STATE = WORK / "reviewed-semantic-state-v1.json"
ATOMIC_REVIEWED = WORK / "atomic-claims-reviewed-v1.json"
NO_CLAIM_REVIEWED = WORK / "atomic-claim-no-claim-reviewed-v1.json"
QUESTION_REGISTRY = WORK / "question-cluster-registry-current.json"
SILVER_ROUTING = WORK / "question-cluster-silver-routing-reviewed-v1.json"
SILVER_CONSOLIDATION = WORK / "silver-draft-consolidation-reviewed-v1.json"
SILVER_PUBLICATION = WORK / "silver-publication-gate-reviewed-v1.json"
VERIFIED_SOURCE_ANCHORS = WORK / "verified-source-anchors-v1.json"
DEFAULT_OUT = ROOT / "runtime" / "reports" / "page-v2-prototype-light.html"
DEFAULT_DETAILS_DIR = ROOT / "runtime" / "reports" / "page-v2-details"
OUT = DEFAULT_OUT
DETAILS_DIR = DEFAULT_DETAILS_DIR

CARD_RE = re.compile(r"^## (T-(\d{8})-\d+) — (.+)$", re.M)
FIELD_RE = re.compile(r"^- ([a-z_]+): (.*)$", re.M)
SOURCE_RANGE_RE = re.compile(r"^full-history-chunks/(\d{4}-\d{2}-\d{2})/(part-\d+\.md):(\d+)-(\d+)$")
GENERIC_TERMS = {
    "任务", "路线", "升级", "练级", "玩家", "群友", "讨论", "问题", "经验", "装备", "副本",
    "职业", "当前", "版本", "时光服", "直接", "继续", "需要", "可以", "一个", "多个", "实际",
    "方法", "信息", "情况", "规则", "建议", "相关", "机制", "地图", "成本", "价值", "影响",
}
CANONICAL_COLLECTIONS = [
    "flight-investment", "first-character-vs-alts", "leveling-friction-and-transition-points",
    "limited-time-event-windows", "server-population-and-character-locks",
    "dk-terminology-and-role-economics", "role-supply-demand", "raid-learning-and-mechanics",
    "multi-client-performance-and-attention", "fresh-80-catchup-economics", "raid-income-roi",
    "multi-character-cost-model", "profession-and-gathering-economics", "legendary-fragment-economy",
    "equipment-price-and-market-dynamics", "tool-and-information-ecosystem", "group-misinformation-corrections",
    "guild-and-raid-governance", "player-time-budget-and-goals", "version-ecology-and-player-migration",
]

# Prototype cross-project overlay. These cards remain in the source data and original chat,
# but are removed from the default review flow when the WoW route project already has a
# stronger user-tested / verified fact and the group-chat card adds no new decision value.
USER_REVIEW_EXCLUDES = {
    "T-20260925-008": "这是特定玩家因清多个满级号团本CD而暂停练级的个人时间分配，不是可迁移的游戏机制或路线经验。",
    "T-20260922-011": "这是玩家等待直升限制时选择起小号的个人安排；对用户当前决策没有可迁移价值。",
    "T-20260925-003": "第一轮分析错误：00:38 的61级来自另一名发言人，不是‘时光三部落’这条DK 67→80时间线，不能作为后续79/80节点的前序样本。",
    "T-20261009-038": "纯玩家叙事体验意见：旧世界任务是否碎片化、DK起始区是否好看，对当前路线和操作决策没有实际帮助。",
    "T-20260919-150": "这是‘玩家依赖群聊’的元观察，不提供可复用的游戏机制、路线或数值信息。",
    "T-20260929-040": "‘猎人省心/有人仍觉得累’只是主观体验冲突；同一原文里真正可操作的信息已拆成独立补漏卡。",
    "T-20260929-041": "‘碎片时间被转成游戏进度’是抽象玩家行为总结，对当前练级决策没有帮助。",
    "T-20260921-030": "‘DK起号简单’只是方向性玩家意见，缺少可执行的门槛、数值或具体操作，按用户反馈从默认审阅流排除。",
    "T-20261005-011": "80级DK没炉石只是旅店交互问题；属于一次性基础交互排错，对职业、练级或打金决策没有持续价值。",
    "T-20260919-040": "直升冰DK首CD约2500G总消费缺少可核对原文与完整装备/天赋/市场输入；不同阶段价格和购买策略差异大，按用户反馈判为无效。",
    "T-20260919-041": "‘去掉误拍后约2000G有效启动成本’与同一未完整还原的消费样本绑定，不能当作可迁移成本基线。",
    "T-20260919-042": "约2000G投入达到231装等仍缺具体装备结构、天赋和市场背景；单独装等/金额组合无法支持实际决策，按用户反馈判为无效。",
    "T-20260924-078": "原文只有反复提问，没有形成可执行回复；‘路线知识需求强’只是元观察，按用户反馈判为无效。",
    "T-20260924-079": "原文没有新增具体路线、装备或操作信息；‘不会当DKT也可先输出练级’过于常识化，按用户反馈判为无效。",
    "T-20260925-005": "78级冰DKT约17.5k血、155装等缺少具体装备结构；只能说明单一样本，无法形成阶段性基线，按用户反馈判为无用。",
    "T-20260921-021": "74级DKT单次随机本约10%一级受等级、副本、职责等变量影响很大；缺少可比较条件，按用户反馈判为无用。",
    "T-20260925-017": "‘双手冰更依赖锻造/鸡蛋剑’缺少稳定边界与可执行价值；同段中与天赋误点有关的有效信息已由独立卡 T-20260925-018 承载，因此本卡隐藏。",
    "T-20260915-052": "只指出‘会嘲讽仍可能OT’，没有给出持续仇恨的具体循环、技能顺序或处理动作；按用户反馈不作为有效教学信息展示。",
    "T-20260925-014": "与 T-20260925-015/016 属于同一条70→75→80双持武器升级链，已合并进重写后的 T-20260925-016，避免拆成三张重复卡。",
    "T-20260925-015": "与 T-20260925-014/016 属于同一条70→75→80双持武器升级链，已合并进重写后的 T-20260925-016，避免拆成三张重复卡。",
}

USER_CARD_REWRITES = {
    "T-20260925-023": {
        "title": "新手DK 55→80约70小时（单一样本）",
        "summary": "群友自报DK一周练到80、每天约10小时；结合项目已确认DK从55级起始，可折算为55→80约70小时。时间表达本身是近似口述，只作为单个新手练级样本；‘除了练级什么都不会’不再作为结论。",
    },
    "T-20260925-016": {
        "title": "双持冰DK 70→80任务/活动武器升级链（群聊实测 + 外部核验）",
        "summary": "群聊给出一条完整过渡链：70级先在AH买两把可用单手武器；75级左右在祖达克用任务奖励替换——痛苦斗兽场最终任务可选物品等级175、2.80速的深红狼牙棒，附近精英任务‘悬赏：怒鬃的鳍肢’可选物品等级175、2.60速的压抑怒火之斧（该精英任务最低等级实际可早到74）。80级部分必须按2026时光服当期事件理解：群里说的‘双持酒杯’对应美酒节恐怖酒杯。外部核验显示2026时光服该酒杯活动初期曾错误到271装等，随后热修为238；它来自限时美酒节的科林·烈酒，不是常驻武器。同期攻略称科林装备可反复刷，且活动初期玩家市场曾出现约200G可买的酒杯，因此当期获取门槛偏低；但活动结束后不再产生新掉落，只剩装备后绑定存货继续交易。故这是一条‘70 AH占位→74/75祖达克两把任务武器→80级在美酒节窗口用酒杯快速替换’的时效路线，不应写成永久固定升级链。该路线对当前打金没有直接价值，但可作为冰DK练级/过渡武器玩法资料保留。",
    },
    "T-20260925-018": {
        "title": "DK天赋排雷：走双手路线时不要再投资萨萨里安的威胁",
        "summary": "原始案例只是‘同时点了双手路线和萨萨里安的威胁’。结合跨日群聊明确说法‘萨萨里安是双持冰DK’，可把它提炼成可复用排雷：双手与双持是两套不同武器路线；已经确定走双手时，再把天赋点投入服务双持武器的萨萨里安路线，会形成无效/浪费的混搭。保留价值来自这个明确误区，而不是某个玩家曾经点错。",
    },
    "T-20261004-019": {
        "title": "冰DK过渡饰品：力量版伟大可直接从AH购买",
        "summary": "群聊给出的有效信息很单一：力量版暗月卡片：伟大可作为冰DK过渡饰品，并可直接从拍卖行购买。这里不扩展成‘必买’或完整配装结论，只保留饰品对象与获取来源。",
    },
    "T-20260926-058": {
        "title": "双子女武神基础打法：吃白打黑、吃黑打白，切色后再处理对应机制",
        "summary": "群聊给出的核心打法是：开打前先点白门获得白色精华，跟大团打黑色女武神；需要转换时去黑门换成黑色精华，再打白色女武神。‘吃白打黑、吃黑打白’是攻击关系；拿到对应颜色精华后，同色球不会按普通伤害处理，因此不能把‘自己看起来是白色’误当成已经吃过白门。外部WotLK攻略进一步说明：光明精华会免疫光明伤害并提高对黑暗女武神的伤害，黑暗精华反之；同色球可安全吸收并叠加Powering Up，异色球才是危险来源；遇到光明/黑暗漩涡时应切到与漩涡同色的精华来免疫大额伤害。群聊中的‘50%血量以下再换色’更像具体团打法/阶段口令，不作为通用硬机制固化。",
    },
}

USER_COLLECTION_OVERRIDES = {
    "T-20260920-114": ["防诈骗经验"],
    "T-20260927-006": ["装备机制"],
    "T-20260920-129": ["装备机制"],
    "T-20260926-058": ["团本Boss技巧"],
}

USER_VALUE_NOTES = {
    "T-20260925-020": {
        "value": "有用",
        "reason": "用户明确以此作为有价值任务知识示例：应补齐风暴峭壁《弥补关系》#12915的任务身份，并保留土灵宠物式控制栏、先护盾/控制再输出的操作排雷。",
    },
    "T-20260915-111": {
        "value": "一般",
        "reason": "属于服务器/阵营锁导致的不可逆操作风险，有一定机制参考价值，但当前使用频率不高。",
    },
    "T-20260920-114": {
        "value": "有用",
        "reason": "可作为防诈骗/野团风险经验：星级只能约束或反映团长侧风险，不能把随机团员质量一并背书。",
    },
    "T-20260927-006": {
        "value": "有用",
        "reason": "装备与专业联动的新手避雷：珠宝专属宝石不是达到珠宝技能等级后就能给任意角色通用，角色自身专业要求仍会限制使用。",
    },
    "T-20260920-129": {
        "value": "有用",
        "reason": "装备与专业联动机制：巫师的炼金石需要炼金专业，不能只看属性把它当成通用饰品。",
    },
    "T-20260926-058": {
        "value": "有用",
        "reason": "群聊原文已经包含可执行的双子女武神基础打法，并经外部攻略补齐了颜色精华、球与漩涡的机制关系。",
    },
    "T-20261003-058": {
        "value": "一般",
        "reason": "70级冰DK买钴质T装、保持冰天赋并一路随机本坦到80属于真实玩法路线；对当前打金无直接帮助，但能丰富对DK练级/坦克玩法的整体认识。",
    },
    "T-20260925-016": {
        "value": "一般",
        "reason": "整合并核验后是一条完整的双持冰DK武器过渡路线；对当前打金大概率无用，但作为职业玩法资料有保留价值。",
    },
    "T-20261004-019": {
        "value": "一般",
        "reason": "只提供一个很单一但可用的点：力量版伟大是冰DK可考虑的过渡饰品，并且可直接从AH购买。",
    },
}

SUPPLEMENTAL_CARDS = [
    {
        "card_id": "SUP-20260922-COLD-FLIGHT-001",
        "date": "2026-09-22",
        "time_range": "23:18–23:26",
        "title": "有大号时，可把寒冷飞行书邮寄给小号，让小号在诺森德直接起飞",
        "semantic_summary": "群聊明确给出做法：大号购买寒冷飞行相关书籍后邮寄给小号，小号到诺森德后可直接获得飞行条件。对方随即回复“非常有用”。这是第一轮 topic card 漏掉的可操作机制信息；具体购买条件、等级限制和当前时光服规则仍需版本核验。",
        "evidence_status": "group_mechanic_claim_requires_verification",
        "tags": ["寒冷飞行", "小号", "邮寄", "诺森德"],
        "collection_candidates": ["飞行机制"],
        "display_status": "supplemental",
        "synthetic_supplement": True,
    },
]

LONGITUDINAL_AGGREGATES = [
    {
        "card_id": "AGG-DK-LEVELING-001",
        "date": "2026-09-15 → 2026-09-26",
        "title": "同一玩家双持冰DK：67→80连续实测",
        "semantic_summary": "同一发言人从9月15日67级持续记录到9月26日80级。路线不是单一刷法：70级后做诺森德任务，同时以双持冰天赋穿T装排随机本；79级时已刷到明显疲劳。67→80的日历跨度约10天19小时，但原文没有连续在线时长，不能当作净练级耗时。原先‘74级一次随机本约10%一级’因等级、副本与职责变量过多，已按用户复核从量化结论中删除。",
        "evidence_status": "longitudinal_direct_sample",
        "tags": ["DK", "双持冰", "67-80", "随机本", "诺森德任务", "连续实测"],
        "collection_candidates": ["升级时间样本"],
        "display_status": "aggregate",
        "aggregate_facts": [
            {"label": "职业 / 路线", "value": "双持冰DK；70级后可穿T装排随机本"},
            {"label": "等级范围", "value": "67 → 80"},
            {"label": "日历跨度", "value": "约10天19小时（不是净在线练级时间）"},
            {"label": "主要方式", "value": "诺森德任务 + 双持冰天赋穿T装排随机本"},
        ],
        "aggregate_source_ids": [
            "T-20260921-022", "T-20260924-066",
            "T-20260925-016", "T-20260925-022", "T-20260926-034",
        ],
        "aggregate_evidence_windows": [
            {"date": "2026-09-15", "time_range": "16:59–17:01"},
            {"date": "2026-09-16", "time_range": "10:33–10:35"},
            {"date": "2026-09-18", "time_range": "18:58"},
            {"date": "2026-09-20", "time_range": "00:14 / 15:23"},
            {"date": "2026-09-21", "time_range": "09:23–09:27"},
            {"date": "2026-09-22", "time_range": "15:38–15:55"},
            {"date": "2026-09-24", "time_range": "14:54 / 22:52–22:58"},
            {"date": "2026-09-25", "time_range": "10:37–10:38 / 17:43 / 21:57–22:13"},
            {"date": "2026-09-26", "time_range": "09:28 / 12:05"},
        ],
        "aggregate_timeline": [
            {"date": "2026-09-15 17:01", "level": "67→68", "detail": "BDK / 双持路线；本人称67级离68只差一格。"},
            {"date": "2026-09-16 10:33–10:35", "level": "69", "detail": "BDK排随机本；明确说自己69级，并继续冲级。"},
            {"date": "2026-09-18 18:58", "level": "进行中", "detail": "暂停其他角色日常，集中冲BDK，原计划20号满级。"},
            {"date": "2026-09-20 00:14 / 15:23", "level": "74", "detail": "70级后去考达拉做任务；同时开始把冰DK当T排本。"},
            {"date": "2026-09-21 09:23–09:27", "level": "74", "detail": "为赶78级继续用DKT职责排随机本；原先‘一次约10%一级’的估算因条件变量过多不再作为有效量化信息。"},
            {"date": "2026-09-22 15:38–15:55", "level": "75", "detail": "仍在练冰DK，并明确熟悉输出/T两套循环。"},
            {"date": "2026-09-24 14:54 / 22:52–22:58", "level": "78", "detail": "到78后可打美酒节；明确一路都是双持冰天赋。"},
            {"date": "2026-09-25 10:37–10:38 / 17:43 / 21:57", "level": "79.5", "detail": "70级起穿T装排本；随机本已刷到肌肉记忆；70级AH双持武器，之后用祖达克竞技场/精英任务奖励替换。"},
            {"date": "2026-09-26 09:28–12:05", "level": "80", "detail": "上午还差约30%经验，12:05明确宣布DK满级。"},
        ],
    },
]

PROJECT_KNOWN_CARD_OVERRIDES = {
    "T-20260917-010": {
        "exclude": True,
        "fact": "58级进入外域已是现行路线事实",
        "source": "wow-quest-route/docs/verified-routes/VETERAN-LEVELING-BACKBONE.md",
    },
    "T-20260917-012": {
        "exclude": True,
        "fact": "58进外域、68转诺森德已在正式路线落地",
        "source": "wow-quest-route/docs/verified-routes/VETERAN-LEVELING-BACKBONE.md",
    },
    "T-20260920-017": {
        "exclude": True,
        "fact": "DK出生区不能跳过，现有项目已按完整出生链实跑",
        "source": "wow-quest-route/docs/verified-routes/DK-STARTING-ZONE-NOTES.md",
    },
    "T-20260920-018": {
        "exclude": True,
        "fact": "DK出生区已有五开实测墙钟约3小时51分，群聊约2小时口述不再有参考价值",
        "source": "wow-quest-route/docs/archive/neat/2026-10-13-dragonblight-dk-second-run-timing-and-fivebox-neat.md",
    },
    "T-20260920-019": {
        "exclude": True,
        "fact": "DK出生区结束状态已有实测：约60级、当前等级约12.2万经验",
        "source": "wow-quest-route/docs/archive/neat/2026-09-25-dk-live-run-closure-and-group-comparison-neat.md",
    },
    "T-20260920-020": {
        "exclude": True,
        "fact": "DK出生链承担功能与角色解锁，项目已经按完整链执行",
        "source": "wow-quest-route/docs/verified-routes/DK-STARTING-ZONE-NOTES.md",
    },
    "T-20261002-003": {
        "exclude": True,
        "fact": "当前项目已实测并固定：DK以55级创建/起步",
        "source": "wow-quest-route/docs/verified-routes/DK-STARTING-ZONE-NOTES.md",
    },
    "T-20261002-012": {
        "exclude": True,
        "fact": "当前项目已实测并固定：DK创建后为55级",
        "source": "wow-quest-route/docs/verified-routes/DK-STARTING-ZONE-NOTES.md",
    },
    "T-20261002-013": {
        "exclude": True,
        "fact": "DK出生区完整任务链已在项目中实跑并沉淀",
        "source": "wow-quest-route/docs/verified-routes/DK-STARTING-ZONE-NOTES.md",
    },
    "T-20261005-047": {
        "exclude": True,
        "fact": "DK起始等级已确认是55级；58级是其他升级/直升语境，不再作为待定问题",
        "source": "wow-quest-route/docs/verified-routes/DK-STARTING-ZONE-NOTES.md",
    },
    "T-20261012-019": {
        "exclude": True,
        "fact": "DK创建/起始等级已由本项目实测确认，不再保留群聊争论作为待审信息",
        "source": "wow-quest-route/docs/verified-routes/DK-STARTING-ZONE-NOTES.md",
    },
}


def parse_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    body = value[1:-1].strip()
    if not body:
        return []
    return [x.strip().strip("`\"'") for x in body.split(",") if x.strip()]


def parse_cards() -> list[dict]:
    cards = []
    for path in sorted(CARDS_DIR.glob("2026-*.md")):
        text = path.read_text(encoding="utf-8")
        matches = list(CARD_RE.finditer(text))
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[m.end():end]
            fields = {k: v.strip() for k, v in FIELD_RE.findall(body)}
            cards.append({
                "card_id": m.group(1),
                "date": f"{m.group(2)[:4]}-{m.group(2)[4:6]}-{m.group(2)[6:]}",
                "title": m.group(3).strip(),
                "semantic_summary": fields.get("semantic_summary", ""),
                "time_range": fields.get("time_range", ""),
                "evidence_status": fields.get("evidence_status", "unknown"),
                "tags": parse_list(fields.get("tags", "[]")),
                "collection_candidates": parse_list(fields.get("collection_candidates", "[]")),
                "display_status": fields.get("display_status", ""),
                "source_ranges": fields.get("source_ranges", ""),
            })
    return cards


def apply_project_known_overrides(cards: list[dict]) -> None:
    for card in cards:
        review_reason = USER_REVIEW_EXCLUDES.get(card["card_id"])
        card["user_review_exclude"] = bool(review_reason)
        card["user_review_reason"] = review_reason or ""

        rewrite = USER_CARD_REWRITES.get(card["card_id"])
        if rewrite:
            if rewrite.get("title"):
                card["title"] = rewrite["title"]
            if rewrite.get("summary"):
                card["semantic_summary"] = rewrite["summary"]

        collection_override = USER_COLLECTION_OVERRIDES.get(card["card_id"])
        if collection_override:
            card["collection_candidates"] = collection_override

        value_note = USER_VALUE_NOTES.get(card["card_id"])
        card["user_value"] = value_note.get("value", "") if value_note else ""
        card["user_value_reason"] = value_note.get("reason", "") if value_note else ""

        override = PROJECT_KNOWN_CARD_OVERRIDES.get(card["card_id"])
        card["project_known"] = bool(override)
        card["project_known_exclude"] = bool(override and override.get("exclude"))
        if not override:
            continue
        card["project_known_fact"] = override.get("fact", "")
        card["project_known_source"] = override.get("source", "")
        if override.get("title"):
            card["title"] = override["title"]
        if override.get("summary"):
            card["semantic_summary"] = override["summary"]


def apply_reorg_overlay(cards: list[dict]) -> dict[str, int]:
    """Attach the v2 full-history triage without mutating first-round source cards."""
    if not REORG_TRIAGE.exists():
        for card in cards:
            card["reorg_decision"] = "keep_unclassified"
            card["reorg_reason"] = "重整层未生成"
            card["reorg_layer"] = "main"
            card["needs_title_review"] = False
        return {"main": len(cards), "review": 0, "hidden": 0, "archive": 0, "collection": 0, "aggregate": 0}

    rows = json.loads(REORG_TRIAGE.read_text(encoding="utf-8"))
    by_id = {row["card_id"]: row for row in rows}
    counts = {"main": 0, "review": 0, "hidden": 0, "archive": 0, "collection": 0, "aggregate": 0, "dictionary": 0}
    for card in cards:
        row = by_id.get(card["card_id"])
        if row is None:
            status = card.get("display_status", "")
            if status == "off_topic":
                row = {"decision": "archive_offtopic", "reason": "增量全文复核：有实质语义但与当前游戏分析主线无关"}
            elif status == "low_priority":
                row = {"decision": "review_incremental_low_priority", "reason": "增量全文复核：低优先级但保留供首次阅读/后续判断"}
            else:
                row = {"decision": "keep_incremental", "reason": "增量全文复核：尚无legacy triage，保留进入语义清洗队列"}
        decision = row.get("decision", "keep_unclassified")
        if decision == "keep_definition":
            layer = "dictionary"
        elif decision == "keep_timebound":
            layer = "review"
        elif decision.startswith("keep_"):
            layer = "main"
        elif decision.startswith("review_"):
            layer = "review"
        elif decision.startswith("hide_"):
            layer = "hidden"
        elif decision.startswith("archive_"):
            layer = "archive"
        elif decision == "collection_insight":
            layer = "collection"
        elif decision == "aggregate_review":
            layer = "aggregate"
        else:
            layer = "main"
        card["reorg_decision"] = decision
        card["reorg_reason"] = row.get("reason", "")
        card["reorg_layer"] = layer
        card["needs_title_review"] = bool(row.get("needs_title_review"))
        if decision == "keep_pitfall" and "pitfall" not in card.get("system_tags", []):
            card.setdefault("system_tags", []).append("pitfall")
        # Candidate titles remain QA metadata only; never silently replace a user-visible title.
        card["proposed_title"] = row.get("proposed_title", card.get("title", ""))
        counts[layer] += 1
    return counts


PROFESSIONS = [
    ("dk", "DK", [r"(?<![A-Za-z])BDK(?![A-Za-z])", r"(?<![A-Za-z])DKT(?![A-Za-z])", r"(?<![A-Za-z])DK(?![A-Za-z])", "死亡骑士", "死骑", "冰DK", "血DK", "邪DK", "双持冰", "双手冰", "深血"]),
    ("druid", "德鲁伊", ["德鲁伊", "小德", "鸟德", "咕咕", "猫德", "野德", "熊德", "熊T", "奶德", "平衡德", "恢复德"]),
    ("mage", "法师", ["法师", "冰法", "火法", "奥法"]),
    ("paladin", "圣骑士", ["圣骑士", "圣骑", "惩戒骑", "防骑", "奶骑"]),
    ("shaman", "萨满", ["萨满", "元素萨", "电萨", "增强萨", "奶萨"]),
    ("priest", "牧师", ["牧师", "暗牧", "戒律牧", "神牧"]),
    ("hunter", "猎人", ["猎人", "生存猎", "射击猎", "兽王猎", "近战猎"]),
    ("warlock", "术士", ["术士", "痛苦术", "恶魔术", "毁灭术"]),
    ("warrior", "战士", ["战士", "武器战", "狂暴战", "防战"]),
    ("rogue", "盗贼", ["盗贼", "刺杀贼", "战斗贼", "敏锐贼"]),
]

TOPIC_GROUPS = [
    ("leveling", "练级 / 起号 / 路线", ["练级", "升级", "起号", "起始", "任务", "路线", "随机本", "排本", "直升", "坐车", "满级追赶", "升级时间", "升级体验"]),
    ("build", "天赋 / 流派 / 循环", ["天赋", "流派", "循环", "技能", "符文", "双持", "双手", "姿态", "手法", "雕文", "命中", "精准", "急速", "暴击", "破甲", "属性阈值"]),
    ("gear", "装备 / 武器 / 配装", ["装备", "武器", "饰品", "BIS", "配装", "套装", "宝石", "附魔", "装等", "裁决", "伟大", "死亡之钟", "六分仪", "村正", "风剑", "橙锤", "橙弓"]),
    ("role", "职责 / 坦克 / 治疗", ["坦克", "治疗", "仇恨", "职责", "切T", "T装", "DKT", "防骑", "奶骑", "奶萨", "奶德", "戒律", "排队", "秒排"]),
    ("performance", "强度 / 输出 / 就业", ["强度", "输出", "伤害", "排名", "就业", "岗位", "供需", "竞争", "人口", "团本需求", "职业选择", "版本答案", "T0"]),
    ("economy", "成本 / 价格 / 打金", ["成本", "价格", "金币", "金价", "工资", "打金", "低预算", "启动", "购买", "竞价", "便宜", "贵", "工资线", "消费"]),
    ("tool", "工具 / 插件 / 操作", ["插件", "宏", "WA", "虚空之花", "一键", "工具", "UI"]),
    ("race_profession", "种族 / 专业", ["种族", "专业", "锻造", "珠宝", "工程", "附魔专业", "采集"]),
    ("pvp", "PVP / 战场", ["PVP", "战场", "竞技场", "决斗"]),
]

SYSTEM_TAGS = [
    ("infinite", "无限服"),
    ("timewalk", "时光服"),
    ("leveling", "练级 / 任务"),
    ("raid", "副本 / Boss技巧"),
    ("gear", "装备机制"),
    ("profession", "专业技能"),
    ("economy", "经济 / 打金"),
    ("tool", "插件 / 故障排查"),
    ("safety", "防诈骗经验"),
    ("pvp", "PVP / 野外生态"),
    ("pitfall", "新手避坑"),
]

V3_TOPIC_LABELS = {
    "infinite": "无限服",
    "leveling": "任务与练级",
    "raid": "副本攻略",
    "gear": "装备机制",
    "profession": "专业技能",
    "economy": "经济 / 打金",
    "tool": "插件 / 故障排查",
    "safety": "防诈骗经验",
    "pvp": "PVP / 野外生态",
}

DISPLAY_PRIMARY_TOPICS = (
    "职业",
    "副本攻略",
    "任务与练级",
    "装备机制",
    "专业技能",
    "经济 / 打金",
    "插件 / 故障排查",
    "防诈骗经验",
    "PVP / 野外生态",
)

SILVER_PRIMARY_TOPIC_ALIASES = {
    "副本攻略": {"副本攻略", "团本", "副本", "五人本", "随机本", "副本任务", "团本运营", "副本导航", "副本机制", "开荒", "观星", "H模式", "NAXX", "奥杜尔", "TOC", "ICC", "ZAM", "ZG", "毒蛇神殿", "卡拉赞", "黑曜石圣殿", "永恒之眼", "红玉圣殿", "阿尔卡冯的宝库"},
    "任务与练级": {"任务与练级", "练级", "任务", "日常", "声望", "路线", "升级", "追赶", "低等级", "诺森德", "外域", "骑术", "交通", "达拉然", "副本任务", "任务机制", "精英任务", "满级"},
    "装备机制": {"装备机制", "装备", "配装", "装等", "掉落", "橙装", "传奇武器", "饰品", "套装", "BIS", "过渡装", "命中", "精准", "急速", "暴击", "破甲", "属性", "宝石", "唯一物品", "Roll", "雷霆", "惊雷"},
    "专业技能": {"专业技能", "专业", "工程", "珠宝", "炼金", "裁缝", "锻造", "采集", "采药", "采矿", "双采", "钓鱼"},
    "经济 / 打金": {"经济 / 打金", "经济", "打金", "金币", "G团", "GDKP", "工资", "收益", "价格", "装备价格", "AH", "消费", "预算", "竞价", "老板", "低起拍", "现金流", "回本", "投资", "交易", "金价", "材料价", "购买力", "通胀", "市场", "赚钱", "摸奖"},
    "插件 / 故障排查": {"插件 / 故障排查", "插件", "WA", "宏", "UI", "RXP", "RXPGuides", "练级插件"},
    "防诈骗经验": {"防诈骗经验", "诈骗", "账号安全", "找回", "代练", "RMT", "金币交易", "第三方平台", "预付款", "黑金", "代拍", "信誉", "账号与服务"},
    "PVP / 野外生态": {"PVP / 野外生态", "PVP", "战场", "竞技场", "野外PVP"},
}

RAID_SUBTOPICS = (
    ("NAXX", ("NAXX", "纳克萨玛斯")),
    ("奥杜尔", ("奥杜尔", "ULDUAR", "观星者", "奥尔加隆", "尤格萨隆", "米米尔隆", "霍迪尔", "托里姆", "弗蕾亚", "维扎克斯", "钢铁议会", "XT-002", "烈焰巨兽", "掌炉者", "科隆加恩", "欧尔莉亚")),
    ("TOC", ("TOC", "十字军的试炼", "双子女武神", "阵营冠军", "阿努巴拉克", "诺森德猛兽", "加拉克苏斯")),
    ("ICC", ("ICC", "冰冠堡垒", "巫妖王", "玛洛加尔", "亡语者", "萨鲁法尔", "普崔塞德", "鲜血女王", "辛达苟萨")),
    ("ZAM", ("ZAM", "祖阿曼")),
    ("ZG", ("ZG", "祖尔格拉布")),
    ("黑曜石圣殿", ("黑曜石圣殿", "萨塔里奥")),
    ("永恒之眼", ("永恒之眼", "玛里苟斯")),
    ("阿尔卡冯的宝库", ("阿尔卡冯的宝库", "宝库", "阿尔卡冯")),
    ("红玉圣殿", ("红玉圣殿", "海里昂")),
    ("毒蛇神殿", ("毒蛇神殿", "SSC")),
    ("卡拉赞", ("卡拉赞", "KARAZHAN")),
    ("黑石深渊", ("黑石深渊", "科林烈酒")),
    ("魔枢", ("魔枢", "THE NEXUS")),
    ("厄运之槌", ("厄运之槌", "厄运")),
    ("玛拉顿", ("玛拉顿", "MARAUDON")),
)

SILVER_DISPLAY_OVERRIDES = {
    "K-THUNDER-UPGRADE-MATERIAL-CLAIM-001": {
        "subject": "雷霆 → 惊雷（锻造武器升级）",
        "question": "雷霆升级成惊雷需要多少升级材料？",
    },
}


DISPLAY_CONTEXT_OVERRIDES = {
    "T-20260925-020": {
        "eyebrow": "风暴峭壁 · 霍迪尔/托里姆前置 · 《弥补关系》 #12915",
        "context": "80级任务（最低77级）。托里姆要求前往丹尼芬雷东边的弗约恩之砧，使用大地符咒在花岗岩石块附近召唤土灵助战，击杀弗约恩和5名雷铸铁巨人。",
        "new_fact": "群聊补充的关键排雷：召出的土灵有类似宠物的控制栏；不要只让它自动打，先通过控制栏使用护盾/控制，再输出，能显著降低土灵秒躺导致的任务难度。",
        "context_source": "wow-quest-route/data/task-cards/12915.json + 群聊实测",
    },
    "T-20260926-058": {
        "eyebrow": "十字军的试炼（TOC）· 80级团本 · 双子女武神 · 第4场首领战",
        "context": "该战斗围绕光明/黑暗精华和对应颜色的球、漩涡机制展开；玩家需要根据目标与机制切换精华。",
        "new_fact": "群聊给出的可执行口令是“吃白打黑、吃黑打白”；开打前拿白色精华跟团打黑色女武神，需要转换时去黑门换黑色精华再打白色女武神。",
        "context_source": "群聊 + 已补充的WotLK攻略核验",
    },
}


def card_text(card: dict) -> str:
    return " ".join([
        card.get("title", ""), card.get("semantic_summary", ""),
        " ".join(card.get("tags", [])), " ".join(card.get("collection_candidates", [])),
    ])


PROFESSION_SUBJECT_TERMS = (
    "天赋", "流派", "循环", "技能", "符文", "灵气", "姿态", "武器", "装备", "饰品", "BIS", "配装",
    "套装", "宝石", "附魔", "魔印", "命中", "精准", "急速", "暴击", "破甲", "力量", "攻强", "属性",
    "坦克", "治疗", "输出", "伤害", "DPS", "T装", "职责", "仇恨", "嘲讽", "减伤", "就业", "岗位",
    "人口", "职业", "专精", "强度", "练级", "升级", "起号", "成型", "成本", "预算", "专业", "种族",
    "AOE", "单体", "群拉", "排本", "秒排", "毕业", "过渡", "需求", "竞争", "腿短", "爆发", "容错",
)
BASE_PROFESSION_ALIASES = {"DK", "死亡骑士", "死骑", "德鲁伊", "小德", "法师", "圣骑士", "圣骑", "萨满", "牧师", "猎人", "术士", "战士", "盗贼"}


def _alias_matches(text: str, alias: str) -> list[tuple[int, int, str]]:
    if alias.startswith("(?"):
        return [(m.start(), m.end(), m.group(0)) for m in re.finditer(alias, text, re.I)]
    return [(m.start(), m.end(), m.group(0)) for m in re.finditer(re.escape(alias), text, re.I)]


def _profession_match_score(text: str, aliases: list[str], *, title: bool) -> int:
    best = 0
    for alias in aliases:
        for start, end, matched_text in _alias_matches(text, alias):
            score = 3 if title else 1
            normalized = matched_text.upper() if matched_text.isascii() else matched_text
            alias_is_specific = normalized not in BASE_PROFESSION_ALIASES and alias not in BASE_PROFESSION_ALIASES
            if alias_is_specific:
                score += 1
            nearby = text[max(0, start - 22): min(len(text), end + 22)].lower()
            subject_hits = sum(1 for term in PROFESSION_SUBJECT_TERMS if term.lower() in nearby)
            score += min(3, subject_hits)
            # A generic class name in prose is often just the speaker's/background character.
            # Require it to participate in an actual class/build/role conclusion.
            if not title and not alias_is_specific and subject_hits == 0:
                score = 0
            best = max(best, score)
    return best


def assign_professions(card: dict) -> list[str]:
    """Assign professions only when the displayed conclusion/title is profession-specific."""
    title = card.get("title", "")
    keys = []
    for key, _label, aliases in PROFESSIONS:
        if _profession_match_score(title, aliases, title=True) >= 4:
            keys.append(key)
    # Summary mentions are evidence/context only. A card whose title is generic stays in
    # 非职业 rather than being copied into class pages because one class appears as an example.
    return keys


def assign_topic_group(card: dict) -> tuple[str, str, int]:
    text = card_text(card).lower()
    best = (0, "other", "其他话题", len(TOPIC_GROUPS))
    for rank, (key, label, words) in enumerate(TOPIC_GROUPS):
        score = 0
        for word in words:
            wl = word.lower()
            if wl in text:
                score += 3 if wl in card.get("title", "").lower() else 1
        if score > best[0]:
            best = (score, key, label, rank)
    return best[1], best[2], best[3]


def related_topic_key(card: dict) -> str:
    """A light-weight mid-level grouping key: keep original cards, only place related ones together."""
    overbroad = {"待核验机制", "黑话词典", "升级时间样本", "多角色时间容量", "多角色运营"}
    candidates = [x for x in card.get("collection_candidates", []) if x and x not in overbroad]
    if candidates:
        if candidates[0] in {"账号安全", "账号安全与风险"}:
            return "防诈骗经验"
        return candidates[0]
    profession_words = {alias.lower() for _k, _l, aliases in PROFESSIONS for alias in aliases if not alias.startswith("(?")}
    useful_tags = [t for t in card.get("tags", []) if t.lower() not in profession_words and t not in GENERIC_TERMS]
    return useful_tags[0] if useful_tags else card.get("topic_group_label", "其他话题")


def assign_system_tags(card: dict) -> list[str]:
    text = card_text(card).lower()
    related = card.get("related_topic", "")
    group = card.get("topic_group_key", "other")
    tags = []
    if "无限服" in text:
        tags.append("infinite")
    if "时光服" in text:
        tags.append("timewalk")
    if group == "leveling":
        tags.append("leveling")
    raid_terms = ("副本", "团本", "boss", "toc", "zam", "naxx", "奥杜尔", "十字军", "女武神", "阵营冠军")
    if any(term in text for term in raid_terms):
        tags.append("raid")
    if group == "gear" or related == "装备机制":
        tags.append("gear")
    if group == "race_profession" or any(term in text for term in ("专业", "珠宝", "炼金", "工程", "锻造", "裁缝", "附魔", "采集")):
        tags.append("profession")
    if group == "economy" or any(term in text for term in ("打金", "金价", "工资", "收益", "价格")):
        tags.append("economy")
    if group == "tool" or "插件故障排查" in text or any(term in text for term in ("插件", "wa", "界面", "ui")):
        tags.append("tool")
    if related == "防诈骗经验" or any(term in text for term in ("账号安全", "诈骗", "被骗", "钓鱼", "找回", "托管")):
        tags.append("safety")
    if group == "pvp" or any(term in text for term in ("pvp", "战场", "竞技场", "野外pvp")):
        tags.append("pvp")
    return list(dict.fromkeys(tags))


def annotate_topic_structure(cards: list[dict]) -> None:
    for card in cards:
        professions = assign_professions(card)
        card["profession_keys"] = professions or ["noncareer"]
        label_map = {key: label for key, label, _aliases in PROFESSIONS}
        card["profession_labels"] = [label_map[key] for key in professions]
        gkey, glabel, grank = assign_topic_group(card)
        card["topic_group_key"] = gkey
        card["topic_group_label"] = glabel
        card["topic_group_rank"] = grank
        card["related_topic"] = related_topic_key(card)
        card["system_tags"] = assign_system_tags(card)


def assign_raid_subtopics(text: str) -> list[str]:
    upper = text.upper()
    labels: list[str] = []
    for label, aliases in RAID_SUBTOPICS:
        if any(alias.upper() in upper for alias in aliases):
            labels.append(label)
    return list(dict.fromkeys(labels))


def assign_silver_display_topics(unit: dict) -> list[str]:
    """Project rich Silver metadata into a small, stable first-level navigation taxonomy."""
    internal_topics = set(unit.get("topics") or [])
    semantic_title = " ".join([
        str(unit.get("subject") or ""),
        str(unit.get("question") or ""),
        " ".join(internal_topics),
    ])
    labels: list[str] = []
    if any(
        any(_alias_matches(semantic_title, alias) for alias in aliases)
        for _key, _label, aliases in PROFESSIONS
    ):
        labels.append("职业")
    for topic in DISPLAY_PRIMARY_TOPICS:
        if topic == "职业":
            continue
        if internal_topics & SILVER_PRIMARY_TOPIC_ALIASES[topic]:
            labels.append(topic)
    return list(dict.fromkeys(labels)) or ["其他"]


def assign_silver_display_subtopics(unit: dict) -> dict[str, list[str]]:
    semantic_title = " ".join([
        str(unit.get("subject") or ""),
        str(unit.get("question") or ""),
        " ".join(unit.get("topics") or []),
    ])
    result: dict[str, list[str]] = {}
    profession_labels = [
        label for _key, label, aliases in PROFESSIONS
        if any(_alias_matches(semantic_title, alias) for alias in aliases)
    ]
    if profession_labels:
        result["职业"] = list(dict.fromkeys(profession_labels))
    if set(unit.get("topics") or []) & SILVER_PRIMARY_TOPIC_ALIASES["副本攻略"]:
        raid_labels = assign_raid_subtopics(semantic_title)
        if raid_labels:
            result["副本攻略"] = raid_labels
    return result


def annotate_silver_display_topics(units: list[dict]) -> None:
    for unit in units:
        unit["display_topics"] = assign_silver_display_topics(unit)
        unit["display_subtopics"] = assign_silver_display_subtopics(unit)


def annotate_silver_display_numbers(units: list[dict]) -> None:
    """Give every Silver unit a stable baseline number independent of filtering/review state."""
    for index, unit in enumerate(units, start=1):
        unit["display_number"] = index


def annotate_silver_display_copy(units: list[dict]) -> None:
    """Apply reviewed user-facing copy without mutating canonical Silver facts."""
    for unit in units:
        override = SILVER_DISPLAY_OVERRIDES.get(str(unit.get("knowledge_id") or ""), {})
        if override.get("subject"):
            unit["display_subject"] = override["subject"]
        if override.get("question"):
            unit["display_question"] = override["question"]


def annotate_v3_projection(cards: list[dict]) -> None:
    profession_label_map = {key: label for key, label, _aliases in PROFESSIONS}
    for card in cards:
        topics: list[dict] = []
        profession_labels: list[str] = []
        for key in card.get("profession_keys", []):
            if key == "noncareer":
                continue
            label = profession_label_map[key]
            profession_labels.append(label)
            topics.append({"key": f"class:{key}", "label": label, "kind": "class"})
        for key in card.get("system_tags", []):
            label = V3_TOPIC_LABELS.get(key)
            if label and key != "infinite":
                topics.append({"key": f"topic:{key}", "label": label, "kind": "topic"})
        seen_topic_keys: set[str] = set()
        card["v3_topics"] = [
            topic for topic in topics
            if not (topic["key"] in seen_topic_keys or seen_topic_keys.add(topic["key"]))
        ]
        primary: list[str] = []
        if profession_labels:
            primary.append("职业")
        primary.extend(
            V3_TOPIC_LABELS[key]
            for key in card.get("system_tags", [])
            if key in V3_TOPIC_LABELS and key != "infinite"
        )
        card["display_topics"] = list(dict.fromkeys(primary)) or ["其他"]
        subtopics: dict[str, list[str]] = {}
        if profession_labels:
            subtopics["职业"] = list(dict.fromkeys(profession_labels))
        if "副本攻略" in card["display_topics"]:
            raids = assign_raid_subtopics(card_text(card))
            if raids:
                subtopics["副本攻略"] = raids
        card["display_subtopics"] = subtopics

        context = DISPLAY_CONTEXT_OVERRIDES.get(card.get("card_id", ""), {})
        card["display_eyebrow"] = context.get("eyebrow", "")
        card["display_context"] = context.get("context", "")
        card["display_new_fact"] = context.get("new_fact", "") or card.get("semantic_summary", "")
        card["display_context_source"] = context.get("context_source", "")

        decision = card.get("reorg_decision", "")
        layer = card.get("reorg_layer", "main")
        has_infinite = "infinite" in card.get("system_tags", [])
        explicitly_seen = bool(
            card.get("user_review_exclude")
            or card.get("user_value")
            or decision == "keep_user_confirmed"
        )
        card["v3_seen"] = explicitly_seen
        card["v3_knowledge"] = bool(
            decision == "keep_user_confirmed"
            or card.get("user_value") in {"有用", "重要"}
        )
        card["v3_completable"] = decision == "review_missing_baseline"

        eligible_layer = layer in {"main", "review"}
        low_value_dynamic = decision in {"keep_timebound", "review_market_context"} and not has_infinite
        card["v3_queue"] = bool(
            eligible_layer
            and not card.get("aggregate_component_exclude")
            and not card.get("project_known_exclude")
            and not explicitly_seen
            and not low_value_dynamic
        )


def inject_longitudinal_aggregates(cards: list[dict]) -> list[dict]:
    aggregate_only_sources = {
        "T-20260924-066", "T-20260925-022", "T-20260926-034",
    }
    for card in cards:
        card["aggregate_component_exclude"] = card["card_id"] in aggregate_only_sources

    aggregates: list[dict] = []
    for raw in LONGITUDINAL_AGGREGATES:
        card = dict(raw)
        card["synthetic_aggregate"] = True
        card["project_known"] = False
        card["project_known_exclude"] = False
        card["user_review_exclude"] = False
        card["user_review_reason"] = ""
        card["time_range"] = ""
        aggregates.append(card)
    annotate_topic_structure(aggregates)
    for card in aggregates:
        card["topic_group_key"] = "leveling"
        card["topic_group_label"] = "练级 / 起号 / 路线"
        card["topic_group_rank"] = 0
        card["related_topic"] = "同一玩家 · DK 67→80连续实测"
        card["evidence_group"] = "direct"
        card["evidence_label"] = "连续实测 / 多日记录"
        card["reorg_decision"] = "keep_longitudinal_aggregate"
        card["reorg_reason"] = "多个无独立意义的进度节点已合成一张连续实测卡"
        card["reorg_layer"] = "main"
        card["needs_title_review"] = False
    return aggregates


def inject_supplemental_cards() -> list[dict]:
    supplements: list[dict] = []
    for raw in SUPPLEMENTAL_CARDS:
        card = dict(raw)
        card["project_known"] = False
        card["project_known_exclude"] = False
        card["user_review_exclude"] = False
        card["user_review_reason"] = ""
        card["aggregate_component_exclude"] = False
        supplements.append(card)
    annotate_topic_structure(supplements)
    for card in supplements:
        if card["card_id"] == "SUP-20260922-COLD-FLIGHT-001":
            card["topic_group_key"] = "leveling"
            card["topic_group_label"] = "练级 / 起号 / 路线"
            card["topic_group_rank"] = 0
            card["related_topic"] = "飞行机制"
            card["reorg_decision"] = "review_verification"
            card["reorg_reason"] = "可操作机制信息，但购买条件/等级限制和当前时光服规则仍需版本核验"
            card["reorg_layer"] = "review"
            card["needs_title_review"] = False
    return supplements


def read_day_lines(date: str) -> list[str]:
    day = CHUNKS_DIR / date
    lines: list[str] = []
    for path in sorted(day.glob("part-*.md")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("# ") or line.startswith("> "):
                continue
            lines.append(line)
    return lines


def read_verified_anchor_context(date: str, anchor: dict) -> list[str]:
    """Read only manually verified source segments; line numbers are 1-based."""
    if anchor.get("date") != date:
        raise ValueError(f"verified source anchor date mismatch: {date} != {anchor.get('date')}")
    context: list[str] = []
    for index, segment in enumerate(anchor.get("segments", [])):
        path = CHUNKS_DIR / date / segment["file"]
        if not path.exists():
            raise ValueError(f"verified source anchor file missing: {path}")
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
        start, end = int(segment["start_line"]), int(segment["end_line"])
        if start < 1 or end < start or end > len(raw):
            raise ValueError(f"verified source anchor line range invalid: {path}:{start}-{end}")
        if index and context:
            context.append("[[SOURCE_WINDOW_GAP]]")
        for line in raw[start - 1:end]:
            line = line.strip()
            if not line or line.startswith("# ") or line.startswith("> "):
                continue
            context.append(line)
    if not context:
        raise ValueError(f"verified source anchor has no readable context for {date}")
    return context


def compact_terms(card: dict) -> list[str]:
    """Build independent anchors, not one fuzzy keyword.

    Composite tags such as `58外域` become `58` + `外域`, so a source
    window must contain more than one independently meaningful clue.
    """
    terms: list[str] = []

    def add(term: str) -> None:
        term = term.strip(" `\"'，。、“”()（）[]【】")
        if len(term) < 2 or term in GENERIC_TERMS or term in terms:
            return
        terms.append(term)

    for raw in card["tags"]:
        raw = raw.strip()
        add(raw)
        for token in re.findall(r"[A-Za-z][A-Za-z0-9+.-]{1,}|\d{2,}", raw):
            add(token)
        for token in re.findall(r"[\u4e00-\u9fff]{2,6}", raw):
            add(token)

    text = card["title"] + " " + card["semantic_summary"]
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+.-]{1,}|\d{2,}", text):
        add(token)

    # Title phrases are fallback anchors only. Avoid single generic words.
    for token in re.findall(r"[\u4e00-\u9fff]{3,7}", card["title"]):
        add(token)

    return terms[:18]


def context_score(lines: list[str], center: int, terms: list[str], radius: int = 5) -> tuple[float, int]:
    lo, hi = max(0, center - radius), min(len(lines), center + radius + 1)
    block = "\n".join(lines[lo:hi]).lower()
    hits = 0
    score = 0.0
    for term in terms:
        tl = term.lower()
        if tl in block:
            hits += 1
            score += 4.0 + min(len(term), 8) * 0.35
    return score, hits


def _clock_minutes(value: str) -> int | None:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", value.strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def _time_windows(value: str) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    for start_s, end_s in re.findall(r"(\d{1,2}:\d{2})(?:\s*[–—-]\s*(\d{1,2}:\d{2}))?", value or ""):
        start = _clock_minutes(start_s)
        end = _clock_minutes(end_s or start_s)
        if start is None or end is None:
            continue
        if end < start:
            end = start
        windows.append((start, end))
    return windows


def _line_clock_minutes(line: str) -> int | None:
    m = re.match(r"^\[(\d{1,2}:\d{2})\]", line)
    return _clock_minutes(m.group(1)) if m else None


def _time_context(lines: list[str], windows: list[tuple[int, int]]) -> tuple[list[str], list[int]]:
    if not windows:
        return [], []
    chunks: list[str] = []
    matched_indices: list[int] = []
    for start_min, end_min in windows:
        ids = [
            i for i, line in enumerate(lines)
            if (minute := _line_clock_minutes(line)) is not None and start_min <= minute <= end_min
        ]
        if not ids:
            continue
        matched_indices.extend(ids)
        lo, hi = max(0, ids[0] - 4), min(len(lines), ids[-1] + 7)
        if chunks:
            chunks.append("[[SOURCE_WINDOW_GAP]]")
        chunks.extend(lines[lo:hi])
    return chunks, matched_indices


def _explicit_source_context(raw: str, expected_date: str) -> tuple[list[str], list[dict]]:
    """Read exact 1-based inclusive source ranges saved on a Topic Card."""
    if not raw:
        return [], []
    context: list[str] = []
    parsed: list[dict] = []
    for piece in (x.strip() for x in raw.split(";")):
        if not piece:
            continue
        match = SOURCE_RANGE_RE.fullmatch(piece)
        if not match:
            return [], []
        date, part_name, start_text, end_text = match.groups()
        start, end = int(start_text), int(end_text)
        if date != expected_date or start < 1 or end < start:
            return [], []
        path = CHUNKS_DIR / date / part_name
        if not path.exists():
            return [], []
        lines = path.read_text(encoding="utf-8").splitlines()
        if end > len(lines):
            return [], []
        if context:
            context.append("[[SOURCE_WINDOW_GAP]]")
        context.extend(lines[start - 1:end])
        parsed.append({
            "file": f"full-history-chunks/{date}/{part_name}",
            "start_line": start,
            "end_line": end,
        })
    return context, parsed


def link_sources(cards: list[dict]) -> dict:
    """Attach source from verified overlays or a card's own saved time_range.

    Keyword-only matching is never allowed to produce user-visible source evidence.
    Historical cards without time_range stay unlinked unless an independently verified
    file/line overlay exists in VERIFIED_SOURCE_ANCHORS.
    """
    verified = {}
    if VERIFIED_SOURCE_ANCHORS.exists():
        verified = json.loads(VERIFIED_SOURCE_ANCHORS.read_text(encoding="utf-8")).get("anchors", {})
    by_date: dict[str, list[dict]] = {}
    for card in cards:
        by_date.setdefault(card["date"], []).append(card)

    stats = {"high": 0, "medium": 0, "none": 0}
    for date, day_cards in by_date.items():
        lines = read_day_lines(date)
        for card in day_cards:
            anchor = verified.get(card.get("card_id", ""))
            if anchor:
                context = read_verified_anchor_context(date, anchor)
                card["source_link"] = {
                    "confidence": "high",
                    "context": context,
                    "matched_terms": [],
                    "time_range": anchor.get("time_range", ""),
                    "reason": "verified_source_backfill",
                }
                stats["high"] += 1
                continue

            explicit_context, explicit_ranges = _explicit_source_context(
                card.get("source_ranges", ""),
                date,
            )
            if explicit_context and explicit_ranges:
                card["source_link"] = {
                    "confidence": "high",
                    "context": explicit_context,
                    "matched_terms": [],
                    "time_range": card.get("time_range", ""),
                    "source_ranges": explicit_ranges,
                    "reason": "explicit_source_ranges",
                }
                stats["high"] += 1
                continue

            windows = _time_windows(card.get("time_range", ""))
            if not lines or not windows:
                card["source_link"] = {
                    "confidence": "none",
                    "context": [],
                    "reason": "no_saved_time_range" if lines else "missing_day_source",
                }
                stats["none"] += 1
                continue

            context, matched_indices = _time_context(lines, windows)
            if not context or not matched_indices:
                card["source_link"] = {
                    "confidence": "none",
                    "context": [],
                    "reason": "time_range_not_found",
                }
                stats["none"] += 1
                continue

            block = "\n".join(x for x in context if x != "[[SOURCE_WINDOW_GAP]]").lower()
            terms = compact_terms(card)
            matched = [t for t in terms if t.lower() in block]
            distinctive = [
                t for t in matched
                if not re.fullmatch(r"\d+", t)
                and t not in GENERIC_TERMS
                and len(t) >= 2
            ]

            # The saved time range is the primary anchor. At least one semantic clue is
            # still required before the page calls the link directly viewable.
            confidence = "high" if distinctive else "medium"
            card["source_link"] = {
                "confidence": confidence,
                "context": context,
                "matched_terms": matched,
                "time_range": card.get("time_range", ""),
                "reason": "saved_time_range",
            }
            stats[confidence] += 1
    return stats


def _chat_text_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", "", normalized).casefold()


def _parse_chat_messages(context: list[str]) -> list[dict]:
    parsed_messages = []
    current = None
    msg_re = re.compile(r"^\[(.*?)\] \[(.*?)\]\s?(.*)$")
    for raw_line in context:
        if raw_line == "[[SOURCE_WINDOW_GAP]]":
            if current:
                parsed_messages.append(current)
                current = None
            parsed_messages.append({"divider": True})
            continue
        m = msg_re.match(raw_line)
        if m:
            if current:
                parsed_messages.append(current)
            current = {"time": m.group(1).strip(), "name": m.group(2).strip(), "content": m.group(3).strip()}
        elif current:
            current["content"] += ("\n" if current["content"] else "") + raw_line
        else:
            parsed_messages.append({"time": "", "name": "", "content": raw_line})
    if current:
        parsed_messages.append(current)

    # Historical canonical text can contain an adjacent-page overlap when one page
    # saw a headerless clipped fragment and the next page reconstructed the same text
    # as part of a complete message. Keep canonical untouched for traceability, but
    # suppress only strongly confirmed display duplicates in the source drawer.
    drop: set[int] = set()
    for i, msg in enumerate(parsed_messages):
        if msg.get("divider"):
            continue
        name = msg.get("name", "")
        time_text = msg.get("time", "")
        key = _chat_text_key(msg.get("content", ""))
        is_unknown_fragment = name in {"", "未知成员"} or time_text in {"", "未知时间"}
        if not is_unknown_fragment or len(key) < 8:
            continue
        for j in range(i + 1, min(len(parsed_messages), i + 9)):
            later = parsed_messages[j]
            if later.get("divider"):
                break
            later_key = _chat_text_key(later.get("content", ""))
            if key and key in later_key:
                drop.add(i)
                break

    deduped: list[dict] = []
    for i, msg in enumerate(parsed_messages):
        if i in drop:
            continue
        if msg.get("divider"):
            deduped.append(msg)
            continue
        key = _chat_text_key(msg.get("content", ""))
        duplicate_index = None
        for k in range(len(deduped) - 1, max(-1, len(deduped) - 9), -1):
            previous = deduped[k]
            if previous.get("divider"):
                break
            if not msg.get("name") or not msg.get("time"):
                continue
            if msg.get("name") != previous.get("name") or msg.get("time") != previous.get("time"):
                continue
            previous_key = _chat_text_key(previous.get("content", ""))
            exact = key == previous_key and len(key) >= 5
            fuzzy = min(len(key), len(previous_key)) >= 12 and SequenceMatcher(None, key, previous_key).ratio() >= 0.90
            if exact or fuzzy:
                duplicate_index = k
                break
        if duplicate_index is not None:
            if len(key) >= len(_chat_text_key(deduped[duplicate_index].get("content", ""))):
                deduped[duplicate_index] = msg
            continue
        deduped.append(msg)

    # QQ reply bubbles can include the quoted sender + quoted body + the new @reply
    # as one OCR message. When the quoted body is already present immediately above,
    # collapse the repeated quote to a small reply marker instead of showing the same
    # sentence twice in the drawer.
    for i, msg in enumerate(deduped):
        if msg.get("divider"):
            continue
        lines = [line.strip() for line in str(msg.get("content", "")).splitlines() if line.strip()]
        if len(lines) < 3 or not lines[-1].startswith("@"):
            continue
        quoted_sender = lines[0]
        quoted_body = "\n".join(lines[1:-1])
        quoted_key = _chat_text_key(quoted_body)
        if not quoted_key:
            continue
        for previous in reversed(deduped[max(0, i - 6):i]):
            if previous.get("divider"):
                break
            if quoted_sender != previous.get("name"):
                continue
            if quoted_key == _chat_text_key(previous.get("content", "")):
                msg["reply_to"] = quoted_sender
                msg["content"] = lines[-1]
                break
    return deduped


def render_chat_messages(context: list[str]) -> str:
    parsed_messages = _parse_chat_messages(context)

    message_html = []
    for msg in parsed_messages:
        if msg.get("divider"):
            message_html.append('<div class="window-gap">另一段时间窗口</div>')
            continue
        time_text = html.escape(msg["time"] or "")
        name_text = html.escape(msg["name"] or "未识别")
        content_text = html.escape(msg["content"] or "")
        reply_ref = f'<div class="reply-ref">↳ 回复 {html.escape(msg["reply_to"])}</div>' if msg.get("reply_to") else ""
        muted = " muted" if msg["name"] in {"", "未知成员"} or msg["time"] == "未知时间" else ""
        message_html.append(
            f'<div class="msg{muted}"><div class="msg-head"><span class="name">{name_text}</span><span class="time">{time_text}</span></div>{reply_ref}<div class="content">{content_text}</div></div>'
        )
    return "".join(message_html)


def write_detail_pages(cards: list[dict]) -> None:
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    for old in DETAILS_DIR.glob("*.html"):
        old.unlink()

    for card in cards:
        aggregate_windows = card.get("aggregate_evidence_windows") or []
        if aggregate_windows:
            detail_name = f"{card['card_id']}.html"
            title = html.escape(card["title"])
            summary = html.escape(card["semantic_summary"])
            cid = html.escape(card["card_id"])
            sections = []
            for item in aggregate_windows:
                date = item["date"]
                windows = _time_windows(item["time_range"])
                context, _matched = _time_context(read_day_lines(date), windows)
                if not context:
                    continue
                sections.append(
                    f'<section class="day"><h2>{html.escape(date)} · {html.escape(item["time_range"])}</h2><div class="chat">{render_chat_messages(context)}</div></section>'
                )
            detail = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>body{{margin:0;background:#f6f8fb;color:#172033;font:16px/1.72 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}main{{padding:20px 18px 40px}}.meta{{color:#7a8698;font-size:12px;margin-bottom:6px}}h1{{font-size:20px;line-height:1.4;margin:0 0 6px}}.summary{{color:#596579;font-size:15px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #e1e7ef}}.day{{margin:18px 0 24px}}.day h2{{font-size:15px;margin:0 0 10px;color:#344054}}.chat{{display:grid;gap:10px}}.msg{{background:#fff;border:1px solid #e1e7ef;border-radius:11px;padding:11px 13px}}.msg-head{{display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin-bottom:4px}}.name{{font-size:13px;font-weight:700;color:#344054}}.time{{font-size:11px;color:#98a2b3;white-space:nowrap}}.reply-ref{{color:#8a96a8;font-size:12px;margin:-1px 0 4px;padding-left:8px;border-left:2px solid #d8dee8}}.content{{white-space:pre-wrap;word-break:break-word;color:#27364b;font-size:15px}}.msg.muted{{background:#fafbfc;border-style:dashed}}.window-gap{{text-align:center;color:#98a2b3;font-size:11px;padding:4px}}@media(max-width:640px){{main{{padding:16px 12px 32px}}}}</style></head><body><main><div class="meta">{cid} · 跨日连续证据</div><h1>{title}</h1><div class="summary">{summary}</div>{''.join(sections)}</main></body></html>'''
            (DETAILS_DIR / detail_name).write_text(detail, encoding="utf-8")
            card["source_link"] = {
                "confidence": "high",
                "detail_href": f"page-v2-details/{detail_name}",
                "matched_terms": [],
            }
            continue

        link = card.get("source_link", {})
        confidence = link.get("confidence", "none")
        context = link.get("context") or []
        if confidence == "high" and context:
            detail_name = f"{card['card_id']}.html"
            title = html.escape(card["title"])
            summary = html.escape(card["semantic_summary"])
            cid = html.escape(card["card_id"])
            date = html.escape(card["date"])

            parsed_messages = _parse_chat_messages(context)

            message_html = []
            for msg in parsed_messages:
                if msg.get("divider"):
                    message_html.append('<div class="window-gap">另一段时间窗口</div>')
                    continue
                time_text = html.escape(msg["time"] or "")
                name_text = html.escape(msg["name"] or "未识别")
                content_text = html.escape(msg["content"] or "")
                reply_ref = f'<div class="reply-ref">↳ 回复 {html.escape(msg["reply_to"])}</div>' if msg.get("reply_to") else ""
                muted = " muted" if msg["name"] in {"", "未知成员"} or msg["time"] == "未知时间" else ""
                message_html.append(
                    f'<div class="msg{muted}"><div class="msg-head"><span class="name">{name_text}</span><span class="time">{time_text}</span></div>{reply_ref}<div class="content">{content_text}</div></div>'
                )
            messages = "".join(message_html)
            detail = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>body{{margin:0;background:#f6f8fb;color:#172033;font:16px/1.72 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}main{{padding:20px 18px 40px}}.meta{{color:#7a8698;font-size:12px;margin-bottom:6px}}h1{{font-size:20px;line-height:1.45;margin:0 0 7px}}.summary{{color:#596579;font-size:15px;margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid #e1e7ef}}.chat{{display:grid;gap:10px}}.msg{{background:#fff;border:1px solid #e1e7ef;border-radius:11px;padding:10px 12px;box-shadow:0 2px 6px rgba(20,30,50,.03)}}.msg-head{{display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin-bottom:4px}}.name{{font-size:13px;font-weight:700;color:#344054}}.time{{font-size:11px;color:#98a2b3;white-space:nowrap}}.reply-ref{{color:#8a96a8;font-size:12px;margin:-1px 0 4px;padding-left:8px;border-left:2px solid #d8dee8}}.content{{white-space:pre-wrap;word-break:break-word;color:#27364b;font-size:15px}}.msg.muted{{background:#fafbfc;border-style:dashed}}.msg.muted .name,.msg.muted .time{{color:#98a2b3}}.msg.muted .content{{color:#667085}}@media(max-width:640px){{main{{padding:16px 12px 32px}}}}</style></head><body><main><div class="meta">{cid} · {date} · 连续原文</div><h1>{title}</h1><div class="summary">{summary}</div><div class="chat">{messages}</div></main></body></html>'''
            (DETAILS_DIR / detail_name).write_text(detail, encoding="utf-8")
            card["source_link"] = {
                "confidence": "high",
                "detail_href": f"page-v2-details/{detail_name}",
                "matched_terms": link.get("matched_terms", []),
                "reason": link.get("reason", ""),
                "time_range": link.get("time_range", ""),
            }
        else:
            card["source_link"] = {
                "confidence": confidence,
                "matched_terms": link.get("matched_terms", []),
                "reason": link.get("reason", ""),
            }


def evidence_group(raw: str) -> tuple[str, str]:
    """Collapse legacy free-form evidence_status into one user-facing source type.

    The old field mixed evidence source, uncertainty, market context and analysis
    method into hundreds of strings. Keep raw status internally, but expose only
    a small understandable primary group in the UI.
    """
    s = (raw or "").lower()

    # Uncertainty wins because this is the most important thing for a reader to notice.
    if any(k in s for k in (
        "disputed", "conflict", "requires_verification", "verification_needed",
        "verification_required", "unresolved", "speculative", "rumor", "hearsay",
        "prelaunch", "beta_claim", "uncertain", "incomplete_context",
    )):
        return "verify", "待核验 / 有争议"

    if any(k in s for k in (
        "market", "price", "income", "cost_sample", "wage", "economic_sample",
        "service_cost", "service_time", "roi_case", "budget_case",
    )):
        return "market", "市场 / 价格样本"

    if any(k in s for k in (
        "derived", "assistant_analysis", "reasoning", "time_model", "taxonomy",
        "design_implication", "best_practice", "analysis_from_context",
    )):
        return "analysis", "AI 推导"

    if any(k in s for k in (
        "direct_", "observed_", "longitudinal_", "field_test", "resolution",
        "actual", "live_sample", "system_evidence",
    )):
        return "direct", "实际操作 / 结果"

    if any(k in s for k in (
        "repeated_", "group_consensus", "independent_peer", "crossday",
        "cross_day", "multiple_samples", "repeated_consensus",
    )):
        return "repeated", "多人重复支持"

    if any(k in s for k in (
        "anecdotal", "player_experience", "player_observation", "player_behavior",
        "player_case", "self_reported", "single_", "expert_anecdote",
    )):
        return "personal", "单人亲历"

    if any(k in s for k in (
        "group_", "peer_advice", "route_advice", "tool_advice", "opinion",
        "heuristic", "strategy", "terminology", "slang", "community_",
    )):
        return "group", "群友说法 / 建议"

    return "other", "其他来源"


def parse_collection(cid: str) -> dict | None:
    path = COLLECTION_DIR / f"{cid}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")

    def section(name: str) -> str:
        m = re.search(rf"^## {re.escape(name)}\n\n(.+?)(?=\n## |\Z)", text, re.M | re.S)
        return re.sub(r"\n{3,}", "\n\n", m.group(1).strip()) if m else ""

    def plain(value: str) -> str:
        value = re.sub(r"\*\*(.+?)\*\*", r"\1", value)
        value = re.sub(r"`(.+?)`", r"\1", value)
        return re.sub(r"\s+", " ", value).strip()

    def bullets(value: str) -> list[str]:
        out = []
        for line in value.splitlines():
            m = re.match(r"^\s*(?:[-*]|\d+\.)\s+(.+)$", line)
            if m:
                item = plain(m.group(1))
                if item:
                    out.append(item)
        return out

    title_m = re.search(r"^# Collection: (.+)$", text, re.M)
    core_m = re.search(r"^- core_question: (.+)$", text, re.M)
    synthesis = section("Cross-day synthesis")
    stable = section("Stable signals")
    disagreements = section("Disagreements / changes")
    decisions = section("Decision factors")
    backlog = ""
    for name in (
        "Verification backlog", "Verification / data backlog", "Verification / modeling backlog",
        "Modeling backlog",
    ):
        backlog = section(name)
        if backlog:
            break

    bold = re.search(r"\*\*(.+?)\*\*", synthesis, re.S)
    if bold:
        conclusion = plain(bold.group(1))
    else:
        first_para = synthesis.split("\n\n", 1)[0] if synthesis else ""
        conclusion = plain(re.split(r"(?<=[。！？])", first_para, maxsplit=1)[0])

    dated = section("Dated evidence")
    evidence_cards = sorted(set(re.findall(r"T-\d{8}-\d+", dated)))
    warnings = bullets(disagreements) or bullets(backlog)

    return {
        "collection_id": cid,
        "title": title_m.group(1).strip() if title_m else cid,
        "core_question": core_m.group(1).strip() if core_m else "",
        "core_conclusion": conclusion,
        "key_points": bullets(stable)[:4],
        "warnings": warnings[:3],
        "decision_factors": bullets(decisions)[:4],
        "evidence_count": len(evidence_cards),
        "synthesis": synthesis,
        "stable_signals": stable,
        "disagreements": disagreements,
        "dated_evidence": dated,
    }


def parse_blackwords() -> list[dict]:
    """Read the normalized slang dictionary as an independent view, not topic cards."""
    if not BLACKWORD_FILE.exists():
        return []
    text = BLACKWORD_FILE.read_text(encoding="utf-8")
    text = text.split("\n# 词典规则", 1)[0]

    def plain(value: str) -> str:
        value = re.sub(r"\*\*(.+?)\*\*", r"\1", value)
        value = re.sub(r"`(.+?)`", r"\1", value)
        value = re.sub(r"\[(.+?)\]", r"\1", value)
        return re.sub(r"\s+", " ", value).strip()

    entries: list[dict] = []
    matches = list(re.finditer(r"^## (.+)$", text, re.M))
    for idx, match in enumerate(matches):
        term = match.group(1).strip()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[match.end():end]
        fields: dict[str, str] = {}
        current = ""
        for raw in block.splitlines():
            line = raw.rstrip()
            m = re.match(r"^- ([a-z_]+):\s*(.*)$", line)
            if m:
                current = m.group(1)
                fields[current] = plain(m.group(2))
                continue
            nested = re.match(r"^\s{2,}-\s+(.+)$", line)
            if nested and current:
                extra = plain(nested.group(1))
                if extra:
                    fields[current] = (fields.get(current, "") + "；" + extra).strip("；")
        entries.append({"term": term, **fields})
    return entries


def build_html(cards: list[dict], collections: list[dict], blackwords: list[dict], stats: dict) -> str:
    raw_card_count = sum(not c.get("synthetic_aggregate") and not c.get("synthetic_supplement") for c in cards)
    aggregate_count = sum(bool(c.get("synthetic_aggregate")) for c in cards)
    supplemental_count = sum(bool(c.get("synthetic_supplement")) for c in cards)
    dates = sorted({c["date"] for c in cards if not c.get("synthetic_aggregate")})
    visible_cards = [
        c for c in cards
        if c.get("reorg_layer", "main") in {"main", "review"}
        and not c.get("aggregate_component_exclude")
    ]
    main_count = sum(c.get("reorg_layer") == "main" and not c.get("aggregate_component_exclude") for c in cards)
    review_count = sum(c.get("reorg_layer") == "review" and not c.get("aggregate_component_exclude") for c in cards)
    hidden_count = sum(c.get("reorg_layer") == "hidden" for c in cards)
    archive_count = sum(c.get("reorg_layer") == "archive" for c in cards)
    collection_only_count = sum(c.get("reorg_layer") == "collection" for c in cards)
    dictionary_card_count = sum(c.get("reorg_layer") == "dictionary" for c in cards)
    aggregate_components_hidden = sum(bool(c.get("aggregate_component_exclude")) for c in cards)

    confidence_labels = {
        "high": "高",
        "medium_high": "较高",
        "medium": "中",
        "high for observed context": "该语境高",
        "high only for this recruitment context": "仅该招募语境高",
        "high only for cited context": "仅引用语境高",
        "high for context-dependence": "上下文依赖性高",
    }
    note_keys = [
        ("important_distinction", "注意"), ("important_distinctions", "注意"),
        ("ambiguity", "歧义"), ("risk_semantics", "风险"), ("interpretation", "解释"),
        ("typical_behavior", "常见表现"), ("connotation", "语气"), ("semantic_extension", "延伸"),
        ("economic_role", "经济含义"), ("price_behavior", "价格特征"),
    ]
    blackword_cards = []
    for entry in blackwords:
        term = html.escape(entry.get("term", ""))
        meaning = html.escape(entry.get("canonical_meaning", "") or "暂未形成稳定释义")
        context = html.escape(entry.get("context", ""))
        notes = []
        for key, label in note_keys:
            value = entry.get(key, "")
            if value:
                notes.append(f'<div class="slang-note"><b>{label}</b><span>{html.escape(value)}</span></div>')
        confidence_raw = entry.get("confidence", "")
        confidence = confidence_labels.get(confidence_raw, confidence_raw.replace("_", " ")) if confidence_raw else ""
        evidence = html.escape(entry.get("evidence", "") or entry.get("first_evidence", ""))
        meta = []
        if confidence:
            meta.append(f"可信度：{html.escape(confidence)}")
        if evidence:
            meta.append(f"来源：{evidence}")
        search_text = " ".join(str(v) for v in entry.values()).lower()
        blackword_cards.append(
            f'<article class="slang-card" data-slang-search="{html.escape(search_text, quote=True)}">'
            f'<h3>{term}</h3><div class="slang-meaning">{meaning}</div>'
            + (f'<div class="slang-context"><b>常见语境</b>{context}</div>' if context else "")
            + "".join(notes)
            + (f'<div class="slang-meta">{" · ".join(meta)}</div>' if meta else "")
            + '</article>'
        )
    blackword_html = "".join(blackword_cards)

    payload = json.dumps(cards, ensure_ascii=False).replace("</", "<\\/")
    collections_payload = json.dumps(collections, ensure_ascii=False).replace("</", "<\\/")
    date_options = "".join(f'<option value="{d}">{d}</option>' for d in dates)
    default_main_cards = [c for c in cards if c.get("reorg_layer") == "main" and not c.get("aggregate_component_exclude")]
    profession_counts = [("all", "全部", len(default_main_cards))]
    profession_counts += [(key, label, sum(key in c.get("profession_keys", []) for c in default_main_cards)) for key, label, _aliases in PROFESSIONS]
    profession_counts.append(("noncareer", "非职业", sum(c.get("profession_keys") == ["noncareer"] for c in default_main_cards)))
    profession_tabs = "".join(
        f'<button class="profession-tab{" active" if key == "all" else ""}" data-profession="{key}" style="{"" if count else "display:none"}">{label}<span>{count}</span></button>'
        for key, label, count in profession_counts
    )
    system_tag_counts = [(key, label, sum(key in c.get("system_tags", []) for c in default_main_cards)) for key, label in SYSTEM_TAGS]
    system_tag_tabs = "".join(
        f'<button class="system-tab" data-system-tag="{key}" style="{"" if count else "display:none"}">{label}<span>{count}</span></button>'
        for key, label, count in system_tag_counts
    )
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>群聊情报 · 页面 v2.1</title>
<style>
:root{{--bg:#f5f7fa;--panel:#fff;--line:#e1e7ef;--ink:#172033;--muted:#667085;--blue:#3159d6;--blueSoft:#edf2ff;--soft:#f8fafc;--amber:#8a570b;--amberSoft:#fff3d7;--green:#1f6b48;--greenSoft:#edf8f2;--red:#9d4335;--redSoft:#fff0ed}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.72 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}button,input,select{{font:inherit}}.shell{{max-width:1220px;margin:auto;padding:22px 26px 70px}}.head{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:18px}}h1{{font-size:21px;margin:0 0 4px}}.sub{{color:var(--muted);font-size:12px}}.stats{{text-align:right;color:var(--muted);font-size:12px}}.stats b{{color:var(--ink)}}.tabs{{position:sticky;top:0;z-index:10;background:rgba(245,247,250,.96);backdrop-filter:blur(10px);display:flex;gap:3px;border-bottom:1px solid var(--line);margin:0 -26px 22px;padding:0 26px;overflow:auto}}.tabs button{{border:0;background:none;padding:12px 11px 10px;color:var(--muted);white-space:nowrap;cursor:pointer;border-bottom:2px solid transparent;font-weight:650}}.tabs button.active{{color:var(--ink);border-color:var(--blue)}}.view{{display:none}}.view.active{{display:block}}.intro{{margin:2px 0 17px}}.intro h2{{font-size:25px;letter-spacing:-.03em;margin:0 0 5px}}.intro p{{margin:0;color:var(--muted);max-width:850px}}.notice{{border:1px solid #ead5a8;background:#fffaf0;border-radius:11px;padding:12px 14px;color:#6e501a;margin-bottom:15px}}.switch{{display:inline-flex;background:#e9eef5;padding:3px;border-radius:9px;margin-bottom:13px}}.switch button{{border:0;background:none;padding:6px 10px;border-radius:7px;color:#667085;cursor:pointer}}.switch button.active{{background:#fff;color:#172033;font-weight:700;box-shadow:0 1px 4px #0001}}.mode{{display:none}}.mode.active{{display:block}}.profession-tabs,.system-tabs{{display:flex;gap:6px;overflow:auto;padding:2px 0 10px;margin-bottom:8px;scrollbar-width:thin}}.profession-tab,.system-tab{{border:1px solid var(--line);background:#fff;color:#596579;border-radius:999px;padding:6px 10px;white-space:nowrap;cursor:pointer;font-size:12px}}.profession-tab span,.system-tab span{{margin-left:5px;color:#98a2b3;font-size:10px}}.profession-tab.active,.system-tab.active{{background:#172033;color:#fff;border-color:#172033}}.profession-tab.active span,.system-tab.active span{{color:#cbd5e1}}.filter-label{{font-size:11px;color:#7a8698;margin:0 0 4px}}.profession-note{{font-size:11px;color:#7a8698;margin:-2px 0 10px}}.toolbar{{display:grid;grid-template-columns:minmax(240px,1.35fr) minmax(150px,.55fr) minmax(170px,.65fr) minmax(165px,.65fr);gap:8px;margin-bottom:10px}}.topic-group-head{{margin:18px 0 8px;padding:9px 3px 6px;border-bottom:1px solid #cfd8e3;display:flex;justify-content:space-between;align-items:baseline}}.topic-group-head b{{font-size:15px}}.topic-group-head span{{font-size:11px;color:#8a96a8}}.related-block{{border:1px solid rgba(90,105,135,.16);border-radius:13px;padding:10px;margin:8px 0 12px}}.related-block.tone-0{{background:#e9f3ff}}.related-block.tone-1{{background:#f3efff}}.related-head{{font-size:13px;font-weight:700;color:#384860;margin:0 2px 8px;padding:0 0 7px;border-bottom:1px solid rgba(90,105,135,.22)}}input,select{{width:100%;border:1px solid var(--line);background:#fff;border-radius:8px;padding:8px 9px;color:var(--ink)}}.resultbar{{display:flex;justify-content:space-between;gap:12px;align-items:center;color:var(--muted);font-size:12px;margin-bottom:9px}}.resultbar strong{{color:var(--ink)}}.evidence-legend{{display:flex;gap:12px;flex-wrap:wrap;margin:2px 0 12px;color:#667085;font-size:12px}}.legend-item{{display:flex;align-items:center;gap:6px}}.legend-swatch{{width:12px;height:12px;border-radius:3px;border:1px solid rgba(70,80,100,.18)}}.legend-strong{{background:#dff4e6}}.legend-verify{{background:#ffe4e1}}.cards{{display:block}}.card{{background:#fff;border:1px solid #dfe5ec;border-radius:10px;padding:14px 16px;margin-top:7px}}.card.evidence-direct{{background:#f1faf4;border-color:#abd8b8;box-shadow:inset 4px 0 0 #58a46f}}.card.evidence-verify{{background:#fff3f1;border-color:#e6ada6;box-shadow:inset 4px 0 0 #cb665a}}.card:first-of-type{{margin-top:0}}.topline{{display:flex;gap:7px;flex-wrap:wrap;align-items:center;color:var(--muted);font-size:11px;margin-bottom:4px}}.id{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#59667a}}.card h3{{font-size:18px;line-height:1.5;margin:0 0 7px}}.summary{{color:#465269;font-size:16px;line-height:1.7}}.aggregate-facts{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 0 4px}}.aggregate-fact{{background:rgba(255,255,255,.72);border:1px solid rgba(95,115,135,.16);border-radius:9px;padding:9px 10px}}.aggregate-fact b{{display:block;font-size:12px;color:#667085;margin-bottom:2px}}.aggregate-fact span{{font-size:15px;color:#2f3b4f}}.card-meta{{margin-top:9px;color:#667085;font-size:13px;line-height:1.55}}.card-meta b{{color:#465269;font-weight:650}}.pending{{margin-top:8px;color:#8c5b1b;background:#fff9eb;border:1px solid #ecd7a7;border-radius:8px;padding:9px 10px;font-size:12px}}.context-button{{border:0;background:none;padding:0;margin-top:9px;color:#3159d6;font-size:12px;font-weight:650;cursor:pointer}}.context-button:hover{{text-decoration:underline}}.feedback{{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}}.feedback span{{color:var(--muted);font-size:11px;align-self:center}}.feedback button{{border:1px solid var(--line);background:#fff;color:#667085;padding:3px 7px;border-radius:6px;font-size:11px;cursor:pointer}}.feedback button.selected{{border-color:#9eb0eb;background:var(--blueSoft);color:#334da7}}.pager{{display:flex;justify-content:center;gap:8px;align-items:center;margin-top:16px}}.pager button{{border:1px solid var(--line);background:#fff;border-radius:7px;padding:6px 10px;cursor:pointer}}.pager button:disabled{{opacity:.4}}.collection-guide{{margin:2px 0 12px;padding:10px 12px;border-radius:9px;background:#fff;border:1px solid #e1e7ef;color:#667085;font-size:12px}}.collections{{display:grid;gap:14px}}.collection{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 20px;box-shadow:0 1px 2px rgba(24,34,52,.03)}}.collection-head{{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;margin-bottom:8px}}.collection h3{{margin:0;font-size:19px;line-height:1.45}}.collection-count{{white-space:nowrap;color:#7d899a;font-size:12px;padding-top:3px}}.question{{color:#6b7688;font-size:14px;margin-bottom:12px}}.collection-conclusion{{background:#f3f7ff;border:1px solid #dbe5fb;border-left:4px solid #7894d6;border-radius:10px;padding:12px 14px;margin-bottom:12px}}.collection-conclusion span{{display:block;color:#6a7890;font-size:11px;font-weight:700;letter-spacing:.08em;margin-bottom:3px}}.collection-conclusion b{{font-size:16px;line-height:1.65;color:#25344e}}.collection-grid{{display:grid;grid-template-columns:1.35fr 1fr;gap:10px;margin-bottom:10px}}.collection-panel{{border:1px solid #e3e8ef;border-radius:10px;padding:12px 13px;background:#fafbfc}}.collection-panel.warn{{background:#fff8f4;border-color:#f0d9cc}}.collection-panel h4{{margin:0 0 7px;font-size:14px}}.collection-panel ul{{margin:0;padding-left:20px}}.collection-panel li{{margin:5px 0;color:#445168;font-size:15px;line-height:1.65}}.collection-panel.warn li{{color:#704f45}}.decision-row{{border-top:1px solid #edf0f4;padding-top:10px;margin-top:4px;color:#5f6b7e;font-size:13px}}.decision-row b{{color:#3f4b5e}}.collection details{{margin-top:10px;border-top:1px solid #edf0f4;padding-top:10px}}.collection details summary{{cursor:pointer;color:#56647a;font-size:14px;font-weight:650}}.detail-section{{margin-top:10px}}.detail-section h5{{margin:8px 0 4px;font-size:13px;color:#667085}}.detail-text{{white-space:pre-wrap;font:15px/1.72 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#536075;background:#f8fafc;border-radius:8px;padding:10px 12px}}@media(max-width:760px){{.collection-grid{{grid-template-columns:1fr}}}}.slang-toolbar{{display:flex;gap:10px;align-items:center;margin:0 0 12px}}.slang-toolbar input{{max-width:520px}}.slang-result{{color:#667085;font-size:13px;white-space:nowrap}}.slang-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}.slang-card{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 18px}}.slang-card h3{{margin:0 0 6px;font-size:19px;line-height:1.4}}.slang-meaning{{font-size:16px;line-height:1.72;color:#354257;margin-bottom:9px}}.slang-context{{font-size:14px;color:#5f6b7e;margin:5px 0}}.slang-context b{{color:#465269;margin-right:8px}}.slang-note{{display:grid;grid-template-columns:58px 1fr;gap:7px;margin-top:6px;font-size:14px;line-height:1.65}}.slang-note b{{color:#7b5b21}}.slang-note span{{color:#56647a}}.slang-meta{{margin-top:10px;padding-top:8px;border-top:1px solid #edf0f4;color:#8994a5;font-size:11px}}@media(max-width:760px){{.slang-grid{{grid-template-columns:1fr}}.slang-toolbar{{display:block}}.slang-result{{margin-top:6px}}}}.placeholder{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:24px;color:#536075}}.placeholder h3{{margin:0 0 7px}}.placeholder p{{margin:0;color:var(--muted)}}.drawer-backdrop{{position:fixed;inset:0;background:rgba(20,30,50,.18);opacity:0;pointer-events:none;transition:opacity .18s ease;z-index:40}}.drawer{{position:fixed;top:0;right:0;height:100vh;width:min(560px,48vw);background:#fff;border-left:1px solid var(--line);box-shadow:-16px 0 38px rgba(22,34,56,.14);transform:translateX(100%);transition:transform .2s ease;z-index:41;display:flex;flex-direction:column}}.drawer.open{{transform:translateX(0)}}.drawer-backdrop.open{{opacity:1;pointer-events:auto}}.drawer-head{{height:52px;display:flex;align-items:center;justify-content:space-between;padding:0 14px 0 18px;border-bottom:1px solid var(--line);flex:none}}.drawer-head b{{font-size:13px}}.drawer-close{{border:1px solid var(--line);background:#fff;border-radius:7px;width:30px;height:30px;cursor:pointer;font-size:18px;line-height:1}}.drawer iframe{{border:0;width:100%;height:100%;background:#f6f8fb}}body.drawer-open{{overflow:hidden}}@media(max-width:820px){{.toolbar{{grid-template-columns:1fr 1fr}}.head{{display:block}}.stats{{text-align:left;margin-top:9px}}.drawer{{width:min(640px,80vw)}}}}@media(max-width:560px){{.shell{{padding:15px 13px 50px}}.tabs{{margin:0 -13px 18px;padding:0 13px}}.toolbar{{grid-template-columns:1fr}}.drawer{{width:100vw}}}}
</style></head><body><div class="shell">
<header class="head"><div><h1>群聊情报 · 页面 v2.1</h1><div class="sub">完整历史原型 · 先收敛成真正可读的信息，再讨论合集/总览</div></div><div class="stats"><b>{main_count:,}</b> 主信息 · <b>{review_count:,}</b> 待核验/建议 · <b>{len(blackwords)}</b> 黑话<br><b>70,973</b> canonical · <b>{raw_card_count:,}</b> 原始 topic cards · 原文可直接查看 {stats['high']:,} / 待核对 {stats['medium']:,} / 待补 {stats['none']:,}</div></header>
<nav class="tabs"><button class="active" data-view="topics">话题总览</button><button data-view="overview">本期总览</button><button data-view="tracking">长期追踪</button><button data-view="knowledge">攻略知识</button><button data-view="project">项目相关</button><button data-view="slang">黑话 · {len(blackwords)}</button></nav>
<section id="topics" class="view active"><div class="intro"><h2>话题总览</h2><p>底层仍保留全部 {raw_card_count:,} 张原始 topic card。当前真正进入主列表的是 <b>{main_count:,}</b> 条；另有 {review_count:,} 条待核验/建议，不计入“有效结论”。黑话从 {dictionary_card_count:,} 张定义类原卡归一为 {len(blackwords)} 个词；默认隐藏 {hidden_count:,} 条，历史留档 {archive_count:,} 条，{collection_only_count:,} 条仅进入总结/合集层。</p></div>
<div class="switch"><button class="active" data-mode="single">话题明细 · 主信息 {main_count:,}</button><button data-mode="collectionMode">合集（方案待定） · {len(collections)}</button></div>
<div id="single" class="mode active"><div class="filter-label">职业</div><div id="professionTabs" class="profession-tabs">{profession_tabs}</div><div class="filter-label">专题</div><div id="systemTabs" class="system-tabs"><button class="system-tab active" data-system-tag="">全部专题</button>{system_tag_tabs}</div><div class="profession-note">职业与专题可以组合筛选；任何标签在当前信息层、搜索、日期或原文状态下变成 0 条时会自动隐藏。专题只收能形成持续知识组的内容，不把每个零散关键词都做成标签。</div><div class="toolbar"><input id="q" placeholder="搜索当前页的标题、摘要、卡片ID"><select id="info"><option value="main">主信息</option><option value="review">待核验 / 建议</option><option value="all">主信息 + 待核验</option></select><select id="date"><option value="">全部日期</option>{date_options}</select><select id="link"><option value="">全部原文状态</option><option value="high">原文可查看</option><option value="medium">原文候选待确认</option><option value="none">原文回链待补</option></select></div><div class="resultbar"><div>当前页 <strong id="shown">0</strong> 条信息</div><div>连续过程优先合成；纯意见、个人安排和缺关键输入的空泛结论不占主列表</div></div><div class="evidence-legend"><span class="legend-item"><i class="legend-swatch legend-strong"></i>绿色：实际操作 / 明确结果</span><span class="legend-item"><i class="legend-swatch legend-verify"></i>红色：待核验 / 有争议</span><span class="legend-item">白色：其余信息，暂不强行赋色</span></div><div id="cards" class="cards"></div><div class="pager"><button id="prev">上一页</button><span id="page"></span><button id="next">下一页</button></div></div>
<div id="collectionMode" class="mode"><div class="collection-guide"><b>方案待定：</b>这20个合集暂时只作为旧结构参考，不再继续精装修。等主信息继续收敛并经过你的逐条审阅后，再决定是否保留独立合集页，还是把“跨日/连续话题的最终总结”直接放到对应话题末尾。</div><div id="collections" class="collections"></div></div></section>
<section id="overview" class="view"><div class="intro"><h2>本期总览</h2><p>这一页暂时不再替你强行选 4 条“重点”。</p></div><div class="notice"><b>本版修正：</b>上一版把抽象分析当成重点，且在没有你的反馈时过早做了强排序。现在先完成 3,123 条单卡审阅和合集归类；GPT 的初始价值判断以后只作为卡片属性，等有足够用户反馈再生成真正个性化的本期总览。</div><div class="placeholder"><h3>总览将在用户判断积累后生成</h3><p>它最终应该回答“你这次最值得看什么”，而不是展示 GPT 自己觉得漂亮的方法论总结。</p></div></section>
<section id="tracking" class="view"><div class="intro"><h2>长期追踪</h2><p>先暂停精装修。等单条/合集与证据回链正确后，再从同一数据层投影动态信息。</p></div><div class="placeholder"><h3>后置</h3><p>价格、版本、服务器生态、职业人口等会变化的信息仍会保留日期和证据状态。</p></div></section>
<section id="knowledge" class="view"><div class="intro"><h2>攻略知识</h2><p>先暂停精装修，避免把抽象 AI 推导误当游戏事实。</p></div><div class="placeholder"><h3>后置</h3><p>正式版只从有具体事实/经验支撑的卡片提炼，并区分可复用、需核验和历史快照。</p></div></section>
<section id="project" class="view"><div class="intro"><h2>项目相关</h2><p>项目关联只是附加关系，不改变原卡语义，也不自动抬高价值。</p></div><div class="placeholder"><h3>后置</h3><p>仍执行“群聊候选 → 用户确认 → 目标项目核验 → 写回”。</p></div></section>
<section id="slang" class="view"><div class="intro"><h2>黑话词典</h2><p>当前直接展示 {len(blackwords)} 个已经语境化归一的黑话。黑话与职业主信息分离：词义用于帮助看懂原文，不因为某个词属于DK/猎人就占职业主列表。</p></div><div class="slang-toolbar"><input id="slangQ" placeholder="搜索黑话、含义或使用语境"><div class="slang-result">显示 <b id="slangShown">{len(blackwords)}</b> / {len(blackwords)}</div></div><div id="slangGrid" class="slang-grid">{blackword_html}</div></section>
</div>
<div id="drawerBackdrop" class="drawer-backdrop" onclick="closeSource()"></div>
<aside id="sourceDrawer" class="drawer" aria-hidden="true"><div class="drawer-head"><b>原文上下文</b><button class="drawer-close" onclick="closeSource()" aria-label="关闭">×</button></div><iframe id="sourceFrame" title="原文上下文"></iframe></aside>
<script id="cardData" type="application/json">{payload}</script><script id="collectionData" type="application/json">{collections_payload}</script>
<script>
const ALL=JSON.parse(document.getElementById('cardData').textContent); const COLLECTIONS=JSON.parse(document.getElementById('collectionData').textContent);
const esc=s=>String(s??'').replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[c]));
let activeProfession='all', activeSystemTag='', filtered=[], page=1; const per=50;
const cardsEl=document.getElementById('cards'), shown=document.getElementById('shown'), pageEl=document.getElementById('page');
function feedback(card){{return localStorage.getItem('gca-feedback:'+card.card_id)||card.user_value||''}}
function setFeedback(id,val){{localStorage.setItem('gca-feedback:'+id,val); render()}}
function reviewKind(decision){{
  const d=String(decision||'');
  if(d.includes('case_sample'))return '数值样本 · 待补比较基线';
  if(d.includes('case_mechanism'))return '案例机制 · 待核验';
  if(d.includes('case_value'))return '案例 · 待提炼可复用结论';
  if(d.includes('missing_baseline'))return '缺比较基线';
  if(d.includes('verification'))return '待核验';
  if(d.includes('advice'))return '建议';
  if(d.includes('rule_sample'))return '团规样本';
  if(d.includes('tool_case'))return '工具个案';
  if(d.includes('market_context'))return '市场背景';
  if(d.includes('group_knowledge'))return '群体经验';
  return '需复核';
}}
function openSource(href){{const drawer=document.getElementById('sourceDrawer'),backdrop=document.getElementById('drawerBackdrop'),frame=document.getElementById('sourceFrame'); frame.src=href; drawer.classList.add('open'); backdrop.classList.add('open'); drawer.setAttribute('aria-hidden','false'); document.body.classList.add('drawer-open')}}
function closeSource(){{const drawer=document.getElementById('sourceDrawer'),backdrop=document.getElementById('drawerBackdrop'),frame=document.getElementById('sourceFrame'); drawer.classList.remove('open'); backdrop.classList.remove('open'); drawer.setAttribute('aria-hidden','true'); document.body.classList.remove('drawer-open'); setTimeout(()=>{{frame.src='about:blank'}},180)}}
document.addEventListener('keydown',e=>{{if(e.key==='Escape')closeSource()}})
function render(){{
  const pages=Math.max(1,Math.ceil(filtered.length/per)); if(page>pages)page=pages;
  const slice=filtered.slice((page-1)*per,page*per); shown.textContent=filtered.length.toLocaleString(); pageEl.textContent=`第 ${{page}} / ${{pages}} 页`;
  document.getElementById('prev').disabled=page<=1; document.getElementById('next').disabled=page>=pages;
  const groupCounts={{}}; filtered.forEach(c=>groupCounts[c.topic_group_label]=(groupCounts[c.topic_group_label]||0)+1);
  let lastGroup='', lastRelated='', band=0, blockOpen=false, html='';
  for(const c of slice){{
    if(c.topic_group_label!==lastGroup){{
      if(blockOpen){{html+='</section>'; blockOpen=false}}
      lastGroup=c.topic_group_label; lastRelated=''; band=0;
      html+=`<div class="topic-group-head"><b>${{esc(c.topic_group_label)}}</b><span>${{groupCounts[c.topic_group_label]||0}} 条</span></div>`
    }}
    if(c.related_topic!==lastRelated){{
      if(blockOpen)html+='</section>';
      lastRelated=c.related_topic; band++;
      html+=`<section class="related-block tone-${{band%2}}"><div class="related-head">关联主题 · ${{esc(c.related_topic)}}</div>`;
      blockOpen=true
    }}
    const link=c.source_link||{{confidence:'none'}}; const fb=feedback(c);
    const sourceLabel=c.synthetic_aggregate?'查看跨日节点原文 →':'查看原文 →';
    const sourceAction=link.confidence==='high'&&link.detail_href?`<button class="context-button" onclick="openSource('${{esc(link.detail_href)}}')">${{sourceLabel}}</button>`:`<div class="pending">${{link.confidence==='medium'?'时间范围已经命中，但语义还需要人工核对。':'这张卡目前没有可靠的时间锚点原文，暂不展示猜测回链。'}}</div>`;
    const cross=(c.profession_labels||[]).length>1?` · <b>涉及</b>：${{esc(c.profession_labels.join(' / '))}}`:'';
    const reviewMeta=c.reorg_layer==='review'?` · <b>性质</b>：${{esc(reviewKind(c.reorg_decision))}}`:'';
    const facts=(c.aggregate_facts||[]).length?`<div class="aggregate-facts">${{c.aggregate_facts.map(x=>`<div class="aggregate-fact"><b>${{esc(x.label)}}</b><span>${{esc(x.value)}}</span></div>`).join('')}}</div>`:'';
    html+=`<article class="card evidence-${{esc(c.evidence_group||'other')}}"><div class="topline"><span class="id">${{esc(c.card_id)}}</span><span>${{esc(c.date)}}</span></div><h3>${{esc(c.title)}}</h3><div class="summary">${{esc(c.semantic_summary)}}</div>${{facts}}<div class="card-meta"><b>证据</b>：${{esc(c.evidence_label)}}${{cross}}${{reviewMeta}}</div>${{sourceAction}}<div class="feedback"><span>你的判断</span>${{['重要','有用','一般','没用','不确定'].map(v=>`<button class="${{fb===v?'selected':''}}" onclick="setFeedback('${{esc(c.card_id)}}','${{v}}')">${{v}}</button>`).join('')}}</div></article>`
  }}
  if(blockOpen)html+='</section>';
  cardsEl.innerHTML=html
}}
function baseMatch(c,info,q,date,link){{
  const layer=c.reorg_layer||'main';
  const layerOk=info==='all'?(layer==='main'||layer==='review'):layer===info;
  const text=[c.card_id,c.title,c.semantic_summary,...(c.tags||[]),...(c.collection_candidates||[])].join(' ').toLowerCase();
  return layerOk&&!c.aggregate_component_exclude&&(!q||text.includes(q))&&(!date||c.date===date)&&(!link||(c.source_link?.confidence||'none')===link)
}}
function professionMatch(c,key){{
  if(key==='all')return true;
  if(key==='noncareer')return (c.profession_keys||[]).length===1&&(c.profession_keys||[])[0]==='noncareer';
  return (c.profession_keys||[]).includes(key)
}}
function updateProfessionCounts(info,q,date,link){{
  document.querySelectorAll('.profession-tab').forEach(b=>{{
    const key=b.dataset.profession;
    const n=ALL.filter(c=>baseMatch(c,info,q,date,link)&&professionMatch(c,key)&&(!activeSystemTag||(c.system_tags||[]).includes(activeSystemTag))).length;
    const badge=b.querySelector('span'); if(badge)badge.textContent=n;
    b.style.display=n>0?'':'none';
  }})
}}
function updateSystemCounts(info,q,date,link){{
  document.querySelectorAll('.system-tab').forEach(b=>{{
    const key=b.dataset.systemTag||'';
    if(!key){{b.style.display='';return}}
    const n=ALL.filter(c=>baseMatch(c,info,q,date,link)&&professionMatch(c,activeProfession)&&(c.system_tags||[]).includes(key)).length;
    const badge=b.querySelector('span'); if(badge)badge.textContent=n;
    b.style.display=n>0?'':'none';
  }})
}}
function apply(){{
  const q=document.getElementById('q').value.trim().toLowerCase(), info=document.getElementById('info').value, date=document.getElementById('date').value, link=document.getElementById('link').value;
  updateProfessionCounts(info,q,date,link);
  updateSystemCounts(info,q,date,link);
  filtered=ALL.filter(c=>baseMatch(c,info,q,date,link)&&professionMatch(c,activeProfession)&&(!activeSystemTag||(c.system_tags||[]).includes(activeSystemTag)));
  const layerRank=c=>c.reorg_layer==='review'?1:0;
  filtered.sort((a,b)=>layerRank(a)-layerRank(b)||(a.topic_group_rank-b.topic_group_rank)||String(a.related_topic||'').localeCompare(String(b.related_topic||''),'zh-CN')||String(a.date).localeCompare(String(b.date))||String(a.card_id).localeCompare(String(b.card_id)));
  page=1; render()
}}
['q','info','date','link'].forEach(id=>document.getElementById(id).addEventListener(id==='q'?'input':'change',apply));
document.querySelectorAll('.profession-tab').forEach(b=>b.onclick=()=>{{activeProfession=b.dataset.profession; document.querySelectorAll('.profession-tab').forEach(x=>x.classList.toggle('active',x===b)); apply(); window.scrollTo({{top:180,behavior:'smooth'}})}});
document.querySelectorAll('.system-tab').forEach(b=>b.onclick=()=>{{activeSystemTag=b.dataset.systemTag||''; document.querySelectorAll('.system-tab').forEach(x=>x.classList.toggle('active',x===b)); apply(); window.scrollTo({{top:180,behavior:'smooth'}})}});
document.getElementById('prev').onclick=()=>{{page--;render();window.scrollTo({{top:180,behavior:'smooth'}})}}; document.getElementById('next').onclick=()=>{{page++;render();window.scrollTo({{top:180,behavior:'smooth'}})}};
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===b.dataset.view));window.scrollTo({{top:0,behavior:'smooth'}})}});
document.querySelectorAll('.switch button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.switch button').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.mode').forEach(x=>x.classList.toggle('active',x.id===b.dataset.mode))}});
const slangQ=document.getElementById('slangQ');
if(slangQ)slangQ.addEventListener('input',()=>{{const q=slangQ.value.trim().toLowerCase();let n=0;document.querySelectorAll('.slang-card').forEach(card=>{{const show=!q||(card.dataset.slangSearch||'').includes(q);card.style.display=show?'':'none';if(show)n++}});document.getElementById('slangShown').textContent=n}});
const listHtml=items=>(items||[]).length?`<ul>${{items.map(x=>`<li>${{esc(x)}}</li>`).join('')}}</ul>`:'<div class="sub">暂无单独提炼项</div>';
const detailHtml=s=>esc(String(s||'')).replace(/\\*\\*/g,'').replace(/`/g,'').replace(/\\n/g,'<br>');
document.getElementById('collections').innerHTML=COLLECTIONS.map(c=>{{
  const hasWarn=(c.warnings||[]).length>0;
  const decisions=(c.decision_factors||[]).slice(0,4);
  return `<article class="collection">
    <div class="collection-head"><h3>${{esc(c.title)}}</h3><span class="collection-count">${{c.evidence_count||0}} 张证据卡</span></div>
    <div class="question">这个合集回答：${{esc(c.core_question)}}</div>
    <div class="collection-conclusion"><span>核心结论</span><b>${{esc(c.core_conclusion||'尚未形成一句话稳定结论')}}</b></div>
    <div class="collection-grid"${{hasWarn?'':' style="grid-template-columns:1fr"'}}>
      <section class="collection-panel"><h4>可以直接带走</h4>${{listHtml(c.key_points)}}</section>
      ${{hasWarn?`<section class="collection-panel warn"><h4>注意 / 未定</h4>${{listHtml(c.warnings)}}</section>`:''}}
    </div>
    ${{decisions.length?`<div class="decision-row"><b>判断时重点看：</b>${{decisions.map(esc).join('；')}}</div>`:''}}
    <details><summary>查看完整分析与证据</summary>
      <div class="detail-section"><h5>完整跨日综合</h5><div class="detail-text">${{detailHtml(c.synthesis)}}</div></div>
      <div class="detail-section"><h5>稳定信号</h5><div class="detail-text">${{detailHtml(c.stable_signals)}}</div></div>
      ${{c.disagreements?`<div class="detail-section"><h5>分歧 / 变化</h5><div class="detail-text">${{detailHtml(c.disagreements)}}</div></div>`:''}}
      <div class="detail-section"><h5>证据时间线</h5><div class="detail-text">${{detailHtml(c.dated_evidence)}}</div></div>
    </details>
  </article>`
}}).join(''); apply();
</script></body></html>'''


def main(argv: list[str] | None = None) -> None:
    global OUT, DETAILS_DIR
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--details-dir", type=Path, default=DEFAULT_DETAILS_DIR)
    args = parser.parse_args(argv)
    OUT = args.output
    DETAILS_DIR = args.details_dir

    cards = parse_cards()
    apply_project_known_overrides(cards)
    annotate_topic_structure(cards)
    reorg_counts = apply_reorg_overlay(cards)
    for card in cards:
        group, label = evidence_group(card.get("evidence_status", ""))
        card["evidence_group"] = group
        card["evidence_label"] = label
    stats = link_sources(cards)
    supplements = inject_supplemental_cards()
    for card in supplements:
        group, label = evidence_group(card.get("evidence_status", ""))
        card["evidence_group"] = group
        card["evidence_label"] = label
    supplement_stats = link_sources(supplements)
    for key in stats:
        stats[key] += supplement_stats[key]
    aggregates = inject_longitudinal_aggregates(cards)
    display_cards = cards + supplements + aggregates
    annotate_v3_projection(display_cards)
    write_detail_pages(display_cards)
    blackwords = parse_blackwords()
    dossier = json.loads(INFINITE_DOSSIER.read_text(encoding="utf-8")) if INFINITE_DOSSIER.exists() else {}
    dossier_refs_by_card = dossier_evidence_index(dossier)
    silver_doc = json.loads(SILVER_KNOWLEDGE.read_text(encoding="utf-8")) if SILVER_KNOWLEDGE.exists() else {"units": []}
    normalized_knowledge = silver_doc.get("units", [])
    reviewed_decisions = (
        json.loads(REVIEWED_SEMANTIC_DECISIONS.read_text(encoding="utf-8"))
        if REVIEWED_SEMANTIC_DECISIONS.exists()
        else None
    )
    reviewed_state = build_reviewed_semantic_state(silver_doc, reviewed_decisions)
    reviewed_state["inputs"] = {
        "silver": {
            "file": SILVER_KNOWLEDGE.name,
            "sha256": sha256_file(SILVER_KNOWLEDGE),
        },
        "decisions": {
            "file": REVIEWED_SEMANTIC_DECISIONS.name,
            "sha256": sha256_file(REVIEWED_SEMANTIC_DECISIONS),
        } if REVIEWED_SEMANTIC_DECISIONS.exists() else None,
    }
    REVIEWED_SEMANTIC_STATE.write_text(
        json.dumps(reviewed_state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for unit in normalized_knowledge:
        unit["semantic_fingerprint"] = semantic_fingerprint(unit)
    annotate_silver_display_topics(normalized_knowledge)
    annotate_silver_display_numbers(normalized_knowledge)
    annotate_silver_display_copy(normalized_knowledge)

    silver_component_ids = {
        ref.get("card_id")
        for unit in normalized_knowledge
        for ref in unit.get("evidence_refs", [])
        if ref.get("card_id") and ref.get("coverage", "full") == "full"
    }
    normalized_component_ids = silver_component_ids | set(dossier_refs_by_card)
    silver_refs_by_card: dict[str, list[dict]] = {}
    for unit in normalized_knowledge:
        for ref in unit.get("evidence_refs", []):
            card_id = ref.get("card_id")
            if not card_id:
                continue
            silver_refs_by_card.setdefault(card_id, []).append({
                "knowledge_id": unit.get("knowledge_id", ""),
                "coverage": ref.get("coverage", "full"),
                "role": ref.get("role", ""),
            })

    candidate_rows = []
    for card in display_cards:
        if not card.get("v3_queue"):
            continue
        card_id = card.get("card_id", "")
        refs = silver_refs_by_card.get(card_id, [])
        dossier_refs = dossier_refs_by_card.get(card_id, [])
        silver_status = "full" if any(ref["coverage"] == "full" for ref in refs) else ("partial" if refs else "unabsorbed")
        normalized_status = "full" if silver_status == "full" or dossier_refs else ("partial" if silver_status == "partial" else "unabsorbed")
        candidate_rows.append({
            "card_id": card_id,
            "date": card.get("date", ""),
            "title": card.get("title", ""),
            "semantic_summary": card.get("semantic_summary", ""),
            "tags": card.get("tags", []),
            "topics": [item.get("label", "") for item in card.get("v3_topics", [])],
            "reorg_decision": card.get("reorg_decision", ""),
            "source_anchor_confidence": card.get("source_link", {}).get("confidence", "none"),
            "source_anchor_reason": card.get("source_link", {}).get("reason", ""),
            "silver_refs": refs,
            "silver_status": silver_status,
            "dossier_refs": dossier_refs,
            "normalized_status": normalized_status,
        })
    candidate_doc = {
        "schema_version": 2,
        "source_queue_count": len(candidate_rows),
        "candidates": candidate_rows,
    }
    SILVER_CANDIDATES.write_text(
        json.dumps(candidate_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    projection_inputs = {
        "atomic": json.loads(ATOMIC_REVIEWED.read_text(encoding="utf-8")),
        "no_claim": json.loads(NO_CLAIM_REVIEWED.read_text(encoding="utf-8")),
        "questions": json.loads(QUESTION_REGISTRY.read_text(encoding="utf-8")),
        "routing": json.loads(SILVER_ROUTING.read_text(encoding="utf-8")),
        "consolidation": json.loads(SILVER_CONSOLIDATION.read_text(encoding="utf-8")),
        "publication": json.loads(SILVER_PUBLICATION.read_text(encoding="utf-8")),
    }
    projection = build_first_read_projection(
        candidate_doc,
        projection_inputs["atomic"],
        projection_inputs["no_claim"],
        projection_inputs["questions"],
        projection_inputs["routing"],
        projection_inputs["consolidation"],
        projection_inputs["publication"],
        silver_doc,
        reviewed_state,
        dossier,
    )
    projection["inputs"] = {
        "candidates": {"file": SILVER_CANDIDATES.name, "sha256": sha256_file(SILVER_CANDIDATES)},
        "atomic": {"file": ATOMIC_REVIEWED.name, "sha256": sha256_file(ATOMIC_REVIEWED)},
        "no_claim": {"file": NO_CLAIM_REVIEWED.name, "sha256": sha256_file(NO_CLAIM_REVIEWED)},
        "questions": {"file": QUESTION_REGISTRY.name, "sha256": sha256_file(QUESTION_REGISTRY)},
        "routing": {"file": SILVER_ROUTING.name, "sha256": sha256_file(SILVER_ROUTING)},
        "consolidation": {"file": SILVER_CONSOLIDATION.name, "sha256": sha256_file(SILVER_CONSOLIDATION)},
        "publication": {"file": SILVER_PUBLICATION.name, "sha256": sha256_file(SILVER_PUBLICATION)},
        "silver": {"file": SILVER_KNOWLEDGE.name, "sha256": sha256_file(SILVER_KNOWLEDGE)},
        "reviewed_state": {
            "file": REVIEWED_SEMANTIC_STATE.name,
            "sha256": sha256_file(REVIEWED_SEMANTIC_STATE),
        },
    }
    FIRST_READ_PROJECTION.write_text(
        json.dumps(projection, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    residual_card_ids = set(projection["queue"]["residual_card_ids"])
    first_read_unit_ids = set(projection["queue"]["silver_knowledge_ids"])
    reviewed_queue_unit_ids = set(projection["queue"]["reviewed_silver_knowledge_ids"])
    reviewed_knowledge_unit_ids = set(
        projection["queue"]["reviewed_knowledge_silver_ids"]
    )
    reviewed_discard_unit_ids = set(
        projection["queue"]["reviewed_discard_silver_ids"]
    )
    for card in display_cards:
        card["v3_first_read_queue"] = (
            bool(card.get("v3_queue"))
            and card.get("card_id") in residual_card_ids
        )
    for unit in normalized_knowledge:
        knowledge_id = str(unit.get("knowledge_id") or "")
        unit["v3_first_read_queue"] = knowledge_id in first_read_unit_ids
        unit["v3_reviewed_semantic"] = knowledge_id in reviewed_queue_unit_ids
        unit["v3_reviewed_decision"] = (
            "knowledge"
            if knowledge_id in reviewed_knowledge_unit_ids
            else "discard"
            if knowledge_id in reviewed_discard_unit_ids
            else ""
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        build_page_v3(display_cards, blackwords, dossier, normalized_knowledge),
        encoding="utf-8",
    )

    raw_queue_count = sum(bool(c.get("v3_queue")) for c in display_cards)
    effective_queue_count = (
        projection["counts"]["first_read_silver_units"]
        + projection["counts"]["raw_card_queue"]
    )
    effective_knowledge_count = sum(
        bool(c.get("v3_knowledge")) and c.get("card_id") not in normalized_component_ids
        for c in display_cards
    ) + projection["counts"]["knowledge_silver_units"]

    v3_topic_counts: dict[str, int] = {}
    for unit in normalized_knowledge:
        if unit.get("initial_state") != "queue":
            continue
        for label in unit.get("display_topics", []):
            if label:
                v3_topic_counts[label] = v3_topic_counts.get(label, 0) + 1
    for card in display_cards:
        if not card.get("v3_first_read_queue"):
            continue
        for topic in card.get("v3_topics", []):
            label = topic["label"]
            v3_topic_counts[label] = v3_topic_counts.get(label, 0) + 1

    print(json.dumps({
        "raw_cards": len(cards),
        "aggregate_cards": len(aggregates),
        "supplemental_cards": len(supplements),
        "blackwords": len(blackwords),
        "source_links": stats,
        "raw_v3_queue": raw_queue_count,
        "silver_units": len(normalized_knowledge),
        "silver_component_cards": len(silver_component_ids),
        "dossier_component_cards": len(dossier_refs_by_card),
        "normalized_component_cards": len(normalized_component_ids),
        "first_read_raw_cards": projection["counts"]["raw_card_queue"],
        "first_read_silver_units": projection["counts"]["first_read_silver_units"],
        "effective_v3_queue": effective_queue_count,
        "effective_v3_knowledge": effective_knowledge_count,
        "v3_topics": dict(sorted(v3_topic_counts.items())),
        "output": str(OUT),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
