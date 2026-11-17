from __future__ import annotations

from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest

from src.analysis.analysis_release import sha256_file, sha256_path
from src.analysis.knowledge_display_projection import qa_fingerprint
from src.analysis.page_renderer import build_page_v3
from src.analysis.reading_batches import ReadingBatchError, ReadingBatchStore, publish_reading_batch
from src.app.serve_analysis import ReviewApp, make_server


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def qa(number: int, answer: str = '结论') -> dict:
    return {'qa_id': f'K-TEST::q{number}', 'question': f'问题{number}？', 'answer': answer,
            'confidence': 'medium', 'lifecycle': 'durable', 'time_context': '',
            'verification_note': '来源说明', 'evidence_refs': ['T-20261019-001']}


def projection(qas: list[dict]) -> dict:
    return {'schema_version': 1, 'status': 'reviewed_knowledge_display_projection',
            'items': [{'knowledge_id': 'K-TEST', 'display_status': 'visible', 'qas': qas}]}


class ReadingBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = ReadingBatchStore(self.root)

    def release(self, day: str, before: list[dict], after: list[dict], *, system_discard: bool = False) -> str:
        bid = 'history-' + day.replace('-', '') + '-full'
        rid = 'ar-test-' + bid
        directory = self.root / 'runtime/analysis/releases' / rid
        baseline = self.root / 'runtime/analysis-work/batches' / bid / 'baseline/knowledge-display-projection-v1.json'
        write(baseline, projection(before))
        write(directory / 'display_projection.json', projection(after))
        source = {'batch_id': bid, 'current_sha256': 'a' * 64, 'message_count': 3,
                  'canonical_batch_sha256': 'b' * 64, 'capture_runtime': f'runtime/history-days/{day}'}
        work = {'schema_version': '1', 'status': 'analysis_work_prepared', 'batch_id': bid, 'source': source,
                'baseline_artifacts': {'display_projection': {'path': 'runtime/analysis-work/knowledge-display-projection-v1.json', 'sha256': sha256_file(baseline)}}}
        write(directory / 'analysis-work-package-v1.json', work)
        receipt = {'schema_version': '1', 'status': 'reviewed_analysis_ready', 'batch_id': bid,
                   'source': {k: source[k] for k in ['current_sha256', 'canonical_batch_sha256', 'message_count']},
                   'work_package': {'path': f'runtime/analysis-work/batches/{bid}/analysis-work-package-v1.json', 'sha256': sha256_file(directory / 'analysis-work-package-v1.json')},
                   'artifacts': {'display_projection': {'path': 'runtime/analysis-work/knowledge-display-projection-v1.json', 'sha256': sha256_file(directory / 'display_projection.json')}},
                   'reviewed_at': '2026-11-13T00:00:00Z', 'reviewer': 'test'}
        write(directory / 'reviewed-analysis-v1.json', receipt)
        write(directory / 'silver_knowledge.json', {'units': [{'knowledge_id': 'K-TEST', 'subject': '测试父对象', 'topics': ['职业', '猎人'], 'scope': {'game_variant': '时光服', 'class_spec': '生存猎', 'instance': '纳克萨玛斯', 'profession': '工程'}}]})
        write(directory / 'quality.json', {'result': 'PASS', 'quality': {'errors': 0}})
        write(directory / 'system_qa_decisions.json', {'items': [{'qa_id': q['qa_id'], 'qa_fingerprint': qa_fingerprint('K-TEST', q), 'decision': 'discard' if system_discard else 'knowledge'} for q in after]})
        (directory / 'page.html').write_text('<html>complete</html>')
        (directory / 'page-v2-details').mkdir()
        (directory / 'page-v2-details/T-20261019-001.html').write_text('<html>原文</html>')
        names = {'work_package': 'analysis-work-package-v1.json', 'review_receipt': 'reviewed-analysis-v1.json',
                 'display_projection': 'display_projection.json', 'silver_knowledge': 'silver_knowledge.json',
                 'system_qa_decisions': 'system_qa_decisions.json', 'page': 'page.html',
                 'page_details': 'page-v2-details', 'quality_report': 'quality.json'}
        artifacts = {k: {'path': v, 'sha256': sha256_path(directory / v)} for k, v in names.items()}
        write(directory / 'result.json', {'schema_version': '1', 'status': 'published_analysis_result', 'run_id': rid,
                                         'batch_id': bid, 'source': source, 'quality': {'errors': 0, 'result': 'PASS'},
                                         'review': {'receipt_sha256': artifacts['review_receipt']['sha256']}, 'artifacts': artifacts})
        return rid

    def publish(self, bid: str, days: list[str], runs: list[str]) -> dict:
        return publish_reading_batch(self.root, reading_batch_id=bid, expected_days=days, run_ids=runs, now='2026-11-13T00:00:00Z')

    def test_exact_id_delta_includes_discard_and_frozen_evidence(self) -> None:
        old = qa(1)
        changed = qa(1, '旧ID新答案，不是新增')
        run = self.release('2026-10-19', [old], [changed, qa(2)], system_discard=True)
        doc = self.publish('r-19', ['2026-10-19'], [run])
        self.assertEqual([q['qa_id'] for q in doc['qas']], ['K-TEST::q2'])
        self.assertEqual(doc['qas'][0]['system_decision'], 'discard')
        self.assertEqual(doc['qas'][0]['qa_fingerprint'], qa_fingerprint('K-TEST', qa(2)))
        self.assertEqual(self.store.evidence_file('r-19', 'K-TEST::q2', 'T-20261019-001').read_text(), '<html>原文</html>')
        self.assertEqual(doc['qas'][0]['answer'], '结论')

    def test_frozen_parent_context_is_read_without_mutating_snapshot(self) -> None:
        run = self.release('2026-10-19', [], [qa(1)])
        self.publish('context', ['2026-10-19'], [run])
        path = self.store.entries / 'context.json'
        before = path.read_bytes()
        # Mutable live knowledge must never override the frozen release context.
        write(self.root / 'runtime/analysis-work/silver-knowledge-v1.json', {'units': []})
        row = self.store.snapshot()['batches'][0]['qas'][0]
        self.assertEqual(row['topics'], ['职业', '猎人'])
        self.assertEqual(row['scope']['class_spec'], '生存猎')
        self.assertEqual(row['scope']['instance'], '纳克萨玛斯')
        self.assertEqual(row['scope']['profession'], '工程')
        self.assertEqual(row['confidence'], 'medium')
        self.assertEqual(path.read_bytes(), before)

    def test_deadline_before_current_switch_keeps_previous_pointer(self) -> None:
        from unittest.mock import patch
        from src.app.runtime_deadline import DeadlineExceeded
        run = self.release('2026-10-19', [], [qa(1)])
        self.publish('old', ['2026-10-19'], [run])
        before = (self.store.root / 'current.json').read_bytes()
        # entry, after release validation, before snapshot write, before current
        with patch('src.analysis.reading_batches.check_environment_deadline', side_effect=[None, None, None, DeadlineExceeded('end')]):
            with self.assertRaises(DeadlineExceeded):
                self.publish('late', ['2026-10-19'], [run])
        self.assertEqual((self.store.root / 'current.json').read_bytes(), before)

    def test_duplicate_support_produces_empty_batch(self) -> None:
        altered = qa(1)
        altered['verification_note'] = '新增支持，问答ID不变'
        run = self.release('2026-10-19', [qa(1)], [altered])
        doc = self.publish('support-only', ['2026-10-19'], [run])
        self.assertEqual(doc['qa_count'], 0)

    def test_three_complete_days_merge_and_partial_cannot_replace_current(self) -> None:
        first = self.release('2026-10-19', [], [qa(1)])
        self.publish('old', ['2026-10-19'], [first])
        current_before = (self.store.root / 'current.json').read_bytes()
        r2 = self.release('2026-10-20', [qa(1)], [qa(1), qa(2)])
        r3 = self.release('2026-10-21', [qa(1), qa(2)], [qa(1), qa(2), qa(3)])
        days = ['2026-10-19', '2026-10-20', '2026-10-21']
        with self.assertRaises(ReadingBatchError):
            self.publish('partial', days, [first, r2])
        self.assertEqual((self.store.root / 'current.json').read_bytes(), current_before)
        doc = self.publish('three-day', days, [r3, first, r2])
        self.assertEqual(doc['qa_count'], 3)
        self.assertEqual(doc['run_ids'], [first, r2, r3])
        snapshot = self.store.snapshot()
        self.assertEqual(snapshot['current_batch_id'], 'three-day')
        self.assertEqual(len(snapshot['batches']), 2)
        self.assertIsNone(next(b for b in snapshot['batches'] if b['reading_batch_id'] == 'old')['seen_at'])

    def test_expected_days_mismatch_and_unpublished_release_rejected(self) -> None:
        run = self.release('2026-10-19', [], [qa(1)])
        with self.assertRaises(ReadingBatchError):
            self.publish('wrong-date', ['2026-10-20'], [run])
        path = self.root / 'runtime/analysis/releases' / run / 'result.json'
        doc = json.loads(path.read_text()); doc['status'] = 'running'; write(path, doc)
        with self.assertRaises(ReadingBatchError):
            self.publish('unfinished', ['2026-10-19'], [run])
        self.assertFalse((self.store.root / 'current.json').exists())

    def test_work_baseline_hash_must_match_and_failed_publish_preserves_current(self) -> None:
        run = self.release('2026-10-19', [], [qa(1)])
        self.publish('first', ['2026-10-19'], [run])
        pointer = (self.store.root / 'current.json').read_bytes()
        bad = self.release('2026-10-20', [qa(1)], [qa(1), qa(2)])
        baseline = self.root / 'runtime/analysis-work/batches/history-20261020-full/baseline/knowledge-display-projection-v1.json'
        write(baseline, projection([]))
        with self.assertRaisesRegex(ReadingBatchError, 'baseline'):
            self.publish('bad', ['2026-10-20'], [bad])
        self.assertEqual((self.store.root / 'current.json').read_bytes(), pointer)
        self.assertFalse((self.store.entries / 'bad.json').exists())

    def test_tampered_release_artifact_is_rejected(self) -> None:
        run = self.release('2026-10-19', [], [qa(1)])
        path = self.root / 'runtime/analysis/releases' / run / 'display_projection.json'
        write(path, projection([qa(2)]))
        with self.assertRaisesRegex(ReadingBatchError, 'hash'):
            self.publish('tampered', ['2026-10-19'], [run])

    def test_seen_is_idempotent_independent_and_immutable_batch_stays(self) -> None:
        run = self.release('2026-10-19', [], [qa(1)])
        self.publish('first', ['2026-10-19'], [run])
        sentinel = self.root / 'runtime/analysis-work/display-review-decisions-v1.json'
        write(sentinel, {'items': [{'qa_id': 'human-sentinel'}]})
        before = sentinel.read_bytes()
        batch = (self.store.entries / 'first.json').read_bytes()
        self.store.mark_seen('first', now='2026-11-13T01:00:00Z')
        self.assertEqual(self.store.mark_seen('first', now='later')['seen_at'], '2026-11-13T01:00:00Z')
        self.assertEqual(sentinel.read_bytes(), before)
        self.assertEqual((self.store.entries / 'first.json').read_bytes(), batch)
        self.assertEqual(self.store.snapshot()['batches'][0]['seen_at'], '2026-11-13T01:00:00Z')
        self.assertEqual(self.publish('first', ['2026-10-19'], [run])['qa_count'], 1)
        self.assertEqual(len(self.store.snapshot()['batches']), 1)

    def test_ui_default_and_api_seen_requires_same_origin_csrf(self) -> None:
        run = self.release('2026-10-19', [], [qa(1)], system_discard=True)
        self.publish('first', ['2026-10-19'], [run])
        page = build_page_v3([], [], {}, [], self.store.snapshot())
        self.assertIn('class="active" data-view="reading"', page)
        self.assertIn('data-reading-seen', page)
        self.assertIn('data-reading-card', page)
        self.assertNotIn("onclick=\"markReadingSeen", page)
        app = ReviewApp(self.root, csrf_token='token', now=lambda: '2026-11-13T02:00:00Z')
        server = make_server(app, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            def request(token: str, origin: str):
                c = HTTPConnection('127.0.0.1', server.server_port)
                c.request('POST', '/api/reading-batch-seen', json.dumps({'reading_batch_id': 'first'}),
                          {'Content-Type': 'application/json', 'X-GCA-CSRF': token, 'Origin': origin})
                response = c.getresponse(); value = (response.status, json.loads(response.read())); c.close(); return value
            origin = f'http://127.0.0.1:{server.server_port}'
            self.assertEqual(request('bad', origin)[0], 403)
            self.assertEqual(request('token', 'http://127.0.0.1:9999')[0], 403)
            self.assertEqual(request('token', origin)[0], 200)
            self.assertFalse((self.root / 'runtime/analysis-work/display-review-decisions-v1.json').exists())
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
