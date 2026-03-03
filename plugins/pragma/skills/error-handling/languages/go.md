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

## SHOULD violations (fix or justify)

### Errors returned without context
- Pattern: bare `return err` without wrapping (e.g., `return fmt.Errorf("...: %w", err)`).
- Note: the *wrapping format* (`%w` vs `%s`) is owned by `go-effective`. This validator only checks whether *any* context is added at all.
- Justification: acceptable at the top of a call stack where the error already carries sufficient context.

## WARN (advisory)

### Errors only logged
- Pattern: `log.Printf("...:", err)` (or equivalent) followed by no return or propagation.
- Why WARN: Logging is better than ignoring, but the caller still has no signal. May be intentional in fire-and-forget paths.
