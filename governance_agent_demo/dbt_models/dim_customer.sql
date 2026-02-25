-- dbt model: dim_customer
-- Output TDEs: customer_email_raw (TDE001), customer_email_cleansed (TDE002)
--
-- GOVERNANCE FLAW #1: COALESCE silently substitutes a placeholder email address
--   instead of surfacing null values for remediation at the source system.
--   This masks data quality issues and causes format-check rules to pass
--   for records that should be flagged as missing.
--
-- GOVERNANCE FLAW #2: LOWER() is applied before format validation, which can
--   corrupt non-ASCII email addresses and disguise format anomalies.
--
-- GOVERNANCE FLAW #3: PII columns (full_name, date_of_birth) are present
--   in plain text with no masking transformation applied, violating the
--   PII masking policy for analytical data products.
--
-- GOVERNANCE FLAW #4: No email format validation pattern (REGEXP or LIKE)
--   is applied anywhere in the model; downstream rules cannot rely on structure.

WITH source AS (
    SELECT * FROM {{ source('raw', 'customers') }}
),

transformed AS (
    SELECT
        customer_id,

        -- FLAW 1: COALESCE masks nulls; root-cause (missing email at registration)
        --         is never surfaced for stewardship action.
        COALESCE(email_address, 'unknown@placeholder.internal') AS email,

        -- FLAW 2: LOWER() applied without prior format validation; RFC 5322
        --         local-parts are case-sensitive, so LOWER() can corrupt valid addresses.
        LOWER(
            COALESCE(email_address, 'unknown@placeholder.internal')
        ) AS cleansed_email,

        -- Demographic fields
        first_name,
        last_name,

        -- FLAW 3: PII concatenated in plain text — no masking or tokenisation
        CONCAT(first_name, ' ', last_name)  AS full_name,
        date_of_birth,                       -- FLAW 3: raw PII, no masking

        -- Metadata
        created_at,
        updated_at,
        is_active

    FROM source
    WHERE customer_id IS NOT NULL
)

SELECT * FROM transformed
