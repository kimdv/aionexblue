# AGENTS.md — aionexblue

## Purpose

Standalone async Python library for the NexBlue EV charger cloud API.
This is the only runtime dependency of the `nexblue` Home Assistant custom integration
([github.com/kimdv/nexblue-integration](https://github.com/kimdv/nexblue-integration)).

## Package

- **PyPI name**: `aionexblue`
- **Python namespace**: `aionexblue`

## API

- **Server URL**: `https://api.nexblue.com/third_party` (from the OpenAPI `servers` block)
- **Path prefix**: all endpoint paths start with `/openapi/…`
- **Machine-readable schema**: <https://prod-management.nexblue.com/swagger/dist/openapi_gen.json>

### Auth constraints

- Always use `account_type: 0` (end_user). Installer and OAuth2 enterprise flows are out of scope.
- The refresh endpoint returns only a new `access_token`; the `refresh_token` does not rotate. (See `AccountRefreshTokenRes` vs `OAuthTokenRes` in the schema.)

## Scope boundary

Implement only the individual-account API surface documented in the OpenAPI.
OAuth2 enterprise endpoints are intentionally excluded from the first release.

## Design rules

- All I/O is `async` (`aiohttp`). Callers supply the `ClientSession`.
- Never log credentials. Use `DEBUG` for HTTP detail, `WARNING` for unexpected
  API responses. Raise exceptions instead of logging errors.
- Typed throughout — all public functions have full type annotations.
  `mypy --strict` must pass.
- No business logic beyond what the API requires. The HA coordinator owns
  polling, caching, and retry policy.

## Key files

| File | Responsibility |
|---|---|
| `auth.py` | `login()` and `refresh()` — returns `NexBlueTokens` |
| `client.py` | `NexBlueClient` with all API endpoint methods |
| `models.py` | Dataclasses and enums for OpenAPI request/response schemas |
| `exceptions.py` | `NexBlueError` hierarchy |

## Testing

- `pytest` + `aioresponses`; target ≥ 90 % coverage.
- Fixtures live in `tests/fixtures/` as JSON stubs from the OpenAPI spec.

## CI

- `ruff check`, `mypy --strict`, `pytest` on every push/PR.
- PyPI publish on `v*` tag via GitHub Actions.

## Related repos

- **HA integration**: [github.com/kimdv/nexblue-integration](https://github.com/kimdv/nexblue-integration) — do not modify HA code from this repo.
