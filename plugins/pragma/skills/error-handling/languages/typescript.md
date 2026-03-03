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

## WARN (advisory)

### Broad catch without re-throw
- Pattern: `catch (e) { ... }` that handles the error but catches all error types without narrowing (e.g., no `instanceof` check) and does not re-throw.
- Why WARN: TypeScript `catch` is inherently untyped (`unknown` or `any`), so every catch block technically matches this pattern. Flagging as advisory rather than requiring justification avoids excessive noise while still surfacing the pattern for review.

### Console-only handling
- Pattern: `catch (e) { console.error(e) }` with no re-throw or return.
- Why WARN: Better than ignoring, but `console.error` is often not sufficient for production error tracking. May be intentional in development-only code.

### Floating promises
- Pattern: calling an async function or a function returning a `Promise` without `await`, `.then()`, or `.catch()`.
- Example: `deleteOldRecords()` where `deleteOldRecords` is async.
- Why WARN: Unhandled rejections can crash the process or be silently lost. May be intentional for fire-and-forget operations, but should be explicitly marked (e.g., `void deleteOldRecords()`).
