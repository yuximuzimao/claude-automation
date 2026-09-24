from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.task_cards import load_task_card, task_card_path, validate_task_card

REVIEW_QUEUE = ROOT / "tasks/task-card-migration/review-queue.json"
VALIDATION_LEDGER = ROOT / "tasks/task-card-migration/fivebox-validation-todo.json"
DEFER_MARKER = "【需要单独修正优化】"

# 这些内容来自旧 dragonblight-special-mechanism-audit.json 的 final_review.facts。
# 已逐 task_id 复核：只保留任务固有执行事实；旧审计中的路线编排/跨任务合并建议被删去。
# None 表示旧 fact 经复核后没有比现有Task Card新增的任务固有事实。
MANUAL_GUIDE_ZHCN: dict[int, str | None] = {
    11930: "护送牦牛人难民跨过北风苔原/龙骨荒野边界，到沃塔克处完成护送。",
    11959: "击杀并拾取洛根后，还必须对自己使用洛根之血；只击杀洛根不会完成任务。",
    11983: "这是对话交互任务：与西风牦牛人难民持续对话，直到逐项获得血誓/进度信用，不是普通击杀或拾取任务。",
    11999: "从死亡的法师猎手尸体上取得个人物品后，打开/右键个人物品，直到获得眠月花园计划。",
    12008: None,
    12011: "在莫亚基港口西南码头使用呼吸辅助并下潜到损坏的螃蟹陷阱，交互后取得并开启后续任务。",
    12013: None,
    12017: "沿钓鱼线找到鱼钩，在鱼钩处使用诱饵召唤图戈瓦尔，然后将其击杀。",
    12028: "在图阿鲁帐篷外的火盆处使用灵魂熏香，会触发脚本化的灵魂视界/飞行过程，通常无需手动操纵。",
    12032: "到深海珍珠处交互并跟随海洋女神脚本；出现强制/增益提示后跳入水中继续试炼。",
    12033: "阅读萨鲁法尔的信后，使用附近火盆将信烧毁，再与信使交谈。",
    12036: "纳尔俊之渊位于地下；从坑洞入口向下进入下层区域探索，不要只在地表坐标附近寻找。",
    12039: None,
    12040: "目标区域位于纳尔俊之渊地下；进入下层找到基利克，并在地下击杀阿努巴尔地穴领主。",
    12047: None,
    12049: "将巨型冰虫打到低血量，等待其张嘴时使用炸药；爆炸后拾取烧焦的肉。",
    12050: "在鹰身人区域使用伐木机控制器召唤并操纵伐木机，用载具收集标记木材；伐木机丢失后可重新召唤。",
    12052: "除普通鹰身人外还必须击杀命名目标冷风女王。",
    12053: "在冰雾村插下战歌军旗并守卫到事件完成；仅放置旗帜还不算完成。",
    12057: "血缚魔典是冰雾村/纳尔俊区域阿努巴尔教徒或命名怪掉落的任务起始物；拾取后右键魔典接取任务。",
    12059: "古拉莫什掉落奇怪的设备；拾取后右键设备接取任务，不是从NPC处直接接取。",
    12061: "使用眠月花园的传送装置到投影区域，继续向前/观察，直到脚本触发投影任务信用。",
    12064: "冰雾村三名命名目标分别携带不同钥匙碎片；阿诺克拉位于较低/地面层，另外两名目标可能在不同位置，返回前收齐全部碎片。",
    12066: "击杀艾米·马林船长取得魔网能量焦点控制环，再到海岸大型魔网焦点拱门处使用控制环读取焦点。",
    12069: "使用阿努巴尔监狱钥匙释放牦牛人酋长，协助其对抗阿努布埃坎，随后拾取所需甲壳碎片。",
    12072: "在冰雾村使用信号弹召唤并骑乘库卡隆战斗飞龙，用载具技能击杀荒芜兽。",
    12075: "样本来自水晶裂痕洞口附近/下方死亡的被蹂躏水晶巨人尸体；应点击尸体取样，不是击杀活体巨人。",
    12076: "冰虫施放/附加腐蚀唾液时对自己使用佐特的刮刀，重复直到取得2份唾液样本。",
    12078: "在水晶裂痕洞穴内，将箱子放在冰虫幼体附近；幼体进入后拾取/右键地上的箱子，重复完成3次。",
    12079: "目标位于北侧水晶裂痕洞穴内部，应从洞口沿洞内路径寻找，不要追地表坐标。",
    12080: "拉特尔博尔位于水晶裂痕洞穴内；若仍有佐特防护药剂，在真正开Boss前使用可降低酸液威胁。",
    12084: "击杀塔辛尼中尉取得魔网能量焦点控制护符，再到洛萨洛尔森林的魔网焦点拱门处使用护符读取焦点。",
    12085: "塔辛尼中尉还会掉落部落信件；拾取并右键信件可接取《一封家书》。",
    12096: "在洛萨洛尔取得林地行者树皮，并对可用的非敌对洛萨洛尔古树使用树皮；这是任务物品对NPC的交互，不是击杀任务。",
    12110: "先在因度雷湖魔网焦点处使用魔网护符，再前往碧蓝巨龙圣地观察点；两段空间检查都必须完成。",
    12111: "对活着的雪落麋鹿和北极灰熊使用疫苗包；这是对目标使用任务物品，不是击杀任务。",
    12117: None,
    12124: "任务交接位于龙眠神殿的特定楼层；使用神殿幼龙/运输NPC前往上层，不要只在地面层寻找。",
    12125: "先把疯狂的因度雷村民打到要求的低血量，再对被削弱目标使用鲜血宝石充能。",
    12126: "按任务要求对瓦伦哈尔公爵使用邪恶宝石充能；不要先直接击杀目标。",
    12127: "对指定的冰霜之魂目标使用冰霜宝石完成充能。",
    12132: "通过库尔迪拉的效果/对话进入阴影世界，在阴影位面击杀暗影折磨者；完成后离开位面，不要在普通龙骨荒野寻找这些目标。",
    12140: "跟随阿格玛/洛纳乌克的脚本并完成洛纳乌克的全部对话，直到效忠事件结束；不是普通命名怪击杀任务。",
    12145: "沿峡谷中的雪怪足迹一路追踪到冰拳，而不是只找终点坐标；在足迹尽头击杀冰拳。",
    12147: "冰拳掉落精致的战斗号角；拾取并右键号角接取任务，再带到龙眠神殿鉴定。",
    12149: "三只猛犸人分布在龙眠神殿周边不同位置；冰碎有危险引导技能，血宴会借附近蛆虫回血，应按三只独立命名目标处理。",
    12150: "到黎明之镜悬崖/洞穴侧找到铭语师，只打到脚本投降/免疫并更新任务即可；进入免疫阶段后不要继续硬打，并避开紫色符文。",
    12151: "在碧蓝巨龙圣地南侧的火炬之环使用精致的战斗号角召唤格罗姆萨；战斗有击退风险，尽量远离悬崖。",
    12200: None,
    12206: "站到血色俘虏/士兵旁，对目标使用凋零药剂瓶；这是任务物品测试，不是普通击杀。",
    12211: "先击杀血色先锋军成员，再对尸体使用老鼠容器；必须完成尸体交互才会增加进度。",
    12214: "击杀先锋军骑士取得马鞭，对无骑手的马使用马鞭后骑上去，带回怨毒镇并使用载具技能1交付；不要直接杀马。",
    12218: "在怨毒镇东侧/大门附近骑乘被遗忘者凋零扩散器，使用载具凋零炸弹击杀营地外所需天灾目标。",
    12232: "对新壁炉谷固定弩炮使用收集到的攻城炸弹；必须用炸弹摧毁，不能按普通目标直接攻击。",
    12234: "三份日常命令分布在新壁炉谷不同建筑/房间，包括兵营和修道院内部；注意楼层和室内位置。",
    12240: "在伐木场/木料堆附近使用莱文家族白蚁，把工头卡雷奇逼出来后击杀。",
    12243: "先用燃烧液点燃船帆，利用短暂混乱时间进入下层船舱，沿船内路线找到并击杀谢利船长，再拾取海图。",
    12245: "几名血色命名目标并非普通击杀信用；按要求先交互/对话使其暴露或触发，再击杀对应NPC。",
    12252: "里克拉夫位于兵营/地下区域；先用烙印/审讯工具5次取得情报，再完成后续击杀/流程。",
    12260: "对先锋军渡鸦祭司使用女妖的魔镜复制伪装形象；这是对指定NPC使用任务物品。",
    12261: "在黑曜石巨龙圣地出口/道路转为雪地的边缘放置毁灭结界，并守卫到结界充能完成；只放下结界不会完成任务。",
    12263: "塞雷纳尔会把你伪装成教徒；保持伪装穿过奈萨里奥之喉洞穴深入教徒区域观察意图。伪装丢失后应返回重新施加。",
    12264: "诅咒教派目标位于奈萨里奥之喉洞穴内部，不在地表。",
    12265: "在奈萨里奥之喉洞穴内右键/摧毁通灵符文；它们是固定洞内物体，不是地表目标。",
    12267: "深入奈萨里奥之喉，在召唤区域使用奈萨里奥之焰触发净化并引出腐烂者洛辛，然后将其击杀。",
    12271: "拷问者魔棒是血色拷问者任务链掉落的任务起始物；拾取并右键魔棒接取任务。",
    12273: "在指定建筑/楼层找到每名血色官员，对其使用强制魔棒，等待谴责脚本完成后再击杀目标。",
    12274: "保持伪装进入修道院，沿螺旋楼梯上楼拉钟绳，再回到楼下与大修道院长交谈/跟随取得情报；先锋军骑士能识破伪装。",
    12283: "阿比迪斯的日记位于教堂附近房屋的楼上房间；楼层/室内位置比平面坐标更关键。",
    12419: "该任务使用前序红玉巨龙圣地链取得的红玉胸针交付，不是龙眠神殿独立拾取物。",
    12435: "龙眠神殿有多个垂直楼层；使用神殿幼龙/运输功能前往德弗雷斯塔兹领主所在楼层。",
    12447: "塞雷纳尔位于黑曜石巨龙圣地的奈萨里奥之喉洞穴内/入口区域，应从洞穴进入，不要只在地表标记处寻找。",
    12449: "从南侧道路进入红玉巨龙圣地，拾取/使用红玉橡果作用于死亡红龙尸体，使其回归大地。",
    12450: "从南侧进入红玉巨龙圣地；除击杀通灵师外，还必须摧毁圣地下面的腐化源，单纯击杀不会完成第二目标。",
    12456: "在东南林地使用天爪蜕皮召唤奥雷托斯，击杀后拾取羽毛；命名目标是召唤出现，不会固定站在地图点。",
    12459: "三名命名目标都必须先用自然愤怒之种削弱，再击杀；目标分布在不同位置，其中包括飞行的冰霜巨龙，不要在施种前先杀掉。",
    12470: "在青铜巨龙圣地使用永恒沙漏启动限时防守事件，守住多波攻击直到取得情报；未来的你可能会出现协助。",
    12496: "龙后位于龙眠神殿上层；通过神殿运输NPC前往上层，不要只在地面层寻找。",
    12498: "使用红玉信标骑乘红龙，用载具技能击杀所需天灾目标，并完成Boss/镰刀事件后再返回龙后处。",
    12767: "龙眠神殿为多层结构；前往部落大使所在的正确楼层，不要只依赖平面坐标。",
    12769: "与塔里奥斯塔兹交谈并使用其幼龙/神殿运输选项，可在龙眠神殿各楼层之间移动。",
    12791: None,
    13242: "在天谴之门后续中拾取战场上的萨鲁法尔战甲，再跨地图带回战歌要塞交给萨鲁法尔。",
}


def _merge_evidence(card: dict[str, Any], entry: dict[str, Any]) -> None:
    evidence = list(card.get("evidence") or [])
    for index, row in enumerate(evidence):
        if isinstance(row, dict) and row.get("evidence_id") == entry["evidence_id"]:
            evidence[index] = entry
            card["evidence"] = evidence
            return
    evidence.append(entry)
    card["evidence"] = evidence


def _append_note(card: dict[str, Any], text: str, *, source_ref: str, reason: str) -> None:
    text = text.strip()
    if not text:
        return
    presentation = card.setdefault("presentation", {})
    note = presentation.get("note_override")
    current = str(note.get("text") or "").strip() if isinstance(note, dict) else ""
    if text in current:
        return
    merged = f"{current}\n{text}".strip() if current else text
    old_source = str(note.get("source_ref") or "").strip() if isinstance(note, dict) else ""
    sources = [part for part in [old_source, source_ref] if part]
    presentation["note_override"] = {
        "text": merged,
        "scope": "all",
        "source_ref": " + ".join(dict.fromkeys(sources)),
        "reason": reason,
    }


def _review_reason_map(queue: dict[str, Any]) -> dict[int, dict[str, dict[str, Any]]]:
    out: dict[int, dict[str, dict[str, Any]]] = {}
    for task in queue.get("tasks", []):
        out[int(task["task_id"])] = {r["kind"]: r for r in task.get("reasons", [])}
    return out


def resolve(*, write: bool) -> dict[str, Any]:
    queue = json.loads(REVIEW_QUEUE.read_text(encoding="utf-8"))
    reasons_by_task = _review_reason_map(queue)
    changed_cards: dict[int, dict[str, Any]] = {}
    stats = {
        "deferred_fivebox_notes": 0,
        "manual_facts_reviewed": 0,
        "manual_guide_additions": 0,
        "workbench_notes_migrated": 0,
        "fivebox_validation_tasks": 0,
        "identity_aliases_resolved": 0,
    }
    validation_tasks: list[dict[str, Any]] = []

    for task_id, reasons in sorted(reasons_by_task.items()):
        card = copy.deepcopy(load_task_card(task_id))
        before = copy.deepcopy(card)

        legacy_note = reasons.get("legacy_fivebox_note_needs_guide_review")
        if legacy_note:
            detail = legacy_note.get("detail") or {}
            raw = str(detail.get("note") or "").strip()
            marked = f"{DEFER_MARKER}{raw}"
            _append_note(
                card,
                marked,
                source_ref=f"data/observations/fivebox-task-types.json#tasks.{task_id}",
                reason="无损迁移：旧fivebox备注暂不做Presentation优化；仅该段以【需要单独修正优化】标记，后续专项搜索处理。",
            )
            _merge_evidence(
                card,
                {
                    "evidence_id": "evidence-fivebox-note-deferred-to-presentation",
                    "source_type": "legacy_migration",
                    "source_ref": f"data/observations/fivebox-task-types.json#tasks.{task_id}",
                    "observed_at": detail.get("confirmed_at") or detail.get("observed_at"),
                    "version_scope": "TitanReforged-Wotlk-ChinaRegion 3.80.2 / 时光服",
                    "confidence": "verified",
                    "supports_fields": ["presentation.note_override"],
                },
            )
            stats["deferred_fivebox_notes"] += 1

        workbench_note = reasons.get("workbench_note_needs_review")
        if workbench_note:
            texts: list[str] = []
            for text in (workbench_note.get("owned_texts") or []) + (workbench_note.get("ambiguous_texts") or []):
                text = str(text).strip()
                if text and text not in texts:
                    texts.append(text)
            if texts:
                _append_note(
                    card,
                    "\n".join(texts),
                    source_ref="data/route-atlas/workbench-routes.json",
                    reason="无损迁移：旧正式workbench存在多条/多任务共用备注；先逐字保全到Task Presentation，后续前端专项审计再精简，不在当前数据迁移阶段丢信息。",
                )
                stats["workbench_notes_migrated"] += 1

        manual = reasons.get("legacy_manual_facts_need_guide_review")
        if manual:
            if task_id not in MANUAL_GUIDE_ZHCN:
                raise ValueError(f"missing curated manual-fact disposition for task {task_id}")
            addition = MANUAL_GUIDE_ZHCN[task_id]
            if addition and addition not in card.get("guide", []):
                card.setdefault("guide", []).append(addition)
                stats["manual_guide_additions"] += 1
            card.setdefault("coverage", {})["guide"] = "verified"
            _merge_evidence(
                card,
                {
                    "evidence_id": "evidence-dragonblight-special-mechanism-audit",
                    "source_type": "legacy_migration",
                    "source_ref": f"data/route-atlas/dragonblight-special-mechanism-audit.json#quest_id={task_id}/final_review.facts",
                    "observed_at": None,
                    "version_scope": "legacy Dragonblight manual executability audit; migrated 2026-09-16",
                    "confidence": "verified",
                    "supports_fields": ["guide"],
                },
            )
            stats["manual_facts_reviewed"] += 1

        fivebox_prompt = reasons.get("workbench_fivebox_text_needs_review")
        if fivebox_prompt:
            prompts: list[str] = []
            for text in (fivebox_prompt.get("owned_texts") or []) + (fivebox_prompt.get("ambiguous_texts") or []):
                text = str(text).strip()
                if text and text not in prompts:
                    prompts.append(text)
            validation_tasks.append(
                {
                    "task_id": task_id,
                    "name": (card.get("identity") or {}).get("name_zhcn"),
                    "current_fivebox_status": (card.get("fivebox") or {}).get("status"),
                    "prompts": prompts,
                    "source": "data/route-atlas/workbench-routes.json",
                    "disposition": "deferred_validation_not_task_fact",
                }
            )
            stats["fivebox_validation_tasks"] += 1

        alias = reasons.get("workbench_name_alias_needs_identity_review")
        if alias:
            if task_id != 13677:
                raise ValueError(f"unexpected unresolved name alias for task {task_id}")
            card["identity"]["name_zhcn"] = "学习驾驭"
            _merge_evidence(
                card,
                {
                    "evidence_id": "evidence-current-server-name-13677",
                    "source_type": "user_live",
                    "source_ref": "docs/analysis/2026-08-30-icecrown-reordered-route-v1.md#Journey-event-2212; data/route-atlas/workbench-routes.json#icecrown",
                    "observed_at": "2026-08-30",
                    "version_scope": "TitanReforged-Wotlk-ChinaRegion 3.80.2 / 时光服",
                    "confidence": "verified",
                    "supports_fields": ["identity.name_zhcn"],
                },
            )
            stats["identity_aliases_resolved"] += 1

        validate_task_card(card, expected_task_id=task_id)
        if card != before:
            changed_cards[task_id] = card

    ledger = {
        "schema_version": 1,
        "status": "workflow_validation_ledger_not_task_truth",
        "purpose": "旧正式workbench中尚待实测的fivebox提示。Task Card用fivebox=pending表达未知；这里仅保留验证问题原文，不作为任务事实真源。",
        "task_count": len(validation_tasks),
        "tasks": validation_tasks,
    }

    if write:
        for task_id, card in changed_cards.items():
            task_card_path(task_id).write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        VALIDATION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        VALIDATION_LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "write": write,
        "changed_card_count": len(changed_cards),
        **stats,
        "validation_ledger_task_count": len(validation_tasks),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve the remaining non-architectural Task Card migration review classes.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(json.dumps(resolve(write=args.write), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
