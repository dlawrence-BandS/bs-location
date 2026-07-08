-- Location Performance Dashboard: daily refresh
-- Set up as a BigQuery scheduled query, daily at 09:00 UTC, location europe-west2.
-- Rebuilds the last 4 days of geo_daily and geo_channel_daily (GA4 export lands late / restates).

DECLARE start_dt DATE DEFAULT DATE_SUB(CURRENT_DATE(), INTERVAL 4 DAY);
DECLARE start_suffix STRING DEFAULT FORMAT_DATE('%Y%m%d', start_dt);
DECLARE end_suffix STRING DEFAULT FORMAT_DATE('%Y%m%d', CURRENT_DATE());

CREATE TEMP TABLE classified AS
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
  FROM `commanding-air-450109-p0.analytics_287404213.events_*`
  WHERE _TABLE_SUFFIX BETWEEN start_suffix AND end_suffix
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
      IF(src IS NOT NULL OR med IS NOT NULL OR gclid IS NOT NULL, STRUCT(src, med, gclid), NULL)
      IGNORE NULLS ORDER BY event_timestamp LIMIT 1
    )[SAFE_OFFSET(0)] AS ts
  FROM ev
  WHERE sid IS NOT NULL
  GROUP BY dt, session_id
)
SELECT
  s.*,
  CASE WHEN s.country != 'United Kingdom' THEN 'Non-UK' ELSE IFNULL(m.tv_region, 'UK - Other') END AS tv_region,
  CASE
    WHEN ts.gclid IS NOT NULL THEN 'Paid Search'
    WHEN LOWER(IFNULL(ts.med,'')) IN ('cpc','ppc','paidsearch')
         AND REGEXP_CONTAINS(LOWER(IFNULL(ts.src,'')), r'google|bing|yahoo|duckduckgo') THEN 'Paid Search'
    WHEN LOWER(IFNULL(ts.med,'')) IN ('cpc','ppc','paid','paid_social','paidsocial','paid-social')
         AND REGEXP_CONTAINS(LOWER(IFNULL(ts.src,'')), r'facebook|instagram|meta|pinterest|tiktok|snapchat|^fb$|^ig$') THEN 'Paid Social'
    WHEN REGEXP_CONTAINS(LOWER(IFNULL(ts.med,'')), r'^(display|banner|cpm|interstitial)$') THEN 'Display'
    WHEN LOWER(IFNULL(ts.med,'')) = 'organic' THEN 'Organic Search'
    WHEN LOWER(IFNULL(ts.med,'')) IN ('social','social-network','social-media','sm')
         OR REGEXP_CONTAINS(LOWER(IFNULL(ts.src,'')), r'facebook|instagram|pinterest|tiktok|linkedin|twitter|t\.co|youtube') THEN 'Organic Social'
    WHEN LOWER(IFNULL(ts.med,'')) = 'email' OR REGEXP_CONTAINS(LOWER(IFNULL(ts.src,'')), r'mail|ometria') THEN 'Email'
    WHEN LOWER(IFNULL(ts.med,'')) IN ('affiliate','affiliates') THEN 'Affiliates'
    WHEN LOWER(IFNULL(ts.med,'')) = 'referral' THEN 'Referral'
    WHEN ts.src IS NULL OR ts.src = '(direct)' THEN 'Direct'
    ELSE 'Other'
  END AS channel
FROM sessions s
LEFT JOIN `commanding-air-450109-p0.geo_dashboard.tv_region_map` m
  ON s.country = 'United Kingdom' AND s.region = m.region AND s.city = m.city;

DELETE FROM `commanding-air-450109-p0.geo_dashboard.geo_daily` WHERE date >= start_dt;
INSERT INTO `commanding-air-450109-p0.geo_dashboard.geo_daily`
SELECT dt, country, region, city, tv_region,
  COUNT(DISTINCT session_id), COUNT(DISTINCT user_pseudo_id),
  SUM(is_new_user), SUM(engaged), SUM(transactions), ROUND(SUM(revenue), 2)
FROM classified GROUP BY 1,2,3,4,5;

DELETE FROM `commanding-air-450109-p0.geo_dashboard.geo_channel_daily` WHERE date >= start_dt;
INSERT INTO `commanding-air-450109-p0.geo_dashboard.geo_channel_daily`
SELECT dt, tv_region, channel,
  COUNT(DISTINCT session_id), COUNT(DISTINCT user_pseudo_id),
  SUM(engaged), SUM(transactions), ROUND(SUM(revenue), 2)
FROM classified GROUP BY 1,2,3;
