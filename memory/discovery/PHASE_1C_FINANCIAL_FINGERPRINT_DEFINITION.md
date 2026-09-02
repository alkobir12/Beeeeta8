# PHASE_1C_FINANCIAL_FINGERPRINT_DEFINITION

| Metric | Source | Exact semantic definition | Filters | Canonical? | Comparable before/after deployment? |
|---|---|---|---|---|---|
| journal_entry_count | Supabase `journal_entries` | Count of all journal rows fetched from canonical ledger table. | none | YES | YES |

| journal_active_business_record_count | `journal_entries` | Count of all active ledger rows. Current schema has no reliable `status/is_reversed`; reversal rows are active contra entries, not inactive rows. | none | YES | YES |

| reversed_original_count | `journal_entries` | Rows explicitly marked original-reversed by `is_reversed=true` or status in reversed/void/cancelled. Current schema lacks these flags, so expected 0 unless schema changes. | explicit status/flag only | YES | YES, but only if same schema semantics |

| reversal_entry_count | `journal_entries` | Contra/reversal rows identified by `source=reversal` OR `transaction_type=reversal` OR `reference_id` starts with `reversal::`. | source/reference semantics | YES | YES |

| explicit_reversal_link_count | `journal_entries` | Rows having `reversal_of/reversed_of/reverses_entry_id` or reference_id `reversal::...`. | explicit link fields/reference | YES | YES |

| total_debit | `journal_entries.lines` with fallback total | Sum debit across journal lines; if a row lacks line debit/credit, fallback to absolute row total for balanced-row fingerprint only. | none | YES | YES |

| total_credit | `journal_entries.lines` with fallback total | Sum credit across journal lines; same fallback as debit. | none | YES | YES |

| canonical_accounts_receivable_estimate | `journal_entries.lines` | Net debit-credit for AR-like account codes/names found in line objects. | code/name matching | PARTIAL | YES only as estimate; canonical report endpoint may be stronger after Phase 2 |

| canonical_accounts_payable_estimate | `journal_entries.lines` | Net credit-debit for AP-like account codes/names found in line objects. | code/name matching | PARTIAL | YES only as estimate |

| source_distribution | `journal_entries.source` | Count rows by source value, including reversal. | none | YES | YES |

| orphan_reference_counts | operations/vehicles/accounts | Count operations referencing missing vehicle IDs plus table counts. | read-only reference check | PARTIAL | YES |

