# KPI Definitions & Business Rules
## Customer Campaign Analytics Platform (CCAP)

> This document is the single source of truth for all metric definitions used across SQL, Python, and Power BI layers.
> Any change to a KPI formula must be approved by the Head of Marketing Analytics and updated here first.

---

## 1. Campaign Effectiveness KPIs

### 1.1 Conversion Rate (CVR)
- **Definition:** The percentage of contacted customers who accepted and activated a product offer.
- **Formula:** `CVR = (Total Conversions / Total Contacts Sent) × 100`
- **Granularity:** Campaign, Channel, Product, Customer Segment, Time Period
- **Threshold:** ≥ 15% is considered a successful campaign
- **SQL Reference:** `vw_campaign_performance.conversion_rate`
- **Business Rule:** A conversion is only counted when `interaction_outcome = 'Converted'` AND `conversion_date IS NOT NULL`

---

### 1.2 Cost Per Acquisition (CPA)
- **Definition:** The total marketing cost incurred to acquire one converted customer.
- **Formula:** `CPA = Total Campaign Cost (£) / Total Conversions`
- **Granularity:** Campaign, Channel
- **Threshold:** ≤ £45 is the approved marketing budget benchmark
- **SQL Reference:** `vw_campaign_roi.cost_per_acquisition`
- **Business Rule:** Total campaign cost includes media spend, production cost, and staff allocation. Excludes overhead.

---

### 1.3 Click-Through Rate (CTR)
- **Definition:** The percentage of contacted customers who engaged with the campaign (opened email, clicked link, answered call, etc.).
- **Formula:** `CTR = (Total Engagements / Total Contacts Sent) × 100`
- **Granularity:** Campaign, Channel
- **Threshold:** ≥ 25% (varies by channel — see Channel Benchmarks below)
- **SQL Reference:** `vw_campaign_performance.click_through_rate`
- **Business Rule:** Engagement is recorded when `interaction_type IN ('Opened', 'Clicked', 'Responded', 'Visited Branch')`

---

### 1.4 Response Rate
- **Definition:** The percentage of customers who took any measurable action (positive or negative) after being contacted.
- **Formula:** `Response Rate = (Total Responses / Total Contacts) × 100`
- **Note:** A response includes converted, declined, requested callback — not simply receiving the message.
- **SQL Reference:** `vw_campaign_performance.response_rate`

---

### 1.5 Opt-Out Rate
- **Definition:** The percentage of contacted customers who opted out (unsubscribed / DNC request).
- **Formula:** `Opt-Out Rate = (Total Opt-Outs / Total Contacts) × 100`
- **Threshold:** ≤ 2% — any campaign exceeding this triggers a compliance review
- **Business Rule:** Customers with `interaction_outcome = 'Opted Out'` are added to the DNC (Do Not Contact) list and excluded from all future campaigns.

---

## 2. Revenue & ROI KPIs

### 2.1 Campaign Revenue
- **Definition:** Total product value attributed to customers converted through a specific campaign.
- **Formula:** `Campaign Revenue = SUM(product_value) WHERE converted_by_campaign_id = X`
- **SQL Reference:** `vw_product_revenue.campaign_revenue`
- **Business Rule:** Revenue is attributed to the campaign that triggered the **first** interaction in the conversion path (first-touch attribution model).

---

### 2.2 Campaign ROI
- **Definition:** The net financial return on the marketing investment for a campaign.
- **Formula:** `ROI = ((Total Revenue - Total Cost) / Total Cost) × 100`
- **Threshold:** ≥ 200% ROI is the minimum acceptable return
- **SQL Reference:** `vw_campaign_roi.campaign_roi_pct`
- **Example:** Cost = £50,000, Revenue = £200,000 → ROI = 300%

---

### 2.3 Revenue Per Conversion
- **Definition:** Average product value generated per successfully converted customer.
- **Formula:** `Revenue Per Conversion = Total Campaign Revenue / Total Conversions`
- **SQL Reference:** `vw_campaign_roi.revenue_per_conversion`

---

## 3. Customer Segment KPIs

### 3.1 RFM Score
- **Definition:** A composite customer scoring model based on three dimensions:
  - **R (Recency):** Days since last campaign interaction (lower = better, scored 1–5)
  - **F (Frequency):** Number of campaign interactions in the past 12 months (higher = better, scored 1–5)
  - **M (Monetary):** Total product value held with the bank (higher = better, scored 1–5)
- **Formula:** `RFM_Score = R_Score × 100 + F_Score × 10 + M_Score`
- **Segments:**

| RFM Score Range | Segment Label | Strategy |
|---|---|---|
| 445–555 | Champions | Reward and upsell |
| 334–444 | Loyal Customers | Upsell to premium products |
| 223–333 | Potential Loyalists | Increase engagement frequency |
| 112–222 | At Risk | Re-engagement campaigns |
| 111 | Lost | Win-back or remove from list |

---

### 3.2 Propensity Score
- **Definition:** ML model output — the probability (0.0–1.0) that a specific customer will convert if targeted by a campaign for a given product.
- **Source:** XGBoost classifier, retrained quarterly
- **Threshold:** Score ≥ 0.65 → Include in campaign targeting list
- **SQL Reference:** `ccap.ml_propensity_scores.propensity_score`

---

## 4. Channel Benchmarks

| Channel | Benchmark CTR | Benchmark CVR | Benchmark CPA |
|---|---|---|---|
| Email | ≥ 22% | ≥ 12% | ≤ £30 |
| SMS | ≥ 18% | ≥ 10% | ≤ £20 |
| Branch | ≥ 45% | ≥ 35% | ≤ £80 |
| Telemarketing | ≥ 30% | ≥ 20% | ≤ £60 |
| Digital / Web | ≥ 28% | ≥ 15% | ≤ £25 |

---

## 5. Product Revenue Reference Values

| Product | Assumed First-Year Revenue (£) | Rationale |
|---|---|---|
| Credit Card | £450 | Annual fee + interchange income (first year) |
| Savings Account | £120 | Net interest margin on average £6,000 balance |
| Fixed Deposit | £380 | Net interest margin on average £10,000 deposit |
| Personal Loan | £1,200 | Net interest income on average £8,000 loan |
| Home Loan | £4,500 | Net interest income on average £150,000 mortgage |

> Note: These are simplified proxy revenue values for analytics purposes. Actual CLV models used in production would incorporate product tenure, attrition rates, and cross-sell probability.

---

## 6. Calculation Glossary

| Term | Definition |
|---|---|
| **Contact** | A customer who received a campaign communication |
| **Engagement** | A contact who took any measurable action (open, click, visit) |
| **Response** | A contact who provided explicit feedback (yes, no, callback) |
| **Conversion** | A contact who accepted the offer and activated the product |
| **Opt-Out** | A contact who requested removal from future campaign lists |
| **DNC** | Do Not Contact — regulatory and preference-based exclusion list |
| **First-Touch Attribution** | Revenue credited to the campaign that initiated the first interaction |
| **CPA** | Cost Per Acquisition — cost per converted customer |
| **ROI** | Return on Investment — net revenue return as % of campaign cost |

---

*Last updated: June 2026 | Owner: Marketing Analytics CoE*
