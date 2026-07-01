# Codex Monitor Capsule Hover Redesign

## Goal

Make the monitor feel like a lightweight desktop status widget instead of a large floating window.

The primary use case is the bottom-left desktop area, where the wallpaper is dark and relatively empty. The collapsed view should be readable at a glance, close to Dock height, and visually calm. Detailed project usage should appear only when the user clicks the capsule.

## Final Interaction

### Collapsed State

- The monitor defaults to a dock-height horizontal capsule.
- Target size: about `258 x 82`.
- Position remains user-draggable and persisted.
- The capsule uses a stronger dark glass background:
  - native macOS blur remains enabled,
  - background is less transparent than the current live version,
  - light text is used directly on the dark glass surface.
- There are no visible text buttons.

### Quota Layout

- Left ring: 5-hour quota.
- Right ring: weekly quota.
- The two rings are visually symmetric.
- The center column shows reset times:
  - upper line uses the 5-hour quota color,
  - lower line uses the weekly quota color,
  - a subtle divider separates the two lines.
- Time is displayed in readable Chinese:
  - examples: `2小时52分`, `6天16小时`,
  - omit zero-value units,
  - use compact fallback only if space becomes impossible.

### Color Direction

Use a softer status-monitor palette instead of the current blue/purple default:

- 5-hour quota: cyan/teal family.
- Weekly quota: warm amber family.
- Text: off-white primary text with muted secondary text.
- Ring tracks: very subtle translucent light track, not a thick gray ring.

## Project Popover

### Trigger

- Clicking anywhere on the collapsed capsule shows a popover above the capsule.
- The popover remains visible while the pointer is over either the capsule or the popover.
- Hide the popover when the pointer leaves both areas.

### Content

- The popover shows only the current project table section.
- It should be `项目 Top 10`, not Top 6.
- Keep the existing table meaning and fields:
  - project name,
  - today,
  - 30-day total,
  - percent.
- Keep the existing estimation note:
  - `结合 Claude Code 和 Codex 本地日志估算`
- Do not include refresh, collapse, close, or quota cards in the popover.

### Visual Style

- The popover uses the same dark glass language as the capsule.
- It can be taller than the capsule because it is transient.
- It should not compress the project table more than the current expanded view does.
- It should appear above the capsule and avoid the Dock.

## Implementation Notes

- Keep the native AppKit blur background approach; do not reparent Tk native views.
- Replace the current 190x190 collapsed canvas with a dock-height capsule canvas.
- Replace click-to-expanded behavior with click-to-popover behavior.
- The popover can be implemented as a transparent/overrideredirect Tk toplevel paired with a native blur background window, following the same layering principle as the main window.
- Existing expanded-window behavior can be removed from the normal UX path once the click popover is implemented.

## Validation

- Unit tests should cover:
  - human-readable duration formatting,
  - click-to-popover behavior,
  - Top 10 project list is preserved,
  - collapsed size constants match the dock-height capsule target,
  - no footer action buttons are shown.
- Manual verification should cover:
  - LaunchAgent restart succeeds,
  - collapsed capsule appears near Dock height,
  - clicking the capsule shows Top 10,
  - moving away hides the popover,
  - text remains readable on the dark desktop background.
