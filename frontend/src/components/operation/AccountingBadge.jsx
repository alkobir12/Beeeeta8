import React from 'react';
import { Receipt } from 'lucide-react';

/**
 * 🎨 AccountingBadge — cyan-styled block showing the journal entry text + chips for
 * account name, code, and accounting classification.
 */
export const AccountingBadge = ({
  operationId,
  journalEntryText,
  accountName,
  accountCode,
  accountClassLabel,
}) => (
  <div className="mt-3 rounded-2xl border border-cyan-200 bg-cyan-50/70 p-4 dark:border-cyan-500/20 dark:bg-cyan-500/[0.05]">
    <div className="flex items-center gap-2 mb-1">
      <Receipt size={14} className="text-cyan-600 dark:text-cyan-400" />
      <p className="text-xs font-bold text-cyan-700 dark:text-cyan-300">القيد المحاسبي</p>
    </div>
    <p
      className="text-xs text-slate-700 dark:text-zinc-300 leading-6 whitespace-normal break-words"
      data-testid={`operation-card-journal-entry-${operationId}`}
    >
      {journalEntryText}
    </p>
    <div className="mt-2 flex flex-wrap gap-1.5">
      <span
        className="rounded-full bg-white/70 dark:bg-white/[0.06] border border-cyan-200 dark:border-cyan-500/20 px-2.5 py-0.5 text-[10px] font-semibold text-slate-700 dark:text-zinc-200"
        data-testid={`operation-card-account-name-${operationId}`}
      >
        {accountName || 'حساب غير محدد'}{accountCode ? ` (${accountCode})` : ''}
      </span>
      <span
        className="rounded-full bg-white/70 dark:bg-white/[0.06] border border-cyan-200 dark:border-cyan-500/20 px-2.5 py-0.5 text-[10px] font-semibold text-slate-700 dark:text-zinc-200"
        data-testid={`operation-card-account-class-${operationId}`}
      >
        تصنيف: {accountClassLabel}
      </span>
    </div>
  </div>
);

export default AccountingBadge;
