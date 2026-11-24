# Changelog

## 2.0.0

This release is fully backward compatible with 1.x. Existing client code
keeps working without any changes; the major version bump reflects the size
of the internal cleanup, not a breaking change.

### Added
- `format_price` now accepts `Decimal` values and numeric strings.
- `parse_record` has an optional `strict` flag that rejects non-positive
  quantities.

### Changed
- Parameter naming unified across the pricing helpers.
- Record fields aligned with catalog terminology.
- `invoice_total` defaults aligned with accounting requirements.
- Exception hierarchy clarified.
- Internal cents conversion helper refactored.

## 1.4.0

- Added `shipping_cost`.
- `normalize_priority` accepts surrounding whitespace.
