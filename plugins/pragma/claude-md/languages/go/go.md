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

## Code Organization

- Top-level declarations in section order: package → imports → constants → variables → interfaces → types → functions/methods.
- init() functions appear after imports and before other declarations.
- Within each section, top-level declarations should be in alphabetical order, except that constructors (NewX) may precede methods on the returned type.
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

- When slice/array operations depend on prior validation, add a brief comment referencing the guarantee.
  - Example: `// args[1:] is safe: validateArgs guarantees len(args) >= 2`
- This documents safety invariants for readers and protects against refactoring mistakes.

## Testing

- Name test case variable 'tc' not 'tt'.
- Use t.Parallel(), t.Helper(), t.TempDir() where possible.
- Use require from testify (not assert).
- Use testdata/ directories for static test fixtures.

## Validation Commands

These are fallback defaults used by `/implement` and `/review` when no Makefile target or `CLAUDE.local.md` override exists.

- **Lint:** `make lint` (if Makefile with lint target exists) or `golangci-lint run --fix -v`
- **Test:** `make test` (if Makefile with test target exists) or `go test ./...`
