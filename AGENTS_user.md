# Global Codex Instructions

- When using Plan mode or otherwise asking the user for input, wait indefinitely for the user's answer. Do not set or pass `autoResolutionMs` to `request_user_input`. If user input is required before continuing, always ask without an auto-resolve timeout.
- In Plan mode, always be meticulous and create a detailed comprehensive plan.
- In Plan mode, always ask me about all important design decisions.
