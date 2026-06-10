# Business Requirements Document (BRD)
## Customer Campaign Analytics Platform (CCAP)
**Version:** 1.0  
**Date:** June 2026  
**Prepared by:** Marketing Analytics CoE  
**Stakeholders:** Head of Retail Marketing, Campaign Operations Manager, Digital Banking Team, CFO Office

---

## 1. Executive Summary

The retail bank currently runs marketing campaigns across five channels (Email, SMS, Branch Walk-In, Telemarketing, Digital/Web). Campaign performance tracking is fragmented across Excel spreadsheets, CRM exports, and manual reports. This results in:

- 3–5 day delays in campaign performance reporting
- Inability to identify underperforming campaigns in real time
- No customer-level conversion attribution
- No forward-looking customer propensity scoring

The **Customer Campaign Analytics Platform (CCAP)** will consolidate all campaign data into a single analytical layer, providing the marketing team with real-time dashboards, customer-level insights, and a machine learning propensity model to optimise future targeting.

---

## 2. Business Objectives

| ID | Objective | Priority |
|---|---|---|
| BO-01 | Reduce campaign reporting cycle from 5 days to same-day | HIGH |
| BO-02 | Identify top-performing channels by conversion rate and CPA | HIGH |
| BO-03 | Segment customers by responsiveness to improve targeting precision | HIGH |
| BO-04 | Attribute revenue to each campaign and calculate ROI | HIGH |
| BO-05 | Build a propensity model to predict which customers will convert | HIGH |
| BO-06 | Enable A/B test analysis for campaign variant comparison | MEDIUM |
| BO-07 | Identify customers at risk of churn (non-responders over N campaigns) | MEDIUM |
| BO-08 | Provide regional breakdown of campaign performance | LOW |

---

## 3. Scope

### In Scope
- Historical campaign data (3 years)
- 5 product lines: Credit Card, Savings Account, Fixed Deposit, Personal Loan, Home Loan
- 5 channels: Email, SMS, Branch, Telemarketing, Digital
- Customer demographic and behavioural attributes
- Campaign cost and revenue data
- Propensity scoring for next-best-offer

### Out of Scope
- Real-time streaming data pipelines (Phase 2)
- Mobile push notification channel (Phase 2)
- Integration with CRM system APIs (Phase 2)
- Customer complaints / NPS data

---

## 4. Key Performance Indicators (KPIs)

### 4.1 Campaign Effectiveness KPIs

| KPI | Definition | Formula | Target |
|---|---|---|---|
| **Conversion Rate** | % of targeted customers who accepted the offer | `Conversions / Contacts × 100` | ≥ 15% |
| **Cost Per Acquisition (CPA)** | Cost incurred per converted customer | `Total Campaign Cost / Conversions` | ≤ £45 |
| **Click-Through Rate (CTR)** | % of contacts who engaged with the campaign | `Clicks / Contacts × 100` | ≥ 25% |
| **Response Rate** | % of contacts who responded (any action) | `Responses / Contacts × 100` | ≥ 20% |
| **Campaign ROI** | Net return on campaign investment | `(Revenue - Cost) / Cost × 100` | ≥ 200% |

### 4.2 Revenue KPIs

| KPI | Definition | Formula | Target |
|---|---|---|---|
| **Revenue Per Campaign** | Total attributed revenue per campaign | `SUM(product_value) per campaign` | ≥ £500K |
| **Revenue Per Conversion** | Average product value of converted customer | `Total Revenue / Conversions` | Benchmark |
| **Lifetime Value Uplift** | Estimated CLV increase post-conversion | ML model output | > 0 |

### 4.3 Customer Segment KPIs

| KPI | Definition |
|---|---|
| **RFM Score** | Recency, Frequency, Monetary composite score |
| **Segment Conversion Rate** | Conversion rate per RFM cluster |
| **Propensity Score** | ML-predicted probability of conversion (0–1) |
| **Churn Risk Score** | % of customers non-responsive for 3+ campaigns |

### 4.4 Operational KPIs

| KPI | Definition |
|---|---|
| **Campaign Reach** | Total unique customers contacted |
| **Opt-Out Rate** | % of customers who unsubscribed |
| **Data Quality Score** | % of records passing validation checks |

---

## 5. Success Metrics

| Metric | Baseline (Current) | Target (Post-CCAP) |
|---|---|---|
| Reporting cycle time | 5 days | Same day (automated) |
| Campaign targeting accuracy | ~60% | ≥ 80% (propensity model) |
| Average CPA | £72 | ≤ £45 |
| Average Conversion Rate | 9% | ≥ 15% |
| Dashboard adoption | 0% (Excel only) | 100% of marketing team |
| A/B test turnaround | 2 weeks | 2 days |

---

## 6. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | System must store customer demographics (age, region, segment) | MUST |
| FR-02 | System must store campaign details (type, channel, start/end date, budget) | MUST |
| FR-03 | System must store interaction events (contact, response, conversion) | MUST |
| FR-04 | System must calculate KPIs at campaign, channel, and segment level | MUST |
| FR-05 | System must support historical trend analysis (MoM, QoQ, YoY) | MUST |
| FR-06 | System must produce customer-level propensity scores | MUST |
| FR-07 | System must support A/B variant analysis | SHOULD |
| FR-08 | System must include data quality validation and logging | MUST |

---

## 7. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Data refresh: Daily batch load by 07:00 AM |
| NFR-02 | Dashboard load time: < 5 seconds for standard views |
| NFR-03 | Data retention: 3 years of campaign history |
| NFR-04 | Access control: Role-based (Analyst, Manager, Executive) |
| NFR-05 | Audit trail: All data loads logged with timestamp and row counts |

---

## 8. Assumptions

1. Customer data is extracted from the core banking system as a nightly CSV dump.
2. Campaign interaction events are logged by the CRM platform.
3. Product revenue values are fixed per product type (not customer-specific LTV).
4. All monetary values are in GBP (£).
5. The data contains no PII in this portfolio version (synthetic data used).

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Data quality issues in source files | HIGH | HIGH | Validation layer + DQ dashboard |
| Low model accuracy on minority class | MEDIUM | HIGH | SMOTE oversampling + XGBoost tuning |
| Stakeholder adoption resistance | LOW | MEDIUM | Executive summary page in dashboard |
| PII compliance exposure | LOW | CRITICAL | Synthetic data, no real customer records |

---

*Document Status: Approved for Phase 1 Implementation*
