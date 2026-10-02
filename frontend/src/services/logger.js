// Dev-only logging shim.
//
// Production builds strip these calls so internal diagnostics never leak into
// the browser console. In development (and under Vitest) the messages still go
// to the real console, preserving local debuggability.
const IS_DEV =
  typeof import.meta !== 'undefined' &&
  import.meta.env &&
  import.meta.env.DEV === true;

function emit(method) {
  return (...args) => {
    if (IS_DEV && typeof console !== 'undefined' && console[method]) {
      console[method](...args);
    }
  };
}

export const logger = {
  log: emit('log'),
  info: emit('info'),
  warn: emit('warn'),
  error: emit('error'),
  debug: emit('debug'),
};

export default logger;
