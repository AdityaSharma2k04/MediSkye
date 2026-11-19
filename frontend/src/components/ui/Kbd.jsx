import React from 'react';
import { cn } from '../../lib/cn';

export default function Kbd({ children, className }) {
  return (
    <kbd
      className={cn(
        'inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-md',
        'border border-slate-200 bg-slate-100 text-xs font-medium text-slate-600 ms-num shadow-sm',
        className
      )}
    >
      {children}
    </kbd>
  );
}
