'use strict';
/**
 * WHAT: auto-execution journal 的人工恢复收口服务
 * WHERE: 未来 CLI/API 恢复入口调用；当前只做纯本地状态修复，不碰 JL/ERP 页面
 * WHY: 人工归档必须同步关闭 journal + queue + simulation/audit，避免只关 journal 留下危险状态
 * ENTRY: future cli.js auto-journal resolve / routes.js recovery endpoint
 */

const { RESOLUTION } = require('./auto-execution-journal');

function assertFunction(value, name) {
  if (typeof value !== 'function') throw new Error(`${name} required`);
}

function assertWorkOrderNum(workOrderNum) {
  const value = String(workOrderNum || '').trim();
  if (!value) throw new Error('缺少工单号');
  return value;
}

function assertOperatorNote(note) {
  const value = String(note || '').trim();
  if (!value) throw new Error('人工归档必须填写 operatorNote');
  return value;
}

function assertResolution(resolution) {
  const value = String(resolution || '').trim();
  if (!Object.values(RESOLUTION).includes(value)) throw new Error(`非法人工归档结论: ${resolution}`);
  return value;
}

function latestByCreatedAt(items) {
  return [...items].sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || '')))[0] || null;
}

function findQueueItem(queue, workOrderNum) {
  return (queue.items || []).find(item => item.workOrderNum === workOrderNum && item.status !== 'done')
    || (queue.items || []).find(item => item.workOrderNum === workOrderNum)
    || null;
}

function queuePatchForResolution(resolution, now, operatorNote) {
  const common = {
    autoExecutionRecovered: true,
    autoExecutionRecoveryRequired: false,
    manualResolvedAt: now,
    manualResolution: resolution,
    manualResolutionNote: operatorNote,
  };
  const clearExecutionFields = {
    executedAt: null,
    autoExecutedAt: null,
    execution: null,
  };
  if (resolution === RESOLUTION.CONFIRMED_EXECUTED) {
    return {
      ...common,
      status: 'auto_executed',
      executedAt: now,
      autoExecutedAt: now,
      manualExecuteBlocked: true,
      autoExecuteBlocked: true,
      batchExecuteBlocked: true,
    };
  }
  if (resolution === RESOLUTION.CONFIRMED_NOT_EXECUTED) {
    return {
      ...common,
      ...clearExecutionFields,
      status: 'simulated',
      autoExecutionInterrupted: true,
      manualExecuteBlocked: false,
      autoExecuteBlocked: true,
      batchExecuteBlocked: true,
      autoBlockedReason: '自动执行中断，人工确认平台未执行；禁止自动重试',
    };
  }
  return {
    ...common,
    ...clearExecutionFields,
    status: 'simulated',
    autoExecutionInterrupted: true,
    manualExecuteBlocked: true,
    autoExecuteBlocked: true,
    batchExecuteBlocked: true,
    autoBlockedReason: '自动执行中断且平台状态不明，禁止自动/批量执行',
  };
}

function stableRecoverySimulationId(workOrderNum, resolution) {
  return `auto-recovery-${workOrderNum}-${resolution}`;
}

function buildAuditSimulation({ workOrderNum, queueItem, latestSimulation, resolution, operatorNote, now, journalRecord }) {
  const base = latestSimulation || {};
  const sim = {
    ...base,
    id: stableRecoverySimulationId(workOrderNum, resolution),
    workOrderNum,
    queueItemId: queueItem.id,
    accountNum: queueItem.accountNum || base.accountNum || null,
    accountNote: queueItem.accountNote || base.accountNote || '',
    mode: queueItem.mode || base.mode || 'live',
    source: 'auto_execution_recovery',
    createdAt: now,
    autoExecutionRecovered: true,
    autoExecutionRecoveryRequired: false,
    manualResolvedAt: now,
    manualResolution: resolution,
    manualResolutionNote: operatorNote,
    journalStatus: journalRecord && journalRecord.status,
    journalPhase: journalRecord && journalRecord.phase,
  };
  if (resolution === RESOLUTION.CONFIRMED_EXECUTED) {
    sim.executedAt = base.executedAt || now;
    sim.autoExecutedAt = base.autoExecutedAt || now;
    sim.execution = base.execution || { success: true, source: 'manual_recovery_confirmed_executed' };
  } else if (resolution === RESOLUTION.CONFIRMED_NOT_EXECUTED) {
    sim.executedAt = null;
    sim.autoExecutedAt = null;
    sim.execution = null;
    sim.autoExecuteError = '自动执行中断，人工确认平台未执行；禁止自动重试';
    sim.manualExecuteBlocked = false;
    sim.batchExecuteBlocked = true;
  } else {
    sim.executedAt = null;
    sim.autoExecutedAt = null;
    sim.execution = null;
    sim.autoExecuteError = '自动执行中断且平台状态不明，禁止自动/批量执行';
    sim.manualExecuteBlocked = true;
    sim.batchExecuteBlocked = true;
  }
  return sim;
}

function createAutoExecutionRecovery({
  journal,
  readQueue,
  updateQueueItem,
  readSimulations,
  appendSimulation,
  now = () => new Date(),
} = {}) {
  if (!journal || typeof journal.resolveManual !== 'function' || typeof journal.read !== 'function') {
    throw new Error('journal with resolveManual/read required');
  }
  assertFunction(readQueue, 'readQueue');
  assertFunction(updateQueueItem, 'updateQueueItem');
  assertFunction(readSimulations, 'readSimulations');
  assertFunction(appendSimulation, 'appendSimulation');

  return {
    resolve({ workOrderNum, resolution, operatorNote, resolvedBy = 'manual' } = {}) {
      const num = assertWorkOrderNum(workOrderNum);
      const finalResolution = assertResolution(resolution);
      const finalNote = assertOperatorNote(operatorNote);
      const stamp = now() instanceof Date ? now().toISOString() : new Date(now()).toISOString();
      const journalRecord = journal.read()[num];
      if (!journalRecord) throw new Error(`工单 ${num} 缺少自动执行 journal 记录`);

      const queue = readQueue();
      const queueItem = findQueueItem(queue, num);
      if (!queueItem || !queueItem.id) throw new Error(`工单 ${num} 缺少 queue item，拒绝 journal-only 归档`);

      const simulations = readSimulations();
      const latestSimulation = latestByCreatedAt((simulations || []).filter(sim => sim.workOrderNum === num));
      const auditId = stableRecoverySimulationId(num, finalResolution);
      const existingAudit = (simulations || []).find(sim => sim.id === auditId);
      const effectiveNote = existingAudit && existingAudit.manualResolutionNote
        ? existingAudit.manualResolutionNote
        : finalNote;
      const queuePatch = queuePatchForResolution(finalResolution, stamp, effectiveNote);
      const updatedQueueItem = updateQueueItem(queueItem.id, queuePatch);
      if (!updatedQueueItem) throw new Error(`工单 ${num} queue 更新失败，拒绝 journal-only 归档`);

      const auditSimulation = buildAuditSimulation({
        workOrderNum: num,
        queueItem: updatedQueueItem,
        latestSimulation,
        resolution: finalResolution,
        operatorNote: effectiveNote,
        now: stamp,
        journalRecord,
      });
      if (!existingAudit) appendSimulation(auditSimulation);

      const resolvedJournal = journal.resolveManual(num, {
        resolution: finalResolution,
        operatorNote: effectiveNote,
        resolvedBy,
        metadata: {
          queueItemId: updatedQueueItem.id,
          recoverySimulationId: auditSimulation.id,
        },
      });

      return {
        ok: true,
        workOrderNum: num,
        resolution: finalResolution,
        queueItem: updatedQueueItem,
        simulation: auditSimulation,
        journal: resolvedJournal,
      };
    },
  };
}

module.exports = {
  createAutoExecutionRecovery,
  buildAuditSimulation,
  queuePatchForResolution,
  stableRecoverySimulationId,
};
