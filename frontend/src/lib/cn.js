import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Compose Tailwind class lists. `clsx` handles conditionals, `twMerge`
 * resolves conflicts so the last utility for a property wins
 * (e.g. cn('px-2', isWide && 'px-6') → 'px-6').
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export default cn;
