# Go Error Handling Patterns

## HARD violations (must fix)

### Ignored error returns
- Pattern: `_ :=` or `_ =` where the discarded value is an `error`.
- Example: `_ := os.Remove(path)`.
- Why HARD: Silently discards failures. The caller has no way to know the operation failed.

### Empty error checks
- Pattern: `if err != nil { }` — the error is checked but the body does nothing.
- Example: `if err != nil { /* no-op */ }`.
- Why HARD: Acknowledges the error exists then deliberately ignores it. Worse than not checking because it looks intentional.

## WARN (advisory)

### Errors only logged
- Pattern: `log.Printf("...:", err)` (or equivalent) followed by no return or propagation.
- Why WARN: Logging is better than ignoring, but the caller still has no signal. May be intentional in fire-and-forget paths.
