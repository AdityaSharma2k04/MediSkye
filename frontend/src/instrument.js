import * as Sentry from "@sentry/react";

const SENSITIVE_KEYS = new Set([
    "email", "authorization", "password", "token", "id_token",
    "health_profile", "phi", "lab_results", "document_text",
    "query", "message", "prompt", "response", "caregiver",
]);

export function scrubPhi(obj) {
    if (Array.isArray(obj)) {
        return obj.map(scrubPhi);
    }
    if (obj && typeof obj === "object") {
        const out = {};
        for (const [k, v] of Object.entries(obj)) {
            out[k] = SENSITIVE_KEYS.has(String(k).toLowerCase()) ? "[scrubbed]" : scrubPhi(v);
        }
        return out;
    }
    if (typeof obj === "string" && obj.length > 256) {
        return obj.slice(0, 256) + "...[truncated]";
    }
    return obj;
}

Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || "production",
    release: import.meta.env.VITE_SENTRY_RELEASE,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
    beforeSend(event) {
        // Strip request object, user identity, breadcrumbs, and scrub PHI-shaped fields & exception messages
        delete event.request;
        delete event.user;
        delete event.breadcrumbs;
        if (event.exception?.values) {
            for (const val of event.exception.values) {
                if (val && typeof val.value === "string") {
                    val.value = "[scrubbed exception message]";
                }
            }
        }
        if (event.extra) {
            event.extra = scrubPhi(event.extra);
        }
        if (event.contexts) {
            event.contexts = scrubPhi(event.contexts);
        }
        return event;
    },
});