-- dbt model: fct_transactions
-- Output TDEs: transaction_id_raw (TDE005), transaction_id_normalized (TDE006)
--
-- GOVERNANCE FLAW #1: COALESCE on txn_id synthesises a fallback ID from
--   created_at timestamp.  Multiple events in the same second share the same
--   synthesised ID, silently destroying the uniqueness invariant for TDE005.
--
-- GOVERNANCE FLAW #2: The normalised ID construction uses string concatenation
--   without zero-padding validation — LPAD operates on sequence_num but if
--   sequence_num is NULL the result is also NULL, defeating the format rule.
--
-- GOVERNANCE FLAW #3: LEFT JOIN on dim_merchant with is_active = TRUE
--   can fan out when a merchant has multiple active records (e.g. after
--   reactivation without deduplication), producing duplicate transaction rows
--   and corrupting uniqueness for downstream reconciliation.
--
-- GOVERNANCE FLAW #4: No deduplication or QUALIFY RANK() OVER (...) is applied
--   after the join, so grain uniqueness is fully dependent on dim_merchant
--   data quality — an undocumented hidden dependency.

WITH transactions AS (
    SELECT * FROM {{ ref('stg_transactions') }}
),

enriched AS (
    SELECT
        t.transaction_date,
        t.amount,
        t.merchant_id,
        t.status,
        t.created_at,

        -- FLAW 1: COALESCE synthesises IDs from timestamp; collisions occur
        --         when multiple transactions share a created_at second.
        COALESCE(
            t.txn_id,
            'TXN-SYNTHETIC-' || CAST(t.created_at AS TEXT)
        )                                                   AS transaction_id,

        -- FLAW 2: If sequence_num IS NULL, LPAD returns NULL and the format
        --         rule TXN-YYYYMMDD-NNNNNN silently fails without alerting.
        'TXN-'
            || REPLACE(CAST(t.transaction_date AS TEXT), '-', '')
            || '-'
            || LPAD(CAST(t.sequence_num AS TEXT), 6, '0')  AS normalized_txn_id,

        m.merchant_name,
        m.merchant_category

    FROM transactions t

    -- FLAW 3: Fan-out risk — dim_merchant may have multiple active rows
    --         per merchant_id after imperfect SCD Type 2 implementation.
    LEFT JOIN {{ ref('dim_merchant') }} m
           ON m.merchant_id = t.merchant_id
          AND m.is_active   = TRUE
    -- FLAW 4: No QUALIFY or ROW_NUMBER() to guard against the fan-out above.
)

SELECT * FROM enriched
