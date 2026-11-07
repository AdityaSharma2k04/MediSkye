import React from 'react';
import { cn } from '../../lib/cn';

export default function Kbd({ children, className }) {
  return (
    <kbd
      className={cn(
        'inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-md',
        'border border-white/[0.1] bg-white/[0.04] text-[10px] font-medium text-ink-mute ms-num',
        className
      )}
    >
      {children}
    </kbd>
  );
}
