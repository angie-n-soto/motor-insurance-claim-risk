-- One row recording which CSV this build read, so downstream exports
-- (dashboards/powerbi/export_for_powerbi.py) can label synthetic data.

{% set csv_path = env_var('MOTOR_CSV_PATH', '../tests/fixtures/policies_sample.csv') %}

select
    '{{ csv_path }}'                                          as source_csv,
    {{ 'true' if csv_path.endswith('tests/fixtures/policies_sample.csv') else 'false' }} as is_synthetic,
    current_timestamp                                         as built_at
