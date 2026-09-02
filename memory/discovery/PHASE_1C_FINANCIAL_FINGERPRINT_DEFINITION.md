# PHASE_1C_FINANCIAL_FINGERPRINT_DEFINITION

| Metric | Source | Exact semantic definition | Filters | Canonical? | Comparable before/after deployment? |
|---|---|---|---|---|---|
| journal_row_count | Supabase `journal_entries` | Count of all rows in the canonical journal table, including normal and reversal/contra rows. | none | YES | YES |
| reversal_entry_count | `journal_entries.source/reference_id/transaction_type` | Count of reversal/contra rows where `source=reversal` OR `transaction_type=reversal` OR `reference_id` starts with `reversal::`. | source/reference semantics | YES | YES |
| non_reversal_entry_count | `journal_entries` minus reversal rows | `journal_row_count - reversal_entry_count`; rows not classified as reversal/contra rows by the above rule. | excludes reversal_entry_count semantics | YES | YES |
| reversed_original_count | `journal_entries` status/flag fields | Count of original rows explicitly marked reversed by `is_reversed=true` or status in reversed/void/cancelled. Current schema has no reliable such flags, so this is 0 unless schema changes. | explicit status/flag only | YES | YES if schema unchanged |
| explicit_reversal_link_count | `journal_entries` link/reference fields | Rows having `reversal_of`, `reversed_of`, `reverses_entry_id`, or `reference_id` starting with `reversal::`. | explicit link/reference semantics | YES | YES |
| total_debit | `journal_entries.lines` with fallback total | Sum of debit values across line objects; if line debit/credit are absent, fallback to absolute row total for balanced-row fingerprint only. | none | YES | YES |
| total_credit | `journal_entries.lines` with fallback total | Sum of credit values across line objects; same fallback as debit. | none | YES | YES |
| canonical_accounts_receivable_estimate | `journal_entries.lines` | Net debit-credit for AR-like account codes/names present in line objects. | code/name matching | PARTIAL | YES as estimate only |
| canonical_accounts_payable_estimate | `journal_entries.lines` | Net credit-debit for AP-like account codes/names present in line objects. | code/name matching | PARTIAL | YES as estimate only |
| source_distribution | `journal_entries.source` | Count journal rows by source value. | none | YES | YES |
| orphan_reference_counts | operations/vehicles/accounts | Count operations referencing missing vehicle IDs plus source table counts. | read-only reference check | PARTIAL | YES |

## Semantic reconciliation
- `journal_active_business_record_count` is deprecated and must not be used as final terminology because reversal rows are active ledger rows and are included in the journal row count.
- Use `journal_row_count`, `reversal_entry_count`, and `non_reversal_entry_count` instead.
- Previous zero reversal metric was caused by querying absent `is_reversed/reversal_of` semantics rather than current `source/reference` semantics.
