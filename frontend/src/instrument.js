import * as Sentry from "@sentry/react";

Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || "production",
    release: import.meta.env.VITE_SENTRY_RELEASE,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
    beforeSend(event) {
        // Strip auth headers and any PHI-shaped fields before sending
        if (event.request?.headers) {
            delete event.request.headers["Authorization"];
            delete event.request.headers["Cookie"];
        }
        return event;
    },
});