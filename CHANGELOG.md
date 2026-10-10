## [0.10.1] - 2026-10-09

### Added

- `Templater`

### Deprecated

- HTMLBase

## [0.10.0] - 2026-10-08

### Added

- `Config.from_toml` / `from_yaml` / `from_json` (and `aio*` variants) accept
  an `overrides` dict for layering env vars, CLI args, or tests on top of
  the loaded file. Precedence: defaults < file < overrides.
- `Daemon` and `AsyncDaemon` accept `stop_timeout` (default 10s). `stop()`
  now waits that long for a graceful exit before forcing termination.
- `Daemon` and `AsyncDaemon` are restartable — `start()` after `stop()`
  works on the same instance.
- `Daemon.is_running()` and `AsyncDaemon.is_running()`.
- `Emailer` supports `chunk`, `max_retries`, `timeout`, `max_queue_size`,
  and `drain_timeout` parameters.
- `Emailer.stop()` drains pending mail with a deadline.
- `AsyncDaemon` module documentation.

### Changed

- `Emailer` `Bcc` is now set only on the SMTP envelope, never as a header.
  Fixes Bcc leaks to To/Cc recipients.
- `Emailer` queue items are frozen slotted `Email` dataclasses instead of
  dicts. `_queue` internals changed shape.
- `Emailer` requires a `to` recipient, and validates all addresses at
  enqueue time (from, to, cc, bcc, reply-to).
- `Config._resolve_path` no longer rejects `..` in filepath strings. Path
  containment is the caller's responsibility; see the module docstring.
- `Config.get()` no longer overrides `dict.get()` to raise
  `ConfigValidationError` on non-str keys. `TypeError` from `dict` propagates.
- `Config.deep_copy()` uses `copy.deepcopy` and preserves `datetime`,
  `date`, and `time` values.
- `Config.sha1` now warns via `warnings.warn(DeprecationWarning)` instead
  of `logging.warning`.
- `Daemon.on_process` and `AsyncDaemon.on_process` accept `**kwargs`.

### Fixed

- `Daemon` and `AsyncDaemon` no longer kill their loop on the first
  exception raised inside `on_process` or a callback. Errors are logged
  with a traceback and the loop continues.
- `Daemon.stop()` and `AsyncDaemon.stop()` wait independently of `interval`.
  Previously `stop()` blocked for `max(5, interval * 2)` seconds.
- `AsyncDaemon.stop()` no longer force-cancels mid-iteration. It signals,
  waits, then cancels only if the timeout expires.
- `Config` atomic writes use a temp file in the target directory and
  `os.fsync` before `os.replace`. Concurrent writers no longer fight over
  a single `.tmp` name.
- `Config.from_toml` / `from_yaml` / `from_json` no longer block the event
  loop in async paths (removed the synchronous `exists()` / `is_file()`
  checks).
