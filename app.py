import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(
    layout="wide",
    page_title="NovaRetail Customer Intelligence Dashboard"
)

st.title("NovaRetail Customer Intelligence Dashboard")
st.subheader("Revenue, Risk Signals, and Growth Opportunities by Segment, Channel, Category, and Region")


# -----------------------------
# Data loading and preparation
# -----------------------------
@st.cache_data
def load_data(path: str = "NR_dataset.xlsx") -> pd.DataFrame:
    try:
        df = pd.read_excel(path)
    except FileNotFoundError:
        st.error("Dataset file not found in repository.")
        st.stop()
    except Exception as e:
        st.error(f"Error loading dataset: {e}")
        st.stop()

    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    return df


df_raw = load_data()

required_fields = {
    "idx": "idx",
    "label": "label",
    "customerid": "customerid",
    "transactionid": "transactionid",
    "transactiondate": "transactiondate",
    "productcategory": "productcategory",
    "purchaseamount": "purchaseamount",
    "customeragegroup": "customeragegroup",
    "customergender": "customergender",
    "customerregion": "customerregion",
    "customersatisfaction": "customersatisfaction",
    "retailchannel": "retailchannel",
}

normalized_cols = set(df_raw.columns)
missing = [logical for logical, col in required_fields.items() if col not in normalized_cols]

if missing:
    st.error(
        "The dataset is missing required logical fields: "
        + ", ".join(missing)
    )
    st.write("Available columns after normalization:", df_raw.columns.tolist())
    st.stop()

col_idx = required_fields["idx"]
col_label = required_fields["label"]
col_customerid = required_fields["customerid"]
col_transactionid = required_fields["transactionid"]
col_transactiondate = required_fields["transactiondate"]
col_productcategory = required_fields["productcategory"]
col_purchaseamount = required_fields["purchaseamount"]
col_customeragegroup = required_fields["customeragegroup"]
col_customergender = required_fields["customergender"]
col_customerregion = required_fields["customerregion"]
col_customersatisfaction = required_fields["customersatisfaction"]
col_retailchannel = required_fields["retailchannel"]

df = df_raw.copy()

df[col_purchaseamount] = pd.to_numeric(df[col_purchaseamount], errors="coerce")
df[col_customersatisfaction] = pd.to_numeric(df[col_customersatisfaction], errors="coerce")
df[col_transactiondate] = pd.to_datetime(df[col_transactiondate], errors="coerce")

before_rows = len(df)
df = df[
    (df[col_purchaseamount].notna()) &
    (df[col_purchaseamount] > 0) &
    (df[col_transactiondate].notna())
]
after_rows = len(df)
dropped_rows = before_rows - after_rows

st.caption(
    f"Data cleaning applied: removed {dropped_rows} rows with missing/invalid purchase amounts "
    f"or transaction dates."
)

if df.empty:
    st.error("All rows were removed during cleaning. Please check the dataset quality.")
    st.stop()


# -----------------------------
# Sidebar filters
# -----------------------------
st.sidebar.header("Filters")

min_date = df[col_transactiondate].min()
max_date = df[col_transactiondate].max()

date_range = st.sidebar.date_input(
    "Date Range",
    value=(min_date.date(), max_date.date()),
    min_value=min_date.date(),
    max_value=max_date.date()
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date.date(), max_date.date()

def multiselect_with_all(label, series):
    unique_vals = sorted(series.dropna().unique())
    options = ["All"] + list(unique_vals)
    selected = st.sidebar.multiselect(label, options, default=["All"])
    return selected

label_sel = multiselect_with_all("Segment (label)", df[col_label])
region_sel = multiselect_with_all("Region", df[col_customerregion])
product_sel = multiselect_with_all("Product Category", df[col_productcategory])
channel_sel = multiselect_with_all("Retail Channel", df[col_retailchannel])
gender_sel = multiselect_with_all("Gender", df[col_customergender])
age_sel = multiselect_with_all("Age Group", df[col_customeragegroup])

df_filtered = df.copy()

mask_date = (
    (df_filtered[col_transactiondate] >= pd.to_datetime(start_date)) &
    (df_filtered[col_transactiondate] <= pd.to_datetime(end_date))
)
df_filtered = df_filtered[mask_date]

def apply_cat_filter(df_in, col, selected):
    if "All" in selected or len(selected) == 0:
        return df_in
    return df_in[df_in[col].isin(selected)]

df_filtered = apply_cat_filter(df_filtered, col_label, label_sel)
df_filtered = apply_cat_filter(df_filtered, col_customerregion, region_sel)
df_filtered = apply_cat_filter(df_filtered, col_productcategory, product_sel)
df_filtered = apply_cat_filter(df_filtered, col_retailchannel, channel_sel)
df_filtered = apply_cat_filter(df_filtered, col_customergender, gender_sel)
df_filtered = apply_cat_filter(df_filtered, col_customeragegroup, age_sel)

if df_filtered.empty:
    st.warning("No data matches the current filters.")
    st.stop()


# -----------------------------
# KPI row
# -----------------------------
total_revenue = df_filtered[col_purchaseamount].sum()
total_transactions = df_filtered[col_transactionid].nunique()
unique_customers = df_filtered[col_customerid].nunique()
avg_satisfaction = df_filtered[col_customersatisfaction].mean()

growth_mask = df_filtered[col_label].str.lower() == "growth"
growth_revenue = df_filtered.loc[growth_mask, col_purchaseamount].sum()
share_growth_revenue = (growth_revenue / total_revenue * 100) if total_revenue > 0 else 0

decline_mask = df_filtered[col_label].str.lower() == "decline"
decline_revenue = df_filtered.loc[decline_mask, col_purchaseamount].sum()

k1, k2, k3, k4, k5, k6 = st.columns(6)

k1.metric("Total Revenue", f"${total_revenue:,.2f}")
k2.metric("Total Transactions", f"{total_transactions:,}")
k3.metric("Unique Customers", f"{unique_customers:,}")
k4.metric("Avg Satisfaction", f"{avg_satisfaction:.2f}")
k5.metric("Share of Revenue from Growth Segment", f"{share_growth_revenue:.1f}%")
k6.metric("Decline Segment Revenue", f"${decline_revenue:,.2f}")


# -----------------------------
# Core Visualizations
# -----------------------------
st.markdown("---")

left, right = st.columns(2)

# Revenue by Segment
with left:
    st.subheader("Revenue by Segment")
    seg_rev = (
        df_filtered.groupby(col_label, as_index=False)[col_purchaseamount]
        .sum()
        .rename(columns={col_purchaseamount: "revenue"})
        .sort_values("revenue", ascending=False)
    )
    fig_seg = px.bar(seg_rev, x=col_label, y="revenue", title="Revenue by Segment")
    st.plotly_chart(fig_seg, use_container_width=True)

# Revenue Trend (Scatterplot, no grouping)
with right:
    st.subheader("Revenue Trend Over Time (Scatterplot)")

    df_trend = df_filtered.copy()
    df_trend["month"] = df_trend[col_transactiondate].dt.to_period("M").dt.to_timestamp()

    trend = (
        df_trend.groupby("month", as_index=False)[col_purchaseamount]
        .sum()
        .rename(columns={col_purchaseamount: "revenue"})
    )

    fig_trend = px.scatter(
        trend,
        x="month",
        y="revenue",
        title="Monthly Revenue Trend (Scatterplot)"
    )

    fig_trend.update_traces(mode="markers+lines")
    fig_trend.update_layout(xaxis_title="Month", yaxis_title="Revenue")

    st.plotly_chart(fig_trend, use_container_width=True)


# Middle row: Revenue by Product + Revenue by Region
mid_left, mid_right = st.columns(2)

with mid_left:
    st.subheader("Revenue by Product")
    cat_channel = (
        df_filtered.groupby([col_productcategory, col_retailchannel], as_index=False)[col_purchaseamount]
        .sum()
        .rename(columns={col_purchaseamount: "revenue"})
    )
    cat_order = (
        cat_channel.groupby(col_productcategory)["revenue"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    fig_cat = px.bar(
        cat_channel,
        x=col_productcategory,
        y="revenue",
        color=col_retailchannel,
        category_orders={col_productcategory: cat_order},
        title="Revenue by Product",
        barmode="group"
    )
    st.plotly_chart(fig_cat, use_container_width=True)

with mid_right:
    st.subheader("Revenue by Region")
    region_group = (
        df_filtered.groupby([col_customerregion, col_label], as_index=False)[col_purchaseamount]
        .sum()
        .rename(columns={col_purchaseamount: "revenue"})
    )
    fig_region = px.bar(
        region_group,
        x=col_customerregion,
        y="revenue",
        color=col_label,
        title="Revenue by Region"
    )
    st.plotly_chart(fig_region, use_container_width=True)


# -----------------------------
# Early Warning Signals
# -----------------------------
st.markdown("---")
st.subheader("Early Warning Signals")

seg_summary = (
    df_filtered
    .groupby(col_label)
    .agg(
        avg_satisfaction=(col_customersatisfaction, "mean"),
        revenue=(col_purchaseamount, "sum"),
        transactions=(col_transactionid, "nunique"),
        unique_customers=(col_customerid, "nunique")
    )
    .reset_index()
)

overall_transactions = df_filtered[col_transactionid].nunique()
overall_customers = df_filtered[col_customerid].nunique()
overall_tx_per_customer = (
    overall_transactions / overall_customers if overall_customers > 0 else np.nan
)

seg_tx = (
    df_filtered
    .groupby(col_label)
    .agg(
        seg_transactions=(col_transactionid, "nunique"),
        seg_customers=(col_customerid, "nunique")
    )
    .reset_index()
)

seg_tx["tx_per_customer"] = (
    seg_tx["seg_transactions"] / seg_tx["seg_customers"]
).replace([np.inf, -np.inf], np.nan)

seg_summary = seg_summary.merge(
    seg_tx[[col_label, "tx_per_customer"]],
    on=col_label,
    how="left"
)

st.dataframe(seg_summary, use_container_width=True)

warnings_triggered = []

# Rule 1: Low satisfaction
low_sat_segments = seg_summary[seg_summary["avg_satisfaction"] < 3.0][col_label].tolist()
if low_sat_segments:
    st.warning(f"Low satisfaction detected in: {', '.join(low_sat_segments)}")
    warnings_triggered.append("low_satisfaction")

# Rule 2: Low engagement
low_eng_segments = seg_summary[
    seg_summary["tx_per_customer"] < overall_tx_per_customer
][col_label].tolist()
if low_eng_segments:
    st.warning(f"Lower engagement detected in: {', '.join(low_eng_segments)}")
    warnings_triggered.append("low_engagement")

# Rule 3: Concentration risk
cust_revenue = (
    df_filtered
    .groupby(col_customerid, as_index=False)[col_purchaseamount]
    .sum()
    .rename(columns={col_purchaseamount: "revenue"})
    .sort_values("revenue", ascending=False)
)

top10 = cust_revenue.head(10)
top10_share = (
    top10["revenue"].sum() / cust_revenue["revenue"].sum()
    if cust_revenue["revenue"].sum() > 0 else 0
)

# 🔥 YOUR REQUESTED CHANGE: Make this line yellow
st.warning(f"Top 10 customers account for {top10_share * 100:.1f}% of revenue.")

if top10_share > 0.4:
    st.warning("High concentration risk detected.")
    warnings_triggered.append("high_concentration")

# Recommended actions
if warnings_triggered:
    st.markdown("**Recommended Actions:**")
    if "low_satisfaction" in warnings_triggered:
        st.write("- Improve service recovery and customer experience for low-satisfaction segments.")
    if "low_engagement" in warnings_triggered:
        st.write("- Launch retention and re-engagement campaigns.")
    if "high_concentration" in warnings_triggered:
        st.write("- Diversify revenue by nurturing mid-tier customers.")


# -----------------------------
# Filtered Data Table
# -----------------------------
st.markdown("---")
st.subheader("Filtered Transactions")

ordered_cols = [
    col_idx,
    col_transactionid,
    col_transactiondate,
    col_customerid,
    col_label,
    col_productcategory,
    col_purchaseamount,
    col_customeragegroup,
    col_customergender,
    col_customerregion,
    col_customersatisfaction,
    col_retailchannel
]

ordered_cols = [c for c in ordered_cols if c in df_filtered.columns]
df_display = df_filtered[ordered_cols].reset_index(drop=True)

st.dataframe(df_display, use_container_width=True)
