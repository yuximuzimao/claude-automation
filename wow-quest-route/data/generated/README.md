# Generated Route Lifecycle artifacts

Everything under route-lifecycle/ is a disposable derived product.

Do not edit any JSON there by hand. If a generated result is wrong, fix the authoritative Task Card,
Route Profile, rule/model input, Observation, or the owning algorithm, then rerun the exact owner
chain required by docs/verified-routes/ROUTE-DESIGN-PROCESS.md.

Downstream code must read/write these artifacts only through lib/generated_artifacts.py. That store
records the registered owner and SHA-256 for every artifact and rejects direct/manual edits on the
next read.

The manifest and artifacts may be versioned for reproducible current-page assembly, but version
control does not make them business truth.
