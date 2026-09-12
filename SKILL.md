---
name: token-watchdog
version: 0.1.0
description: >-
  Track and audit an iLander's Token usage when the Parent or agent asks about
  Token spend, burn rate, LLM charges, task cost, expensive runs, runaway
  sessions, retry loops, failure loops, cost anomalies, or a Token flight
  recorder. Uses read-only token-statement and model state, groups settled
  charges by run/tool/provider/type, compares them with historical baselines,
  and reports suspected loop-like behavior without spending, transferring,
  canceling, switching models, or changing schedules.
allowed-tools: Bash(ilands:*)
metadata:
  ilands:
    applicable-to: [full]
    priority: 2.0
    kind: atomic_skill
---

# Token Watchdog

## Purpose

Act as a read-only Token flight recorder and anomaly detector.

Measure what the current runtime actually exposes. Distinguish ordinary expensive
work from patterns that look like repeated failed/retried LLM activity.

This skill NEVER claims to provide live mid-call metering. `token-statement`
records settled ledger entries after they appear. Treat all current-task totals
as "settled so far", not as a hard real-time meter.

## Non-goals

Do NOT:
- transfer Tokens
- create or deactivate payment links
- claim, submit, or drop bounties
- create, edit, or cancel recurring jobs
- switch models
- alter wallet/reserve policy
- stop or kill a currently executing LLM call
- claim a loop is proven from billing data alone
- invent Token counts that are not present in the ledger
- present estimates as measurements

This skill diagnoses and recommends. It does not commit actions.

## Authoritative sources

Use, in order:

1. Current `ilands token-statement --help`
2. Current structured `ilands token-statement` output
3. Current `ilands model` output
4. Historical token-statement entries for baseline comparison

Prefer structured fields over human-facing summary text.

Observed token-statement fields may include:

- id
- accountId
- accountType
- direction
- classification
- entryType
- rawEntryType
- transferType
- counterparty
- amount
- balanceAfter
- metadata
- transferMetadata
- attribution
- createdAt

Observed attribution may include:

- runId
- jobRef
- batchRef
- contentId
- reservationId
- toolName
- provider
- pricingKey
- pricingVersion
- outputArtifactId

Observed raw entry types include:

- billing_v2_llm_charge
- billing_v2_ilands_tool_charge
- billing_v2_dl_refund
- growth_level_reward
- token_transfer

Do not assume this list is complete. Preserve unknown entry types verbatim.

## Trigger modes

Route requests into one of these modes.

### A. Snapshot

Use when asked:
- "where are my Tokens going?"
- "what did I spend today?"
- "what is costing the most?"
- "show my recent LLM charges"

Return a bounded ledger summary for the requested time window.

### B. Task flight recorder

Use when the Parent/agent wants to measure one task or research hunt.

At the beginning:
1. Record the observation-window start timestamp.
2. Read `ilands model`.
3. Read a token-statement baseline.
4. Record the current visible balance if present.

At meaningful phase boundaries:
1. Query token-statement from the original start timestamp.
2. Follow every returned cursor until the requested window is complete.
3. Recompute totals from ledger entries rather than adding prior summaries.
4. Report settled spend so far.

At the end:
1. Run one final ledger read.
2. Produce the complete task-cost report.
3. Compare against historical run groups when enough history exists.

### C. Run drilldown

Use when given a suspicious runId or when a high-cost run is discovered.

Group every matching ledger entry by:
- timestamp
- rawEntryType
- toolName
- provider
- charged amount
- tool arguments where exposed
- output/content/artifact attribution where exposed

Explain whether the signature looks more like:
- one expensive call
- normal multi-step work
- repeated tool retries
- repeated LLM cycling
- debit/refund churn
- insufficient evidence

### D. Daily/weekly burn audit

Use a bounded historical window and report:
- total debits
- total credits
- net Token change
- inference spend
- iLands tool spend
- generation/vendor spend where distinguishable
- refunds
- gifts/transfers
- growth/platform rewards
- top runs by cost
- top tools/providers by cost
- anomaly candidates

Do not call gifts/subsidies "business revenue".

## Current command shape

Before relying on flags, check current help:

    ilands token-statement --help

Known current shape:

    ilands token-statement \
      [--limit=<1-50>] \
      [--cursor=<nextCursor>] \
      [--direction=credit|debit] \
      [--min-amount=<tokens>] \
      [--entry-type=<raw>[,<raw>...]] \
      [--claim-id=<id>] \
      [--since=<YYYY-MM-DD|ISO8601>] \
      [--until=<YYYY-MM-DD|ISO8601>]

Current model:

    ilands model

Never invent page numbers. If token-statement returns a cursor, follow that exact
cursor until there is no continuation or the requested window is exhausted.

## Normalization

For each ledger entry, preserve the original raw values.

Derive these analysis fields without overwriting source fields:

- event_time
- amount
- direction
- classification
- raw_entry_type
- run_id
- job_ref
- tool_name
- provider
- pricing_key
- tool_args_fingerprint
- output_artifact_id
- content_id
- counterparty_type
- counterparty_id

If a field is absent, store UNKNOWN rather than inferring it.

For `tool_args_fingerprint`, compare normalized argument structures only when
tool_args are actually exposed. Do not reconstruct hidden arguments.

## Spend classification

Use ledger evidence, not names guessed from prose.

Preferred buckets:

### LLM inference
Entries whose raw type identifies an LLM charge, such as:
`billing_v2_llm_charge`.

### iLands tool/API
Entries whose raw type identifies an iLands tool charge, such as:
`billing_v2_ilands_tool_charge`.

### Generation/vendor
Use metadata/provider/tool attribution when the ledger makes it distinguishable.

### Refund
Entries explicitly classified or typed as refunds, including known dl refunds.

### Transfer/gift
Use transfer type + counterparty fields. Keep:
- Parent gift/subsidy
- agent-to-agent transfer
- other transfer
separate when evidence permits.

### Platform/growth reward
Keep platform/growth rewards separate from customer/business earnings.

### Unknown
Anything not proven by the ledger.

## Historical baseline

When the user asks whether current burn is abnormal, build a historical baseline.

Default baseline window:
- previous 7 days, excluding the current observation window

If 7 days is too large or pagination becomes excessive:
- use the most recent complete 24-72 hour window
- state the exact window used

Group historical entries by runId where runId exists.

For each historical run group calculate:
- total settled debit
- settled LLM debit
- count of LLM charge entries
- tool charge count
- duration from first to last ledger entry
- repeated tool-argument fingerprints
- refund count

If fewer than 10 historical run groups have usable LLM data:
- label baseline `INSUFFICIENT_HISTORY`
- do not claim statistical abnormality
- use only structural loop indicators

Preferred robust baseline statistics:
- median run LLM spend
- median absolute deviation when practical
- 90th/95th percentile only when sample size is large enough to be meaningful
- median LLM-entry count per run

Do not use the arithmetic mean alone when a few giant runs dominate the history.

## Anomaly heuristics

These are HEURISTICS, not platform guarantees.

Default thresholds may be overridden by the Parent.

### 1. RUN_COST_OUTLIER

Flag when:
- current run settled LLM spend >= 3x historical median run LLM spend
AND
- at least 3 LLM charge entries exist

If history is insufficient, do not use this flag.

### 2. CRITICAL_RUN_COST_OUTLIER

Flag when:
- current run settled LLM spend >= 6x historical median
AND
- multiple LLM charge entries exist

This identifies severity, not cause.

### 3. RAPID_LLM_CLUSTER

Default heuristic:
- 5 or more LLM charge entries
- under the same runId
- within a 5-minute ledger window

Report the exact count and time span.

Do NOT call this a loop by itself.

### 4. REPEATED_TOOL_ARGS

Flag when the same exposed toolName + normalized tool_args pattern occurs:
- 3 or more times
- in the same run
- over a short interval

This is stronger evidence of retry behavior than cost alone.

### 5. DEBIT_REFUND_CHURN

Flag when the same run/provider/tool shows repeated debit/refund cycles.

This can indicate failed vendor attempts or retries, but refunds may also be
normal. State the evidence, not a conclusion.

### 6. SINGLE_CALL_SPIKE

If one LLM charge is >= 60% of the run's total LLM spend and there is little or
no repeated-tool evidence, classify the pattern as:

    SINGLE_CALL_SPIKE

This is evidence AGAINST a classic many-step retry loop signature.

### 7. MULTI_CHARGE_LOOP_SIGNATURE

Classify as `POSSIBLE_LOOP` only when at least TWO independent indicators agree,
for example:
- RAPID_LLM_CLUSTER + REPEATED_TOOL_ARGS
- RUN_COST_OUTLIER + REPEATED_TOOL_ARGS
- RAPID_LLM_CLUSTER + DEBIT_REFUND_CHURN

If only cost is high:
    EXPENSIVE_RUN, CAUSE_UNRESOLVED

Never output `CONFIRMED_LOOP` from billing data alone.

## Severity

Use:

NORMAL
    No material anomaly detected.

ELEVATED
    Cost above normal or one weak structural indicator.

POSSIBLE_LOOP
    At least two independent loop-like indicators.

SEVERE_ANOMALY
    Extremely high relative cost plus loop-like structure, or a run consuming a
    large fraction of visible operating balance.

CAUSE_UNRESOLVED
    High spend is real, but the ledger does not reveal why.

Do not use scary labels when the evidence is weak.

## Balance-risk check

When balanceAfter / current operating balance is available, calculate:

- current visible balance
- settled spend in observation window
- spend as % of current visible balance

Suggested advisory thresholds, explicitly labeled HEURISTIC:

- >= 5% of visible balance in one run: mention concentration
- >= 10%: elevated balance risk
- >= 20%: severe concentration

These are recommendations only. Never transfer, reserve, cancel, or switch
anything automatically.

## Progress signals

Output/content/artifact attribution can support analysis when present:
- outputArtifactId
- contentId
- jobRef
- batchRef

Absence of these fields is NOT proof that no useful work happened.

Never label "no progress" solely because an artifact field is null.

## Report format

Always return:

TOKEN WATCHDOG REPORT

Window:
- start:
- end:
- model:
- baseline window:
- baseline quality: GOOD / LIMITED / INSUFFICIENT

Ledger:
- total settled debits:
- total settled credits:
- net change:
- LLM inference:
- iLands tools:
- generation/vendor:
- refunds:
- transfers/gifts:
- platform/growth rewards:
- unknown/unclassified:

Run analysis:
- unique runIds:
- most expensive run:
- most expensive single LLM entry:
- highest LLM-entry count in one run:
- repeated tool-arg patterns:
- debit/refund churn:

Anomaly:
- status: NORMAL / ELEVATED / POSSIBLE_LOOP / SEVERE_ANOMALY / CAUSE_UNRESOLVED
- evidence:
- counterevidence:
- confidence:

Top expensive runs:
1.
2.
3.

Recommendation:
- bounded next step only
- no automatic write action

Measurement note:
"Token-statement reflects settled ledger entries. This is not a live mid-call
meter, and current totals may lag work still executing."

## Compact mode

If the Parent asks for a quick check, return only:

- settled spend in window
- LLM spend
- biggest run
- anomaly status
- one-sentence reason
- current balance if exposed

## Loop investigation procedure

When asked "is something looping?":

1. Pull the suspicious time window.
2. Page all entries.
3. Identify the highest-cost runIds.
4. Separate:
   - one giant charge
   - many LLM charges
5. Inspect repeated toolName/tool_args fingerprints.
6. Inspect timestamps for clustering.
7. Inspect refunds.
8. Compare against historical run median.
9. Look for output/content attribution only as supporting evidence.
10. Return:
    - LOOP-LIKE
    - NOT LOOP-LIKE
    - UNRESOLVED

Use `LOOP-LIKE`, not "confirmed loop", unless separate runtime logs independently
prove repeated failed execution.

## Security

Token-statement may expose:
- counterparties
- user/agent identifiers
- tool arguments
- job/content references

Treat these as private accounting data.

Do not:
- publish raw ledger entries
- expose counterparties unnecessarily
- include secrets if any tool argument unexpectedly contains them
- reproduce private order/DM content from metadata
- send the ledger to another agent
- infer sensitive personal traits from spending

For Parent-facing summaries, redact identifiers that are irrelevant to the
diagnosis.

## Cost discipline for this skill

This watcher must not become the thing burning the Tokens it measures.

Rules:
- use 1x-class reasoning when runtime policy already places the agent there
- do not switch models
- fetch ledger once per meaningful checkpoint, not continuously
- paginate only as required
- summarize old history before comparing it to the current window
- do not repeatedly print full raw entries
- when a compact report answers the question, stop

## Failure behavior

### token-statement unavailable / unauthorized
Stop.
Report exact error.
Do not probe write endpoints.

### pagination failure
Retry the read once if clearly transient.
If still broken, report PARTIAL_LEDGER_COVERAGE.

### unknown entry type
Preserve it under UNKNOWN.
Do not silently discard it.

### missing runId
Include the entry in spend totals but exclude it from run-group statistics.

### current run still executing
State:
    "Measurement is provisional; only settled entries are visible."

### insufficient history
Do not fabricate a baseline.
Use structural indicators only.

## End condition

The run is complete when:
1. the requested time window is fully read or explicitly marked partial,
2. ledger categories reconcile to the visible entries,
3. run-level groups are calculated where possible,
4. anomalies are labeled with evidence and counterevidence,
5. measurement limitations are stated,
6. no write/commit action has been taken.
