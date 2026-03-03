# Go Error Handling Patterns

## HARD violations (must fix)

### Ignored error returns
- Pattern: `_ =` where the discarded value is an `error`, or multi-return `result, _ :=` where the blank identifier replaces an `error`.
- Examples: `_ = os.Remove(path)` (single return), `conn, _ := net.Dial("tcp", addr)` (multi-return, error discarded).
- Why HARD: Silently discards failures. The caller has no way to know the operation failed.

### Empty error checks
- Pattern: `if err != nil { }` — the error is checked but the body does nothing.
- Example: `if err != nil { /* no-op */ }`.
- Why HARD: Acknowledges the error exists then deliberately ignores it. Worse than not checking because it looks intentional.

## WARN (advisory)

### Errors only logged
- Pattern: `log.Printf("...:", err)` (or equivalent) followed by no return or propagation.
- Why WARN: Logging is better than ignoring, but the caller still has no signal. May be intentional in fire-and-forget paths.
