These changes repair reliability and authorization handling; they do not establish the cause of any OpenAI account termination. For example, a usage 404 without a terminal code leaves the local account eligible, while a 401 token_revoked stops credential use until reauthentication. A 503 Retry-After: 60 delays the next attempt at least 60 seconds even though local exponential backoff caps at two seconds.

The archived implementation also includes two terminal-auth ordering corrections
identified during review: HTTP bridge connection and reattachment paths only
force refresh for refreshable authentication errors, and streamed permanent
failures settle an API-key reservation before account-health writes. This keeps a
revoked credential from being replayed and prevents a terminal SSE failure from
observing a still-reserved request while the account is marked for reauthentication.
