# TypeScript Error Handling Patterns

## HARD violations (must fix)

### Empty catch blocks
- Pattern: `catch (e) { }` or `catch { }` — the error is caught but the body does nothing.
- Example: `try { await fetch(url) } catch (e) { }`.
- Why HARD: Silently swallows the error. The caller has no way to know the operation failed.

### Swallowed promise rejections
- Pattern: `.catch(() => {})` or `.catch(() => undefined)` — rejection handler that does nothing.
- Example: `fetchData().catch(() => {})`.
- Why HARD: Silently discards async failures. Equivalent to an empty catch block for promises.

## SHOULD violations (fix or justify)

### Catch returns default without logging
- Pattern: `catch (e) { return defaultValue }` without any logging or re-throw.
- Note: if the catch block logs before returning the default, this downgrades to WARN.
- Justification: acceptable in optional enhancement paths where the default is a documented fallback.

### Broad catch without re-throw
- Pattern: `catch (e) { ... }` that handles the error but catches all error types without narrowing (e.g., no `instanceof` check) and does not re-throw.
- Justification: acceptable when the catch genuinely needs to handle all error types (e.g., top-level error boundary).

## WARN (advisory)

### Console-only handling
- Pattern: `catch (e) { console.error(e) }` with no re-throw or return.
- Why WARN: Better than ignoring, but `console.error` is often not sufficient for production error tracking. May be intentional in development-only code.

### Floating promises
- Pattern: calling an async function or a function returning a `Promise` without `await`, `.then()`, or `.catch()`.
- Example: `deleteOldRecords()` where `deleteOldRecords` is async.
- Why WARN: Unhandled rejections can crash the process or be silently lost. May be intentional for fire-and-forget operations, but should be explicitly marked (e.g., `void deleteOldRecords()`).
