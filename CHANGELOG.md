# Changelog

## [0.1.2] - 2026-03-15

### Fixed
- `on_text()` streaming callback for chain_step entries
- Thread-safety improvements in `AutopsyLangChainHandler`
- CLI `--version` flag now shows correct version

### Changed
- Terminology: "legally defensible" -> "cryptographically verifiable" in footer

## [0.1.0] - 2026-03-05

### Added
- `Autopsy` context manager for minimal-config error tracing
- `AutopsyLangChainHandler` for automatic LangChain event capture
- CLI tool (`autopsy view`) with terminal tree rendering and ANSI colors
- JSON trace file format with timestamps, durations, and error details
- Thread-safe trace capture
