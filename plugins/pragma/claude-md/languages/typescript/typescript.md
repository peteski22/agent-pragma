# TypeScript Language Rules

## Style

- Enable strict mode in tsconfig.json.
- Use double quotes for strings.
- No semicolons (unless required for disambiguation).
- Use Biome for formatting and linting.
- End single-line comments with a full stop.

## Project Structure

- Use Vite as the build tool.
- Use pnpm for package management.
- Organize components by feature in folders.
- Keep hooks in a dedicated hooks/ directory.
- Use file-based routing (TanStack Router).

## React Patterns

- Always use functional components with hooks.
- Never use class components.
- Use custom hooks with `use` prefix for reusable logic.
- Track dependency arrays properly in useEffect and useCallback.
- Use TanStack Query for server state management.

## Type Safety

- Prefer type unions (`string | null`) over `any`.
- Use generics for reusable components and hooks.
- Generate API client types from OpenAPI spec.
- Use Zod for runtime validation (forms, route params).

## Error Handling

- Handle API errors with proper status code checks.
- Redirect to login on 401/403 responses.
- Use error boundaries for component-level errors.
- Provide meaningful error messages to users.

## Testability

- Extract logic that depends on framework/external state into pure functions.
- When business logic depends on hooks or context, create a pure function that the hook calls.
- Prefer dependency injection over global state.

## Testing

- Use Vitest as the test framework.
- Use Testing Library for component tests.
- Mock external services with vi.mock().
- Use vi.clearAllMocks() in beforeEach.

## State Management

- Use TanStack Query for server state.
- Use React useState for local UI state.
- Avoid global state libraries unless necessary.
- Invalidate queries after mutations.

## Validation Commands

These are fallback defaults used by `/implement` and `/review` when no Makefile target or `CLAUDE.local.md` override exists.

- **Lint:** `make lint` (if Makefile with lint target exists) or `pnpm run lint`
- **Test:** `make test` (if Makefile with test target exists) or `pnpm run test`
