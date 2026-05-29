import React from 'react';

/**
 * 🎨 StatusBadge — small color-coded pill used in operation card headers and meta sections.
 */
export const StatusBadge = ({ text, tone = 'slate', testid, title }) => {
  const tones = {
    emerald: 'bg-emerald-500/10 text-emerald-700 border-emerald-300 dark:text-emerald-300 dark:border-emerald-700',
    amber:   'bg-amber-500/10 text-amber-700 border-amber-300 dark:text-amber-300 dark:border-amber-700',
    rose:    'bg-rose-500/10 text-rose-700 border-rose-300 dark:text-rose-300 dark:border-rose-700',
    sky:     'bg-sky-500/10 text-sky-700 border-sky-300 dark:text-sky-300 dark:border-sky-700',
    indigo:  'bg-indigo-500/10 text-indigo-700 border-indigo-300 dark:text-indigo-300 dark:border-indigo-700',
    cyan:    'bg-cyan-500/10 text-cyan-700 border-cyan-300 dark:text-cyan-300 dark:border-cyan-700',
    slate:   'bg-slate-500/10 text-slate-700 border-slate-300 dark:text-slate-200 dark:border-slate-600',
  };
  return (
    <span
      data-testid={testid}
      title={title}
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-bold ${tones[tone] || tones.slate}`}
    >
      {text}
    </span>
  );
};

export default StatusBadge;
