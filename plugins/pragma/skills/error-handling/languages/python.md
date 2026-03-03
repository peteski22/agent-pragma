# Python Error Handling Patterns

## HARD violations (must fix)

### Bare except
- Pattern: `except:` with no exception type.
- Example: `except:` catches `KeyboardInterrupt`, `SystemExit`, and every other exception.
- Why HARD: Catches everything including signals that should propagate. Always specify an exception type.

### Empty except blocks
- Pattern: `except SomeError: pass` or `except SomeError: ...`.
- Example: `except ValueError: pass`.
- Why HARD: Silently swallows the error. The caller has no way to know the operation failed.

### Broad except Exception without re-raise
- Pattern: `except Exception:` (or `except BaseException:`) where the body does not re-raise.
- Example: `except Exception: return None`.
- Why HARD: Catches far too broadly and swallows the error. Either narrow the exception type or re-raise.
- Note: `except Exception: return None` also matches the SHOULD "silent fallback" rule below, but per the intra-rule precedence clause this location is reported only as HARD.

## SHOULD violations (fix or justify)

### Silent fallback returns
- Pattern: `except SomeError: return None` (or any default value) without logging.
- Note: if the except block logs before returning the default, this downgrades to WARN.
- Justification: acceptable in lookup-style functions where `None` is a documented "not found" return.

## WARN (advisory)

### Log-only handling
- Pattern: `except SomeError as e: logger.error(e)` with no raise, return, or other control flow.
- Why WARN: Logging is better than ignoring, but the caller still has no signal. May be intentional in background tasks.
