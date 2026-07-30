# Hospitality example (day-granular scheduling)

A hotel front desk scheduled at **day granularity** (`period_type: day`),
showcasing the commercial-parity constraint set:

| Constraint | Rule in this example |
|---|---|
| `min_rest` (hard) | 11 hours between any two shifts — no "clopening" (late until 22:00, early at 06:00) |
| `max_consecutive` (hard) | at most 5 working days in a row |
| `shift_succession` (per-rule hard) | never an early shift the day after a night shift |
| `consecutive_shift_type` (hard) | at most 3 nights in a row, then a full day off |
| `weekend` (soft) | prefer complete weekends; at most 3 working weekends per roster |
| `workload` (soft, hours) | at most 40 hours in any rolling 7-day window |
| `fairness` (soft, tolerance 1) | night shifts spread evenly, spread of 1 tolerated |
| `preference` (soft) | worker_1 prefers early shifts; worker_5 must work in the first week (`required` availability); worker_6 prefers late shifts mid-month |
| `worker_pairing` (soft) | worker_2 and worker_3 kept apart |
| `pinned` (hard) | worker_1's already-published day-1 early shift stays fixed |

The roster: 8 workers, 5 slots per day (2 early, 2 late, 1 night), one
worker restricted from nights.

Run it from the project root:

```bash
bash examples/hospitality/run.sh
```

The generate step omits `--end-date` to demonstrate the
`schedule.num_periods` horizon (28 day periods from the start date), and
passes `--explain` to print the per-constraint objective penalty
breakdown after solving.
