# Go Language Rules

## Core Philosophy

- Follow the Go Proverbs (https://go-proverbs.github.io/).
- Reference specific proverbs when making design decisions.
- Prefer functional and declarative approaches over imperative and mutating approaches.

## Key Proverbs to Enforce

- Don't communicate by sharing memory, share memory by communicating.
- Concurrency is not parallelism.
- The bigger the interface, the weaker the abstraction.
- Make the zero value useful.
- A little copying is better than a little dependency.
- Clear is better than clever.
- Errors are values.
- Don't just check errors, handle them gracefully.

## Go Version and Standard Library

- Write for the Go version in `go.mod`, not the version you remember. The standard library gains packages and functions every release.
- Before hand-writing something or adding a dependency, check what the standard library offers (`go doc <pkg>`, `go list std`) and read the release notes for any version newer than you know. Do not rely on recalled knowledge of what the standard library has.
- `go doc` reports the installed toolchain, which may be newer than `go.mod`. Use only what the `go.mod` version provides; raising that version is the user's decision.
  - Examples that recalled knowledge misses: the `uuid` package, `encoding/json/jsontext` (`Value.Canonicalize` gives RFC 8785 canonical JSON), `errors.AsType`, `strings.CutLast`, and the `ignore` directive in `go.mod`.
- Keep `go fix -diff ./...` clean (Go 1.26 or later). Its modernizers rewrite code to the current standard library idioms.
- Enable golangci-lint's `modernize` (golangci-lint v2.6.0 or later) and `usetesting` linters.

## Package Layout

- Every non-main package has a `doc.go` that holds the package comment, however small the package. No other file carries a package comment. External test packages (name ending `_test`) are exempt.
- Exported sentinel errors live in `errors.go`.

## Code Organization

- Top-level declarations in section order: package → imports → constants → variables → interfaces → types → functions/methods.
- init() functions appear after imports and before other declarations.
- Within each section, exported declarations come before unexported ones, and each group is in name order. A byte-order sort of the names gives this, since every uppercase letter sorts before every lowercase one. Functions and methods sort together by name. The one exception: constructors (NewX) may precede methods on the returned type.
- The same order applies to the names inside a const or var block. An iota sequence keeps the order its values depend on.
- Test files follow the same order, so Test, Benchmark, Fuzz and Example functions come before test helpers.
- Struct fields should be grouped logically (e.g., configuration fields together, state fields together, embedded types first).
- Always start with unexported types, functions, fields. Only export when necessary.
- Unexported structs should have unexported fields (unless required for serialization, reflection, or code generation).

## Function Design

- Prefer 4 parameters or fewer. More than 4 requires justification; use options pattern or config struct.
- Never group similar types in signatures: use `(urlStr string, registryName string)` not `(urlStr, registryName string)`.
- Use pointer types (*string, *bool) for optional configuration fields.
- Use value types for required fields.

## Naming

- No GetX() accessors; use X() for getters (e.g., user.GetName() → user.Name()). SetX() is acceptable for setters.
- Function names should not include package name as prefix (e.g., http.HTTPServer is wrong).
- Function names should not repeat receiver type context (e.g., userRepo.GetUser() → userRepo.User()).
- Prefer concise names when receiver provides context: repo.UserByID() over repo.GetUserByID(), hash.Compute() over hash.ComputeHashValue().
- `New` is idiomatic for constructors.

## Error Handling

- Use '%s' (not %q) in error format strings.
- Reference items by name/identifier in errors, not array indices.
- Use errors.Join for collecting multiple validation errors.

## Interface Design

- Prefer type assertion over expanding interfaces.
- Keep interfaces small and focused.

## Testability

- Extract logic that depends on framework/external state into pure functions.
- When validation depends on framework state (e.g., Cobra's `ArgsLenAtDash()`), create a wrapper that calls a testable pure function.
- Prefer dependency injection over global state.

## Comments

- Every declared identifier has a doc comment, exported or not: constants, variables, types, functions, methods, struct fields and interface methods. Each is a full sentence that starts with the identifier's name.
- For declarations this overrides the universal default of writing no comments. Inside function bodies the universal default still holds.
- Doc comments follow the universal docstring rules. Describe the unit's own intent and contract. Do not describe callers, other packages or tools (such as the build that sets a variable), design rationale, history, or a step-by-step account of the implementation.
- Use US English in identifiers and comments. A wire value keeps the spelling its spec fixes.
- When slice/array operations depend on prior validation, add a brief comment referencing the guarantee.
  - Example: `// args[1:] is safe: validateArgs guarantees len(args) >= 2`
- This documents safety invariants for readers and protects against refactoring mistakes.

## Testing

- Name test case variable 'tc' not 'tt'.
- Use t.Parallel() only in a test that waits on something (I/O, network, a sleep or timer). Do not add it to a quick test of pure computation: it saves no time there and adds noise to every test and table loop.
- Test code must read as test code, because a test file shares its package's namespace:
  - Prefix every top-level type, variable, constant and function in a `_test.go` file with `test`, `fake` or `mock`. Test, Benchmark, Fuzz, Example and TestMain functions are exempt. Local variables such as `tc` are not top-level and keep their usual names.
  - Every function in a test file that is not itself a test takes `*testing.T` and calls `t.Helper()` first. A helper shared with a benchmark or fuzz target takes `testing.TB` instead.
  - Test-only types have no methods; use functions. The exception is a method a fake or mock needs to satisfy an interface.
- Keep test helpers minimal. A helper must not contain logic that would itself need a test. Inline small conversions in the test, and prefer literal table cases to helpers that build values.
- Use t.TempDir() for any file a test writes.
- Use require from testify (not assert).
- Use testdata/ directories for static test fixtures that the package owns.
- Never reach out of a test's directory with a relative path (`../`). For data owned elsewhere in the repository, add a small package beside the data that embeds it with `//go:embed` and returns a copy, and import that package from the test.

## Pre-PR Checklist

Work through this list before asking for review:

1. Every non-main package has a `doc.go`, except external test packages.
2. Exported sentinel errors are in `errors.go`.
3. Every identifier has a doc comment that starts with its name.
4. Declarations are in section order, then exported before unexported, then by name.
5. Top-level test identifiers are prefixed, and test helpers take `*testing.T` (or `testing.TB`) and call `t.Helper()`.
6. Test helpers are minimal.
7. Test data is in `testdata/` or embedded; no relative paths out of a test's directory.
8. `go fix -diff ./...` prints nothing (Go 1.26 or later).
9. Every comment in the diff passes the docstring rules and uses US English.
10. Lint and tests pass (see Validation Commands).
11. The validators pass.

## Validation Commands

These are fallback defaults used by `/implement` and `/review` when no Makefile target or `CLAUDE.local.md` override exists.

- **Lint:** `make lint` (if Makefile with lint target exists) or `golangci-lint run --fix -v`, then `go fix -diff ./...` (Go 1.26 or later)
- **Test:** `make test` (if Makefile with test target exists) or `go test ./...`
