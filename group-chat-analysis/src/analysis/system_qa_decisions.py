"""Independent, fingerprint-bound system suggestions; never user read state."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
from src.analysis.knowledge_display_projection import qa_fingerprint

STATUS = 'reviewed_system_qa_decisions'
DECISIONS = {'knowledge', 'discard', 'archive', 'defer'}


def apply_system_qa_decisions(units: list[dict], document: dict | None, overrides: dict | None = None) -> list[dict]:
    result = copy.deepcopy(units)
    if document is None:
        return result
    if document.get('schema_version') != 1 or document.get('status') != STATUS:
        raise ValueError('invalid system QA decisions document')
    index = {q['qa_id']: q for u in result for q in u.get('display_qas', [])}
    seen = set()
    suppressed = {r['qa_id']: r for r in (overrides or {}).get('items', [])}
    for row in document.get('items', []):
        qid = row.get('qa_id')
        if qid in seen or row.get('decision') not in DECISIONS or not str(row.get('reason', '')).strip():
            raise ValueError(f'invalid or duplicate system QA decision: {qid}')
        seen.add(qid)
        qa = index.get(qid)
        # Changed/deleted QA must be reviewed again, never inherit stale advice.
        if qa is None or row.get('qa_fingerprint') != qa['qa_fingerprint']:
            continue
        if qa['lifecycle'] == 'time_bound' and row['decision'] == 'knowledge':
            raise ValueError(f'time-bound QA cannot be system knowledge: {qid}')
        qa['system_decision'] = row['decision']
        qa['system_reason'] = row['reason']
        qa['system_gaps'] = row.get('gaps', '')
        qa['system_retrieval_question'] = row.get('retrieval_question', '')
        override = suppressed.get(qid, {})
        qa['system_suppressed'] = bool(override.get('suppressed') and override.get('qa_fingerprint') == qa['qa_fingerprint'])
    return result


def set_system_override(work: Path, qa_id: str, suppressed: bool, expected_fingerprint: str) -> dict:
    if not isinstance(suppressed, bool):
        raise ValueError('suppressed must be boolean')
    projection = json.loads((work / 'knowledge-display-projection-v1.json').read_text())
    matches = [(u['knowledge_id'], q) for u in projection['items'] for q in u['qas'] if q['qa_id'] == qa_id]
    if len(matches) != 1:
        raise ValueError('unknown QA')
    kid, qa = matches[0]
    fp = qa_fingerprint(kid, qa)
    if expected_fingerprint != fp:
        raise ValueError("QA changed; reload before changing system override")
    system = json.loads((work / 'system-qa-decisions-v1.json').read_text())
    if not any(r.get('qa_id') == qa_id and r.get('qa_fingerprint') == fp for r in system['items']):
        raise ValueError('no current system decision for QA')
    path = work / 'system-qa-overrides-v1.json'
    doc = json.loads(path.read_text()) if path.exists() else {'schema_version': 1, 'items': []}
    row = {'qa_id': qa_id, 'qa_fingerprint': fp, 'suppressed': suppressed}
    doc['items'] = [r for r in doc['items'] if r['qa_id'] != qa_id] + [row]
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, path)
    return row
