"""
CCAP — Phase 3: Synthetic Data Generation
==========================================
Generates realistic UK retail banking data for the Customer Campaign Analytics Platform.

Output (7 CSV files → data/raw/):
    customers.csv              ~10,000 rows
    products.csv                    10 rows
    campaign_channels.csv            5 rows
    campaigns.csv               ~50 rows
    campaign_interactions.csv  ~100,000 rows
    campaign_conversions.csv    ~10,000 rows (derived)
    customer_products.csv       ~10,000 rows (derived)

Run:
    python scripts/ingestion/generate_data.py
"""

import sys
import os
import yaml
import random
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    from config.logging_config import get_logger
    logger = get_logger("generate_data")
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    logger = logging.getLogger("generate_data")


# ─────────────────────────────────────────────────────────────────────────────
# REFERENCE DATA — fixed lookup values
# ─────────────────────────────────────────────────────────────────────────────

MALE_FIRST_NAMES = [
    "James", "Oliver", "Harry", "Jack", "George", "Noah", "Charlie", "Jacob",
    "Alfie", "Freddie", "Oscar", "Henry", "Archie", "Leo", "Arthur", "Ethan",
    "Thomas", "Joshua", "William", "Samuel", "Muhammad", "Rajan", "Arjun",
    "Daniel", "Adam", "Liam", "Lucas", "Elijah", "Nathan", "Kieran",
    "Patrick", "Sean", "Callum", "Ryan", "Connor", "Dylan", "Alex", "Ben",
]

FEMALE_FIRST_NAMES = [
    "Olivia", "Amelia", "Isla", "Ava", "Mia", "Isabella", "Sophie",
    "Poppy", "Emily", "Ella", "Grace", "Lily", "Evie", "Sophia", "Freya",
    "Charlotte", "Alice", "Florence", "Daisy", "Layla", "Priya", "Aisha",
    "Emma", "Hannah", "Chloe", "Lucy", "Zoe", "Sarah", "Jessica", "Lauren",
    "Natasha", "Yasmin", "Fatima", "Ananya", "Mei", "Rachel", "Kate",
]

LAST_NAMES = [
    "Smith", "Jones", "Williams", "Taylor", "Brown", "Davies", "Evans",
    "Wilson", "Thomas", "Roberts", "Johnson", "Lewis", "Walker", "Robinson",
    "Wood", "Thompson", "White", "Watson", "Jackson", "Wright", "Green",
    "Harris", "Cooper", "King", "Martin", "Clarke", "Hall", "Allen", "Scott",
    "Turner", "Mitchell", "Morgan", "Hughes", "Hill", "Patel", "Shah",
    "Khan", "Ahmed", "Singh", "Kumar", "Sharma", "Ali", "Begum", "Hussain",
    "Anderson", "Campbell", "Stewart", "Murray", "Morrison", "Reid",
]

# Region → cities (weighted toward London and major hubs)
REGIONS = {
    "Greater London":           (["London"],                                    0.22),
    "South East":               (["Brighton", "Southampton", "Oxford",
                                  "Reading", "Portsmouth"],                     0.12),
    "North West":               (["Manchester", "Liverpool", "Bolton",
                                  "Salford", "Blackpool"],                      0.11),
    "West Midlands":            (["Birmingham", "Coventry", "Wolverhampton",
                                  "Stoke-on-Trent"],                            0.09),
    "Yorkshire and the Humber": (["Leeds", "Sheffield", "Bradford",
                                  "Hull", "York"],                              0.08),
    "East of England":          (["Cambridge", "Norwich", "Ipswich",
                                  "Peterborough"],                              0.07),
    "South West":               (["Bristol", "Plymouth", "Exeter", "Bath"],     0.07),
    "East Midlands":            (["Nottingham", "Leicester", "Derby"],          0.06),
    "North East":               (["Newcastle", "Sunderland", "Durham"],         0.05),
    "Scotland":                 (["Glasgow", "Edinburgh", "Aberdeen"],          0.06),
    "Wales":                    (["Cardiff", "Swansea", "Newport"],             0.04),
    "Northern Ireland":         (["Belfast", "Derry"],                          0.03),
}

OCCUPATIONS_BY_SEGMENT = {
    "Mass Market": [
        "Retail Worker", "Driver", "Care Worker", "Warehouse Operative",
        "Admin Assistant", "Customer Service Agent", "Receptionist", "Chef",
        "Security Guard", "Factory Worker", "Delivery Driver", "Hairdresser",
        "Mechanic", "Teaching Assistant", "Cleaner",
    ],
    "Affluent": [
        "Software Engineer", "Data Analyst", "Nurse", "Accountant",
        "Marketing Manager", "HR Manager", "Civil Servant", "Pharmacist",
        "Financial Advisor", "Project Manager", "Sales Manager", "Teacher",
        "Physiotherapist", "Police Officer", "Architect",
    ],
    "Premier": [
        "Doctor", "Lawyer", "Director", "Senior Manager", "Consultant",
        "IT Director", "Finance Manager", "Surgeon", "Chartered Accountant",
        "Investment Analyst", "Barrister", "Professor", "Head of Department",
        "Senior Engineer", "Solicitor",
    ],
    "Private Banking": [
        "CEO", "CFO", "Managing Director", "Investment Banker", "Partner",
        "Hedge Fund Manager", "Property Developer", "Business Owner",
        "Private Equity Analyst", "Senior Consultant",
    ],
}

CAMPAIGN_MANAGERS = [
    "Sarah Mitchell", "James Okafor", "Priya Sharma", "Tom Henderson",
    "Lucy Chen", "Mark Davies", "Aisha Rahman", "David Thompson",
]

# Outcome probability distributions per channel
# Keys: outcomes; values: probability weights (will be normalised)
OUTCOME_PROBS = {
    "Email": {
        "No Response":        0.52,
        "Not Interested":     0.18,
        "Opted Out":          0.03,
        "Interested":         0.10,
        "Callback Requested": 0.05,
        "Converted":          0.12,
    },
    "SMS": {
        "No Response":        0.58,
        "Not Interested":     0.16,
        "Opted Out":          0.05,
        "Interested":         0.08,
        "Callback Requested": 0.03,
        "Converted":          0.10,
    },
    "Branch": {
        "Not Interested":     0.18,
        "Interested":         0.20,
        "Callback Requested": 0.10,
        "Declined":           0.07,
        "Converted":          0.35,
        "No Response":        0.10,
    },
    "Telemarketing": {
        "No Response":        0.32,
        "Not Interested":     0.25,
        "Opted Out":          0.05,
        "Interested":         0.14,
        "Callback Requested": 0.05,
        "Declined":           0.01,
        "Converted":          0.18,
    },
    "Digital": {
        "No Response":        0.48,
        "Not Interested":     0.20,
        "Opted Out":          0.02,
        "Interested":         0.13,
        "Callback Requested": 0.03,
        "Converted":          0.14,
    },
}

# Segment conversion multiplier (relative boost for higher-value segments)
SEGMENT_CONVERSION_BOOST = {
    "Mass Market":    1.00,
    "Affluent":       1.25,
    "Premier":        1.40,
    "Private Banking":1.55,
}

# interaction_type assigned based on channel + outcome
INTERACTION_TYPE_MAP = {
    "Email": {
        "Converted": "Clicked", "Interested": "Opened",
        "Not Interested": "Opened", "Callback Requested": "Opened",
        "No Response": "Delivered", "Opted Out": "Opened",
        "Declined": "Clicked", "Pending": "Sent",
    },
    "SMS": {
        "Converted": "Opened", "Interested": "Opened",
        "Not Interested": "Opened", "Callback Requested": "Opened",
        "No Response": "Delivered", "Opted Out": "Opened",
        "Declined": "Opened", "Pending": "Sent",
    },
    "Branch": {
        k: "Visited Branch" for k in
        ["Converted","Interested","Not Interested","Callback Requested",
         "No Response","Opted Out","Declined","Pending"]
    },
    "Telemarketing": {
        k: "Called" for k in
        ["Converted","Interested","Not Interested","Callback Requested",
         "No Response","Opted Out","Declined","Pending"]
    },
    "Digital": {
        "Converted": "Clicked", "Interested": "Web Visit",
        "Not Interested": "Web Visit", "Callback Requested": "Web Visit",
        "No Response": "Web Visit", "Opted Out": "Web Visit",
        "Declined": "Clicked", "Pending": "Web Visit",
    },
}

# Product revenue proxies (£ first-year, matches 03_seed_reference_data.sql)
PRODUCT_DEFINITIONS = [
    (1, "CC-CLASSIC",    "Classic Credit Card",       "Credit Card",    450.00,  18),
    (2, "CC-PLATINUM",   "Platinum Credit Card",      "Credit Card",    850.00,  21),
    (3, "SA-EASY",       "Easy Access Savings",       "Savings Account",120.00,  18),
    (4, "SA-REGULAR",    "Regular Saver Account",     "Savings Account",180.00,  18),
    (5, "FD-12M",        "12-Month Fixed Deposit",    "Fixed Deposit",  380.00,  18),
    (6, "FD-24M",        "24-Month Fixed Deposit",    "Fixed Deposit",  520.00,  18),
    (7, "PL-PERSONAL",   "Personal Loan",             "Personal Loan", 1200.00,  18),
    (8, "PL-CAR",        "Car Finance Loan",          "Personal Loan", 1800.00,  18),
    (9, "HL-RESIDENTIAL","Residential Mortgage",      "Home Loan",     4500.00,  18),
    (10,"HL-BTL",        "Buy-to-Let Mortgage",       "Home Loan",     6000.00,  21),
]

CHANNEL_DEFINITIONS = [
    (1, "Email",         22.00, 12.00,  30.00),
    (2, "SMS",           18.00, 10.00,  20.00),
    (3, "Branch",        45.00, 35.00,  80.00),
    (4, "Telemarketing", 30.00, 20.00,  60.00),
    (5, "Digital",       28.00, 15.00,  25.00),
]

# Mapping channel_name → channel_id
CHANNEL_ID = {name: cid for cid, name, *_ in CHANNEL_DEFINITIONS}

# Product value ranges per category (£ — represents balance/outstanding amount)
PRODUCT_VALUE_RANGES = {
    "Credit Card":     (500,    10_000),
    "Savings Account": (1_000,  60_000),
    "Fixed Deposit":   (5_000, 120_000),
    "Personal Loan":   (2_000,  25_000),
    "Home Loan":      (80_000, 600_000),
}


# ─────────────────────────────────────────────────────────────────────────────
# GENERATOR CLASS
# ─────────────────────────────────────────────────────────────────────────────

class CCAPDataGenerator:
    def __init__(self, seed: int = 42, n_customers: int = 10_000,
                 n_campaigns: int = 50, n_interactions: int = 100_000,
                 output_dir: str = "data/raw"):
        self.seed = seed
        self.n_customers = n_customers
        self.n_campaigns = n_campaigns
        self.n_interactions = n_interactions
        self.output_dir = ROOT / output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        np.random.seed(seed)
        random.seed(seed)

        # Shared state built progressively
        self.products_df   = None
        self.channels_df   = None
        self.customers_df  = None
        self.campaigns_df  = None
        self.interactions_df = None
        self.conversions_df  = None
        self.cp_df           = None

    # ─────────────────────────────────────────────────────────────────────
    # 1. PRODUCTS
    # ─────────────────────────────────────────────────────────────────────
    def _build_products(self) -> pd.DataFrame:
        df = pd.DataFrame(
            PRODUCT_DEFINITIONS,
            columns=["product_id","product_code","product_name",
                     "product_category","revenue_value","min_eligibility_age"]
        )
        df["product_description"] = "Synthetic product — see KPI_definitions.md"
        df["is_active"] = True
        logger.info("Products: %d rows", len(df))
        return df

    # ─────────────────────────────────────────────────────────────────────
    # 2. CHANNELS
    # ─────────────────────────────────────────────────────────────────────
    def _build_channels(self) -> pd.DataFrame:
        rows = []
        descs = {
            "Email":         "Outbound email campaigns via the bank CRM platform",
            "SMS":           "SMS text message campaigns to opted-in mobile numbers",
            "Branch":        "In-branch face-to-face conversations",
            "Telemarketing": "Outbound telephone calls by the contact centre",
            "Digital":       "Online display ads, web personalisation, social retargeting",
        }
        for cid, name, ctr, cvr, cpa in CHANNEL_DEFINITIONS:
            rows.append({
                "channel_id": cid, "channel_name": name,
                "channel_description": descs[name],
                "benchmark_ctr": ctr, "benchmark_cvr": cvr,
                "benchmark_cpa": cpa, "is_active": True,
            })
        df = pd.DataFrame(rows)
        logger.info("Channels: %d rows", len(df))
        return df

    # ─────────────────────────────────────────────────────────────────────
    # 3. CUSTOMERS
    # ─────────────────────────────────────────────────────────────────────
    def _generate_customers(self) -> pd.DataFrame:
        n = self.n_customers
        logger.info("Generating %d customers ...", n)

        # --- Segment distribution ---
        segments    = ["Mass Market", "Affluent", "Premier", "Private Banking"]
        seg_weights = [0.68, 0.22, 0.08, 0.02]
        segment     = np.random.choice(segments, size=n, p=seg_weights)

        # --- Gender ---
        gender = np.random.choice(
            ["Male", "Female", "Non-Binary", "Prefer Not to Say"],
            size=n, p=[0.48, 0.48, 0.025, 0.015]
        )

        # --- Names ---
        first_names, last_names = [], []
        for g in gender:
            pool = MALE_FIRST_NAMES if g == "Male" else FEMALE_FIRST_NAMES
            first_names.append(random.choice(pool))
            last_names.append(random.choice(LAST_NAMES))

        # --- Date of birth (age 18–79, skewed toward 30–55) ---
        today = date.today()
        age   = np.clip(np.random.normal(42, 13, n).astype(int), 18, 79)
        dob   = [today - timedelta(days=int(a * 365.25)) for a in age]

        # --- Region / City ---
        region_names = list(REGIONS.keys())
        region_weights = [REGIONS[r][1] for r in region_names]
        chosen_regions = np.random.choice(region_names, size=n, p=region_weights)
        cities  = [random.choice(REGIONS[r][0]) for r in chosen_regions]
        postcodes = [
            random.choice("ABCDEFGHIJKLMNOPRSTW")
            + random.choice("ABCDEFGHIJKLMNOPRSTW")
            + str(random.randint(1, 99)) for _ in range(n)
        ]

        # --- Income (lognormal, correlated with segment) ---
        income_params = {
            "Mass Market":    (10.25, 0.35),   # mean ~£28K
            "Affluent":       (11.05, 0.30),   # mean ~£63K
            "Premier":        (11.85, 0.28),   # mean ~£140K
            "Private Banking":(12.75, 0.35),   # mean ~£344K
        }
        annual_income = np.array([
            round(np.random.lognormal(*income_params[s]), 2) for s in segment
        ])

        # --- Employment status (age-correlated) ---
        def pick_employment(a):
            if a < 25:
                return np.random.choice(["Employed","Student","Part-Time","Unemployed"],
                                         p=[0.35,0.40,0.15,0.10])
            elif a < 55:
                return np.random.choice(["Employed","Self-Employed","Part-Time","Unemployed"],
                                         p=[0.70,0.18,0.08,0.04])
            elif a < 65:
                return np.random.choice(["Employed","Self-Employed","Retired","Part-Time"],
                                         p=[0.45,0.20,0.25,0.10])
            else:
                return np.random.choice(["Retired","Part-Time","Self-Employed"],
                                         p=[0.75,0.15,0.10])
        employment_status = [pick_employment(a) for a in age]

        # --- Credit score (correlated with income and segment) ---
        def credit_for_segment(seg):
            params = {
                "Mass Market":    (630,  80),
                "Affluent":       (720,  60),
                "Premier":        (790,  45),
                "Private Banking":(850,  35),
            }
            mu, sd = params[seg]
            return int(np.clip(np.random.normal(mu, sd), 300, 999))
        credit_score = [credit_for_segment(s) for s in segment]

        # --- Acquisition date (3-year window, uniform) ---
        start_acq = date(2021, 1, 1)
        end_acq   = date(2024, 12, 31)
        span_days = (end_acq - start_acq).days
        acq_date  = [start_acq + timedelta(days=int(d))
                     for d in np.random.randint(0, span_days, n)]

        # --- Acquisition channel (for pre-existing customers) ---
        acq_channel = np.random.choice([1, 2, 3, 4, 5], size=n, p=[0.30, 0.15, 0.25, 0.20, 0.10])

        # --- DNC flag (2% of customers) ---
        is_dnc = np.random.random(n) < 0.02

        # --- Active flag (97% active) ---
        is_active = np.random.random(n) < 0.97

        df = pd.DataFrame({
            "customer_id":            range(1, n + 1),
            "customer_code":          [f"CUST-{i:05d}" for i in range(1, n + 1)],
            "first_name":             first_names,
            "last_name":              last_names,
            "date_of_birth":          dob,
            "gender":                 gender,
            "email":                  [
                f"{fn.lower()}.{ln.lower()}{i}@example.com"
                for i, (fn, ln) in enumerate(zip(first_names, last_names), 1)
            ],
            "phone":                  [f"07{random.randint(100_000_000, 999_999_999)}" for _ in range(n)],
            "region":                 chosen_regions,
            "city":                   cities,
            "postcode":               postcodes,
            "customer_segment":       segment,
            "employment_status":      employment_status,
            "annual_income":          annual_income,
            "credit_score":           credit_score,
            "number_of_products":     0,   # updated after conversions
            "is_active":              is_active,
            "is_dnc":                 is_dnc,
            "acquisition_date":       acq_date,
            "acquisition_channel_id": acq_channel,
        })

        logger.info("Customers generated: %d rows", len(df))
        return df

    # ─────────────────────────────────────────────────────────────────────
    # 4. CAMPAIGNS
    # ─────────────────────────────────────────────────────────────────────
    def _generate_campaigns(self) -> pd.DataFrame:
        n = self.n_campaigns
        logger.info("Generating %d campaigns ...", n)

        products  = self.products_df
        channels  = self.channels_df

        campaign_types = ["Acquisition", "Retention", "Cross-Sell",
                          "Upsell", "Win-Back", "Awareness"]
        type_weights   = [0.35, 0.20, 0.20, 0.10, 0.10, 0.05]

        segments = ["All", "Mass Market", "Affluent", "Premier", "Private Banking"]

        records = []
        for i in range(1, n + 1):
            camp_type  = np.random.choice(campaign_types, p=type_weights)
            product    = products.sample(1).iloc[0]
            channel    = channels.sample(1).iloc[0]

            # Campaign duration varies by type
            duration_map = {
                "Acquisition": (45, 90), "Retention": (30, 60),
                "Cross-Sell":  (30, 60), "Upsell":    (21, 45),
                "Win-Back":    (14, 30), "Awareness": (60, 90),
            }
            lo, hi   = duration_map[camp_type]
            duration = random.randint(lo, hi)

            # Start dates spread across Jan 2023 – Sep 2025
            start_epoch = date(2023, 1, 1)
            end_epoch   = date(2025, 9, 1)
            span        = (end_epoch - start_epoch).days
            start       = start_epoch + timedelta(days=random.randint(0, span))
            end         = start + timedelta(days=duration)

            # Budget and contacts
            contacts_map = {
                "Acquisition": (2000, 6000), "Retention":  (1000, 3000),
                "Cross-Sell":  (1500, 4000), "Upsell":     (800,  2000),
                "Win-Back":    (500,  1500), "Awareness":  (3000, 8000),
            }
            contacts = random.randint(*contacts_map[camp_type])
            budget   = round(contacts * random.uniform(8, 25), 2)

            # Target segment — Acquisition usually targets All or Mass Market
            seg_options = {
                "Acquisition": (["All", "Mass Market", "Affluent"], [0.5, 0.3, 0.2]),
                "Retention":   (["All", "Mass Market", "Affluent", "Premier"], [0.3,0.3,0.25,0.15]),
                "Cross-Sell":  (["Affluent", "Premier", "All"], [0.4, 0.35, 0.25]),
                "Upsell":      (["Premier", "Affluent", "Private Banking"], [0.4,0.4,0.2]),
                "Win-Back":    (["Mass Market", "Affluent", "All"], [0.5,0.3,0.2]),
                "Awareness":   (["All"], [1.0]),
            }
            seg_pool, seg_p = seg_options[camp_type]
            target_seg = np.random.choice(seg_pool, p=seg_p)

            ab_enabled = random.random() < 0.30   # 30% of campaigns run A/B tests

            year  = start.year
            q     = (start.month - 1) // 3 + 1
            ccode = (f"CMP-{year}-Q{q}-"
                     f"{product['product_code'][:3]}-"
                     f"{channel['channel_name'][:3].upper()}-"
                     f"{i:03d}")

            # Status based on end_date relative to today
            today = date.today()
            if end < today:
                status = "Completed"
            elif start <= today <= end:
                status = "Active"
            else:
                status = "Planned"

            records.append({
                "campaign_id":      i,
                "campaign_code":    ccode,
                "campaign_name":    (f"{camp_type} — {product['product_name']} "
                                     f"({channel['channel_name']}) {year}"),
                "campaign_type":    camp_type,
                "product_id":       int(product["product_id"]),
                "channel_id":       int(channel["channel_id"]),
                "target_segment":   target_seg,
                "start_date":       start,
                "end_date":         end,
                "total_budget":     budget,
                "contacts_target":  contacts,
                "ab_test_enabled":  ab_enabled,
                "campaign_manager": random.choice(CAMPAIGN_MANAGERS),
                "status":           status,
            })

        df = pd.DataFrame(records)
        logger.info("Campaigns generated: %d rows", len(df))
        return df

    # ─────────────────────────────────────────────────────────────────────
    # 5. CAMPAIGN INTERACTIONS
    # ─────────────────────────────────────────────────────────────────────
    def _generate_interactions(self) -> pd.DataFrame:
        logger.info("Generating ~%d campaign interactions ...", self.n_interactions)

        customers = self.customers_df
        campaigns = self.campaigns_df
        channels  = self.channels_df

        # Build channel_name lookup
        ch_name = dict(zip(channels["channel_id"], channels["channel_name"]))

        # Distribute total interaction budget across campaigns proportional
        # to contacts_target
        total_target = campaigns["contacts_target"].sum()
        campaigns    = campaigns.copy()
        campaigns["alloc"] = (
            campaigns["contacts_target"] / total_target * self.n_interactions
        ).astype(int)
        # Give leftover rows to the largest campaign
        leftover = self.n_interactions - campaigns["alloc"].sum()
        campaigns.loc[campaigns["contacts_target"].idxmax(), "alloc"] += leftover

        # Targetable customers (active, not DNC)
        eligible = customers[customers["is_active"] & ~customers["is_dnc"]].copy()

        all_interactions = []
        interaction_id   = 1

        for _, camp in campaigns.iterrows():
            n_contacts = int(camp["alloc"])
            if n_contacts == 0:
                continue

            cid        = int(camp["campaign_id"])
            chan_id    = int(camp["channel_id"])
            chan_name  = ch_name[chan_id]
            target_seg = camp["target_segment"]
            ab_enabled = bool(camp["ab_test_enabled"])
            start_dt   = pd.Timestamp(camp["start_date"]).date()
            end_dt     = pd.Timestamp(camp["end_date"]).date()
            span_days  = max((end_dt - start_dt).days, 1)

            # Filter by segment
            if target_seg != "All":
                pool = eligible[eligible["customer_segment"] == target_seg]
                if len(pool) < n_contacts:
                    pool = eligible    # fall back to all if not enough in segment
            else:
                pool = eligible

            # Sample unique customers — cap at pool size
            n_contacts = min(n_contacts, len(pool))
            sampled    = pool.sample(n=n_contacts, replace=False)

            # Outcome probabilities (apply segment boost to conversion weight)
            base_probs = OUTCOME_PROBS[chan_name].copy()
            outcomes   = list(base_probs.keys())
            weights    = np.array([base_probs[o] for o in outcomes], dtype=float)

            # Per-customer boost: adjust conversion weight by segment
            # We'll vectorise using a group-by approach
            seg_boosts = sampled["customer_segment"].map(SEGMENT_CONVERSION_BOOST).values
            conv_idx   = outcomes.index("Converted")

            # Build matrix: (n_contacts × n_outcomes)
            weight_matrix = np.tile(weights, (n_contacts, 1))
            weight_matrix[:, conv_idx] *= seg_boosts
            # Renormalise each row
            weight_matrix = weight_matrix / weight_matrix.sum(axis=1, keepdims=True)

            # Vectorised multinomial draw
            chosen_outcome_idx = np.array([
                np.random.choice(len(outcomes), p=weight_matrix[r])
                for r in range(n_contacts)
            ])
            chosen_outcomes = [outcomes[i] for i in chosen_outcome_idx]

            # Interaction dates (random within campaign window)
            interact_dates = [
                start_dt + timedelta(days=random.randint(0, span_days))
                for _ in range(n_contacts)
            ]

            # Response dates (1–7 days after interaction for responded rows)
            responded_outcomes = {
                "Interested","Converted","Not Interested",
                "Callback Requested","Opted Out","Declined"
            }
            response_dates = [
                (d + timedelta(days=random.randint(1, 7)))
                if o in responded_outcomes else None
                for d, o in zip(interact_dates, chosen_outcomes)
            ]

            # interaction_type derived from channel + outcome
            type_map = INTERACTION_TYPE_MAP[chan_name]
            interaction_types = [type_map.get(o, "Sent") for o in chosen_outcomes]

            # A/B variant
            if ab_enabled:
                ab_variants = np.random.choice(["A", "B"], size=n_contacts, p=[0.5, 0.5]).tolist()
            else:
                ab_variants = [None] * n_contacts

            batch = pd.DataFrame({
                "interaction_id":    range(interaction_id, interaction_id + n_contacts),
                "campaign_id":       cid,
                "customer_id":       sampled["customer_id"].values,
                "channel_id":        chan_id,
                "interaction_date":  interact_dates,
                "interaction_type":  interaction_types,
                "interaction_outcome": chosen_outcomes,
                "response_date":     response_dates,
                "ab_variant":        ab_variants,
            })
            all_interactions.append(batch)
            interaction_id += n_contacts

        df = pd.concat(all_interactions, ignore_index=True)
        df["interaction_id"] = range(1, len(df) + 1)   # reassign sequential IDs

        logger.info("Interactions generated: %d rows  |  overall CVR: %.1f%%",
                    len(df),
                    (df["interaction_outcome"] == "Converted").mean() * 100)
        return df

    # ─────────────────────────────────────────────────────────────────────
    # 6. CAMPAIGN CONVERSIONS (derived from interactions)
    # ─────────────────────────────────────────────────────────────────────
    def _generate_conversions(self) -> pd.DataFrame:
        logger.info("Deriving campaign conversions ...")

        interactions = self.interactions_df
        campaigns    = self.campaigns_df
        products     = self.products_df

        converted = interactions[
            interactions["interaction_outcome"] == "Converted"
        ].copy()

        # Join product_id from campaign
        camp_product = campaigns[["campaign_id", "product_id"]].set_index("campaign_id")
        converted    = converted.join(camp_product, on="campaign_id")

        # Join revenue_value from products
        prod_rev = products[["product_id", "revenue_value",
                              "product_category"]].set_index("product_id")
        converted = converted.join(prod_rev, on="product_id")

        # Determine conversion_type per customer
        # Sort by response_date so we process chronologically
        converted = converted.sort_values(["customer_id",
                                           "response_date",
                                           "interaction_date"])

        # Track which categories each customer already has
        customer_categories: dict[int, set] = {}
        conversion_types = []

        for _, row in converted.iterrows():
            cust_id  = int(row["customer_id"])
            category = row["product_category"]
            held     = customer_categories.setdefault(cust_id, set())

            if not held:
                ctype = "New"
            elif category in held:
                ctype = "Upsell"
            else:
                ctype = "Cross-Sell"

            held.add(category)
            conversion_types.append(ctype)

        converted["conversion_type"] = conversion_types
        converted["conversion_date"] = converted["response_date"].fillna(
            converted["interaction_date"]
        )

        df = pd.DataFrame({
            "conversion_id":      range(1, len(converted) + 1),
            "interaction_id":     converted["interaction_id"].values,
            "campaign_id":        converted["campaign_id"].values,
            "customer_id":        converted["customer_id"].values,
            "product_id":         converted["product_id"].values,
            "channel_id":         converted["channel_id"].values,
            "conversion_date":    converted["conversion_date"].values,
            "revenue_attributed": converted["revenue_value"].values,
            "conversion_type":    converted["conversion_type"].values,
            "ab_variant":         converted["ab_variant"].values,
        })

        logger.info("Conversions generated: %d rows", len(df))
        return df

    # ─────────────────────────────────────────────────────────────────────
    # 7. CUSTOMER PRODUCTS (derived from conversions)
    # ─────────────────────────────────────────────────────────────────────
    def _generate_customer_products(self) -> pd.DataFrame:
        logger.info("Deriving customer_products ...")

        conversions = self.conversions_df
        products    = self.products_df

        prod_category = products.set_index("product_id")["product_category"]

        rows = []
        for i, row in conversions.iterrows():
            cat        = prod_category.loc[int(row["product_id"])]
            val_lo, val_hi = PRODUCT_VALUE_RANGES[cat]
            product_val = round(random.uniform(val_lo, val_hi), 2)

            # ~5% of products are closed after acquisition
            status  = "Closed" if random.random() < 0.05 else "Active"
            conv_dt = pd.Timestamp(row["conversion_date"]).date()
            closure = None
            if status == "Closed":
                closure = conv_dt + timedelta(days=random.randint(60, 730))

            rows.append({
                "customer_product_id": i + 1,
                "customer_id":         int(row["customer_id"]),
                "product_id":          int(row["product_id"]),
                "campaign_id":         int(row["campaign_id"]),
                "channel_id":          int(row["channel_id"]),
                "acquisition_date":    conv_dt,
                "closure_date":        closure,
                "status":              status,
                "product_value":       product_val,
            })

        df = pd.DataFrame(rows)
        df["customer_product_id"] = range(1, len(df) + 1)

        logger.info("Customer products generated: %d rows", len(df))
        return df

    # ─────────────────────────────────────────────────────────────────────
    # 8. UPDATE customer.number_of_products
    # ─────────────────────────────────────────────────────────────────────
    def _update_product_counts(self) -> None:
        counts = (
            self.cp_df[self.cp_df["status"] == "Active"]
            .groupby("customer_id")["customer_product_id"]
            .count()
            .rename("n")
        )
        self.customers_df = self.customers_df.set_index("customer_id")
        self.customers_df["number_of_products"] = (
            counts.reindex(self.customers_df.index).fillna(0).astype(int)
        )
        self.customers_df = self.customers_df.reset_index()

    # ─────────────────────────────────────────────────────────────────────
    # SAVE
    # ─────────────────────────────────────────────────────────────────────
    def _save(self, df: pd.DataFrame, filename: str) -> None:
        path = self.output_dir / filename
        df.to_csv(path, index=False)
        logger.info("Saved %-40s  %7d rows  ->  %s", filename, len(df), path)

    # ─────────────────────────────────────────────────────────────────────
    # ORCHESTRATOR
    # ─────────────────────────────────────────────────────────────────────
    def run(self) -> None:
        logger.info("=" * 60)
        logger.info("CCAP Synthetic Data Generator  (seed=%d)", self.seed)
        logger.info("=" * 60)

        self.products_df      = self._build_products()
        self.channels_df      = self._build_channels()
        self.customers_df     = self._generate_customers()
        self.campaigns_df     = self._generate_campaigns()
        self.interactions_df  = self._generate_interactions()
        self.conversions_df   = self._generate_conversions()
        self.cp_df            = self._generate_customer_products()
        self._update_product_counts()

        self._save(self.products_df,     "products.csv")
        self._save(self.channels_df,     "campaign_channels.csv")
        self._save(self.customers_df,    "customers.csv")
        self._save(self.campaigns_df,    "campaigns.csv")
        self._save(self.interactions_df, "campaign_interactions.csv")
        self._save(self.conversions_df,  "campaign_conversions.csv")
        self._save(self.cp_df,           "customer_products.csv")

        logger.info("=" * 60)
        logger.info("Generation complete. Files written to: %s", self.output_dir)
        logger.info("=" * 60)
        self._print_summary()

    def _print_summary(self) -> None:
        interactions = self.interactions_df
        conversions  = self.conversions_df
        campaigns    = self.campaigns_df

        total_contacts   = len(interactions)
        total_converted  = len(conversions)
        overall_cvr      = total_converted / total_contacts * 100
        total_revenue    = conversions["revenue_attributed"].sum()
        total_budget     = campaigns["total_budget"].sum()
        roi              = (total_revenue - total_budget) / total_budget * 100

        print("\n" + "=" * 60)
        print("  CCAP DATA GENERATION SUMMARY")
        print("=" * 60)
        print(f"  Customers        : {len(self.customers_df):>10,}")
        print(f"  Products         : {len(self.products_df):>10,}")
        print(f"  Channels         : {len(self.channels_df):>10,}")
        print(f"  Campaigns        : {len(campaigns):>10,}")
        print(f"  Interactions     : {total_contacts:>10,}")
        print(f"  Conversions      : {total_converted:>10,}")
        print(f"  Overall CVR      : {overall_cvr:>9.1f}%")
        print(f"  Total Revenue    : £{total_revenue:>10,.0f}")
        print(f"  Total Budget     : £{total_budget:>10,.0f}")
        print(f"  Overall ROI      : {roi:>9.0f}%")
        print("=" * 60)

        # Conversion rate by channel
        ch_name = dict(zip(self.channels_df["channel_id"],
                           self.channels_df["channel_name"]))
        print("\n  Conversion Rate by Channel")
        print("  " + "-" * 35)
        for chan_id, grp in interactions.groupby("channel_id"):
            cvr = (grp["interaction_outcome"] == "Converted").mean() * 100
            print(f"  {ch_name.get(chan_id, chan_id):<16}: {cvr:>5.1f}%")

        # Conversion rate by segment
        seg_map = dict(zip(self.customers_df["customer_id"],
                           self.customers_df["customer_segment"]))
        interactions_seg = interactions.copy()
        interactions_seg["segment"] = interactions_seg["customer_id"].map(seg_map)
        print("\n  Conversion Rate by Customer Segment")
        print("  " + "-" * 35)
        for seg, grp in interactions_seg.groupby("segment"):
            cvr = (grp["interaction_outcome"] == "Converted").mean() * 100
            print(f"  {seg:<18}: {cvr:>5.1f}%")
        print()


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Load config if available, otherwise use defaults
    cfg_path = ROOT / "config" / "config.yaml"
    cfg = {}
    if cfg_path.exists():
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f).get("data_generation", {})

    generator = CCAPDataGenerator(
        seed           = cfg.get("random_seed",      42),
        n_customers    = cfg.get("n_customers",   10_000),
        n_campaigns    = cfg.get("n_campaigns",       50),
        n_interactions = cfg.get("n_interactions", 100_000),
        output_dir     = "data/raw",
    )
    generator.run()
