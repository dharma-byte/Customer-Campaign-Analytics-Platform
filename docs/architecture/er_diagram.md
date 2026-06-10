# Entity Relationship Diagram
## Customer Campaign Analytics Platform — Database Schema

---

## Table Relationship Map

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          LOOKUP / DIMENSION TABLES                            │
│                                                                                │
│  ┌───────────────────┐          ┌──────────────────────┐                      │
│  │    products        │          │   campaign_channels   │                      │
│  │─────────────────── │          │──────────────────────│                      │
│  │ PK product_id      │          │ PK channel_id         │                      │
│  │    product_code    │          │    channel_name        │                      │
│  │    product_name    │          │    benchmark_ctr       │                      │
│  │    product_category│          │    benchmark_cvr       │                      │
│  │    revenue_value   │          │    benchmark_cpa       │                      │
│  └────────┬──────────┘          └──────────┬───────────┘                      │
└───────────┼──────────────────────────────--─┼───────────────────────────────--─┘
            │                                 │
            │ 1                               │ 1
            │                                 │
┌───────────┼─────────────────────────────────┼──────────────────────────────────┐
│           │        CORE ENTITY TABLES        │                                  │
│           │                                  │                                  │
│  ┌────────┴──────────────────────────────────┴───────┐                         │
│  │                     campaigns                      │                         │
│  │────────────────────────────────────────────────── │                         │
│  │ PK campaign_id                                     │                         │
│  │ FK product_id          ──► products               │                         │
│  │ FK channel_id          ──► campaign_channels      │                         │
│  │    campaign_code                                   │                         │
│  │    campaign_name                                   │                         │
│  │    campaign_type                                   │                         │
│  │    target_segment                                  │                         │
│  │    start_date / end_date                           │                         │
│  │    total_budget                                    │                         │
│  │    ab_test_enabled                                 │                         │
│  │    status                                          │                         │
│  └──────────────────────────────┬─────────────────---┘                         │
│                                  │ 1                                            │
│  ┌───────────────────┐           │                                              │
│  │     customers      │           │                                              │
│  │────────────────── │           │                                              │
│  │ PK customer_id     │           │                                              │
│  │    customer_code   │           │                                              │
│  │    full_name       │           │                                              │
│  │    date_of_birth   │           │                                              │
│  │    gender          │           │                                              │
│  │    region / city   │           │                                              │
│  │    segment         │           │                                              │
│  │    annual_income   │           │                                              │
│  │    credit_score    │           │                                              │
│  │    acquisition_date│           │                                              │
│  └────────┬──────────┘           │                                              │
└───────────┼──────────────────────┼──────────────────────────────────────────────┘
            │ 1                    │ 1
            │                      │
┌───────────┼──────────────────────┼──────────────────────────────────────────────┐
│           │     FACT TABLES       │                                               │
│           │                       │                                               │
│           │      ┌────────────────┴────────────────────────────────┐             │
│           │      │              campaign_interactions               │             │
│           │      │──────────────────────────────────────────────── │             │
│           │      │ PK interaction_id                                │             │
│           ├──────┤ FK customer_id      ──► customers               │             │
│           │      │ FK campaign_id      ──► campaigns               │             │
│           │      │ FK channel_id       ──► campaign_channels       │             │
│           │      │    interaction_date                              │             │
│           │      │    interaction_type                              │             │
│           │      │    interaction_outcome                           │             │
│           │      │    ab_variant                                    │             │
│           │      └───────────────────┬─────────────────────────────┘             │
│           │                          │ 1                                          │
│           │      ┌───────────────────┴────────────────────────────┐              │
│           │      │              campaign_conversions               │              │
│           │      │──────────────────────────────────────────────  │              │
│           │      │ PK conversion_id                                │              │
│           ├──────┤ FK customer_id      ──► customers              │              │
│           │      │ FK campaign_id      ──► campaigns              │              │
│           │      │ FK interaction_id   ──► campaign_interactions  │              │
│           │      │ FK product_id       ──► products               │              │
│           │      │ FK channel_id       ──► campaign_channels      │              │
│           │      │    conversion_date                              │              │
│           │      │    revenue_attributed                           │              │
│           │      │    conversion_type                              │              │
│           │      └─────────────────────────────────────────────---┘              │
│           │                                                                       │
│           │      ┌─────────────────────────────────────────────────┐             │
│           │      │               customer_products                  │             │
│           │      │───────────────────────────────────────────────  │             │
│           │      │ PK customer_product_id                           │             │
│           └──────┤ FK customer_id      ──► customers               │             │
│                  │ FK product_id       ──► products                │             │
│                  │ FK campaign_id      ──► campaigns               │             │
│                  │ FK channel_id       ──► campaign_channels       │             │
│                  │    acquisition_date                              │             │
│                  │    status                                        │             │
│                  │    product_value                                 │             │
│                  └─────────────────────────────────────────────────┘             │
└───────────────────────────────────────────────────────────────────────────────--─┘
```

---

## Cardinality Summary

| Relationship | Type | Business Meaning |
|---|---|---|
| products → campaigns | 1 : MANY | One product can be promoted by many campaigns |
| campaign_channels → campaigns | 1 : MANY | One channel can be used by many campaigns |
| customers → campaign_interactions | 1 : MANY | One customer can have many interactions |
| campaigns → campaign_interactions | 1 : MANY | One campaign can have many interactions |
| campaign_channels → campaign_interactions | 1 : MANY | One channel can have many interaction records |
| campaign_interactions → campaign_conversions | 1 : 0..1 | One interaction leads to at most one conversion |
| customers → customer_products | 1 : MANY | One customer can hold many products |
| products → customer_products | 1 : MANY | One product can be held by many customers |
| campaigns → customer_products | 1 : MANY | One campaign can drive acquisition of many products |

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Primary key type | `SERIAL` (auto-increment INT) | Simpler joins, better index performance than UUID for analytics queries |
| Business keys | Separate `*_code` columns | Allows surrogate PK to be stable while business codes can change |
| Soft deletes | `is_active` flag | Preserves history — never physically delete customer or product records |
| Audit columns | `created_at`, `updated_at` on all tables | Required for data lineage and reconciliation |
| Monetary values | `NUMERIC(15,2)` | Avoids floating-point rounding errors for financial figures |
| Dates | `DATE` for business dates, `TIMESTAMPTZ` for system events | Timezone-safe audit trail |
| Text enumerations | `VARCHAR` + `CHECK` constraints | Enforces valid values without rigid ENUM types (easier to extend) |
