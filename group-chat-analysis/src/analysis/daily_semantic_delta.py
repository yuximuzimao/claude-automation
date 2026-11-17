"""Apply a source-checked daily semantic delta, without signing or publishing.

The caller supplies reviewed model decisions. This module performs deterministic
validation and lineage bookkeeping only. An interrupted journal must be recovered
before another day can mutate the shared knowledge baseline.
"""
from __future__ import annotations

import copy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from src.app.runtime_deadline import Deadline
from .analysis_release import fsync_dir, sha256_json
from .knowledge_display_projection import apply_knowledge_display_projection, qa_fingerprint
from .question_cluster_bootstrap_apply import apply_bootstrap
from .question_registry_store import validate_monotonic_update
from .silver_draft_materialization import materialize
from .silver_publication_apply import build_publication_candidate

HUMAN_FILES = (
    'display-review-decisions-v1.json', 'reviewed-semantic-decisions-v1.json',
    'reviewed-semantic-state-v1.json', 'system-qa-overrides-v1.json',
)


def _bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def _sha(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def _read(path: Path) -> bytes | None:
    if path.is_symlink():
        raise ValueError(f'refusing symlink: {path}')
    return path.read_bytes() if path.exists() else None


def _atomic(path: Path, data: bytes, deadline: Deadline) -> None:
    """Byte-preserving companion to write_json_atomic, with a pre-replace bound."""
    deadline.check()
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline.check()
    fd, name = tempfile.mkstemp(prefix=f'.{path.name}.tmp-', dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            deadline.check()
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        deadline.check()
        os.replace(tmp, path)
        fsync_dir(path.parent)
    finally:
        # Temporary files contain no committed semantic state.
        if tmp.exists() and deadline.remaining() > 0:
            tmp.unlink()


def _text(row: dict, key: str, *, empty: bool = False) -> str:
    value = row.get(key)
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f'{key} must be a nonempty string')
    return value


def _safe_file(work: Path, name: str) -> Path:
    p = (work / name).resolve()
    if not p.is_relative_to(work.parent.resolve()) or Path(name).is_absolute():
        raise ValueError(f'file outside analysis runtime: {name}')
    return p


def _validate(proposals: list[dict], lines: list[str], units: dict) -> list[dict]:
    if not isinstance(proposals, list):
        raise ValueError('proposals must be a list')
    seen: set[str] = set()
    for row in proposals:
        if not isinstance(row, dict):
            raise ValueError('proposal must be an object')
        pid = _text(row, 'proposal_id')
        if pid in seen or not re.fullmatch(r'[A-Za-z0-9_.:-]+', pid):
            raise ValueError(f'duplicate or unsafe proposal_id: {pid}')
        seen.add(pid)
        for key in ('subject', 'question', 'reason'):
            _text(row, key)
        scope = row.get('scope')
        if not isinstance(scope, dict):
            raise ValueError(f'missing scope: {pid}')
        _text(scope, 'game_variant')
        topics=row.get('topics')
        if not isinstance(topics,list) or not topics or any(not isinstance(t,str) or not t.strip() for t in topics):
            raise ValueError(f'missing or invalid topics: {pid}')
        action = row.get('disposition')
        if action not in {'new', 'support_existing', 'discard', 'defer'}:
            raise ValueError(f'invalid disposition: {pid}')
        if 'target_knowledge_id' not in row:
            raise ValueError(f'missing target_knowledge_id: {pid}')
        target = row['target_knowledge_id']
        if target is not None and (not isinstance(target, str) or target not in units):
            raise ValueError(f'unknown target: {pid}: {target}')
        if action == 'support_existing' and target is None:
            raise ValueError(f'support requires real target: {pid}')
        if action == 'new' and target is not None:
            raise ValueError(f'new must not overwrite an existing target: {pid}')
        facts = row.get('facts')
        if not isinstance(facts, list) or (action in {'new','support_existing'} and not facts):
            raise ValueError(f'facts required: {pid}')
        for fact in facts:
            if not isinstance(fact, dict):
                raise ValueError(f'invalid fact: {pid}')
            _text(fact, 'statement')
            quote = _text(fact, 'quote')
            start, end = fact.get('start_line'), fact.get('end_line')
            if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
                raise ValueError(f'fact range outside current day: {pid}: {start}..{end}')
            if quote not in '\n'.join(lines[start - 1:end]):
                raise ValueError(f'quote not found inside cited range: {pid}: {start}..{end}')
        qa = row.get('qa')
        if not isinstance(qa, dict):
            raise ValueError(f'QA required: {pid}')
        if qa.get('confidence') not in {'medium','low'}:
            raise ValueError(f'invalid QA confidence: {pid}')
        for key in ('question', 'answer'):
            _text(qa, key)
        for key in ('verification_note', 'time_context'):
            _text(qa, key, empty=True)
        if qa.get('lifecycle') not in {'durable', 'time_bound'}:
            raise ValueError(f'invalid QA lifecycle: {pid}')
        if qa.get('decision') not in {'knowledge', 'discard', 'archive', 'defer'}:
            raise ValueError(f'invalid QA decision: {pid}')
        if qa['lifecycle'] == 'time_bound':
            if not qa['time_context'].strip() or qa['decision'] == 'knowledge':
                raise ValueError(f'time-bound QA needs time and cannot be knowledge: {pid}')
    return sorted(copy.deepcopy(proposals), key=lambda row: row['proposal_id'])


def _restore(work: Path, journal_path: Path, journal: dict, deadline: Deadline) -> None:
    """Recover only our byte versions; never overwrite an unrelated edit."""
    entries = journal.get('files', [])
    for entry in entries:
        path = _safe_file(work, entry['file'])
        if _sha(_read(path)) not in {entry['before_sha256'], entry['after_sha256']}:
            raise ValueError(f'rollback conflicts with external edit: {path}')
        backup = _safe_file(work, entry['backup'])
        if entry['before_sha256'] is not None and _sha(_read(backup)) != entry['before_sha256']:
            raise ValueError(f'rollback backup invalid: {backup}')
    for entry in reversed(entries):
        path = _safe_file(work, entry['file'])
        if _sha(_read(path)) == entry['before_sha256']:
            continue
        deadline.check()
        if entry['before_sha256'] is None:
            path.unlink(missing_ok=True)
            fsync_dir(path.parent)
        else:
            _atomic(path, _safe_file(work, entry['backup']).read_bytes(), deadline)
    journal['status'] = 'rolled_back'
    _atomic(journal_path, _bytes(journal), deadline)


def apply_reviewed_delta(project_root: Path, day: str, proposals: list[dict], deadline: Deadline) -> dict:
    """Append reviewed new units/support, preserving user state and old semantics.

    No receipt is signed and no page/release pointer is published here. On an
    exception before the hard bound, all changed files are restored byte-for-byte.
    At/after the hard bound the prewritten journal is left for next-run recovery;
    there is deliberately no after-deadline rollback or other business write.
    """
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError('day must be YYYY-MM-DD')
    deadline.check(reserve=30)
    root = Path(project_root).resolve()
    work = root / 'runtime/analysis-work'
    batch = work / 'batches' / f'history-{day.replace("-", "")}-full'
    journal_path = batch / 'delta-application-journal.json'
    applied_path = batch / 'delta-applied.json'
    # An interrupted application on any day blocks a later day from moving on.
    for other in sorted((work / 'batches').glob('*/delta-application-journal.json')):
        doc = json.loads(other.read_text())
        if doc.get('status') == 'applying':
            _restore(work, other, doc, deadline)
            raise ValueError(f'recovered interrupted application; retry explicitly: {other}')
    if applied_path.exists():
        raise ValueError('day already applied; do not replay semantic delta')
    package_path = batch / 'analysis-work-package-v1.json'
    if not package_path.is_file():
        raise ValueError('prepare-work must freeze baseline before applying')
    package = json.loads(package_path.read_text())
    if package.get('status') != 'analysis_work_prepared' or package.get('batch_id') != batch.name:
        raise ValueError('work package does not match day')
    for artifact in package.get('baseline_artifacts', {}).values():
        artifact_path = (root / artifact['path']).resolve()
        if not artifact_path.is_relative_to((root / 'runtime').resolve()):
            raise ValueError('work package artifact outside runtime')
        if _sha(_read(artifact_path)) != artifact['sha256']:
            raise ValueError(f'prepared knowledge baseline changed: {artifact_path}')
    state_path = root / f'runtime/history-days/{day}/state/batch-state.json'
    state = json.loads(state_path.read_text())
    if state.get('status') != 'completed' or state.get('pending_capture') is not None:
        raise ValueError('capture must be completed with no pending operation')
    if state.get('batch_id') != batch.name:
        raise ValueError('capture batch/day mismatch')
    chunk = work / f'full-history-chunks/{day}/part-01.md'
    canonical = root / f'runtime/history-days/{day}/inbox/current.md'
    source = chunk.read_bytes()
    if source != canonical.read_bytes():
        raise ValueError('day chunk differs from completed canonical inbox')
    if package.get('source', {}).get('current_sha256') != _sha(source):
        raise ValueError('work package canonical input hash mismatch')
    lines = source.decode('utf-8').splitlines()
    before: dict[Path, bytes | None] = {}
    outputs: dict[Path, bytes] = {}

    def load(name: str) -> object:
        path = _safe_file(work, name)
        data = _read(path)
        before.setdefault(path, data)
        if data is None:
            raise ValueError(f'required semantic baseline missing: {name}')
        return json.loads(data)

    def put(name: str, value: object) -> None:
        path = _safe_file(work, name)
        before.setdefault(path, _read(path))
        outputs[path] = _bytes(value)

    def put_raw(path: Path, data: bytes) -> None:
        before.setdefault(path, _read(path))
        outputs[path] = data

    protected = {work / name: _read(work / name) for name in HUMAN_FILES}
    formal = load('silver-knowledge-v1.json')
    original_formal = copy.deepcopy(formal)
    units = {u['knowledge_id']: u for u in formal['units']}
    if len(units) != len(formal['units']):
        raise ValueError('duplicate baseline Silver id')
    rows = _validate(proposals, lines, units)
    projection = load('knowledge-display-projection-v1.json')
    original_projection = copy.deepcopy(projection)
    system = load('system-qa-decisions-v1.json')
    old_system = copy.deepcopy(system['items'])
    candidates = load('silver-candidates-v1.json')
    anchors = load('verified-source-anchors-v1.json')
    triage = load('reorg-v2/card-triage.json')
    atomic_registry = load('atomic-claims-reviewed-v1.json')
    registry = load('question-cluster-registry-current.json')
    routing = load('question-cluster-silver-routing-reviewed-v1.json')
    consolidation = load('silver-draft-consolidation-reviewed-v1.json')
    publication = load('silver-publication-gate-reviewed-v1.json')
    drafts = load('silver-draft-work-queue-v1.json')
    authored_registry = load('silver-draft-authored-registry-v1.json')
    publication_proposals = load('silver-publication-gate-proposals-v1.json')
    assignment_proposals = load('question-cluster-silver-assignment-proposals-v1.json')
    atomic, gold, authored, gate, groups, routed, cards, supports, new_qa_ids = [], [], [], [], [], [], [], [], []
    filtered = []
    token = day.replace('-', '')
    role = f'daily_{token}'
    existing_cards = {r['card_id'] for r in candidates['candidates']} | set(anchors['anchors'])
    for number, row in enumerate(rows, 1):
        deadline.check()
        if row['disposition'] in {'discard', 'defer'}:
            filtered.append(row)
            continue
        suffix = f'{token}-{number:03d}'
        cid = f'T-{suffix}'
        if cid in existing_cards:
            raise ValueError(f'daily source id collision: {cid}')
        existing_cards.add(cid)
        refs = [{'date': day, 'file': 'part-01.md', 'start_line': f['start_line'], 'end_line': f['end_line']} for f in row['facts']]
        facts = [f['statement'] for f in row['facts']]
        anchors['anchors'][cid] = {'date': day, 'segments': [{k: v for k, v in ref.items() if k != 'date'} for ref in refs], 'verification': {'status': 'verified', 'review_batch': role, 'reviewer': 'reviewed_daily_semantic_delta', 'source': 'completed_canonical'}}
        ranges = '; '.join(f"full-history-chunks/{day}/part-01.md:{r['start_line']}-{r['end_line']}" for r in refs)
        single = lambda text: str(text).replace('\r', ' ').replace('\n', ' ')
        cards.append(f"## {cid} — {single(row['subject'])}\n- time_range: {day}\n- semantic_summary: {single('；'.join(facts))}\n- claims: {single('；'.join(facts))}\n- evidence_status: player_report\n- source_ranges: {ranges}\n- tags: []\n- collection_candidates: []\n- display_status: main\n")
        triage.append({'card_id': cid, 'decision': 'keep_mechanism', 'reason': row['reason']})
        candidates['candidates'].append({'card_id': cid, 'date': day, 'title': row['subject'], 'semantic_summary': '；'.join(facts), 'silver_status': 'unabsorbed', 'normalized_status': 'unabsorbed', 'silver_refs': [], 'source_anchor_confidence': 'high'})
        if row['disposition'] == 'support_existing':
            target = row['target_knowledge_id']
            units[target]['evidence_refs'].append({'card_id': cid, 'role': 'support', 'coverage': 'full', 'display': False})
            supports.append({'proposal_id': row['proposal_id'], 'card_id': cid, 'target_knowledge_id': target, 'reason': row['reason'], 'source_refs': refs})
            continue
        kid, qid, gid = f'K-D{suffix}', f'G-D{suffix}', f'SDG-D{suffix}'
        if kid in units:
            raise ValueError(f'daily knowledge id collision: {kid}')
        claims = [{'id': f'AC-D{suffix}-{j:02d}', 'statement': f['statement'], 'entity': row['subject'], 'question': row['question'], 'kind': 'mechanism', 'evidence_type': 'player_report', 'certainty': 'reported', 'source_refs': [refs[j-1]]} for j, f in enumerate(row['facts'], 1)]
        atomic.append({'card': cid, 'claims': claims, 'rejected': []})
        gold.append({'cluster_id': qid, 'canonical_question': row['question'], 'members': [c['id'] for c in claims]})
        unit = {'knowledge_id': kid, 'subject': row['subject'], 'question': row['question'], 'kind': 'mechanism', 'topics': row['topics'], 'scope': row['scope'], 'canonical_facts': facts, 'structured': {'conditions': [row['scope']['game_variant']], 'action': row['qa']['answer'], 'failure_mode': row['qa']['verification_note']}, 'evidence_refs': [{'card_id': cid, 'role': 'direct_report', 'coverage': 'full'}], 'search_terms': [row['subject'], row['question']], 'evidence_state': 'reported_not_independently_verified', 'freshness': 'time_bound' if row['qa']['lifecycle'] == 'time_bound' else 'version_sensitive', 'initial_state': 'queue'}
        entry = {'unit': unit, 'lineage': {'group_id': gid, 'member_question_ids': [qid], 'claim_ids': [c['id'] for c in claims], 'canonical_source_refs': refs}}
        authored.append(entry)
        routed.append({'question_id': qid, 'canonical_question': row['question'], 'decision': 'new_draft', 'reason': row['reason'], 'related_silver_ids': [], 'review_origin': role})
        groups.append({'group_id': gid, 'canonical_question': row['question'], 'members': [qid], 'reason': row['reason'], 'reasons': [row['reason']], 'source_cards': [cid], 'claim_count': len(claims)})
        gate.append({'group_id': gid, 'draft_knowledge_id': kid, 'decision': 'append_new', 'target_knowledge_id': None, 'reason': row['reason'], 'review_origin': role})
        drafts['items'].append({'question_id': qid, 'canonical_question': row['question'], 'entities': [row['subject']], 'source_cards': [cid], 'claim_count': len(claims), 'related_silver_ids': [], 'reason': row['reason'], 'review_origin': role, 'status': 'draft_consolidation_required'})
        publication_proposals['items'].append({'group_id': gid, 'knowledge_id': kid, 'draft_knowledge_id': kid})
        assignment_proposals['proposals'].append({'question_id': qid, 'canonical_question': row['question'], 'entities': [row['subject']], 'source_cards': [cid], 'claim_count': len(claims), 'related_silver_ids': []})
        qa = copy.deepcopy(row['qa'])
        decision = qa.pop('decision')
        qa.update(qa_id=f'{kid}::q01', evidence_refs=[cid])
        projection['items'].append({'knowledge_id': kid, 'display_status': 'visible', 'qas': [qa]})
        new_qa_ids.append(qa['qa_id'])
        system['items'].append({'qa_id': qa['qa_id'], 'qa_fingerprint': qa_fingerprint(kid, qa), 'knowledge_id': kid, 'decision': decision, 'reason': row['reason'], 'gaps': qa['verification_note'], 'retrieval_question': qa['question'], 'decision_source': 'system'})

    atomicdoc = {'schema_version': 1, 'status': 'reviewed_daily_atomic_claims', 'source_cards_rebuilt': len(atomic), 'atomic_claim_count': sum(len(r['claims']) for r in atomic), 'items': atomic}
    gatedoc = {'schema_version': 1, 'status': 'reviewed_silver_publication_gate_not_applied', 'counts': {'active_work_items': 0, 'append_new': len(gate), 'update_existing': 0, 'hold': 0}, 'items': gate}
    authdoc = {'schema_version': 1, 'status': 'authored_silver_drafts_not_published', 'items': authored}
    updated_registry, _ = apply_bootstrap(registry, atomicdoc, {'clusters': gold, 'must_separate': []})
    validate_monotonic_update(registry, updated_registry)
    old_claims = {c['id'] for r in atomic_registry['items'] for c in r['claims']}
    fresh_claims = {c['id'] for r in atomic for c in r['claims']}
    if old_claims & fresh_claims:
        raise ValueError('daily atomic claim id collision')
    for item in copy.deepcopy(atomic):
        item.update(review_origin=role, review_source_file=f'atomic-claims-daily-{token}-v1.json')
        atomic_registry['items'].append(item)
    routing['items'].extend(routed)
    consolidation['groups'].extend(groups)
    publication['items'].extend(gate)
    authored_registry['items'].extend(authored)
    newformal, newcandidates, report = build_publication_candidate(formal, authdoc, gatedoc, candidates)
    # Check the protected contracts before any shared write.
    old_units = {u['knowledge_id']: u for u in original_formal['units']}
    for unit in newformal['units']:
        if unit['knowledge_id'] in old_units:
            old = old_units[unit['knowledge_id']]
            if {k: v for k, v in unit.items() if k != 'evidence_refs'} != {k: v for k, v in old.items() if k != 'evidence_refs'} or unit['evidence_refs'][:len(old['evidence_refs'])] != old['evidence_refs']:
                raise ValueError('existing Silver semantics or evidence changed')
    if projection['items'][:len(original_projection['items'])] != original_projection['items'] or system['items'][:len(old_system)] != old_system:
        raise ValueError('existing QA or system decisions changed')
    apply_knowledge_display_projection(newformal['units'], projection)

    def dataset(manifest_name: str, filename: str, doc: dict, aggregate: dict, **metadata: object) -> None:
        manifest = load(manifest_name)
        if any(r['role'] == role or r['file'] == filename for r in manifest['datasets']):
            raise ValueError(f'daily manifest collision: {filename}')
        manifest['datasets'].append({'role': role, 'file': filename})
        put(filename, doc)
        put(manifest_name, manifest)
        aggregate.setdefault('datasets', []).append({'role': role, 'file': filename, 'sha256': _sha(_bytes(doc)), **metadata})
        aggregate['manifest'] = {'file': manifest_name, 'sha256': _sha(_bytes(manifest))}

    dataset('atomic-claim-reviewed-manifest-v1.json', f'atomic-claims-daily-{token}-v1.json', atomicdoc, atomic_registry, source_cards=len(atomic), atomic_claims=len(fresh_claims))
    dataset('question-cluster-silver-routing-reviewed-manifest-v1.json', f'question-cluster-silver-routing-reviewed-daily-{token}-v1.json', {'schema_version': 1, 'status': 'reviewed_question_to_silver_routing_not_applied_to_silver', 'items': routed}, routing, questions=len(routed))
    dataset('silver-draft-consolidation-reviewed-manifest-v1.json', f'silver-draft-consolidation-reviewed-daily-{token}-v1.json', {'schema_version': 1, 'status': 'reviewed_silver_draft_consolidation', 'groups': groups, 'exclusions': [], 'separations': []}, consolidation)
    dataset('silver-publication-gate-reviewed-manifest-v1.json', f'silver-publication-gate-reviewed-daily-{token}-v1.json', {'schema_version': 1, 'status': 'reviewed_silver_publication_gate', 'decisions': gate}, publication)
    dataset('silver-draft-authored-manifest-v1.json', f'silver-draft-authored-daily-{token}-v1.json', authdoc, authored_registry)
    atomic_registry['counts'] = {'reviewed_source_cards': len(atomic_registry['items']), 'reviewed_atomic_claims': len(old_claims | fresh_claims), 'input_datasets': len(atomic_registry['datasets'])}
    routing['counts'] = {'reviewed_questions': len(routing['items']), 'reused_questions': sum(r['decision'] == 'reuse_existing' for r in routing['items']), 'new_draft_questions': sum(r['decision'] == 'new_draft' for r in routing['items']), 'needs_review_questions': sum(r['decision'] == 'needs_review' for r in routing['items']), 'existing_silver_links': sum(len(r.get('targets', [])) for r in routing['items'] if r['decision'] == 'reuse_existing'), 'input_datasets': len(routing['datasets'])}
    assigned = {q for g in consolidation['groups'] for q in g['members']}
    excluded = {r['question_id'] for r in consolidation.get('exclusions', [])}
    draft_ids = {r['question_id'] for r in drafts['items']}
    if not assigned <= draft_ids or assigned & excluded:
        raise ValueError('consolidation/draft coverage mismatch')
    consolidation['counts'] = {'draft_questions': len(draft_ids), 'assigned_questions': len(assigned), 'excluded_questions': len(excluded), 'active_work_items': len(draft_ids - assigned - excluded), 'provisional_groups': len(consolidation['groups']), 'multi_question_groups': sum(len(g['members']) > 1 for g in consolidation['groups']), 'separation_boundaries': len(consolidation.get('separations', [])), 'input_datasets': len(consolidation['datasets'])}
    materialized = materialize(consolidation, updated_registry, atomic_registry, drafts, newformal)
    authored_groups = {r['lineage']['group_id'] for r in authored_registry['items']}
    materialized_groups = {r['group_id'] for r in materialized['items']}
    if authored_groups != materialized_groups:
        raise ValueError('authored/materialized coverage mismatch')
    authored_registry['counts'] = {'materialized_groups': len(materialized_groups), 'authored_groups': len(authored_groups), 'active_work_items': 0, 'input_datasets': len(authored_registry['datasets'])}
    gate_groups = {r['group_id'] for r in publication['items']}
    if gate_groups != authored_groups or len(gate_groups) != len(publication['items']):
        raise ValueError('publication/authored coverage mismatch')
    publication['counts'] = {'authored_drafts': len(authored_groups), 'reviewed_groups': len(gate_groups), **{k: sum(r['decision'] == k for r in publication['items']) for k in ('append_new', 'update_existing', 'hold')}, 'active_work_items': 0, 'input_datasets': len(publication['datasets'])}
    publication_proposals.setdefault('counts', {}).update(authored_drafts=len(authored_groups), drafts_requiring_publication_review=len(publication_proposals['items']))
    drafts['counts'] = {'draft_questions': len(drafts['items']), 'questions_with_existing_silver_context': sum(bool(r.get('related_silver_ids')) for r in drafts['items']), 'questions_without_existing_silver_context': sum(not r.get('related_silver_ids') for r in drafts['items'])}
    assignment_proposals.setdefault('counts', {}).update(reviewed_questions=len(assignment_proposals['proposals']), existing_silver_units=len(newformal['units']))
    # Remaining queues must not retain yesterday's stale completed counts.
    put('silver-draft-consolidation-work-queue-v1.json', {'schema_version': 1, 'status': 'silver_draft_consolidation_work_queue', 'counts': {'total_draft_questions': len(draft_ids), 'assigned_questions': len(assigned), 'excluded_questions': len(excluded), 'active_work_items': len(draft_ids - assigned - excluded)}, 'items': [r for r in drafts['items'] if r['question_id'] not in assigned | excluded]})
    put('silver-draft-authoring-work-queue-v1.json', {'schema_version': 1, 'status': 'silver_draft_authoring_work_queue', 'counts': {'materialized_groups': len(materialized_groups), 'authored_groups': len(authored_groups), 'active_work_items': 0}, 'items': []})
    put('silver-publication-gate-work-queue-v1.json', {'schema_version': 1, 'status': 'silver_publication_gate_work_queue', 'counts': {'authored_drafts': len(authored_groups), 'reviewed_groups': len(gate_groups), 'active_work_items': 0}, 'items': []})
    projection['stats'].update(visible=sum(r.get('display_status') == 'visible' for r in projection['items']), qas=sum(len(r.get('qas', [])) for r in projection['items']))
    anchors['verified_count'] = len(anchors['anchors'])
    newcandidates['source_queue_count'] = len(newcandidates['candidates'])
    for name, doc in [('silver-knowledge-v1.json', newformal), ('silver-candidates-v1.json', newcandidates), ('verified-source-anchors-v1.json', anchors), ('reorg-v2/card-triage.json', triage), ('atomic-claims-reviewed-v1.json', atomic_registry), ('question-cluster-registry-current.json', updated_registry), ('question-cluster-silver-routing-reviewed-v1.json', routing), ('silver-draft-work-queue-v1.json', drafts), ('question-cluster-silver-assignment-proposals-v1.json', assignment_proposals), ('silver-draft-consolidation-reviewed-v1.json', consolidation), ('silver-draft-materialized-work-queue-v1.json', materialized), ('silver-draft-authored-registry-v1.json', authored_registry), ('silver-publication-gate-proposals-v1.json', publication_proposals), ('silver-publication-gate-reviewed-v1.json', publication), ('knowledge-display-projection-v1.json', projection), ('system-qa-decisions-v1.json', system)]:
        put(name, doc)
    snapshot_hash = sha256_json(updated_registry)
    snapshot_path = root / f'runtime/analysis/question-registries/{snapshot_hash}.json'
    snapshot_bytes = _bytes(updated_registry)
    if snapshot_path.exists() and snapshot_path.read_bytes() != snapshot_bytes:
        raise ValueError('hash-addressed question snapshot contains conflicting bytes')
    put_raw(snapshot_path, snapshot_bytes)
    put('question-cluster-registry-current.meta.json', {'schema_version': 1, 'status': 'question_registry_current', 'current_sha256': snapshot_hash, 'previous_sha256': sha256_json(registry), 'source_label': role, 'snapshot': str(snapshot_path), 'counts': copy.deepcopy(updated_registry['counts'])})
    topic_path = work / f'topic-cards-v1/{day}.md'
    if topic_path.exists():
        raise ValueError('daily topic file already exists without application receipt')
    put_raw(topic_path, (f'# Topic Cards — {day}\n\n' + '\n'.join(cards)).encode())
    result = {'status': 'semantic_delta_applied_pending_quality_release', 'day': day, 'new_silver': len(authored), 'new_qa': len(new_qa_ids), 'new_qa_ids': new_qa_ids, 'silent_support_cards': len(supports), 'new_source_cards': len(cards), 'new_claims': len(fresh_claims), 'new_questions': len(gold), 'filtered': len(filtered), 'source_sha256': _sha(source), 'proposal_sha256': sha256_json(rows), 'publication_candidate': report, 'batch_path': str(batch), 'baseline_projection': str(batch / 'baseline/knowledge-display-projection-v1.json')}
    put(str((batch / 'silent-support.json').relative_to(work)), {'items': supports})
    put(str((batch / 'filtered-proposals.json').relative_to(work)), {'items': filtered})
    put(str((batch / 'authored-delta.json').relative_to(work)), authdoc)
    put(str((batch / 'publication-delta.json').relative_to(work)), gatedoc)
    put(str(applied_path.relative_to(work)), result)
    deadline.check(reserve=30)
    # Preserve the prepared reading-batch baseline. Never overwrite a previous one.
    baseline_projection = batch / 'baseline/knowledge-display-projection-v1.json'
    original_projection_bytes = before[work / 'knowledge-display-projection-v1.json']
    if baseline_projection.exists():
        if baseline_projection.read_bytes() != original_projection_bytes:
            raise ValueError('existing baseline projection differs; refusing overwrite')
    else:
        _atomic(baseline_projection, original_projection_bytes, deadline)
    entries = []
    for path, data in outputs.items():
        original = before[path]
        relative = os.path.relpath(path, work)
        backup = batch / 'delta-baseline' / ('registry-snapshots/' + path.name if not path.is_relative_to(work) else relative)
        if original is not None:
            if backup.exists() and backup.read_bytes() != original:
                raise ValueError(f'backup already contains different version: {backup}')
            if not backup.exists():
                _atomic(backup, original, deadline)
        entries.append({'file': relative, 'backup': str(backup.relative_to(work)), 'before_sha256': _sha(original), 'after_sha256': _sha(data)})
    journal = {'schema_version': 1, 'status': 'applying', 'day': day, 'source_sha256': _sha(source), 'proposal_sha256': sha256_json(rows), 'files': entries}
    _atomic(journal_path, _bytes(journal), deadline)
    try:
        for path, original in {**before, **protected}.items():
            if _read(path) != original:
                raise ValueError(f'baseline changed while preparing: {path}')
        if chunk.read_bytes() != source or canonical.read_bytes() != source:
            raise ValueError('canonical input changed while preparing')
        for path, data in outputs.items():
            deadline.check()
            if _read(path) != before[path]:
                raise ValueError(f'concurrent edit before write: {path}')
            _atomic(path, data, deadline)
        for path, original in protected.items():
            if _read(path) != original:
                raise ValueError(f'protected human state changed: {path}')
        deadline.check()
        journal['status'] = 'applied'
        _atomic(journal_path, _bytes(journal), deadline)
    except BaseException:
        # Hard cutoff wins: leave applying journal for bounded next-run recovery.
        if deadline.remaining() > 0:
            _restore(work, journal_path, journal, deadline)
        raise
    return result
