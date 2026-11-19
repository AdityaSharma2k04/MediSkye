import React from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Drawer } from 'vaul';
import { X } from 'lucide-react';
import { cn } from '../../lib/cn';
import useViewport from '../../hooks/useViewport';

/**
 * Responsive sheet.
 *  • < 768px  → native-feeling bottom sheet (vaul): drag handle, swipe to dismiss,
 *               safe-area aware, max 92dvh.
 *  • ≥ 768px  → right-side panel (variant="side") or centered dialog (variant="center").
 *
 * Both modes are Radix Dialog underneath: focus trap, Esc to close,
 * aria-modal, labelled by `title`.
 */
export default function Sheet({
  open,
  onOpenChange,
  title,
  description,
  icon: Icon,
  children,
  footer,
  variant = 'side',
  width = 480,
  className,
  bodyClassName,
  hideHeader = false,
}) {
  const { isMobile } = useViewport();

  const header = !hideHeader && (
    <div className="flex items-start gap-3 px-5 pt-4 pb-3 border-b border-slate-200 shrink-0">
      {Icon && (
        <div className="mt-0.5 w-9 h-9 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-cyan-700 shrink-0">
          <Icon className="w-4 h-4" />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <SheetTitle isMobile={isMobile} className="ms-display text-lg text-slate-900 leading-tight">{title}</SheetTitle>
        {description ? (
          <SheetDescription isMobile={isMobile} className="text-xs text-ink-mute mt-1 leading-relaxed">{description}</SheetDescription>
        ) : (
          <SheetDescription isMobile={isMobile} className="sr-only">{title}</SheetDescription>
        )}
      </div>
      <SheetClose isMobile={isMobile}>
        <button
          type="button"
          aria-label={`Close ${typeof title === 'string' ? title : 'panel'}`}
          className="ms-tap w-9 h-9 -mr-1.5 rounded-xl flex items-center justify-center text-slate-400 hover:text-slate-800 hover:bg-slate-100 transition"
        >
          <X className="w-4 h-4" />
        </button>
      </SheetClose>
    </div>
  );

  const body = <div className={cn('flex-1 overflow-y-auto overscroll-contain', bodyClassName)}>{children}</div>;
  const foot = footer && <div className="shrink-0 border-t border-slate-200 px-5 py-3 pb-safe-composer">{footer}</div>;

  if (isMobile) {
    return (
      <Drawer.Root open={open} onOpenChange={onOpenChange} shouldScaleBackground={false}>
        <Drawer.Portal>
          <Drawer.Overlay className="fixed inset-0 z-[60] bg-slate-900/40 backdrop-blur-[2px]" />
          <Drawer.Content
            className={cn(
              'fixed inset-x-0 bottom-0 z-[61] flex flex-col max-h-[92dvh] rounded-t-[28px] outline-none',
              'bg-carbon border-t border-slate-200 shadow-xl',
              className
            )}
          >
            <div className="pt-2.5 pb-1 flex justify-center shrink-0" aria-hidden="true">
              <div className="w-10 h-1.5 rounded-full bg-slate-300" />
            </div>
            {header}
            {body}
            {foot}
          </Drawer.Content>
        </Drawer.Portal>
      </Drawer.Root>
    );
  }

  const isSide = variant === 'side';
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[60] bg-slate-900/40 backdrop-blur-[3px] animate-backdrop-in" />
        {isSide ? (
          <Dialog.Content
            style={{ width: `min(${width}px, 100vw)` }}
            className={cn(
              'fixed z-[61] right-0 top-0 h-app flex flex-col outline-none bg-carbon border border-slate-200 border-r-0 rounded-l-3xl shadow-xl animate-[sheetSide_0.32s_cubic-bezier(0.22,1,0.36,1)_both]',
              className
            )}
          >
            {header}
            {body}
            {foot}
          </Dialog.Content>
        ) : (
          <Dialog.Content
            style={{ width: `min(${width}px, calc(100vw - 24px))` }}
            className={cn(
              'fixed z-[61] inset-x-0 mx-auto top-[12dvh] flex flex-col max-h-[86dvh] rounded-3xl outline-none bg-carbon border border-slate-200 shadow-xl animate-modal-in',
              className
            )}
          >
            {header}
            {body}
            {foot}
          </Dialog.Content>
        )}
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function SheetTitle({ isMobile, ...props }) {
  return isMobile ? <Drawer.Title {...props} /> : <Dialog.Title {...props} />;
}
function SheetDescription({ isMobile, ...props }) {
  return isMobile ? <Drawer.Description {...props} /> : <Dialog.Description {...props} />;
}
function SheetClose({ isMobile, children }) {
  return isMobile ? <Drawer.Close asChild>{children}</Drawer.Close> : <Dialog.Close asChild>{children}</Dialog.Close>;
}
