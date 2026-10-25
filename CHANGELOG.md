# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CodeQL code scanning workflow and Dependabot configuration (pip, Docker, GitHub Actions).
- API reference and terminal screenshots in the README.
- Roadmap tracked as GitHub issues under the `v0.2.0` milestone.

### Changed

- CI workflow runs with a read-only `GITHUB_TOKEN` by default.

## [0.1.0] - 2026-10-25

First public release.

### Added

- Catalogue with nested categories, product variants, images and per-variant inventory; filtering, search and ordering.
- Guest carts via `X-Cart-Token`, user carts via JWT, and a merge endpoint after login.
- Single-transaction checkout with `select_for_update` inventory locks in PK order, stock reservations with a TTL, coupons, zone-based courier fees and VAT.
- Order state machine with an audit row per transition.
- Payment intents and signature-verified, idempotent webhooks for bKash and SSLCommerz (sandbox adapters); cash on delivery confirmed at checkout.
- Courier rate calculators by zone, weight and COD fee.
- Coupons (percentage with cap, fixed, free shipping) with limits and usage reverted on cancellation or expiry.
- Reviews with verified-purchase flag and rating aggregate.
- `release_expired_reservations` and `seed_demo` management commands.
- JWT auth, JSON error envelope, OpenAPI schema, admin, `/health/`, Docker image, docker compose with PostgreSQL, CI on Python 3.10/3.11, Pages API reference, Codespaces and Render kits.

### Fixed

- Platform hostnames and proxy TLS are accepted on managed hosting.

[Unreleased]: https://github.com/AkibUllah/ecommerce-api/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AkibUllah/ecommerce-api/releases/tag/v0.1.0
