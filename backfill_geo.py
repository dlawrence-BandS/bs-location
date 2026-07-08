"""
Location Performance Dashboard - BigQuery setup & backfill
============================================================
Creates and populates:
  commanding-air-450109-p0.geo_dashboard.tv_region_map     (UK city -> ITV/BARB TV macro region + lat/lng)
  commanding-air-450109-p0.geo_dashboard.geo_daily         (date x country x region x city x tv_region, all key metrics)
  commanding-air-450109-p0.geo_dashboard.geo_channel_daily (date x tv_region x channel - for TV halo analysis)

Usage:
  py backfill_geo.py             # full backfill from 2024-04-01 (creates dataset + all tables)
  py backfill_geo.py --refresh   # refresh last 4 days only (same logic as the scheduled query)
  py backfill_geo.py --map-only  # just (re)build the tv_region_map table

Requires: pip install google-cloud-bigquery
"""

import os
import sys
import glob
from datetime import date, timedelta

from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT = "commanding-air-450109-p0"
GA4_DATASET = "analytics_287404213"
DEST_DATASET = "geo_dashboard"
LOCATION = "europe-west2"
BACKFILL_START = "20240401"

# ---------------------------------------------------------------------------
# Service account key discovery (same pattern as other dashboards)
# ---------------------------------------------------------------------------
KEY_SEARCH_DIRS = [
    r"C:\Users\dlawrence\Documents",
    r"C:\Users\dlawrence\Downloads",
    r"C:\Users\dlawrence\Documents\Price Scraping",
    os.path.dirname(os.path.abspath(__file__)),
]

def find_key():
    for d in KEY_SEARCH_DIRS:
        for path in glob.glob(os.path.join(d, "commanding-air-450109-p0-*.json")):
            return path
    sys.exit("No service account key found. Expected commanding-air-450109-p0-*.json in Documents/Downloads.")

def get_client():
    key_path = find_key()
    print(f"Using key: {key_path}")
    creds = service_account.Credentials.from_service_account_file(key_path)
    return bigquery.Client(project=PROJECT, credentials=creds, location=LOCATION)

# ---------------------------------------------------------------------------
# TV region mapping: (GA4 region, GA4 city) -> ITV/BARB macro region, lat, lng
# Join is on region + city so Newport (Wales) / Bangor (NI vs Wales) etc. don't clash.
# Unmapped UK cities fall through to 'UK - Other'; non-UK traffic -> 'Non-UK'.
# ---------------------------------------------------------------------------
TV_REGION_MAP = [
    # --- London ---
    ("England", "London", "London", 51.51, -0.13),
    ("England", "Croydon", "London", 51.37, -0.10),
    ("England", "Bromley", "London", 51.41, 0.02),
    ("England", "Ilford", "London", 51.56, 0.07),
    ("England", "Romford", "London", 51.58, 0.18),
    ("England", "Enfield", "London", 51.65, -0.08),
    ("England", "Harrow", "London", 51.58, -0.34),
    ("England", "Kingston upon Thames", "London", 51.41, -0.30),
    ("England", "Sutton", "London", 51.36, -0.19),
    ("England", "Twickenham", "London", 51.45, -0.34),
    ("England", "Watford", "London", 51.66, -0.40),
    ("England", "Slough", "London", 51.51, -0.59),
    ("England", "St Albans", "London", 51.75, -0.34),
    ("England", "Woking", "London", 51.32, -0.56),
    ("England", "Guildford", "London", 51.24, -0.57),
    ("England", "Dartford", "London", 51.44, 0.22),
    ("England", "Hemel Hempstead", "London", 51.75, -0.47),
    ("England", "High Wycombe", "London", 51.63, -0.75),
    ("England", "Harlow", "London", 51.77, 0.11),
    ("England", "Epsom", "London", 51.33, -0.27),
    # --- Midlands (Central) ---
    ("England", "Birmingham", "Midlands", 52.49, -1.90),
    ("England", "Coventry", "Midlands", 52.41, -1.51),
    ("England", "Wolverhampton", "Midlands", 52.59, -2.11),
    ("England", "Leicester", "Midlands", 52.64, -1.13),
    ("England", "Nottingham", "Midlands", 52.95, -1.15),
    ("England", "Derby", "Midlands", 52.92, -1.48),
    ("England", "Stoke-on-Trent", "Midlands", 53.00, -2.18),
    ("England", "Walsall", "Midlands", 52.59, -1.98),
    ("England", "Dudley", "Midlands", 52.51, -2.09),
    ("England", "Solihull", "Midlands", 52.41, -1.78),
    ("England", "West Bromwich", "Midlands", 52.52, -1.99),
    ("England", "Sutton Coldfield", "Midlands", 52.57, -1.82),
    ("England", "Northampton", "Midlands", 52.24, -0.90),
    ("England", "Telford", "Midlands", 52.68, -2.45),
    ("England", "Shrewsbury", "Midlands", 52.71, -2.75),
    ("England", "Worcester", "Midlands", 52.19, -2.22),
    ("England", "Redditch", "Midlands", 52.31, -1.94),
    ("England", "Tamworth", "Midlands", 52.63, -1.69),
    ("England", "Nuneaton", "Midlands", 52.52, -1.47),
    ("England", "Burton upon Trent", "Midlands", 52.81, -1.64),
    ("England", "Kettering", "Midlands", 52.40, -0.73),
    ("England", "Corby", "Midlands", 52.49, -0.69),
    ("England", "Rugby", "Midlands", 52.37, -1.26),
    ("England", "Loughborough", "Midlands", 52.77, -1.21),
    ("England", "Mansfield", "Midlands", 53.14, -1.20),
    ("England", "Hereford", "Midlands", 52.06, -2.72),
    ("England", "Stafford", "Midlands", 52.81, -2.12),
    ("England", "Cannock", "Midlands", 52.69, -2.03),
    # --- North West (Granada) ---
    ("England", "Manchester", "North West", 53.48, -2.24),
    ("England", "Liverpool", "North West", 53.41, -2.98),
    ("England", "Bolton", "North West", 53.58, -2.43),
    ("England", "Stockport", "North West", 53.41, -2.16),
    ("England", "Salford", "North West", 53.49, -2.29),
    ("England", "Wigan", "North West", 53.55, -2.63),
    ("England", "Warrington", "North West", 53.39, -2.60),
    ("England", "Oldham", "North West", 53.54, -2.11),
    ("England", "Rochdale", "North West", 53.61, -2.16),
    ("England", "St Helens", "North West", 53.45, -2.74),
    ("England", "Bury", "North West", 53.59, -2.30),
    ("England", "Preston", "North West", 53.76, -2.70),
    ("England", "Blackpool", "North West", 53.82, -3.05),
    ("England", "Blackburn", "North West", 53.75, -2.48),
    ("England", "Burnley", "North West", 53.79, -2.24),
    ("England", "Chester", "North West", 53.19, -2.89),
    ("England", "Crewe", "North West", 53.10, -2.44),
    ("England", "Macclesfield", "North West", 53.26, -2.13),
    ("England", "Southport", "North West", 53.65, -3.01),
    ("England", "Birkenhead", "North West", 53.39, -3.01),
    ("England", "Runcorn", "North West", 53.34, -2.73),
    ("England", "Lancaster", "North West", 54.05, -2.80),
    # --- Yorkshire ---
    ("England", "Leeds", "Yorkshire", 53.80, -1.55),
    ("England", "Sheffield", "Yorkshire", 53.38, -1.47),
    ("England", "Bradford", "Yorkshire", 53.80, -1.75),
    ("England", "Kingston upon Hull", "Yorkshire", 53.75, -0.34),
    ("England", "Hull", "Yorkshire", 53.75, -0.34),
    ("England", "York", "Yorkshire", 53.96, -1.08),
    ("England", "Wakefield", "Yorkshire", 53.68, -1.50),
    ("England", "Huddersfield", "Yorkshire", 53.65, -1.78),
    ("England", "Doncaster", "Yorkshire", 53.52, -1.13),
    ("England", "Rotherham", "Yorkshire", 53.43, -1.36),
    ("England", "Barnsley", "Yorkshire", 53.55, -1.48),
    ("England", "Halifax", "Yorkshire", 53.72, -1.86),
    ("England", "Harrogate", "Yorkshire", 54.00, -1.54),
    ("England", "Grimsby", "Yorkshire", 53.57, -0.08),
    ("England", "Scunthorpe", "Yorkshire", 53.59, -0.65),
    ("England", "Lincoln", "Yorkshire", 53.23, -0.54),
    ("England", "Keighley", "Yorkshire", 53.87, -1.90),
    ("England", "Castleford", "Yorkshire", 53.73, -1.36),
    ("England", "Chesterfield", "Yorkshire", 53.24, -1.42),
    # --- North East (Tyne Tees) ---
    ("England", "Newcastle upon Tyne", "North East", 54.98, -1.61),
    ("England", "Sunderland", "North East", 54.91, -1.38),
    ("England", "Middlesbrough", "North East", 54.57, -1.23),
    ("England", "Gateshead", "North East", 54.95, -1.60),
    ("England", "Durham", "North East", 54.78, -1.58),
    ("England", "Darlington", "North East", 54.52, -1.55),
    ("England", "Hartlepool", "North East", 54.69, -1.21),
    ("England", "Stockton-on-Tees", "North East", 54.57, -1.32),
    ("England", "South Shields", "North East", 55.00, -1.43),
    ("England", "Washington", "North East", 54.90, -1.52),
    # --- East (Anglia) ---
    ("England", "Norwich", "East", 52.63, 1.30),
    ("England", "Ipswich", "East", 52.06, 1.16),
    ("England", "Cambridge", "East", 52.21, 0.12),
    ("England", "Peterborough", "East", 52.57, -0.24),
    ("England", "Colchester", "East", 51.89, 0.90),
    ("England", "Chelmsford", "East", 51.74, 0.47),
    ("England", "Southend-on-Sea", "East", 51.54, 0.71),
    ("England", "Basildon", "East", 51.58, 0.49),
    ("England", "Luton", "East", 51.88, -0.42),
    ("England", "Bedford", "East", 52.14, -0.47),
    ("England", "Milton Keynes", "East", 52.04, -0.76),
    ("England", "King's Lynn", "East", 52.75, 0.40),
    ("England", "Great Yarmouth", "East", 52.61, 1.73),
    ("England", "Lowestoft", "East", 52.48, 1.75),
    ("England", "Bury St Edmunds", "East", 52.25, 0.71),
    ("England", "Stevenage", "East", 51.90, -0.20),
    # --- South & South East (Meridian) ---
    ("England", "Southampton", "South & South East", 50.90, -1.40),
    ("England", "Portsmouth", "South & South East", 50.80, -1.09),
    ("England", "Brighton", "South & South East", 50.83, -0.14),
    ("England", "Brighton and Hove", "South & South East", 50.83, -0.14),
    ("England", "Reading", "South & South East", 51.45, -0.98),
    ("England", "Oxford", "South & South East", 51.75, -1.26),
    ("England", "Bournemouth", "South & South East", 50.72, -1.88),
    ("England", "Poole", "South & South East", 50.72, -1.98),
    ("England", "Basingstoke", "South & South East", 51.27, -1.09),
    ("England", "Winchester", "South & South East", 51.06, -1.31),
    ("England", "Eastbourne", "South & South East", 50.77, 0.28),
    ("England", "Hastings", "South & South East", 50.85, 0.57),
    ("England", "Crawley", "South & South East", 51.11, -0.19),
    ("England", "Worthing", "South & South East", 50.81, -0.37),
    ("England", "Maidstone", "South & South East", 51.27, 0.52),
    ("England", "Canterbury", "South & South East", 51.28, 1.08),
    ("England", "Ashford", "South & South East", 51.15, 0.87),
    ("England", "Gillingham", "South & South East", 51.39, 0.55),
    ("England", "Chatham", "South & South East", 51.38, 0.53),
    ("England", "Royal Tunbridge Wells", "South & South East", 51.13, 0.26),
    ("England", "Tunbridge Wells", "South & South East", 51.13, 0.26),
    ("England", "Salisbury", "South & South East", 51.07, -1.79),
    ("England", "Andover", "South & South East", 51.21, -1.48),
    ("England", "Aldershot", "South & South East", 51.25, -0.76),
    ("England", "Farnborough", "South & South East", 51.29, -0.75),
    ("England", "Newbury", "South & South East", 51.40, -1.32),
    ("England", "Bracknell", "South & South East", 51.42, -0.75),
    ("England", "Maidenhead", "South & South East", 51.52, -0.72),
    # --- West & South West (West Country / HTV West) ---
    ("England", "Bristol", "West & South West", 51.45, -2.59),
    ("England", "Bath", "West & South West", 51.38, -2.36),
    ("England", "Gloucester", "West & South West", 51.86, -2.24),
    ("England", "Cheltenham", "West & South West", 51.90, -2.07),
    ("England", "Swindon", "West & South West", 51.56, -1.78),
    ("England", "Plymouth", "West & South West", 50.38, -4.14),
    ("England", "Exeter", "West & South West", 50.72, -3.53),
    ("England", "Torquay", "West & South West", 50.46, -3.53),
    ("England", "Taunton", "West & South West", 51.02, -3.10),
    ("England", "Truro", "West & South West", 50.26, -5.05),
    ("England", "Weston-super-Mare", "West & South West", 51.35, -2.98),
    ("England", "Yeovil", "West & South West", 50.94, -2.63),
    ("England", "Bridgwater", "West & South West", 51.13, -3.00),
    ("England", "Barnstaple", "West & South West", 51.08, -4.06),
    ("England", "Stroud", "West & South West", 51.75, -2.22),
    # --- Wales ---
    ("Wales", "Cardiff", "Wales", 51.48, -3.18),
    ("Wales", "Swansea", "Wales", 51.62, -3.94),
    ("Wales", "Newport", "Wales", 51.58, -3.00),
    ("Wales", "Wrexham", "Wales", 53.05, -3.00),
    ("Wales", "Barry", "Wales", 51.40, -3.28),
    ("Wales", "Neath", "Wales", 51.66, -3.81),
    ("Wales", "Cwmbran", "Wales", 51.65, -3.02),
    ("Wales", "Bridgend", "Wales", 51.50, -3.58),
    ("Wales", "Llanelli", "Wales", 51.68, -4.16),
    ("Wales", "Merthyr Tydfil", "Wales", 51.75, -3.38),
    ("Wales", "Bangor", "Wales", 53.23, -4.13),
    ("Wales", "Aberystwyth", "Wales", 52.41, -4.08),
    # --- Central Scotland (STV Central) ---
    ("Scotland", "Glasgow", "Central Scotland", 55.86, -4.25),
    ("Scotland", "Edinburgh", "Central Scotland", 55.95, -3.19),
    ("Scotland", "Stirling", "Central Scotland", 56.12, -3.94),
    ("Scotland", "Falkirk", "Central Scotland", 56.00, -3.78),
    ("Scotland", "Dunfermline", "Central Scotland", 56.07, -3.44),
    ("Scotland", "Kirkcaldy", "Central Scotland", 56.11, -3.16),
    ("Scotland", "Livingston", "Central Scotland", 55.90, -3.52),
    ("Scotland", "Paisley", "Central Scotland", 55.85, -4.42),
    ("Scotland", "East Kilbride", "Central Scotland", 55.76, -4.18),
    ("Scotland", "Hamilton", "Central Scotland", 55.78, -4.05),
    ("Scotland", "Kilmarnock", "Central Scotland", 55.61, -4.50),
    ("Scotland", "Ayr", "Central Scotland", 55.46, -4.63),
    ("Scotland", "Motherwell", "Central Scotland", 55.79, -4.00),
    ("Scotland", "Coatbridge", "Central Scotland", 55.86, -4.03),
    ("Scotland", "Cumbernauld", "Central Scotland", 55.95, -3.99),
    ("Scotland", "Greenock", "Central Scotland", 55.95, -4.76),
    # --- North Scotland (STV North / Grampian) ---
    ("Scotland", "Aberdeen", "North Scotland", 57.15, -2.09),
    ("Scotland", "Dundee", "North Scotland", 56.46, -2.97),
    ("Scotland", "Inverness", "North Scotland", 57.48, -4.22),
    ("Scotland", "Perth", "North Scotland", 56.40, -3.44),
    ("Scotland", "Elgin", "North Scotland", 57.65, -3.32),
    ("Scotland", "Arbroath", "North Scotland", 56.56, -2.59),
    # --- Border ---
    ("England", "Carlisle", "Border", 54.89, -2.94),
    ("Scotland", "Dumfries", "Border", 55.07, -3.61),
    ("England", "Workington", "Border", 54.64, -3.55),
    ("England", "Whitehaven", "Border", 54.55, -3.59),
    ("England", "Penrith", "Border", 54.66, -2.75),
    ("England", "Kendal", "Border", 54.33, -2.75),
    ("Scotland", "Galashiels", "Border", 55.62, -2.81),
    ("Scotland", "Hawick", "Border", 55.42, -2.79),
    ("England", "Berwick-upon-Tweed", "Border", 55.77, -2.00),
    # --- Northern Ireland (UTV) ---
    ("Northern Ireland", "Belfast", "Northern Ireland", 54.60, -5.93),
    ("Northern Ireland", "Londonderry", "Northern Ireland", 55.00, -7.31),
    ("Northern Ireland", "Derry", "Northern Ireland", 55.00, -7.31),
    ("Northern Ireland", "Lisburn", "Northern Ireland", 54.51, -6.04),
    ("Northern Ireland", "Newtownabbey", "Northern Ireland", 54.66, -5.90),
    ("Northern Ireland", "Bangor", "Northern Ireland", 54.65, -5.67),
    ("Northern Ireland", "Craigavon", "Northern Ireland", 54.45, -6.39),
    ("Northern Ireland", "Ballymena", "Northern Ireland", 54.86, -6.28),
]

# ---------------------------------------------------------------------------
# Shared SQL fragments
# ---------------------------------------------------------------------------

def session_cte(start_suffix, end_suffix):
    """Session-level rollup from GA4 events with geo, engagement, ecommerce and first traffic source."""
    return f"""
    WITH ev AS (
      SELECT
        PARSE_DATE('%Y%m%d', event_date) AS dt,
        user_pseudo_id,
        event_timestamp,
        event_name,
        (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS sid,
        geo.country AS country,
        geo.region  AS region,
        geo.city    AS city,
        COALESCE(
          (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'session_engaged'),
          CAST((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'session_engaged') AS STRING)
        ) AS engaged,
        ecommerce.purchase_revenue AS purchase_revenue,
        collected_traffic_source.manual_source AS src,
        collected_traffic_source.manual_medium AS med,
        collected_traffic_source.gclid AS gclid
      FROM `{PROJECT}.{GA4_DATASET}.events_*`
      WHERE _TABLE_SUFFIX BETWEEN '{start_suffix}' AND '{end_suffix}'
    ),
    sessions AS (
      SELECT
        dt,
        CONCAT(user_pseudo_id, '-', CAST(sid AS STRING)) AS session_id,
        ANY_VALUE(user_pseudo_id) AS user_pseudo_id,
        COALESCE(MAX(IF(country != '(not set)', country, NULL)), '(not set)') AS country,
        COALESCE(MAX(IF(region  != '(not set)', region,  NULL)), '(not set)') AS region,
        COALESCE(MAX(IF(city    != '(not set)', city,    NULL)), '(not set)') AS city,
        MAX(IF(engaged = '1', 1, 0)) AS engaged,
        MAX(IF(event_name = 'first_visit', 1, 0)) AS is_new_user,
        COUNTIF(event_name = 'purchase') AS transactions,
        IFNULL(SUM(IF(event_name = 'purchase', purchase_revenue, 0)), 0) AS revenue,
        ARRAY_AGG(
          IF(src IS NOT NULL OR med IS NOT NULL OR gclid IS NOT NULL,
             STRUCT(src, med, gclid), NULL)
          IGNORE NULLS ORDER BY event_timestamp LIMIT 1
        )[SAFE_OFFSET(0)] AS ts
      FROM ev
      WHERE sid IS NOT NULL
      GROUP BY dt, session_id
    ),
    classified AS (
      SELECT
        s.*,
        CASE
          WHEN s.country != 'United Kingdom' THEN 'Non-UK'
          ELSE IFNULL(m.tv_region, 'UK - Other')
        END AS tv_region,
        CASE
          WHEN ts.gclid IS NOT NULL THEN 'Paid Search'
          WHEN LOWER(IFNULL(ts.med,'')) IN ('cpc','ppc','paidsearch')
               AND REGEXP_CONTAINS(LOWER(IFNULL(ts.src,'')), r'google|bing|yahoo|duckduckgo') THEN 'Paid Search'
          WHEN LOWER(IFNULL(ts.med,'')) IN ('cpc','ppc','paid','paid_social','paidsocial','paid-social')
               AND REGEXP_CONTAINS(LOWER(IFNULL(ts.src,'')), r'facebook|instagram|meta|pinterest|tiktok|snapchat|^fb$|^ig$') THEN 'Paid Social'
          WHEN REGEXP_CONTAINS(LOWER(IFNULL(ts.med,'')), r'^(display|banner|cpm|interstitial)$') THEN 'Display'
          WHEN LOWER(IFNULL(ts.med,'')) = 'organic' THEN 'Organic Search'
          WHEN LOWER(IFNULL(ts.med,'')) IN ('social','social-network','social-media','sm')
               OR REGEXP_CONTAINS(LOWER(IFNULL(ts.src,'')), r'facebook|instagram|pinterest|tiktok|linkedin|twitter|t\\.co|youtube') THEN 'Organic Social'
          WHEN LOWER(IFNULL(ts.med,'')) = 'email' OR REGEXP_CONTAINS(LOWER(IFNULL(ts.src,'')), r'mail|ometria') THEN 'Email'
          WHEN LOWER(IFNULL(ts.med,'')) IN ('affiliate','affiliates') THEN 'Affiliates'
          WHEN LOWER(IFNULL(ts.med,'')) = 'referral' THEN 'Referral'
          WHEN ts.src IS NULL OR ts.src = '(direct)' THEN 'Direct'
          ELSE 'Other'
        END AS channel
      FROM sessions s
      LEFT JOIN `{PROJECT}.{DEST_DATASET}.tv_region_map` m
        ON s.country = 'United Kingdom' AND s.region = m.region AND s.city = m.city
    )
    """

GEO_DAILY_SELECT = """
    SELECT
      dt AS date,
      country, region, city, tv_region,
      COUNT(DISTINCT session_id) AS sessions,
      COUNT(DISTINCT user_pseudo_id) AS users,
      SUM(is_new_user) AS new_users,
      SUM(engaged) AS engaged_sessions,
      SUM(transactions) AS transactions,
      ROUND(SUM(revenue), 2) AS revenue
    FROM classified
    GROUP BY date, country, region, city, tv_region
"""

GEO_CHANNEL_DAILY_SELECT = """
    SELECT
      dt AS date,
      tv_region,
      channel,
      COUNT(DISTINCT session_id) AS sessions,
      COUNT(DISTINCT user_pseudo_id) AS users,
      SUM(engaged) AS engaged_sessions,
      SUM(transactions) AS transactions,
      ROUND(SUM(revenue), 2) AS revenue
    FROM classified
    GROUP BY date, tv_region, channel
"""

# ---------------------------------------------------------------------------

def build_map_table(client):
    print("Building tv_region_map...")
    client.query(f"CREATE SCHEMA IF NOT EXISTS `{PROJECT}.{DEST_DATASET}` OPTIONS(location='{LOCATION}')").result()
    rows = ",\n".join(
        f"('{r}', \"{c.replace(chr(34), '')}\", '{t}', {lat}, {lng})"
        for (r, c, t, lat, lng) in TV_REGION_MAP
    )
    sql = f"""
    CREATE OR REPLACE TABLE `{PROJECT}.{DEST_DATASET}.tv_region_map`
    (region STRING, city STRING, tv_region STRING, lat FLOAT64, lng FLOAT64)
    AS SELECT * FROM UNNEST([
      STRUCT<region STRING, city STRING, tv_region STRING, lat FLOAT64, lng FLOAT64>
      {rows}
    ]);
    """
    client.query(sql).result()
    print(f"  tv_region_map: {len(TV_REGION_MAP)} city mappings loaded.")


def full_backfill(client):
    end_suffix = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
    cte = session_cte(BACKFILL_START, end_suffix)

    print(f"Backfilling geo_daily ({BACKFILL_START} -> {end_suffix})... this can take a few minutes.")
    client.query(
        f"CREATE OR REPLACE TABLE `{PROJECT}.{DEST_DATASET}.geo_daily` "
        f"PARTITION BY date CLUSTER BY tv_region, city AS {cte} {GEO_DAILY_SELECT}"
    ).result()
    print("  geo_daily done.")

    print("Backfilling geo_channel_daily...")
    client.query(
        f"CREATE OR REPLACE TABLE `{PROJECT}.{DEST_DATASET}.geo_channel_daily` "
        f"PARTITION BY date CLUSTER BY tv_region, channel AS {cte} {GEO_CHANNEL_DAILY_SELECT}"
    ).result()
    print("  geo_channel_daily done.")


def refresh_recent(client, days=4):
    start = date.today() - timedelta(days=days)
    start_suffix = start.strftime("%Y%m%d")
    end_suffix = date.today().strftime("%Y%m%d")
    cte = session_cte(start_suffix, end_suffix)

    for table, select in [("geo_daily", GEO_DAILY_SELECT), ("geo_channel_daily", GEO_CHANNEL_DAILY_SELECT)]:
        print(f"Refreshing {table} from {start}...")
        client.query(
            f"DELETE FROM `{PROJECT}.{DEST_DATASET}.{table}` WHERE date >= '{start}'"
        ).result()
        client.query(
            f"INSERT INTO `{PROJECT}.{DEST_DATASET}.{table}` {cte} {select}"
        ).result()
    print("Refresh complete.")


if __name__ == "__main__":
    client = get_client()
    if "--map-only" in sys.argv:
        build_map_table(client)
    elif "--refresh" in sys.argv:
        refresh_recent(client)
    else:
        build_map_table(client)
        full_backfill(client)
        print("\nAll done. Set up the daily scheduled query with daily_refresh.sql (09:00 UTC).")
