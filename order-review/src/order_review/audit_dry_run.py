from __future__ import annotations

import argparse
import json
import sys

from . import cdp
from .audit_probe import AuditExecutionLogStore, AuditProbeError, run_audit_preflight
from .erp_reader import (
    build_read_sequence_one_js,
    find_erp_toaudit_target,
    snapshot_from_payload,
)
from .package_plan import SourceSnapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="单包订单普通审核前检查（只读，不点击 ERP）"
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--no-log", action="store_true", help="不写入本地检查日志")
    args = parser.parse_args(argv)
    try:
        target_id = find_erp_toaudit_target()
        if not target_id:
            raise AuditProbeError(
                "TOAUDIT_TARGET_NOT_FOUND",
                "请先把 Chrome 当前标签页切换到快麦 ERP「订单处理 → 待审核订单」",
            )
        payload = cdp.eval_js(target_id, build_read_sequence_one_js())
        if not isinstance(payload, dict) or not payload.get("ok"):
            raise AuditProbeError("ORDER_READ_FAILED", "无法只读读取当前序号 1 订单")
        snapshot = snapshot_from_payload(payload)
        if not snapshot.is_expanded or not snapshot.products:
            raise AuditProbeError(
                "ORDER_NOT_EXPANDED",
                "当前序号 1 订单未展开；为保持检查过程零点击，命令不会自动展开",
            )
        source = SourceSnapshot.from_order_snapshot(snapshot)
        report = run_audit_preflight(
            target_system_order_id=snapshot.system_order_id,
            expected_source=source,
            target_id=target_id,
            log_store=None if args.no_log else AuditExecutionLogStore(),
        )
    except AuditProbeError as exc:
        print(f"{exc.code}：{exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        if args.json
        else report.render_text()
    )
    return 0 if report.preflight_ready else 3


if __name__ == "__main__":
    raise SystemExit(main())
