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
      ? 'bg-white/[0.08] text-white border-white/[0.12]'
      : 'text-ink-mute hover:text-white hover:bg-white/[0.06] border-transparent',
    outline: active
      ? 'bg-cyan-500/15 text-cyan-200 border-cyan-500/35'
      : 'bg-white/[0.03] text-ink-soft hover:text-white hover:bg-white/[0.07] border-white/[0.08]',
    primary: 'bg-clinical-cyan text-slate-950 hover:bg-cyan-300 border-cyan-300/40',
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
