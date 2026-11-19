import React, { forwardRef } from 'react';
import { cn } from '../../lib/cn';

/**
 * Square icon button with a guaranteed 36px (44px on touch) hit area.
 * Always pass `label` — it becomes the accessible name and tooltip.
 */
const IconButton = forwardRef(function IconButton(
  { label, title, children, active = false, tone = 'default', size = 'md', className, ...props },
  ref
) {
  const sizes = { sm: 'w-8 h-8', md: 'w-9 h-9', lg: 'w-11 h-11' };
  const tones = {
    default: active
      ? 'bg-slate-200 text-slate-900 border-slate-300'
      : 'text-slate-500 hover:text-slate-900 hover:bg-slate-100 border-transparent',
    outline: active
      ? 'bg-cyan-50 text-cyan-800 border-cyan-200'
      : 'bg-slate-50 text-slate-700 hover:text-slate-900 hover:bg-slate-100 border-slate-200',
    primary: 'bg-cyan-600 text-white hover:bg-cyan-700 border-cyan-600 shadow-sm',
  };
  return (
    <button
      ref={ref}
      type="button"
      aria-label={label}
      title={title ?? label}
      aria-pressed={props['aria-pressed']}
      className={cn(
        'ms-tap relative inline-flex items-center justify-center rounded-xl border shrink-0',
        'transition-[background-color,color,border-color,transform] duration-150 active:scale-[0.94]',
        'disabled:opacity-40 disabled:pointer-events-none',
        sizes[size],
        tones[tone],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
});

export default IconButton;
