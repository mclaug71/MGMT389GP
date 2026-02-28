# app.py
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

    # Normalize column names
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    return df


df_raw = load_data()

# Logical required fields (normalized)
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

# Rename for convenience (already normalized, but keep mapping explicit)
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

# Type conversions
df[col_purchaseamount] = pd.to_numeric(df[col_purchaseamount], errors="coerce")
df[col_customersatisfaction] = pd.to_numeric(df[col_customersatisfaction], errors="coerce")
df[col_transactiondate] = pd.to_datetime(df[col_transactiondate], errors="coerce")

# Data cleaning rules
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
# Sidebar filters (layout inspired by Filters.pdf)
# -----------------------------
st.sidebar.header("Filters")

# Date range filter
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

# Helper to build multiselect with "All"
def multiselect_with_all(label, series):
    unique_vals = sorted(series.dropna().unique())
    options = ["All"] + list(unique_vals)
    selected = st.sidebar.multiselect(label, options, default=["All"])
    return selected, options

label_sel, label_opts = multiselect_with_all("Segment (label)", df[col_label])
region_sel, region_opts = multiselect_with_all("Region", df[col_customerregion])
product_sel, product_opts = multiselect_with_all("Product Category", df[col_productcategory])
channel_sel, channel_opts = multiselect_with_all("Retail Channel", df[col_retailchannel])
gender_sel, gender_opts = multiselect_with_all("Gender", df[col_customergender])
age_sel, age_opts = multiselect_with_all("Age Group", df[col_customeragegroup])

# -----------------------------
# Apply filters (without modifying original df)
# -----------------------------
df_filtered = df.copy()

# Date filter
mask_date = (
    (df_filtered[col_transactiondate] >= pd.to_datetime(start_date)) &
    (df_filtered[col_transactiondate] <= pd.to_datetime(end_date))
)
df_filtered = df_filtered[mask_date]

# Categorical filters
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
kpi_required_cols = [
    col_purchaseamount,
    col_transactionid,
    col_customerid,
    col_customersatisfaction,
    col_label,
]

missing_kpi_cols = [c for c in kpi_required_cols if c not in df_filtered.columns]
if missing_kpi_cols:
    st.error(
        "Cannot compute KPIs due to missing columns: "
        + ", ".join(missing_kpi_cols)
    )
    st.stop()

total_revenue = df_filtered[col_purchaseamount].sum()
total_transactions = df_filtered[col_transactionid].nunique()
unique_customers = df_filtered[col_customerid].nunique()
avg_satisfaction = df_filtered[col_customersatisfaction].mean()

# Share of revenue from Growth segment (label == "Growth")
# Do not hardcode label values beyond using what's present
growth_mask = df_filtered[col_label].str.lower() == "growth"
growth_revenue = df_filtered.loc[growth_mask, col_purchaseamount].sum()
share_growth_revenue = (growth_revenue / total_revenue * 100) if total_revenue > 0 else 0

# Decline segment revenue
decline_mask = df_filtered[col_label].str.lower() == "decline"
decline_revenue = df_filtered.loc[decline_mask, col_purchaseamount].sum()

kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5, kpi_col6 = st.columns(6)

kpi_col1.metric("Total Revenue", f"${total_revenue:,.2f}")
kpi_col2.metric("Total Transactions", f"{total_transactions:,}")
kpi_col3.metric("Unique Customers", f"{unique_customers:,}")
kpi_col4.metric("Avg Satisfaction", f"{avg_satisfaction:.2f}" if not np.isnan(avg_satisfaction) else "N/A")
kpi_col5.metric("Share of Revenue from Growth Segment", f"{share_growth_revenue:.1f}%")
kpi_col6.metric("Decline Segment Revenue", f"${decline_revenue:,.2f}")


# -----------------------------
# Core visualizations (layout inspired by Filters.pdf)
# -----------------------------
st.markdown("---")

# Top row: Revenue by Segment & Revenue Trend
top_left, top_right = st.columns(2)

with top_left:
    st.subheader("Revenue by Segment")
    seg_rev = (
        df_filtered
        .groupby(col_label, as_index=False)[col_purchaseamount]
        .sum()
        .rename(columns={col_purchaseamount: "revenue"})
        .sort_values("revenue", ascending=False)
    )
    if not seg_rev.empty:
        fig_seg = px.bar(
            seg_rev,
            x=col_label,
            y="revenue",
            title="Revenue by Segment",
        )
        fig_seg.update_layout(xaxis_title="Segment", yaxis_title="Revenue")
        st.plotly_chart(fig_seg, use_container_width=True)

with top_right:
    st.subheader("Revenue Trend Over Time")
    color_choice = st.selectbox(
        "Color revenue trend by",
        options=[col_label, col_retailchannel],
        format_func=lambda x: "Segment (label)" if x == col_label else "Retail Channel"
    )

    df_trend = df_filtered.copy()
    df_trend["month"] = df_trend[col_transactiondate].dt.to_period("M").dt.to_timestamp()
    trend_group_cols = ["month", color_choice]

    trend = (
        df_trend
        .groupby(trend_group_cols, as_index=False)[col_purchaseamount]
        .sum()
        .rename(columns={col_purchaseamount: "revenue"})
        .sort_values("month")
    )

    if not trend.empty:
        fig_trend = px.line(
            trend,
            x="month",
            y="revenue",
            color=color_choice,
            title="Monthly Revenue Trend"
        )
        fig_trend.update_layout(xaxis_title="Month", yaxis_title="Revenue")
        st.plotly_chart(fig_trend, use_container_width=True)

# Middle row: Channel & Category Mix, Regional Performance
mid_left, mid_right = st.columns(2)

with mid_left:
    st.subheader("Channel and Category Mix")
    cat_channel = (
        df_filtered
        .groupby([col_productcategory, col_retailchannel], as_index=False)[col_purchaseamount]
        .sum()
        .rename(columns={col_purchaseamount: "revenue"})
    )
    # Sort categories by total revenue
    cat_order = (
        cat_channel.groupby(col_productcategory)["revenue"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    if not cat_channel.empty:
        fig_cat = px.bar(
            cat_channel,
            x=col_productcategory,
            y="revenue",
            color=col_retailchannel,
            category_orders={col_productcategory: cat_order},
            title="Revenue by Product Category and Channel",
            barmode="group"
        )
        fig_cat.update_layout(xaxis_title="Product Category", yaxis_title="Revenue")
        st.plotly_chart(fig_cat, use_container_width=True)

with mid_right:
    st.subheader("Regional Performance")
    region_group = (
        df_filtered
        .groupby([col_customerregion, col_label], as_index=False)[col_purchaseamount]
        .sum()
        .rename(columns={col_purchaseamount: "revenue"})
    )
    if not region_group.empty:
        fig_region = px.bar(
            region_group,
            x=col_customerregion,
            y="revenue",
            color=col_label,
            title="Revenue by Region (colored by Segment)",
        )
        fig_region.update_layout(xaxis_title="Region", yaxis_title="Revenue")
        st.plotly_chart(fig_region, use_container_width=True)


# -----------------------------
# Early Warning Signals panel
# -----------------------------
st.markdown("---")
st.subheader("Early Warning Signals")

# Segment-level summary
seg_summary = (
    df_filtered
    .groupby(col_label)
    .agg(
        avg_satisfaction=(col_customersatisfaction, "mean"),
        revenue=(col_purchaseamount, "sum"),
        transactions=(col_transactionid, "nunique"),
        unique_customers=(col_customerid, "nunique"),
    )
    .reset_index()
)

# Overall metrics for heuristics
overall_transactions = df_filtered[col_transactionid].nunique()
overall_customers = df_filtered[col_customerid].nunique()
overall_tx_per_customer = (
    overall_transactions / overall_customers if overall_customers > 0 else np.nan
)

# Transactions per customer per segment
seg_tx_per_customer = (
    df_filtered
    .groupby(col_label)
    .agg(
        seg_transactions=(col_transactionid, "nunique"),
        seg_customers=(col_customerid, "nunique"),
    )
    .reset_index()
)
seg_tx_per_customer["tx_per_customer"] = (
    seg_tx_per_customer["seg_transactions"] / seg_tx_per_customer["seg_customers"]
).replace([np.inf, -np.inf], np.nan)

seg_summary = seg_summary.merge(seg_tx_per_customer[[col_label, "tx_per_customer"]], on=col_label, how="left")

st.dataframe(seg_summary, use_container_width=True)

# Heuristic rules
warnings_triggered = []

# Rule 1: Low satisfaction
low_sat_threshold = 3.0
low_sat_segments = seg_summary[seg_summary["avg_satisfaction"] < low_sat_threshold][col_label].tolist()
if low_sat_segments:
    st.warning(
        f"Low satisfaction detected in segments: {', '.join(map(str, low_sat_segments))} "
        f"(avg satisfaction < {low_sat_threshold})."
    )
    warnings_triggered.append("low_satisfaction")

# Rule 2: Lower engagement (transactions per customer below overall average)
if not np.isnan(overall_tx_per_customer):
    low_eng_segments = seg_summary[
        seg_summary["tx_per_customer"] < overall_tx_per_customer
    ][col_label].tolist()
    if low_eng_segments:
        st.warning(
            "Lower engagement detected in segments: "
            + ", ".join(map(str, low_eng_segments))
            + " (transactions per customer below overall average)."
        )
        warnings_triggered.append("low_engagement")

# Rule 3: High concentration risk (top 10 customers share)
cust_revenue = (
    df_filtered
    .groupby(col_customerid, as_index=False)[col_purchaseamount]
    .sum()
    .rename(columns={col_purchaseamount: "revenue"})
    .sort_values("revenue", ascending=False)
)
top_n_concentration = 10
top_n = cust_revenue.head(top_n_concentration)
top_n_share = (
    top_n["revenue"].sum() / cust_revenue["revenue"].sum()
    if not cust_revenue.empty and cust_revenue["revenue"].sum() > 0
    else 0
)
concentration_threshold = 0.4  # adjustable in code

st.write(
    f"Top {top_n_concentration} customers account for "
    f"{top_n_share * 100:.1f}% of total revenue."
)

if top_n_share > concentration_threshold:
    st.warning(
        f"High revenue concentration risk: top {top_n_concentration} customers "
        f"contribute more than {concentration_threshold * 100:.0f}% of revenue."
    )
    warnings_triggered.append("high_concentration")

# Recommended actions based on triggered warnings
if warnings_triggered:
    st.markdown("**Recommended Actions:**")
    actions = []
    if "low_satisfaction" in warnings_triggered:
        actions.append(
            "- Implement service recovery programs and targeted satisfaction surveys for low-satisfaction segments."
        )
        actions.append(
            "- Prioritize training and quality improvements in touchpoints serving these segments."
        )
    if "low_engagement" in warnings_triggered:
        actions.append(
            "- Launch retention campaigns (personalized offers, loyalty benefits) for low-engagement segments."
        )
        actions.append(
            "- Analyze channel and category preferences to design relevant cross-sell and up-sell journeys."
        )
    if "high_concentration" in warnings_triggered:
        actions.append(
            "- Diversify revenue base by nurturing mid-tier customers with growth potential."
        )
        actions.append(
            "- Develop contingency plans and strategic account management for top customers."
        )

    for a in actions:
        st.write(a)


# -----------------------------
# Top Customers panel
# -----------------------------
st.markdown("---")
st.subheader("Top Customers")

top_n_choice = st.selectbox("Number of top customers to display", options=[5, 10, 20], index=1)

cust_group = df_filtered.groupby(col_customerid)

def most_frequent(series: pd.Series):
    if series.empty:
        return np.nan
    return series.value_counts().idxmax()

top_customers = cust_group.agg(
    total_revenue=(col_purchaseamount, "sum"),
    transactions=(col_transactionid, "nunique"),
    avg_satisfaction=(col_customersatisfaction, "mean"),
    most_frequent_productcategory=(col_productcategory, most_frequent),
    most_frequent_retailchannel=(col_retailchannel, most_frequent),
).reset_index()

top_customers = top_customers.sort_values("total_revenue", ascending=False).head(top_n_choice)

top_left, top_right = st.columns(2)

with top_left:
    st.write(f"Top {top_n_choice} Customers by Revenue")
    st.dataframe(top_customers, use_container_width=True)

with top_right:
    if not top_customers.empty:
        fig_top_cust = px.bar(
            top_customers,
            x=col_customerid,
            y="total_revenue",
            title=f"Top {top_n_choice} Customers by Revenue",
        )
        fig_top_cust.update_layout(xaxis_title="Customer ID", yaxis_title="Total Revenue")
        st.plotly_chart(fig_top_cust, use_container_width=True)


# -----------------------------
# Filtered data table
# -----------------------------
st.markdown("---")
st.subheader("Filtered Transactions")

# Keep columns in a clean, readable order
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
    col_retailchannel,
]

ordered_cols = [c for c in ordered_cols if c in df_filtered.columns]
df_display = df_filtered[ordered_cols].reset_index(drop=True)

st.dataframe(df_display, use_container_width=True)
