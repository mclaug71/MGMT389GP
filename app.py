import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(
    layout="wide",
    page_title="NovaRetail Customer Intelligence Dashboard"
)

st.title("NovaRetail Customer Intelligence Dashboard")
st.subheader(
    "Revenue, Risk Signals, and Growth Opportunities by Segment, Channel, Category, and Region"
)

# =========================
# DATA LOADING
# =========================
try:
    df = pd.read_excel("NR_dataset.xlsx")
except FileNotFoundError:
    st.error("Dataset file not found in repository.")
    st.stop()
except Exception as e:
    st.error(f"Error loading dataset: {e}")
    st.stop()

# Normalize column names
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_")
)

# Logical fields required
required_fields = [
    "idx",
    "label",
    "customerid",
    "transactionid",
    "transactiondate",
    "productcategory",
    "purchaseamount",
    "customeragegroup",
    "customergender",
    "customerregion",
    "customersatisfaction",
    "retailchannel"
]

missing_fields = [col for col in required_fields if col not in df.columns]

if missing_fields:
    st.error(f"Missing required logical fields: {missing_fields}")
    st.write("Available columns:", df.columns.tolist())
    st.stop()

# Data type conversions
df["purchaseamount"] = pd.to_numeric(df["purchaseamount"], errors="coerce")
df["customersatisfaction"] = pd.to_numeric(df["customersatisfaction"], errors="coerce")
df["transactiondate"] = pd.to_datetime(df["transactiondate"], errors="coerce")

# Drop invalid rows
initial_rows = len(df)
df = df.dropna(subset=["purchaseamount", "transactiondate"])
df = df[df["purchaseamount"] > 0]
dropped_rows = initial_rows - len(df)

if dropped_rows > 0:
    st.caption(f"{dropped_rows} rows removed due to invalid purchaseamount or transactiondate.")

if df.empty:
    st.error("No valid data available after cleaning.")
    st.stop()

# =========================
# SIDEBAR FILTERS
# =========================
st.sidebar.header("Filters")

min_date = df["transactiondate"].min()
max_date = df["transactiondate"].max()

date_range = st.sidebar.date_input(
    "Transaction Date Range",
    [min_date, max_date],
    min_value=min_date,
    max_value=max_date
)

def multiselect_filter(column_name, label_name):
    unique_vals = sorted(df[column_name].dropna().unique())
    options = ["All"] + list(unique_vals)
    selection = st.sidebar.multiselect(
        label_name,
        options=options,
        default=["All"]
    )
    return selection

label_filter = multiselect_filter("label", "Customer Segment")
region_filter = multiselect_filter("customerregion", "Customer Region")
category_filter = multiselect_filter("productcategory", "Product Category")
channel_filter = multiselect_filter("retailchannel", "Retail Channel")
gender_filter = multiselect_filter("customergender", "Customer Gender")
age_filter = multiselect_filter("customeragegroup", "Customer Age Group")

# Apply filters (without modifying original df)
filtered_df = df.copy()

if len(date_range) == 2:
    filtered_df = filtered_df[
        (filtered_df["transactiondate"] >= pd.to_datetime(date_range[0])) &
        (filtered_df["transactiondate"] <= pd.to_datetime(date_range[1]))
    ]

def apply_filter(dataframe, column_name, selection):
    if "All" not in selection and selection:
        return dataframe[dataframe[column_name].isin(selection)]
    return dataframe

filtered_df = apply_filter(filtered_df, "label", label_filter)
filtered_df = apply_filter(filtered_df, "customerregion", region_filter)
filtered_df = apply_filter(filtered_df, "productcategory", category_filter)
filtered_df = apply_filter(filtered_df, "retailchannel", channel_filter)
filtered_df = apply_filter(filtered_df, "customergender", gender_filter)
filtered_df = apply_filter(filtered_df, "customeragegroup", age_filter)

if filtered_df.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# =========================
# KPI SECTION
# =========================
try:
    total_revenue = filtered_df["purchaseamount"].sum()
    total_transactions = filtered_df["transactionid"].count()
    unique_customers = filtered_df["customerid"].nunique()
    avg_satisfaction = filtered_df["customersatisfaction"].mean()

    growth_revenue = filtered_df[filtered_df["label"] == "Growth"]["purchaseamount"].sum()
    decline_revenue = filtered_df[filtered_df["label"] == "Decline"]["purchaseamount"].sum()
    growth_share = (growth_revenue / total_revenue) if total_revenue > 0 else 0
except Exception as e:
    st.error(f"Error computing KPIs: {e}")
    st.stop()

kpi_cols = st.columns(6)

kpi_cols[0].metric("Total Revenue", f"${total_revenue:,.0f}")
kpi_cols[1].metric("Total Transactions", f"{total_transactions:,}")
kpi_cols[2].metric("Unique Customers", f"{unique_customers:,}")
kpi_cols[3].metric("Avg Satisfaction", f"{avg_satisfaction:.2f}")
kpi_cols[4].metric("Growth Revenue Share", f"{growth_share:.1%}")
kpi_cols[5].metric("Decline Segment Revenue", f"${decline_revenue:,.0f}")

st.markdown("---")

# =========================
# VISUALIZATIONS
# =========================

# A. Revenue by Segment
st.subheader("Revenue by Segment")

rev_by_segment = (
    filtered_df.groupby("label")["purchaseamount"]
    .sum()
    .reset_index()
    .sort_values("purchaseamount", ascending=False)
)

fig_segment = px.bar(
    rev_by_segment,
    x="label",
    y="purchaseamount"
)
st.plotly_chart(fig_segment, use_container_width=True)

# B. Revenue Trend Over Time
st.subheader("Revenue Trend Over Time")

color_option = st.selectbox(
    "Color trend by:",
    options=["label", "retailchannel"]
)

trend_df = filtered_df.copy()
trend_df["year_month"] = trend_df["transactiondate"].dt.to_period("M").astype(str)

trend_agg = (
    trend_df.groupby(["year_month", color_option])["purchaseamount"]
    .sum()
    .reset_index()
)

fig_trend = px.line(
    trend_agg,
    x="year_month",
    y="purchaseamount",
    color=color_option
)
st.plotly_chart(fig_trend, use_container_width=True)

# C. Channel and Category Mix
st.subheader("Channel and Category Mix")

mix_df = (
    filtered_df.groupby(["productcategory", "retailchannel"])["purchaseamount"]
    .sum()
    .reset_index()
)

total_category = (
    mix_df.groupby("productcategory")["purchaseamount"]
    .sum()
    .sort_values(ascending=False)
)

mix_df["productcategory"] = pd.Categorical(
    mix_df["productcategory"],
    categories=total_category.index,
    ordered=True
)

fig_mix = px.bar(
    mix_df.sort_values("productcategory"),
    x="productcategory",
    y="purchaseamount",
    color="retailchannel",
    barmode="group"
)
st.plotly_chart(fig_mix, use_container_width=True)

# D. Regional Performance
st.subheader("Regional Performance")

region_df = (
    filtered_df.groupby(["customerregion", "label"])["purchaseamount"]
    .sum()
    .reset_index()
)

fig_region = px.bar(
    region_df,
    x="customerregion",
    y="purchaseamount",
    color="label"
)
st.plotly_chart(fig_region, use_container_width=True)

st.markdown("---")

# =========================
# EARLY WARNING SIGNALS
# =========================
st.subheader("Early Warning Signals")

segment_summary = (
    filtered_df.groupby("label")
    .agg(
        revenue=("purchaseamount", "sum"),
        transactions=("transactionid", "count"),
        unique_customers=("customerid", "nunique"),
        avg_satisfaction=("customersatisfaction", "mean")
    )
    .reset_index()
)

segment_summary["transactions_per_customer"] = (
    segment_summary["transactions"] / segment_summary["unique_customers"]
)

overall_tpc = total_transactions / unique_customers if unique_customers > 0 else 0

st.dataframe(segment_summary, use_container_width=True)

# Concentration risk
customer_revenue = (
    filtered_df.groupby("customerid")["purchaseamount"]
    .sum()
    .sort_values(ascending=False)
)

top_10_share = (
    customer_revenue.head(10).sum() / total_revenue
    if total_revenue > 0 else 0
)

warnings_triggered = []

for _, row in segment_summary.iterrows():
    if row["avg_satisfaction"] < 3.0:
        warnings_triggered.append(f"Low satisfaction in segment: {row['label']}")
    if row["transactions_per_customer"] < overall_tpc:
        warnings_triggered.append(f"Lower engagement in segment: {row['label']}")

if top_10_share > 0.4:
    warnings_triggered.append("High revenue concentration risk (Top 10 customers)")

for w in warnings_triggered:
    st.warning(w)

if warnings_triggered:
    st.write("### Recommended Actions")
    st.write("- Prioritize service recovery initiatives in low satisfaction segments.")
    st.write("- Deploy targeted retention offers to segments with declining engagement.")
    st.write("- Diversify revenue base to reduce concentration risk.")
    st.write("- Invest in high-performing regions, channels, and categories to accelerate growth.")

st.markdown("---")

# =========================
# TOP CUSTOMERS
# =========================
st.subheader("Top Customers by Revenue")

top_n = st.selectbox("Select Top N Customers:", [5, 10, 20])

customer_summary = (
    filtered_df.groupby("customerid")
    .agg(
        total_revenue=("purchaseamount", "sum"),
        transactions=("transactionid", "count"),
        avg_satisfaction=("customersatisfaction", "mean")
    )
    .reset_index()
)

# Most frequent category and channel
most_category = (
    filtered_df.groupby(["customerid", "productcategory"])
    .size()
    .reset_index(name="count")
    .sort_values(["customerid", "count"], ascending=[True, False])
    .drop_duplicates("customerid")
    [["customerid", "productcategory"]]
)

most_channel = (
    filtered_df.groupby(["customerid", "retailchannel"])
    .size()
    .reset_index(name="count")
    .sort_values(["customerid", "count"], ascending=[True, False])
    .drop_duplicates("customerid")
    [["customerid", "retailchannel"]]
)

customer_summary = customer_summary.merge(most_category, on="customerid", how="left")
customer_summary = customer_summary.merge(most_channel, on="customerid", how="left")

top_customers = customer_summary.sort_values(
    "total_revenue", ascending=False
).head(top_n)

st.dataframe(top_customers, use_container_width=True)

fig_top = px.bar(
    top_customers,
    x="customerid",
    y="total_revenue"
)
st.plotly_chart(fig_top, use_container_width=True)

st.markdown("---")

# =========================
# TRANSACTION TABLE
# =========================
st.subheader("Filtered Transaction Data")

display_columns = [
    "transactiondate",
    "customerid",
    "transactionid",
    "label",
    "productcategory",
    "retailchannel",
    "purchaseamount",
    "customersatisfaction",
    "customerregion",
    "customergender",
    "customeragegroup"
]

display_columns = [col for col in display_columns if col in filtered_df.columns]

st.dataframe(
    filtered_df[display_columns].reset_index(drop=True),
    use_container_width=True
)
