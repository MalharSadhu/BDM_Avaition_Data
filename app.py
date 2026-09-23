import os
import time
import psycopg2
import psycopg2.extensions
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Schiphol Airport | Operational & Commercial Hub",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Corporate Styling
st.markdown("""
<style>
    div[data-testid="stMetricValue"] { font-size: 1.65rem; font-weight: 700; color: #003580; }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 0.92rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# DATABASE UTILITIES
# ----------------------------------------------------
def get_db_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        try:
            url = st.secrets["DATABASE_URL"]
        except Exception:
            pass
    if not url:
        st.error("Database connection string not configured.")
        st.stop()
    return url

@st.cache_resource
def get_db_connection():
    return psycopg2.connect(get_db_url())

@st.cache_data(ttl=300)
def run_query(query):
    conn = get_db_connection()
    return pd.read_sql_query(query, conn)

def run_timed_query(query):
    conn = get_db_connection()
    start_time = time.perf_counter()
    df = pd.read_sql_query(query, conn)
    latency_ms = (time.perf_counter() - start_time) * 1000
    return df, latency_ms

# ----------------------------------------------------
# SIDEBAR
# ----------------------------------------------------
st.sidebar.title("✈️ Schiphol Airport")
st.sidebar.markdown("**Operations & Commercial Intelligence**")
st.sidebar.caption("Connected to Cloud Database (24/7 Live)")

st.sidebar.markdown("---")
st.sidebar.markdown("**Database Sync**")
if st.sidebar.button("🔄 Refresh Cached Reports", use_container_width=True):
    try:
        conn = psycopg2.connect(get_db_url())
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY aviation.mv_daily_operational_summary;")
        conn.close()
        st.cache_data.clear()
        st.sidebar.success("Reports synchronized successfully!")
    except Exception as e:
        st.sidebar.error(f"Sync failed: {e}")

st.sidebar.markdown("---")
st.sidebar.caption("Amsterdam Airport Schiphol • Hub Operations")

# ----------------------------------------------------
# GLOBAL EXECUTIVE KPIS
# ----------------------------------------------------
st.title("Schiphol Airport Operational Summary")
st.caption("Live flight schedules, ground ramp operations, and airside commercial performance.")

kpi_sql = """
SELECT 
    (SELECT COUNT(*) FROM aviation.flights) AS total_flights,
    (SELECT COUNT(DISTINCT airline_iata) FROM aviation.flights WHERE airline_iata IS NOT NULL) AS active_airlines,
    (SELECT COALESCE(SUM(amount_eur), 0) FROM aviation.retail) AS total_retail,
    (SELECT COALESCE(ROUND(SUM(weight_kg)::numeric, 0), 0) FROM aviation.baggage) AS total_baggage_kg,
    (SELECT COALESCE(SUM(total_amount_eur), 0) FROM aviation.parking) AS parking_revenue
"""
kpis = run_query(kpi_sql)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Scheduled Flights", f"{kpis['total_flights'][0]:,}")
c2.metric("Operating Airlines", f"{kpis['active_airlines'][0]:,}")
c3.metric("Terminal Retail Revenue", f"€{kpis['total_retail'][0]:,.2f}")
c4.metric("Luggage Handled", f"{kpis['total_baggage_kg'][0]:,.0f} kg")
c5.metric("Parking Revenue", f"€{kpis['parking_revenue'][0]:,.2f}")

st.divider()

# ----------------------------------------------------
# MAIN DASHBOARD TABS
# ----------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 1. Airport Data Overview",
    "🛍️ 2. Terminal Retail & Dining",
    "🌧️ 3. Adverse Weather & Ramp Cargo",
    "🧳 4. Airline Baggage Operations",
    "📈 5. Commercial Revenue Mix",
    "🛠️ 6. SQL Architecture & Engineering"
])

# ----------------------------------------------------
# TAB 1: AIRPORT DATA OVERVIEW
# ----------------------------------------------------
with tab1:
    st.subheader("Data Warehouse Inventory Across Airport Touchpoints")
    st.write("Record inventory across connected terminal systems:")

    manifest_sql = """
    SELECT 
        table_name AS "Operational Area",
        COUNT(*) AS "Total Records"
    FROM (
        SELECT 'Flight Schedules' AS table_name FROM aviation.flights
        UNION ALL SELECT 'Partner Airlines' FROM aviation.airlines
        UNION ALL SELECT 'Global Airport Hubs' FROM aviation.airports
        UNION ALL SELECT 'Passenger Telemetry' FROM aviation.passengers
        UNION ALL SELECT 'Luggage Handling' FROM aviation.baggage
        UNION ALL SELECT 'Terminal Stores & Dining' FROM aviation.retail
        UNION ALL SELECT 'Parking Facilities' FROM aviation.parking
        UNION ALL SELECT 'Weather Observations' FROM aviation.weather
        UNION ALL SELECT 'Aircraft Maintenance Logs' FROM aviation.maintenance_logs
    ) t GROUP BY table_name
    ORDER BY "Total Records" DESC;
    """
    df_manifest = run_query(manifest_sql)

    col_m1, col_m2 = st.columns([3, 2])
    with col_m1:
        st.markdown("#### Database Ingestion Volume")
        st.bar_chart(df_manifest.set_index("Operational Area"), height=300)
    with col_m2:
        st.markdown("#### Operational Table Counts")
        st.dataframe(df_manifest, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# TAB 2: TERMINAL RETAIL & CONCESSIONS
# ----------------------------------------------------
with tab2:
    st.subheader("Terminal Retail & Commercial Spend Analysis")
    st.write("Tracking passenger commercial demand across airport terminals, time of day, and purchase tiers.")

    # 1. Hourly Trend Query (Intraday footfall wave)
    hourly_sql = """
    SELECT 
        TO_CHAR(transacted_at, 'HH24:00') AS "Hour of Day",
        COUNT(*) AS "Transactions",
        ROUND(SUM(amount_eur)::numeric, 2) AS "Total Hourly Revenue (€)",
        ROUND(AVG(amount_eur)::numeric, 2) AS "Avg Spend (€)"
    FROM aviation.retail
    WHERE transacted_at IS NOT NULL
    GROUP BY TO_CHAR(transacted_at, 'HH24:00')
    ORDER BY "Hour of Day" ASC;
    """
    df_hourly = run_query(hourly_sql)

    # 2. Spend Tier Query
    tier_sql = """
    SELECT 
        CASE 
            WHEN amount_eur < 25 THEN '1. Grab & Go (< €25)'
            WHEN amount_eur BETWEEN 25 AND 100 THEN '2. Standard Dining & Retail (€25–€100)'
            ELSE '3. High-Value Concessions (> €100)'
        END AS "Spending Tier",
        COUNT(*) AS "Volume",
        ROUND(SUM(amount_eur)::numeric, 2) AS "Revenue (€)"
    FROM aviation.retail
    GROUP BY 1
    ORDER BY 1;
    """
    df_tier = run_query(tier_sql)

    # 3. Terminal Query
    terminal_sql = """
    SELECT 
        COALESCE(terminal, 'Main Concourse') AS "Terminal",
        COUNT(*) AS "Transactions",
        ROUND(SUM(amount_eur)::numeric, 2) AS "Total Revenue (€)",
        ROUND(AVG(amount_eur)::numeric, 2) AS "Avg Ticket (€)"
    FROM aviation.retail
    GROUP BY terminal
    ORDER BY "Total Revenue (€)" DESC;
    """
    df_term = run_query(terminal_sql)

    total_rev = df_term["Total Revenue (€)"].sum()
    total_tx = df_term["Transactions"].sum()
    avg_ticket = total_rev / total_tx if total_tx > 0 else 0

    c_r1, c_r2, c_r3 = st.columns(3)
    c_r1.metric("Total Retail Sales", f"€{total_rev:,.2f}")
    c_r2.metric("Total Transactions", f"{total_tx:,}")
    c_r3.metric("Average Transaction Value", f"€{avg_ticket:.2f}")

    st.markdown("---")

    st.markdown("#### Intraday Concession Revenue Waves (Peak Departure Surges)")
    if not df_hourly.empty:
        st.line_chart(df_hourly.set_index("Hour of Day")["Total Hourly Revenue (€)"], height=280)

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown("#### Revenue by Terminal Facility")
        st.bar_chart(df_term.set_index("Terminal")["Total Revenue (€)"], height=260)

    with col_t2:
        st.markdown("#### Purchase Tier Distribution")
        st.bar_chart(df_tier.set_index("Spending Tier")["Revenue (€)"], height=260)

    st.markdown("#### Terminal Sales Performance Table")
    st.dataframe(df_term, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# TAB 3: ADVERSE WEATHER & RAMP CARGO
# ----------------------------------------------------
with tab3:
    st.subheader("Severe Weather Turnaround Risk: Cargo Weight by Airline")
    st.write(
        "**Operational Context:** High wind speeds create ramp ground equipment handling hazards. "
        "This view evaluates total cargo weight moved by each airline during adverse wind periods."
    )

    weather_weight_sql = """
    WITH adverse_weather_days AS (
        SELECT DISTINCT recorded_at::DATE AS weather_date
        FROM aviation.weather
        WHERE wind_speed_kmh >= (SELECT AVG(wind_speed_kmh) FROM aviation.weather)
    ),
    carrier_weather_loads AS (
        SELECT 
            f.airline_iata AS airline,
            COUNT(DISTINCT f.flight_api_id) AS flight_count,
            COUNT(b.bag_tag_number) AS total_bags,
            ROUND(SUM(b.weight_kg)::numeric, 1) AS total_cargo_kg,
            ROUND(AVG(b.weight_kg)::numeric, 2) AS avg_bag_weight_kg
        FROM aviation.flights f
        JOIN adverse_weather_days aw ON f.schedule_date = aw.weather_date
        JOIN aviation.baggage b ON f.flight_api_id = b.flight_api_id
        WHERE f.airline_iata IS NOT NULL
        GROUP BY f.airline_iata
    )
    SELECT 
        airline AS "Airline",
        flight_count AS "Active Flights",
        total_bags AS "Bags Handled",
        total_cargo_kg AS "Total Cargo Weight (kg)",
        avg_bag_weight_kg AS "Avg Bag Weight (kg)"
    FROM carrier_weather_loads
    ORDER BY total_cargo_kg DESC;
    """
    df_weather = run_query(weather_weight_sql)

    col_w1, col_w2, col_w3 = st.columns(3)
    col_w1.metric("Airlines Operating in Wind Events", f"{len(df_weather)}")
    col_w2.metric("Total Cargo Handled in Wind", f"{df_weather['Total Cargo Weight (kg)'].sum():,.0f} kg")
    col_w3.metric("Busiest Carrier", f"{df_weather.iloc[0]['Airline']}")

    col_wg1, col_wg2 = st.columns([3, 2])
    with col_wg1:
        st.markdown("#### Total Cargo Weight Handled by Airline (kg)")
        st.bar_chart(df_weather.set_index("Airline")["Total Cargo Weight (kg)"], height=300)
    with col_wg2:
        st.markdown("#### Airline Wind Load Summary")
        st.dataframe(df_weather, use_container_width=True, hide_index=True)

# ----------------------------------------------------
# TAB 4: AIRLINE BAGGAGE OPERATIONS
# ----------------------------------------------------
with tab4:
    st.subheader("Airline Baggage Operations & Weight Distribution")
    st.write("Comparing total cargo weight handled against average piece weight across airlines.")

    carrier_bag_sql = """
    SELECT 
        f.airline_iata AS "Airline",
        COUNT(DISTINCT f.flight_api_id) AS "Flights",
        COUNT(b.bag_tag_number) AS "Bags Handled",
        ROUND(SUM(b.weight_kg)::numeric, 0) AS "Total Weight (kg)",
        ROUND(AVG(b.weight_kg)::numeric, 2) AS "Avg Bag Weight (kg)"
    FROM aviation.flights f
    JOIN aviation.baggage b ON f.flight_api_id = b.flight_api_id
    WHERE f.airline_iata IS NOT NULL
    GROUP BY f.airline_iata
    ORDER BY "Total Weight (kg)" DESC;
    """
    df_carrier = run_query(carrier_bag_sql)

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.markdown("#### Total Cargo Weight by Airline (kg)")
        st.bar_chart(df_carrier.set_index("Airline")["Total Weight (kg)"], height=280)
    with col_c2:
        st.markdown("#### Average Bag Weight per Airline (kg)")
        st.bar_chart(df_carrier.set_index("Airline")["Avg Bag Weight (kg)"], height=280)

    st.markdown("#### Flight Turnaround Luggage Rankings (Window Ranking)")
    rank_sql = """
    SELECT 
        f.schedule_date AS "Date",
        f.airline_iata AS "Airline",
        f.flight_name AS "Flight Number",
        COUNT(b.bag_tag_number) AS "Bags",
        ROUND(SUM(b.weight_kg)::numeric, 1) AS "Flight Weight (kg)",
        DENSE_RANK() OVER (
            PARTITION BY f.airline_iata 
            ORDER BY SUM(b.weight_kg) DESC
        ) AS "Rank Within Carrier"
    FROM aviation.flights f
    JOIN aviation.baggage b ON f.flight_api_id = b.flight_api_id
    GROUP BY f.schedule_date, f.airline_iata, f.flight_name
    ORDER BY "Flight Weight (kg)" DESC
    LIMIT 25;
    """
    st.dataframe(run_query(rank_sql), use_container_width=True, hide_index=True)

# ----------------------------------------------------
# TAB 5: COMMERCIAL REVENUE MIX
# ----------------------------------------------------
with tab5:
    st.subheader("Airport Commercial Revenue Breakdown")
    st.write("Comparing terminal retail spend with ground parking facilities revenue.")

    rev_sql = """
    SELECT 
        'Terminal Concessions' AS "Revenue Stream",
        ROUND(COALESCE(SUM(amount_eur), 0)::numeric, 2) AS "Amount (€)"
    FROM aviation.retail
    UNION ALL
    SELECT 
        'Parking Facilities',
        ROUND(COALESCE(SUM(total_amount_eur), 0)::numeric, 2)
    FROM aviation.parking;
    """
    df_rev = run_query(rev_sql)

    col_rv1, col_rv2 = st.columns([3, 2])
    with col_rv1:
        st.markdown("#### Revenue Mix Comparison (€)")
        st.bar_chart(df_rev.set_index("Revenue Stream")["Amount (€)"], height=300)
    with col_rv2:
        st.markdown("#### Revenue Channel Totals")
        st.dataframe(df_rev, use_container_width=True, hide_index=True)
        total_comm = df_rev["Amount (€)"].sum()
        st.metric("Total Commercial Turnover", f"€{total_comm:,.2f}")

# ----------------------------------------------------
# TAB 6: DEDICATED SQL & DATA ENGINEERING LAB
# ----------------------------------------------------
with tab6:
    st.subheader("🛠️ Data Engineering & SQL Architecture Hub")
    st.write("Catalog of underlying database queries, execution plans, and architectural benchmarks.")

    sql_tab1, sql_tab2, sql_tab3, sql_tab4, sql_tab5 = st.tabs([
        "⚡ 1. CTE vs. Subquery Benchmark",
        "📊 2. Retail & Statistical Profiling",
        "🪟 3. Window Partitions & Ranks",
        "💾 4. Views vs. Materialized Views",
        "🗄️ 5. Warehouse Schema & Manifest"
    ])

    with sql_tab1:
        st.markdown("#### Architectural Benchmark: Modular CTE vs. Nested Correlated Subquery")
        st.write("""
        **Problem:** Identify flights carrying cargo loads above the carrier benchmark during high-wind weather conditions.
        """)

        sub_sql = """
        SELECT 
            f.flight_api_id, f.airline_iata, f.schedule_date,
            (SELECT SUM(b.weight_kg) FROM aviation.baggage b WHERE b.flight_api_id = f.flight_api_id) AS total_weight_kg
        FROM aviation.flights f
        WHERE f.airline_iata IS NOT NULL
          AND (SELECT SUM(b.weight_kg) FROM aviation.baggage b WHERE b.flight_api_id = f.flight_api_id) >= (
            SELECT COALESCE(AVG(w_sum), 0)
            FROM (
                SELECT SUM(b2.weight_kg) AS w_sum
                FROM aviation.flights f2
                JOIN aviation.baggage b2 ON f2.flight_api_id = b2.flight_api_id
                WHERE f2.airline_iata = f.airline_iata
                GROUP BY f2.flight_api_id
            ) sub_airline_avg
        )
        AND f.schedule_date IN (
            SELECT DISTINCT recorded_at::DATE 
            FROM aviation.weather 
            WHERE wind_speed_kmh >= (SELECT AVG(wind_speed_kmh) FROM aviation.weather)
        );
        """

        cte_sql = """
        WITH adverse_weather_days AS (
            SELECT DISTINCT recorded_at::DATE AS weather_date
            FROM aviation.weather
            WHERE wind_speed_kmh >= (SELECT AVG(wind_speed_kmh) FROM aviation.weather)
        ),
        flight_baggage_metrics AS (
            SELECT flight_api_id, ROUND(SUM(weight_kg)::numeric, 1) AS total_weight_kg
            FROM aviation.baggage
            GROUP BY flight_api_id
        ),
        airline_benchmarks AS (
            SELECT f.airline_iata, AVG(fbm.total_weight_kg) AS avg_carrier_weight
            FROM aviation.flights f
            JOIN flight_baggage_metrics fbm ON f.flight_api_id = fbm.flight_api_id
            WHERE f.airline_iata IS NOT NULL
            GROUP BY f.airline_iata
        )
        SELECT 
            f.flight_api_id, f.airline_iata, f.schedule_date,
            fbm.total_weight_kg, ROUND(ab.avg_carrier_weight::numeric, 1) AS benchmark_weight
        FROM aviation.flights f
        JOIN adverse_weather_days aw ON f.schedule_date = aw.weather_date
        JOIN flight_baggage_metrics fbm ON f.flight_api_id = fbm.flight_api_id
        JOIN airline_benchmarks ab ON f.airline_iata = ab.airline_iata
        WHERE fbm.total_weight_kg >= ab.avg_carrier_weight;
        """

        df_sub, lat_sub = run_timed_query(sub_sql)
        df_cte, lat_cte = run_timed_query(cte_sql)
        speedup = (lat_sub / lat_cte) if lat_cte > 0 else 1.0

        col_b1, col_b2, col_b3 = st.columns(3)
        col_b1.metric("Subquery Execution Time", f"{lat_sub:.1f} ms", delta="Slower", delta_color="inverse")
        col_b2.metric("CTE Execution Time", f"{lat_cte:.1f} ms", delta=f"{speedup:.1f}x Faster", delta_color="normal")
        col_b3.metric("Latency Reduction", f"{((lat_sub - lat_cte) / lat_sub) * 100:.0f}% Faster")

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("**Approach A: Nested Subquery**")
            st.caption("Re-evaluates subqueries row-by-row")
            st.code(sub_sql, language="sql")
        with col_c2:
            st.markdown("**Approach B: Common Table Expressions (CTE)**")
            st.caption("Materializes intermediate sets in memory once")
            st.code(cte_sql, language="sql")

    with sql_tab2:
        st.markdown("#### Concession Category & Hourly Wave SQL (Tab 2)")
        st.code(hourly_sql, language="sql")

    with sql_tab3:
        st.markdown("#### Window Function Ranking SQL (Tab 4)")
        st.code(rank_sql, language="sql")

    with sql_tab4:
        st.markdown("#### Materialized View Definition & Indexing (Tab 5)")
        st.code("""
        CREATE MATERIALIZED VIEW aviation.mv_daily_operational_summary AS
        SELECT 
            f.schedule_date,
            COUNT(DISTINCT f.flight_api_id) AS total_flights,
            COUNT(DISTINCT f.airline_iata) AS distinct_airlines,
            COALESCE(SUM(r.amount_eur), 0) AS total_retail_spend_eur,
            COALESCE(SUM(p.total_amount_eur), 0) AS total_parking_intake_eur
        FROM aviation.flights f
        LEFT JOIN aviation.retail r ON f.flight_api_id = r.flight_api_id
        LEFT JOIN aviation.parking p ON f.schedule_date = p.parked_date
        GROUP BY f.schedule_date;

        CREATE UNIQUE INDEX idx_mv_daily_summary_date 
        ON aviation.mv_daily_operational_summary (schedule_date);
        """, language="sql")

    with sql_tab5:
        st.markdown("#### Live Warehouse Entity Manifest Query (Tab 1)")
        st.code(manifest_sql, language="sql")