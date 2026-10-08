"""Two-group incremental capture orchestration over the formal runner."""

from __future__ import annotations

from .full_capture import FullCaptureRunner, GroupTarget
from .run_capture import CaptureRunConfig, CaptureRunner, RecoveryRequired


class IncrementalCaptureRunner(FullCaptureRunner):
    """Refresh each target history window, then stop at the previous anchor."""

    def run(self):
        state = self.state_store.load()
        expected_groups = {target.group_key for target in self.config.groups}
        if state is None:
            raise RecoveryRequired(
                "incremental capture requires a previous completed baseline; refusing any QQ UI action"
            )
        if state["batch_id"] != self.config.batch_id:
            if state["status"] not in {"completed", "analyzed"}:
                raise RecoveryRequired(
                    "incremental capture requires the prior batch to be completed before any QQ UI action"
                )
            if set(state["groups"]) != expected_groups:
                raise RecoveryRequired(
                    "previous completed group set differs from local config; refusing any QQ UI action"
                )
            for group_key, progress in state["groups"].items():
                if len(progress["last_completed_anchor"]) < 2:
                    raise RecoveryRequired(
                        f"previous completed group {group_key} has no continuous anchor; refusing any QQ UI action"
                    )
        elif state.get("batch_kind") != "incremental":
            raise RecoveryRequired(
                "requested incremental batch_id already belongs to a non-incremental batch"
            )
        return super().run()

    def _runner_for(self, target: GroupTarget) -> CaptureRunner:
        return CaptureRunner(
            self.project_root,
            CaptureRunConfig(
                batch_id=self.config.batch_id,
                group_key=target.group_key,
                expected_title=target.history_title,
                page_count=None,
                window_x=self.config.window_x,
                window_y=self.config.window_y,
                window_width=self.config.window_width,
                window_height=self.config.window_height,
                scroll_pixels=self.config.scroll_pixels,
                runtime_root=self.config.runtime_root,
                batch_group_keys=tuple(item.group_key for item in self.config.groups),
                boundary_confirmations=self.config.boundary_confirmations,
                max_new_pages=self.config.max_new_pages_per_run,
                batch_kind="incremental",
            ),
            step_executor=self.step_executor,
            now=self.now,
        )

