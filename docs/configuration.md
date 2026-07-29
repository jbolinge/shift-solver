# Configuration Reference

This document describes every field in a shift-solver YAML config file:
`solver`, `schedule`, `shift_types`, `constraints`, and `logging`. It is
written against the code in `src/shift_solver/` as of this writing --
when in doubt, the source (`config/schema.py`,
`solver/constraint_registry.py`, and each file under `constraints/`) is
the ground truth.

The top-level config, and every nested config model, rejects unknown
keys (Pydantic `extra="forbid"`). A typo in a field name (e.g.
`enalbed: true`) is a validation error at load time, not a silently
ignored setting.

```yaml
solver: { ... }        # optional -- see "Solver settings"
schedule: { ... }       # optional -- see "Schedule settings"
constraints: { ... }    # optional -- per-constraint overrides, see "Constraints"
shift_types: [ ... ]    # required -- at least one shift type
logging: { ... }        # optional -- see "Logging"
```

## Solver settings (`solver`)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `max_time_seconds` | int > 0 | 3600 | CP-SAT wall-clock time limit for a full solve. |
| `num_workers` | int >= 1 | 8 | Parallel CP-SAT search workers (threads), not scheduling workers. |
| `quick_solution_seconds` | int > 0 | 60 | Time limit used by callers that want a fast/approximate solve (e.g. `--quick-solve`). |
| `save_interval_seconds` | int > 0 | 300 | Reserved for periodic checkpointing; not currently read by the CLI `generate` command. |

## Schedule settings (`schedule`)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `period_type` | str | `"week"` | The CLI's `generate` command currently only implements *weekly* period computation and explicitly rejects any config whose `period_type` isn't `"week"` (a `ClickException` at run time, not a schema validation error -- the schema itself accepts any string here). The underlying `ShiftSolver` engine is actually period-length agnostic (see "Period-granular scheduling model" below); day- or month-granularity scheduling is only reachable today by constructing `period_dates` and calling `ShiftSolver` directly, not through the shipped CLI. |
| `num_periods` | int >= 1 or null | null | Not currently consumed by the CLI's date-range-based period calculation. |
| `date_format` | `iso`\|`us`\|`eu`\|`auto` | `auto` | Date parsing mode used by CSV import (`auto` tries all formats and warns on ambiguity). |

## Shift types (`shift_types`)

Each entry defines a `ShiftType`:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | str (non-empty) | required | Unique identifier referenced by constraints, requests, and worker restrictions. |
| `name` | str (non-empty) | required | Human-readable display name. |
| `category` | str | required | Grouping label used by `fairness`, `sequence`, and `shift_order_preference` category filters (e.g. `"day"`, `"night"`, `"weekend"`). |
| `start_time` / `end_time` | `HH:MM` string | required | Nominal shift times. An overnight shift (e.g. 23:00-07:00) is expressed with `end_time` earlier than `start_time`; the shift is understood to wrap past midnight. |
| `duration_hours` | float, 0 < x <= 24 | required | **Must exactly match** the `start_time`/`end_time` span (through midnight for overnight shifts), within a `1e-6` tolerance. A mismatch is a config validation error at load time -- this catches copy/paste errors like changing `end_time` without updating `duration_hours`. |
| `is_undesirable` | bool | `false` | Default bucket the `fairness` constraint balances when its `categories` parameter is not set. |
| `workers_required` | int >= 1 | 1 | Exact headcount the `coverage` constraint enforces for this shift type, per period. |
| `required_attributes` | dict[str, str] | `{}` | Worker `attributes` key/value pairs required to work this shift (see the `skills` constraint). Empty = unconstrained. Matching is **string-exact**: YAML values are coerced to strings at load (`level: 3` becomes `"3"`, booleans become `"true"`/`"false"`) so they can match CSV-loaded worker attributes, which are always strings. |
| `applicable_days` | list[int] (0=Mon..6=Sun) or null | null | Restricts which days of the week a shift applies to within a period (see `coverage`). `null` = every day. |

The config's `validate_constraint_filter_references` check also cross-checks
that every `categories`/`shift_types` filter used under `constraints.*.parameters`
(see below) actually names a `category`/`id` declared here -- a stale or
typo'd filter value is rejected at load time rather than silently matching
nothing.

## Constraints (`constraints`)

### The enabled / is_hard / weight / parameters model

Each entry under `constraints.<id>` is optional and every field within it
is optional:

```yaml
constraints:
  fairness:
    enabled: true        # optional -- omit to inherit the registry default
    is_hard: false        # optional -- omit to inherit the registry default
    weight: 1000          # optional -- omit to inherit the registry default
    parameters:           # optional -- constraint-specific settings
      categories: ["night", "weekend"]
```

`enabled`, `is_hard`, and `weight` default to `None` (unset) in the config
schema, which means **"inherit whatever `ConstraintRegistry` registered as
the default for this constraint id."** The registry
(`src/shift_solver/solver/constraint_registry.py`) is the single source of
truth for defaults -- the tables below list them. Call
`ShiftSolverConfig.get_constraint_config(constraint_id)` to get a fully
resolved `ConstraintConfig` (every field filled in); the raw
`config.constraints[id]` may have some fields left as `None`.

`parameters` is **not** deep-merged with the registry default: if you set
`parameters:` at all (any non-empty dict), it replaces the default
parameters dict wholesale. In practice this rarely matters because each
constraint reads individual keys with its own hardcoded Python-level
fallback (e.g. `config.get_param("max_periods_between", 4)`), so omitting
a key you don't care about still gets that key's sane in-code default --
it just isn't sourced from the registry's `default_config.parameters`.

Unknown constraint ids (anything `ConstraintRegistry` doesn't know about)
are rejected at config-load time, as is any `parameters` key not
recognized by that constraint's typed parameter model (see
`CONSTRAINT_PARAMETER_MODELS` in `config/schema.py`) -- both catch typos
that would otherwise be silently ignored by the solver.

### `is_hard` only matters for constraints registered as soft

Constraints are registered with `ConstraintRegistry.register_hard` or
`.register_soft`, and this registration -- not the `is_hard` config field
-- determines whether a constraint is applied as a hard OR-Tools
constraint or contributes to the weighted objective:

- **Hard-registered constraints** (`coverage`, `restriction`,
  `availability`, `worker_shift_limit`, `skills`) are always enforced as
  hard constraints whenever `enabled: true` -- they have no soft mode, and
  `ShiftSolver._apply_hard_constraints` only checks `enabled`. Setting
  `is_hard: false` on one of these is **rejected at config load** with a
  validation error (it would otherwise be silently ignored). If an older
  config sets `is_hard: false` on one of these ids, remove the line -- to
  make the rule optional, disable the constraint (`enabled: false`)
  instead.
- **Soft-registered constraints** (`fairness`, `frequency`, `request`,
  `sequence`, `max_absence`, `shift_frequency`, `shift_order_preference`,
  `workload`) normally contribute a weighted penalty to the objective.
  Setting `is_hard: true` on one of these promotes it to a hard
  requirement for that deployment: `ShiftSolver._enforce_hard_mode` adds
  `model.add(v == 0)` for every one of the constraint's violation
  variables whose registered type is `"violation"` or
  `"objective_target"` (`"auxiliary"` helper variables, e.g. fairness's
  max/min intermediates, are left alone since they aren't themselves a
  violation).
  - `request` and `shift_frequency` set the class attribute
    `handles_hard_mode = True` and implement their own hard/soft branching
    directly in `apply()` (see "Requests" and "shift_frequency" below), so
    the generic zero-forcing pass is skipped for them -- it would be
    redundant (or, for `request`, actively wrong, since positive/negative
    requests have different hard semantics that the generic mechanism
    doesn't know about).
  - All other soft-registered constraints use the generic mechanism.

### Constraint reference table

"Registered" = hard (always enforced, `is_hard` config field ignored) or
soft (contributes to the objective unless promoted via `is_hard: true`).

| id | registered | enabled (default) | is_hard (default) | weight (default) |
|---|---|---|---|---|
| `coverage` | hard | `true` | `true` (ignored) | n/a |
| `restriction` | hard | `true` | `true` (ignored) | n/a |
| `availability` | hard | `true` | `true` (ignored) | n/a |
| `worker_shift_limit` | hard | `true` | `true` (ignored) | n/a |
| `skills` | hard | `true` | `true` (ignored) | n/a |
| `fairness` | soft | `true` | `false` | `1000` |
| `frequency` | soft | `false` | `false` | `100` |
| `request` | soft | `true` | `false` | `150` |
| `sequence` | soft | `false` | `false` | `100` |
| `max_absence` | soft | `false` | `false` | `100` |
| `shift_frequency` | soft | `false` | `false` | `500` |
| `shift_order_preference` | soft | `false` | `false` | `200` |
| `workload` | soft | `false` | `false` | `100` |

#### `coverage` (hard)

Ensures each shift type has exactly `workers_required` workers assigned,
per period. Honors `applicable_days` on the shift type: for a period with
zero applicable days, the required headcount is forced to 0 for that
shift instead of erroring.

No parameters.

#### `restriction` (hard)

Forces `assignment == 0` for every (worker, period) where the shift type
is in that worker's `restricted_shifts`. References to shift type ids
that don't exist in `shift_types` are silently skipped (not an error).

No parameters.

#### `availability` (hard)

Blocks assignment during a worker's `unavailable` `Availability` records
(`preferred`/`required` availability types are not enforced by this
constraint). If the availability record has `shift_type_id` set, only
that shift is blocked in the overlapping periods; otherwise all shift
types are blocked.

No parameters.

#### `worker_shift_limit` (hard)

Caps how many shift assignments a single worker may hold within one
period (across all shift types combined). Without this constraint
nothing stops one worker from being assigned the day, evening, *and*
night shift in the same period.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `max_shifts_per_period` | int >= 1 | 1 | Maximum simultaneous shift assignments per worker per period. The default of 1 makes shifts mutually exclusive. |

#### `skills` (hard)

For every shift type with a non-empty `required_attributes`, forces
`assignment == 0` for any worker whose `Worker.attributes` don't satisfy
every required key/value pair (exact equality per key; a shift type with
`required_attributes: {}` is unconstrained). `Worker.attributes` is
populated from the CSV worker loader's optional `attributes` column (see
"`workers.csv` columns" below), or can be set programmatically.

No parameters.

#### `fairness` (soft)

Minimizes the spread (max - min) of "undesirable" shift assignments
across workers, using the constraint's own `spread` variable as the
objective term (registered type `"objective_target"`).

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `categories` | list[str] or null | null | If set, count shifts in these categories as "undesirable" for this constraint, instead of using each shift type's `is_undesirable` flag. |

No-op with fewer than 2 workers, or if no shift types qualify as
undesirable.

#### `frequency` (soft)

For every worker and every sliding window of `max_periods_between`
consecutive periods, penalizes the worker having zero assignments (across
the filtered shift types) anywhere in that window. See "Sliding-window
semantics" below.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `max_periods_between` | int >= 1 | 4 | Window size in periods; every window of this many consecutive periods must contain at least one qualifying assignment. |
| `shift_types` | list[str] or null | null | If set, only count assignments to these shift type ids. `null` = count all shift types. |

If `max_periods_between` exceeds the number of periods in the schedule,
the constraint has no effect (logged as a warning).

#### `request` (soft, `handles_hard_mode = True`)

Honors `SchedulingRequest` records (from CSV or programmatically). No
constraint-level parameters -- each request carries its own
`worker_id`/`shift_type_id`/date range/`priority`/optional per-record
`is_hard` override (`SchedulingRequest.is_hard`; `None` falls back to this
constraint's own `is_hard` config value).

See "Positive vs. negative requests" below for the asymmetric semantics.

#### `sequence` (soft)

Penalizes a worker being assigned the same shift category in two
consecutive periods (e.g. discouraging back-to-back night shifts).

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `categories` | list[str] or null | null | If set, only apply to these categories. `null` = all categories. |

No-op with fewer than 2 periods in the schedule.

#### `max_absence` (soft)

Same sliding-window mechanics as `frequency` (see "Sliding-window
semantics"), under a separate parameter name so the two can be tuned
independently (e.g. a tight `frequency` window for a specific
high-priority shift type alongside a looser overall `max_absence`
window).

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `max_periods_absent` | int >= 1 | 8 | Window size in periods. |
| `shift_types` | list[str] or null | null | If set, only count assignments to these shift type ids. `null` = all shift types. |

#### `shift_frequency` (soft, `handles_hard_mode = True`)

Per-worker requirements: a named worker must work at least one of a
specific *set* of shift types within every sliding window of N periods
(unlike `frequency`, which applies the same rule to every worker for
individually-tracked shift types). Useful for "must work at least one of
[site_a_day, site_a_night] every 4 weeks"-style rules that differ by
worker.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `requirements` | list of `{worker_id, shift_types, max_periods_between}` | `[]` | One entry per per-worker requirement. `shift_types` is a non-empty list of shift type ids (any one satisfies the window); `max_periods_between` (int > 0) is that requirement's window size. |

This constraint's own `is_hard` config value (not a per-requirement
field) controls all requirements uniformly: when `is_hard: true`, each
window is enforced with `sum(window_assignments) >= 1` directly (or, if
no valid assignment variables exist for a window at all -- e.g. every
matching shift type is restricted for that worker -- the model is made
infeasible); when `is_hard: false` (default), each window instead gets a
soft violation variable.

If a requirement's window is larger than the schedule, it's clamped to
the full horizon (unlike `frequency`/`max_absence`, which instead disable
themselves with a warning).

#### `shift_order_preference` (soft)

Encourages a preferred shift/category in the period adjacent to a
triggering condition (a specific shift type, a category, or the worker
being unavailable).

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `rules` | list of rule objects | `[]` | See fields below. |

Each rule:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `rule_id` | str (non-empty) | required | Identifier, also used to name generated solver variables. |
| `trigger_type` | `shift_type`\|`category`\|`unavailability` | required | What activates the rule. |
| `trigger_value` | str or null | required unless `trigger_type` is `unavailability` | Shift type id or category name. |
| `direction` | `after`\|`before` | required | `after`: prefer the target shift in the period *following* the trigger. `before`: prefer it in the period *preceding* the trigger. |
| `preferred_type` | `shift_type`\|`category` | required | Type of the preferred target. |
| `preferred_value` | str (non-empty) | required | Shift type id or category name preferred. |
| `priority` | int >= 1 | 1 | Multiplier applied to this constraint's `weight` for this rule's violation term. |
| `worker_ids` | list[str] or null | null | If set, only apply this rule to these workers. `null` = all workers. |

A rule referencing a trigger/preferred shift type or category that
doesn't exist in `shift_types` is silently skipped.

#### `workload` (soft)

Bounds each worker's total shift count over the *entire* scheduling
horizon (not per-period), using the `shift_counts` variables the solver
already builds.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `min_total_shifts` | int >= 0 | 0 | Minimum shifts a worker should be assigned across the whole horizon. `0` disables the shortfall penalty entirely. |
| `max_total_shifts` | int >= 1 or null | null | Maximum shifts a worker should be assigned across the whole horizon. `null` disables the excess penalty entirely (unbounded). |

Config validation rejects `min_total_shifts > max_total_shifts` when both
are set. In hard mode (`is_hard: true`), both the shortfall and excess
violation amounts are forced to 0, which pins every worker's total into
`[min_total_shifts, max_total_shifts]` exactly.

## Sliding-window semantics (`frequency`, `max_absence`, `shift_frequency`)

All three "must work at least once every N periods" constraints use the
same convention: **a window is N consecutive periods, and every such
window must contain at least one qualifying assignment.** Concretely,
`max_periods_between: 4` (or `max_periods_absent: 4`) means:

- window size = 4 periods (`window_size = N`, *not* `N + 1`)
- for a schedule of `num_periods` periods, windows start at period index
  `0, 1, ..., num_periods - window_size` (i.e. `num_periods - window_size
  + 1` windows total)
- each window independently gets its own violation variable (or hard
  constraint), so a worker can rack up multiple violations across
  overlapping windows if they go without an assignment for a long stretch

If `window_size > num_periods`, `frequency` and `max_absence` disable
themselves for that run (logged as a warning) since no window fits;
`shift_frequency` instead clamps the window down to the full horizon.

## Period-granular scheduling model

The solver's only decision variable is a boolean "assignment" per
(worker, period, shift type) -- there is no per-day variable within a
period. Practical consequences:

- **One assignment covers the entire period**, however long that period
  is. With the CLI's current weekly periods, a worker assigned the
  `"day"` shift type for period 3 has that single assignment represent
  the *whole week*, not "the day shift on one day of that week." Getting
  actual day-by-day assignment requires each period to be one calendar
  day (i.e. a `period_dates` list with one day per period) -- today that
  means calling `ShiftSolver` directly with daily `period_dates`, since
  the shipped `generate` CLI command only builds weekly periods (see the
  `schedule.period_type` note above).
- **`ShiftInstance.date` is always the period's start date** --
  `SolutionExtractor` stamps every generated shift instance with
  `period_start`, never a per-day date within a multi-day period.
- **Not expressible at this granularity**: minimum rest time between
  shifts, maximum consecutive calendar days worked, and maximum hours
  worked per week are all *sub-period* concepts and cannot be enforced by
  any constraint in this library when `period_type` is `"week"` or
  `"month"`. The closest analogues available are: `worker_shift_limit`
  (caps simultaneous shift types *within* one period, not across periods),
  `sequence` (discourages the same shift *category* in two *consecutive
  periods*, which only approximates "no back-to-back shifts" at
  week/month granularity), and `workload`/`shift_counts` (whole-horizon
  totals). If you need true rest-hours/consecutive-days/hours-per-week
  enforcement, drive `ShiftSolver` with daily `period_dates` directly
  (bypassing the CLI's weekly-only `generate` command) and express the
  rule via `sequence` (categories) and `worker_shift_limit` at day
  granularity instead.

## Positive vs. negative requests

`SchedulingRequest.request_type` is `"positive"` (worker wants to work) or
`"negative"` (worker wants to avoid). The `request` constraint applies
different semantics to each, over however many periods the request's date
range overlaps:

- **Positive**: "at least once in range" -- satisfied if the worker is
  assigned the requested shift type in *any one* of the overlapping
  periods. Hard: `sum(assignment_vars over the range) >= 1`. Soft: a
  single violation variable is true iff the worker was assigned in
  *none* of them.
- **Negative**: per-period -- the worker must (hard) or should (soft)
  avoid the shift type in *every* overlapping period individually. Hard:
  `assignment == 0` for each period. Soft: one violation variable per
  period, true iff assigned that period.

A request whose `worker_id`/`shift_type_id` doesn't match a known worker
or shift type is skipped with a logged warning, not an error.

## Objective model

`ObjectiveBuilder` sums, over every enabled soft-registered constraint (in
effectively-soft mode) and every one of its violation variables:

```
objective = sum(violation_var * weight * priority_multiplier)
```

- `weight` is the constraint's configured (or registry-default) weight.
- `priority_multiplier` defaults to 1; `request` and
  `shift_order_preference` set it per-violation from the record's
  `priority` field.
- Variables registered as `"auxiliary"` (helper/intermediate variables,
  e.g. fairness's per-worker max/min, or the `*_total_violations` debug
  counters several constraints expose) never enter the objective --
  they'd otherwise double-count a penalty already captured by other
  terms.
- Variables registered as `"objective_target"` (currently only
  fairness's `spread`) enter the objective directly at `weight * 1`
  (`priority_multiplier` is always 1 for these).

**There is no normalization.** A `weight: 1000` fairness spread and a
`weight: 100` frequency violation are not "10x as important" in any
principled sense -- they're simply multiplied into the same linear sum,
and each constraint can contribute a wildly different number of terms
(fairness contributes exactly one `spread` term total; `frequency`
contributes one term per worker per sliding window, which scales with
both worker count and schedule length). Weights are only safely
comparable across constraints that produce a similar number/shape of
terms; when tuning, look at `ObjectiveBuilder.get_total_weight_by_constraint()`
(or a solved schedule's objective breakdown) to see actual relative
contribution rather than assuming raw weight values are comparable.

## `workers.csv` columns

Loaded by `CSVLoader.load_workers` (used by `generate --workers <file.csv>`
and `import-data`).

| Column | Required | Format | Meaning |
|---|---|---|---|
| `id` | yes | non-empty string | Unique worker id, referenced by `restricted_shifts`, `preferred_shifts`, availability/request CSVs, and `attributes`-driven `required_attributes` matching. |
| `name` | yes | non-empty string | Display name. |
| `worker_type` | no | string | Free-form classification (e.g. `full_time`, `part_time`). Not read by any built-in constraint. |
| `restricted_shifts` | no | comma-separated shift type ids | Shift types this worker may never be assigned (see `restriction`). |
| `preferred_shifts` | no | comma-separated shift type ids | Shift types this worker prefers. |
| `attributes` | no | semicolon-separated `key=value` pairs | Populates `Worker.attributes` for the `skills` constraint's `required_attributes` matching. Whitespace around `;`/`=`/keys/values is stripped. A malformed entry (missing `=`, or an empty key) raises a `CSVLoaderError` naming the row and expected format. |

Example pairing a shift type's `required_attributes` with a worker's
`attributes` column so only qualified workers can be assigned:

```yaml
# config.yaml
shift_types:
  - id: icu_shift
    name: ICU Shift
    category: day
    start_time: "07:00"
    end_time: "15:00"
    duration_hours: 8.0
    workers_required: 1
    required_attributes:
      certification: icu
```

```csv
# workers.csv
id,name,attributes
W001,Alice Smith,certification=icu;seniority=senior
W002,Bob Jones,
```

Here `W002` has no matching `certification` attribute, so the `skills`
constraint (hard, enabled by default) forces their assignment variable to
0 for `icu_shift` in every period -- only `W001` is eligible.

## See also

- `config/config.yaml` -- annotated reference config; as of this writing
  it shows every constraint except `skills`, `shift_frequency`, and
  `workload` (which have no shipped example block, commented or
  otherwise).
- `config/examples/*.yaml`, `examples/*/config.yaml` -- worked
  industry-specific configs paired with sample worker/availability/request
  CSVs under `examples/*/`.
- `src/shift_solver/io/sample_generator/` -- generates CSV/Excel sample
  data whose shift type ids/categories are kept in sync with
  `config/examples/{retail,healthcare,warehouse}.yaml` (see that module's
  `presets.py`); `shift_types.csv` in its output is informational only
  (no loader reads it back -- shift types always come from a YAML config).
