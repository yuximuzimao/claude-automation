ObjC.import('Cocoa');
ObjC.import('Foundation');

function readStatus(filePath) {
  try {
    const text = ObjC.unwrap(
      $.NSString.stringWithContentsOfFileEncodingError(
        filePath,
        $.NSUTF8StringEncoding,
        null
      )
    );
    return JSON.parse(text);
  } catch (e) {
    return null;
  }
}

function safeNumber(value, fallback) {
  const num = Number(value);
  return Number.isFinite(num) ? num : fallback;
}

function setText(field, value) {
  field.setStringValue(String(value == null ? '' : value));
}

function terminalTitle(phase) {
  if (phase === 'done') return '自动扫描完成';
  if (phase === 'completed_with_errors') return '自动扫描完成 · 有异常';
  if (phase === 'cancelled') return '自动扫描已停止';
  return '自动扫描异常结束';
}

function terminalStatus(state) {
  if (state.status) return state.status;
  if (state.phase === 'done') return '本轮工单自动扫描已完成';
  if (state.phase === 'completed_with_errors') return '本轮扫描已完成，部分店铺出现异常';
  if (state.phase === 'cancelled') return '本轮扫描已停止';
  return '本轮扫描因异常结束';
}

function render(state, fields) {
  const now = Date.now();
  const phase = state.phase || 'running';
  const shopIndex = safeNumber(state.shopIndex, 0);
  const shopTotal = safeNumber(state.shopTotal, 0);
  const remainingShops = safeNumber(state.remainingShops, Math.max(0, shopTotal - shopIndex));
  const ticketIndex = safeNumber(state.ticketIndex, 0);
  const ticketTotal = safeNumber(state.ticketTotal, 0);
  const accountErrors = safeNumber(state.accountErrors, 0);
  const processedTickets = safeNumber(state.processedTickets, 0);

  if (phase === 'countdown') {
    const remainingMs = Math.max(0, safeNumber(state.countdownUntil, now) - now);
    const seconds = Math.ceil(remainingMs / 1000);
    setText(fields.title, '售后自动扫描即将开始');
    setText(fields.status, `${seconds} 秒后开始工单自动扫描`);
    setText(fields.detail, state.detail || '请暂存当前工作，并暂时停止鼠标键盘操作。');
    setText(fields.shop, '准备时间');
    setText(fields.ticket, `00:${String(seconds).padStart(2, '0')}`);
    fields.progress.setDoubleValue(Math.max(0, Math.min(1, 1 - seconds / 10)));
    return;
  }

  if (phase === 'queued') {
    setText(fields.title, '售后自动扫描准备中');
    setText(fields.status, state.status || '等待扫描队列');
    setText(fields.detail, '自动扫描尚未开始浏览器操作。');
    setText(fields.shop, '店铺：等待开始');
    setText(fields.ticket, '工单：等待开始');
    fields.progress.setDoubleValue(0);
    return;
  }

  if (['done', 'completed_with_errors', 'error', 'cancelled'].includes(phase)) {
    setText(fields.title, terminalTitle(phase));
    setText(fields.status, terminalStatus(state));
    setText(
      fields.detail,
      state.error ? `异常：${state.error}` : (accountErrors > 0 ? `异常店铺 ${accountErrors} 个` : '可以继续正常使用电脑。')
    );
    setText(fields.shop, `店铺：${shopIndex}/${shopTotal || shopIndex} · 剩余 ${Math.max(0, remainingShops)} 个`);
    setText(fields.ticket, `本轮已处理工单 ${processedTickets} 个`);
    fields.progress.setDoubleValue(1);
    return;
  }

  setText(fields.title, '售后自动扫描进行中');
  setText(fields.status, state.status || '正在处理');
  setText(
    fields.detail,
    state.error ? `异常：${state.error}` : (accountErrors > 0 ? `本轮已有 ${accountErrors} 个店铺异常` : '请暂时不要操作自动化浏览器。')
  );
  const shopName = state.shopName || '准备中';
  setText(fields.shop, `店铺 ${shopIndex}/${shopTotal || '?'} · ${shopName} · 剩余 ${remainingShops} 个`);
  if (state.workOrderNum) {
    setText(fields.ticket, `工单 ${ticketIndex || '?'}/${ticketTotal || '?'} · ${state.workOrderNum}`);
  } else {
    setText(fields.ticket, ticketTotal > 0 ? `待处理工单 ${ticketTotal} 个` : '正在读取待处理工单清单');
  }

  let progress = 0;
  if (shopTotal > 0) {
    const completedShops = Math.max(0, shopIndex - 1);
    const ticketFraction = ticketTotal > 0 ? Math.min(1, ticketIndex / ticketTotal) : 0;
    progress = Math.min(1, (completedShops + ticketFraction) / shopTotal);
  }
  fields.progress.setDoubleValue(progress);
}

function makeLabel(text, frame, size, bold) {
  const field = $.NSTextField.labelWithString(text);
  field.setFrame(frame);
  field.setFont(bold ? $.NSFont.boldSystemFontOfSize(size) : $.NSFont.systemFontOfSize(size));
  field.setTextColor($.NSColor.labelColor);
  field.setLineBreakMode($.NSLineBreakByTruncatingTail);
  return field;
}

function run(argv) {
  const filePath = argv && argv.length ? argv[0] : null;
  if (!filePath) return 'missing status file';

  const app = $.NSApplication.sharedApplication;
  app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
  app.finishLaunching;

  const styleMask = $.NSWindowStyleMaskTitled | $.NSWindowStyleMaskNonactivatingPanel;
  const panel = $.NSPanel.alloc.initWithContentRectStyleMaskBackingDefer(
    $.NSMakeRect(0, 0, 440, 230),
    styleMask,
    $.NSBackingStoreBuffered,
    false
  );
  panel.setTitle('售后自动扫描');
  panel.setLevel($.NSFloatingWindowLevel);
  panel.setCollectionBehavior(
    $.NSWindowCollectionBehaviorCanJoinAllSpaces |
    $.NSWindowCollectionBehaviorFullScreenAuxiliary
  );
  panel.setHidesOnDeactivate(false);
  panel.setFloatingPanel(true);
  panel.setBecomesKeyOnlyIfNeeded(true);
  panel.center;

  const content = panel.contentView;
  const title = makeLabel('售后自动扫描', $.NSMakeRect(24, 178, 392, 28), 20, true);
  const status = makeLabel('准备中', $.NSMakeRect(24, 142, 392, 24), 16, true);
  const detail = makeLabel('', $.NSMakeRect(24, 112, 392, 22), 13, false);
  detail.setTextColor($.NSColor.secondaryLabelColor);
  const shop = makeLabel('', $.NSMakeRect(24, 76, 392, 22), 13, false);
  const ticket = makeLabel('', $.NSMakeRect(24, 48, 392, 22), 13, false);

  const progress = $.NSProgressIndicator.alloc.initWithFrame($.NSMakeRect(24, 22, 392, 8));
  progress.setIndeterminate(false);
  progress.setMinValue(0);
  progress.setMaxValue(1);
  progress.setDoubleValue(0);

  content.addSubview(title);
  content.addSubview(status);
  content.addSubview(detail);
  content.addSubview(shop);
  content.addSubview(ticket);
  content.addSubview(progress);

  panel.orderFrontRegardless;

  let missingSince = null;
  while (true) {
    const state = readStatus(filePath);
    const now = Date.now();
    if (!state) {
      if (missingSince == null) missingSince = now;
      if (now - missingSince > 5000) break;
    } else {
      missingSince = null;
      render(state, { title, status, detail, shop, ticket, progress });

      const heartbeatAt = safeNumber(state.heartbeatAt, now);
      if (now - heartbeatAt > 15 * 60 * 1000) break;

      if (['done', 'completed_with_errors', 'error', 'cancelled'].includes(state.phase)) {
        const finishedAt = safeNumber(state.finishedAt, now);
        const closeAfterMs = safeNumber(state.closeAfterMs, 5000);
        if (now - finishedAt >= closeAfterMs) break;
      }
    }

    $.NSRunLoop.currentRunLoop.runUntilDate(
      $.NSDate.dateWithTimeIntervalSinceNow(0.2)
    );
  }

  panel.orderOut(null);
  try { $.NSFileManager.defaultManager.removeItemAtPathError(filePath, null); } catch (e) {}
  app.terminate(null);
  return 'closed';
}
