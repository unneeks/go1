-- dbt model: fct_revenue
-- Output TDEs: revenue_usd (TDE003), revenue_local_currency (TDE004)
--
-- GOVERNANCE FLAW #1: CAST(... AS INTEGER) truncates decimal cents, silently
--   losing sub-dollar precision.  A $9.99 order becomes $9, introducing
--   systematic revenue under-reporting of up to $0.99 per transaction.
--
-- GOVERNANCE FLAW #2: No range validation guard — negative amount_cents
--   values (refunds coded incorrectly) pass through undetected and produce
--   negative revenue_usd figures, violating the numeric range DQ rule.
--
-- GOVERNANCE FLAW #3: The LEFT JOIN on fx_rates uses a non-equi condition
--   (effective_date <= order_date).  If multiple FX rates exist for a date
--   range, the join fans out and produces duplicate revenue rows, inflating
--   totals and corrupting uniqueness of the grain.
--
-- GOVERNANCE FLAW #4: COALESCE on fx.rate defaults to 1.0, silently applying
--   a 1:1 conversion for currencies whose rate is missing, producing incorrect
--   local currency amounts with no audit trail.

WITH orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
),

fx_rates AS (
    SELECT * FROM {{ ref('stg_fx_rates') }}
),

joined AS (
    SELECT
        o.order_id,
        o.customer_id,
        o.order_date,

        -- FLAW 1: INTEGER cast truncates sub-dollar precision (e.g. $9.99 → $9)
        CAST(o.amount_cents / 100 AS INTEGER)                            AS revenue_usd,

        -- FLAW 4: COALESCE on fx.rate silently defaults to 1.0 when rate is missing
        CAST(
            o.amount_cents / 100.0 * COALESCE(fx.rate, 1.0) AS DECIMAL(15, 2)
        )                                                                AS revenue_local,

        fx.currency_code,
        o.status

    FROM orders o

    -- FLAW 3: Non-equi join on effective_date fans out rows when multiple
    --         FX rates are active for overlapping date ranges.
    LEFT JOIN fx_rates fx
           ON fx.currency_code  = o.currency_code
          AND fx.effective_date <= o.order_date

    -- FLAW 2: Missing guard: AND o.amount_cents >= 0
    --         Negative amounts (mis-coded refunds) pass through undetected.
    WHERE o.amount_cents IS NOT NULL
)

SELECT * FROM joined
