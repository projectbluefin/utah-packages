---
name: test-coverage
description: >-
  Measure tool coverage including Python subprocesses and maintain the CI floor.
metadata:
  type: procedure
---

# Tool coverage

The unit-test job in `.github/workflows/validate.yml` measures `tools/`, emits
terminal and XML reports, and enforces an 80% floor. This is a baseline, not a
target: raise it deliberately as tests improve, rather than lowering it to
accommodate regressions. The XML report is uploaded even if the test step fails.

Many suites invoke tools with `sys.executable` from temporary directories.
Parent-process instrumentation alone misses those executions. With the pinned
pytest-cov and coverage versions, set both `COVERAGE_PROCESS_START` (the absolute
configuration path, enabling coverage's child-process startup hook) and
`COVERAGE_FILE` (an absolute workspace path, preserving data after temporary
directories disappear). The generated configuration enables parallel data files
and includes `*/tools/*.py` in children; pytest-cov selects repository `tools/`
in the parent and combines the child data into its report. A child `source =
tools` would select only the original directory when a copied script runs from
the repository working directory, silently excluding that copy.
The `[paths]` mapping credits copies under `/tmp/*/tools` to the corresponding
repository source files. Several guard suites copy scripts into temporary trees
because the scripts locate fixture workflows relative to their own location;
without remapping, their failure-path executions are missing from the real files.
Keep this mapping aligned with the temporary paths used by the Ubuntu runner.

When updating either dependency, reproduce the CI invocation and inspect the
entries for `validate.py`, `check_workflow_quoting.py`, and
`check_build_container_pinning.py`. The latter two must not report zero coverage
when their subprocess suites pass. Check the XML report as well as the total;
a green total alone does not prove child instrumentation worked.

Keep configuration generation in its own workflow step. The gate catalog in
`tests/test_gate_catalog.py` recognises blocks consisting of Python gate commands;
a mixed `printf`/pytest block is not recognised in the validation workflow.
Retain `python3 -m pytest tests` so it normalises to the Justfile's `unit-tests`
gate, even with coverage options.
