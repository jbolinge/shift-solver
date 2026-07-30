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
| `period_type` | `"day"`\|`"week"` | `"week"` | Validated at load time; any other value is a schema error. `"week"` chunks the schedule into 7-day periods. `"day"` gives each calendar day its own period -- required for the day-granular constraints (`min_rest`, `weekend`, and per-day semantics of `max_consecutive`/`consecutive_shift_type`) to be meaningful. |
| `num_periods` | int >= 1 or null | null | Alternative to `generate --end-date`: when set and `--end-date` is omitted, the horizon is `num_periods` whole periods starting at `--start-date`. An explicit `--end-date` always wins. |
| `date_format` | `iso`\|`us`\|`eu`\|`auto` | `auto` | Date parsing mode used by CSV/Excel import (`auto` tries all formats and warns on ambiguity). |

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
| `pinned` | hard | `false` | `true` (ignored) | n/a |
| `min_rest` | soft | `false` | `true` | `1000` |
| `max_consecutive` | soft | `false` | `true` | `100` |
| `shift_succession` | soft | `false` | `false` | `100` |
| `consecutive_shift_type` | soft | `false` | `true` | `100` |
| `weekend` | soft | `false` | `false` | `150` |
| `preference` | soft | `false` | `false` | `100` |
| `worker_pairing` | soft | `false` | `false` | `200` |

All constraints added in the commercial-parity expansion (`pinned` and
below) ship **disabled by default**: enabling a new rule by default would
silently change the schedules an existing config produces. Turn each on
explicitly with `enabled: true`.

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
period. Without this constraint nothing stops one worker from being
assigned the day, evening, *and* night shift in the same period.

The limit is **day-aware**: shift types only compete for the same slots
on calendar days where they both apply (per `applicable_days`). Two
shift types with disjoint `applicable_days` -- e.g. a weekday-only shift
and a weekend-only shift -- can both be held by the same worker in the
same (weekly) period under `max_shifts_per_period: 1`, since they never
occur on the same day. Shift types without `applicable_days` apply every
day and always compete. The post-solve validator applies the same
day-aware rule.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `max_shifts_per_period` | int >= 1 | 1 | Maximum shift assignments per worker on any single calendar day of a period. The default of 1 makes same-day shifts mutually exclusive. |

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
| `tolerance` | int >= 0 | 0 | Spread allowed before the constraint reacts. Hard mode enforces `spread <= tolerance` (an exact equal split -- `tolerance: 0` -- is rarely satisfiable); soft mode only penalizes the spread *above* tolerance. |

No-op with fewer than 2 workers, or if no shift types qualify as
undesirable (logged as warnings).

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

Bounds each worker's total workload -- shift count or **hours** -- across
the whole horizon or across every **rolling window** of a configured
size, optionally restricted to specific shift types or categories.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `unit` | `"shifts"`\|`"hours"` | `"shifts"` | What the bounds measure. Hours are computed from each shift type's `duration_hours`. |
| `window_periods` | int >= 1 or null | null | Apply the bounds to every rolling window of this many consecutive periods instead of the whole horizon (e.g. `7` with day periods = a weekly cap). |
| `shift_types` / `categories` | list or null | null | Filters (AND when both set) restricting which assignments count. |
| `min_total_shifts` | int >= 0 | 0 | Minimum shifts (when `unit: shifts`). `0` disables the shortfall penalty. |
| `max_total_shifts` | int >= 1 or null | null | Maximum shifts (when `unit: shifts`). `null` = unbounded. |
| `min_total_hours` / `max_total_hours` | float or null | null | Bounds when `unit: hours` (e.g. `max_total_hours: 40.0` with `window_periods: 7` = a weekly overtime cap). |

Config validation rejects min > max (for either unit) and mixing hours
params with `unit: shifts` (or vice versa). In hard mode
(`is_hard: true`), shortfall and excess are forced to 0, pinning every
worker's total into the configured range exactly.

```yaml
constraints:
  workload:
    enabled: true
    is_hard: false
    weight: 50
    parameters:
      unit: hours
      window_periods: 7          # one week of daily periods
      max_total_hours: 40.0      # weekly overtime cap
```

#### `pinned` (hard)

Forces specific worker/period/shift assignment values, leaving every
other assignment free for the solver to optimize. This is the engine hook
for republishing a schedule without disturbing already-published periods,
and for rolling re-solves in general. Each pin is also passed to CP-SAT
as a solution hint so the search warm-starts from it.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `assignments` | list of `{worker_id, period_index, shift_type_id, value}` | `[]` | `value` is `1` (must work) or `0` (must not work). |

Records referencing an unknown `worker_id` or out-of-range
`period_index` are skipped with a warning at solve time; an unknown
`shift_type_id` is rejected at config load.

```yaml
constraints:
  pinned:
    enabled: true
    parameters:
      assignments:
        - {worker_id: worker_1, period_index: 0, shift_type_id: shift_day, value: 1}
        - {worker_id: worker_2, period_index: 0, shift_type_id: shift_night, value: 0}
```

#### `min_rest` (soft, hard by default when enabled)

Enforces minimum rest hours between shifts for the same worker (the
"clopening" rule -- e.g. no closing at night then opening the next
morning). Checks both shifts assigned within the same single-day period
and shifts spanning the boundary between two adjacent periods, using each
shift type's `start_time`/`end_time` (overnight shifts wrap to the next
calendar day) and the real calendar dates in `period_dates`. Most
meaningful with `period_type: day`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `min_rest_hours` | float > 0 | `11.0` | Minimum rest required between two shifts, in hours (11 is the EU working-time norm). |
| `shift_types` | list[str] or null | null | Restrict the rule to these shift types (both shifts in a checked pair must be in the set). |
| `per_worker_overrides` | map worker id -> hours or null | null | Override `min_rest_hours` for specific workers. |

```yaml
constraints:
  min_rest:
    enabled: true
    is_hard: true
    parameters:
      min_rest_hours: 11.0
```

#### `max_consecutive` (soft, hard by default when enabled)

Caps how many periods in a row a worker may be assigned "working" shifts
(any filtered shift type/category), and optionally enforces a minimum run
length once a working streak starts. With `period_type: day` this is the
classic "max N days in a row" rule.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `max_consecutive_periods` | int >= 1 or null | null | Maximum consecutive working periods allowed. |
| `min_consecutive_periods` | int >= 1 or null | null | Minimum run length once a streak starts. Runs truncated by the schedule horizon are exempt (lenient boundary policy). |
| `shift_types` / `categories` | list or null | null | What counts as "working" (AND when both set). |

At least one bound must be set or the constraint warns and no-ops.

```yaml
constraints:
  max_consecutive:
    enabled: true
    is_hard: true
    parameters:
      max_consecutive_periods: 5
      min_consecutive_periods: 2
```

#### `shift_succession` (soft, `handles_hard_mode = True`)

Forbids or penalizes specific shift-type transitions between periods
(e.g. "no early shift after a night shift"). Each rule matches a "from"
shift type/category at period `p` and a "to" shift type/category at
period `p + gap_periods`. Each rule may set its own `is_hard`, overriding
the constraint-level default, so hard and soft succession rules coexist.
Supersedes `sequence`'s same-category special case with per-rule control.

| Rule field | Type | Default | Meaning |
|---|---|---|---|
| `rule_id` | str | required | Identifier used in variable names and logs. |
| `from_type` / `to_type` | `shift_type`\|`category` | required | What `from_value`/`to_value` name. |
| `from_value` / `to_value` | str | required | The shift type id or category. Validated against `shift_types` at config load. |
| `is_hard` | bool or null | null | Per-rule override; null inherits the constraint's `is_hard`. |
| `priority` | int >= 1 | 1 | Weight multiplier for this rule's violations. |
| `gap_periods` | int >= 1 | 1 | Transition distance (1 = consecutive periods). |

```yaml
constraints:
  shift_succession:
    enabled: true
    is_hard: false
    weight: 100
    parameters:
      rules:
        - rule_id: no_early_after_night
          from_type: shift_type
          from_value: night
          to_type: shift_type
          to_value: early
          is_hard: true
```

#### `consecutive_shift_type` (soft, hard by default when enabled)

Bounds and/or requires consecutive-period runs of a "shift group" (a set
of shift type ids and/or categories, unioned) per worker, with optional
mandatory rest after a completed run. Covers "no more than 3 nights in a
row", "a night rotation must last at least 2 periods once started", and
"2 periods of rest immediately after a night block ends".

| Rule field | Type | Default | Meaning |
|---|---|---|---|
| `rule_id` | str | required | Identifier. |
| `shift_types` / `categories` | list or null | null | The shift group (union; at least one required). |
| `min_consecutive` | int >= 1 or null | null | Minimum run length once started (horizon-lenient). |
| `max_consecutive` | int >= 1 or null | null | Maximum run length. |
| `rest_after_run` | int >= 0 | 0 | Periods with no work at all required after a run of this group ends. |

```yaml
constraints:
  consecutive_shift_type:
    enabled: true
    is_hard: true
    weight: 500
    parameters:
      rules:
        - rule_id: night_block
          categories: ["night"]
          max_consecutive: 3
          rest_after_run: 2
```

#### `weekend` (soft)

Weekend-specific rostering rules. Only meaningful when every period in
the horizon is one calendar day (`period_type: day`) -- with multi-day
periods it logs a warning and has no effect.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `weekend_days` | list[int] (0=Mon..6=Sun) | `[5, 6]` | Which weekdays form a "weekend" group. |
| `require_complete` | bool | `false` | Penalize/forbid working only part of a weekend. |
| `identical_shift_type` | bool | `false` | Penalize/forbid different shift types across a weekend the worker fully works. |
| `max_working_weekends` | int or null | null | Cap on total weekends worked across the horizon. |
| `max_consecutive_weekends` | int or null | null | Cap on runs of consecutive working weekends. |

All four sub-rules are independent and optional -- enable only what you
need.

```yaml
constraints:
  weekend:
    enabled: true
    is_hard: false
    weight: 150
    parameters:
      require_complete: true
      max_working_weekends: 3
```

#### `preference` (soft, `handles_hard_mode = True`)

Honors two data channels that are otherwise unused by the solver: a
worker's `preferred_shifts` (from `workers.csv`), and `Availability`
records of type `"preferred"` or `"required"`.

- **preferred_shifts**: assignment to any shift type outside a worker's
  non-empty preferred set is penalized (soft) or forbidden (hard).
- **`availability_type: preferred`**: the worker not working at all
  (optionally restricted to the record's `shift_type_id`) anywhere in the
  availability window is penalized (soft) or forbidden (hard).
- **`availability_type: required`**: the worker must work at least one
  matching shift in the window. Always hard when
  `honor_required_availability` is true, regardless of the constraint's
  own `is_hard`. A required window overlapping no periods is skipped with
  a warning rather than making the schedule infeasible.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `worker_preferred_weight` | int >= 1 | 1 | Priority multiplier for preferred_shifts violations. |
| `availability_preferred_weight` | int >= 1 | 1 | Priority multiplier for "preferred" availability violations. |
| `honor_required_availability` | bool | true | Whether "required" availability windows are enforced. |

```yaml
constraints:
  preference:
    enabled: true
    weight: 100
    parameters:
      worker_preferred_weight: 2
```

#### `worker_pairing` (soft, `handles_hard_mode = True`)

Keeps two named workers apart (never sharing a shift) or together (a
"tutor"/backup who must be present whenever the other works).

| Rule field | Type | Default | Meaning |
|---|---|---|---|
| `rule_id` | str | required | Identifier. |
| `type` | `together`\|`apart` | required | `apart`: never share the same shift+period. `together`: `worker_b` must work (any scope shift) whenever `worker_a` does. |
| `worker_a` / `worker_b` | str | required | Distinct worker ids. Unknown ids are skipped with a warning at solve time. |
| `shift_types` | list[str] or null | null | Rule scope; null = all shift types. Validated at config load. |
| `is_hard` | bool or null | null | Per-rule override; null inherits the constraint's `is_hard`. |
| `priority` | int >= 1 | 1 | Weight multiplier. |

```yaml
constraints:
  worker_pairing:
    enabled: true
    weight: 200
    parameters:
      rules:
        - {rule_id: keep_apart, type: apart, worker_a: worker_1, worker_b: worker_2, is_hard: true}
        - {rule_id: tutor_new_hire, type: together, worker_a: worker_3, worker_b: worker_4, priority: 3}
```

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
  is. With `period_type: week`, a worker assigned the `"day"` shift type
  for period 3 has that single assignment represent the *whole week*,
  not "the day shift on one day of that week." For actual day-by-day
  assignment, set `schedule.period_type: day` -- each calendar day
  becomes its own period, fully supported by the shipped `generate`
  command (see the `schedule.period_type` note above and the
  `examples/hospitality/` walkthrough).
- **`ShiftInstance.date` is always the period's start date** --
  `SolutionExtractor` stamps every generated shift instance with
  `period_start`. With day periods this *is* the calendar day; with
  multi-day periods it is only the period's first day.
- **Day-granular rules need day periods**: minimum rest time between
  shifts (`min_rest`), maximum consecutive calendar days worked
  (`max_consecutive`), weekend rules (`weekend`), and rolling
  hours-per-week caps (`workload` with `unit: hours` +
  `window_periods: 7`) are all *day-level* concepts. Run them with
  `period_type: day`; with `week` periods, `min_rest` only checks
  period-boundary days, `weekend` disables itself with a warning, and a
  "consecutive periods" cap means consecutive *weeks*. The older
  week-granularity approximations (`sequence` for back-to-back
  categories, day-aware `worker_shift_limit` for within-period
  exclusivity, whole-horizon `workload` totals) remain available when
  week periods are the right model.

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
