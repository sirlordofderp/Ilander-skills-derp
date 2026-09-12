---
name: token-watchdog
version: 0.3.0
description: >-
  Track and audit an iLander's Token usage when the Parent or agent asks about
  Token spend, burn rate, LLM charges, task cost, expensive runs, runaway
  sessions, retry loops, failure loops, cost anomalies, burst minutes, or a
  Token flight recorder. Uses read-only token-statement and model state, groups
  settled charges by run/tool/provider/type/time, compares them with historical
  baselines, and reports suspected anomalies without spending, transferring,
  canceling, switching models, or changing schedules. Final output is plain
  text by default; do not require JSON deliverables.
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


## Output format rule

`token-statement` may return structured JSON internally. That is an INPUT format,
not a required user-facing OUTPUT format.

Default final output MUST be ordinary plain text.

When a file is requested, prefer:
- `.txt` for full reports or raw-ledger exports
- `.csv` for flattened tables when a spreadsheet-like view is useful

Do NOT require the Parent or agent to consume a `.json` file.

If a raw ledger export is requested and JSON attachments are inconvenient or
unsupported, write a `.txt` ledger using one human-readable record block per
entry:

    ENTRY 0001
    timestamp: ...
    amount: ...
    direction: ...
    raw_entry_type: ...
    run_id: ...
    tool_name: ...
    provider: ...
    balance_after: ...
    metadata:
      key: value
      key: value

Nested values should be rendered as indented `key: value` text, not JSON syntax.

A compact tabular export may use CSV with flattened fields. Preserve unknown
fields in the TXT export rather than dropping them.

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
- billing_v2_dl_charge
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


### E. Minute-burst audit

Use when asked:
- "did I burn Tokens while idle?"
- "find the 30-tokens-a-minute thing"
- "show burst minutes"
- "alert-worthy minutes"
- "which minute was worst?"

Bin ALL settled debit entries by UTC minute regardless of whether they have a
runId.

For each minute calculate:
- total debit
- LLM debit
- non-LLM debit
- debit entry count
- distinct runIds
- raw entry types
- top tool/provider when exposed

Default advisory thresholds:

    >= 100 Tokens/minute  -> BURST_WARNING
    >= 250 Tokens/minute  -> HIGH_BURN_BURST
    >= 400 Tokens/minute  -> EXTREME_BURN_BURST

Also flag:

    SUSTAINED_BURST

when 3 consecutive minutes each exceed 100 Tokens.

These are heuristic alert thresholds, not platform limits.

If the requested window is described as "idle" or "quiet hours", compare the
burst against the user's stated intended activity. Do not infer that an agent
was idle merely from missing runId or missing artifact output.

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

## Timestamp normalization

Current runtime behavior observed during acceptance testing:

- `--since` / `--until` accepts UTC `Z`
- full offsets such as `+00:00` are valid
- truncated offsets such as `+00` can return HTTP 400

Before issuing a time-bounded statement query, normalize timestamps to one of:

    2026-09-12T12:34:56Z

or:

    2026-09-12T12:34:56+00:00

Do not send truncated timezone offsets.

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

Acceptance testing found that `tool_args` may be absent from practical ledger
entries even when other attribution fields are present. Therefore
REPEATED_TOOL_ARGS is a low-availability corroborating signal, not a required
signal for healthy operation or anomaly detection.

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
Treat explicit `billing_v2_dl_charge` entries as generation/vendor debit unless
current runtime documentation says otherwise.

Treat `billing_v2_dl_refund` as the corresponding refund class.

Use metadata/provider/tool attribution for finer breakdowns when the ledger makes
them distinguishable. Preserve the raw entry type in every report.

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

## No-run / unattributed spend

Entries without `runId` MUST remain in the accounting totals.

Never discard them merely because run-level attribution is unavailable.

For every analysis window, calculate:

- no-run debit total
- no-run credit total
- no-run entry count
- top no-run raw entry types
- top no-run tools/providers when exposed
- largest individual no-run debit

This bucket is especially important for iLands tool charges and `dl` charges that
may legitimately carry no runId.

Call this bucket:

    UNATTRIBUTED_TO_RUN

This means "not attributable to a runId", NOT "unknown cause". A raw entry type,
tool, or provider may still identify the cost source.

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

### 8. SINGLE_LLM_ENTRY_PER_RUN counterevidence

If the suspicious window shows:
- maximum LLM-entry count per run == 1
- no repeated-tool evidence
- no debit/refund retry pattern

then treat this as strong counterevidence to a classic LLM retry loop.

A high-cost run under this signature should normally be classified:

    SINGLE_CALL_SPIKE

or:

    EXPENSIVE_RUN, CAUSE_UNRESOLVED

not POSSIBLE_LOOP.

## Time-density analysis

Run-level grouping alone can miss wallet-wide bursts.

For any broad burn investigation:
1. group all debit entries into UTC one-minute bins;
2. calculate total, LLM, and non-LLM debit per minute;
3. identify the top 10 most expensive minutes;
4. identify consecutive high-burn streaks;
5. keep entries with no runId in the minute totals;
6. report whether the burst is dominated by:
   - one LLM charge,
   - multiple LLM charges,
   - dl/vendor spend,
   - iLands tool charges,
   - mixed/unknown spend.

A high-burn minute is not automatically a loop.

Strong loop evidence still requires repeated/clustered behavior beyond raw cost.

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
- entries retrieved:
- pages/cursors consumed:
- coverage: COMPLETE / PARTIAL
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

Unattributed-to-run:
- debit total:
- credit total:
- entry count:
- top raw entry types:
- top tools/providers:
- largest debit:

Run analysis:
- unique runIds:
- most expensive run:
- most expensive single LLM entry:
- highest LLM-entry count in one run:
- repeated tool-arg patterns:
- debit/refund churn:

Minute-density:
- highest-burn minute:
- highest-burn minute total:
- LLM share of highest minute:
- non-LLM share of highest minute:
- minutes >= 100:
- minutes >= 250:
- minutes >= 400:
- sustained 3-minute bursts:
- top 5 burst minutes:

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

## Reconciliation check

Before finalizing a report:

1. Sum all visible debit entries.
2. Sum all visible credit entries.
3. Sum every reporting bucket independently.
4. Confirm bucketed debits reconcile to visible debit total.
5. Confirm bucketed credits reconcile to visible credit total.
6. If they do not reconcile, report the exact residual under
   `UNCLASSIFIED_RESIDUAL` and do not hide it.

This prevents a clean-looking report from silently dropping unknown/no-run entry
types.

## Plain-text delivery modes

### Human report — DEFAULT

Return the normal report directly as plain text.

### TXT full ledger export

When the user asks to "spit out the data", "dump the ledger", "give me all the
entries", or equivalent, create a `.txt` file containing every retrieved ledger
entry as human-readable field blocks.

Requirements:
- preserve entry order;
- include the exact requested time window;
- state number of pages/cursors consumed;
- state total entries;
- state COMPLETE or PARTIAL coverage;
- include every API-returned field that is safe to expose to the Parent;
- retain unknown entry types verbatim;
- do not silently summarize or deduplicate raw entries.

### CSV flattened export

Use only when explicitly useful.

Suggested columns:

    timestamp,amount,direction,classification,raw_entry_type,run_id,job_ref,
    tool_name,provider,pricing_key,balance_after,counterparty_type,
    output_artifact_id,content_id

Do not force nested metadata into malformed pseudo-JSON. Put fields that cannot
be faithfully flattened in the TXT export instead.

### JSON

JSON may be consumed internally from CLI responses, but is NEVER required as a
final deliverable. Only emit a `.json` file if the Parent explicitly asks for
JSON and the destination accepts it.

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
3. Bin all debits by minute and identify high-burn bursts.
4. Identify the highest-cost runIds.
5. Separate:
   - one giant charge
   - many LLM charges
6. Inspect repeated toolName/tool_args fingerprints.
7. Inspect timestamps for clustering.
8. Inspect refunds.
9. Compare against historical run median.
10. Separately total no-run charges by raw entry type; do not force them into a
   suspicious run.
11. Look for output/content attribution only as supporting evidence.
12. Return:
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

## v0.3 acceptance-derived changes

v0.3 adds:
- plain-text output as the default final format
- `.txt` raw-ledger export with human-readable record blocks
- optional flattened `.csv` export
- JSON treated as internal input unless explicitly requested for final delivery
- wallet-wide one-minute burn-density analysis
- 100 / 250 / 400 Tokens-per-minute advisory burst thresholds
- sustained-burst detection for 3 consecutive minutes above 100
- top burst-minute reporting independent of runId

These changes are based on lifetime-ledger testing in which a 410-entry history
required 9 cursor-paged calls and one quiet-hours interval showed a concentrated
2,656-Token burn event that run-level analysis alone did not fully characterize.

## v0.2 acceptance-derived changes

v0.2 incorporates live acceptance findings:

- normalize query timestamps to `Z` or full `+HH:MM` offsets
- recognize `billing_v2_dl_charge` explicitly
- keep `billing_v2_dl_refund` paired with dl debit accounting
- add a dedicated `UNATTRIBUTED_TO_RUN` section
- treat single-LLM-entry-per-run as loop counterevidence
- document that tool_args may often be absent
- report pages/entries/coverage
- require debit/credit reconciliation before final output

## End condition

The run is complete when:
1. the requested time window is fully read or explicitly marked partial,
2. ledger categories reconcile to the visible entries,
3. run-level groups are calculated where possible,
4. no-run entries remain included and are separately summarized,
5. debit/credit bucket totals reconcile or expose a residual,
6. minute-density analysis is included when the request concerns bursts,
   idle burn, or broad spending anomalies,
7. final user-facing output is plain text unless another format was explicitly
   requested,
8. anomalies are labeled with evidence and counterevidence,
9. measurement limitations are stated,
10. no write/commit action has been taken.
