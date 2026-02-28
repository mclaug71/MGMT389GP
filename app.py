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
        title="Monthly Revenue Trend (Scatterplot)",
    )

    fig_trend.update_traces(mode="markers+lines")  # optional: connects points
    fig_trend.update_layout(xaxis_title="Month", yaxis_title="Revenue")

    st.plotly_chart(fig_trend, use_container_width=True)
