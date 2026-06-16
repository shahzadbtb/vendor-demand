import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Auto BI Dashboard", layout="wide")

# -----------------------------
# 🔹 Helpers
# -----------------------------
def detect_columns(df):
    cols = df.columns.str.lower()

    def find(keyword_list):
        for c in df.columns:
            if any(k in c.lower() for k in keyword_list):
                return c
        return None

    mapping = {
        "date": find(["date", "time", "day"]),
        "qty": find(["qty", "quantity", "units"]),
        "value": find(["value", "amount", "sales", "revenue", "price"]),
        "vendor": find(["vendor", "supplier"]),
        "category": find(["category", "cat"]),
        "store": find(["store", "branch", "location"]),
        "item": find(["item", "product", "name"])
    }

    return mapping


def clean_data(df, mapping):
    df = df.copy()

    if mapping["date"]:
        df[mapping["date"]] = pd.to_datetime(df[mapping["date"]], errors="coerce")
        df["Year"] = df[mapping["date"]].dt.year
        df["Month"] = df[mapping["date"]].dt.month
        df["Day"] = df[mapping["date"]].dt.day

    return df


# -----------------------------
# 🔹 UI
# -----------------------------
st.title("📊 Auto Excel Analytics Dashboard (Mini Power BI)")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

if uploaded_file:

    df = pd.read_excel(uploaded_file)

    st.subheader("📄 Raw Data Preview")
    st.dataframe(df.head(20))

    # detect columns automatically
    mapping = detect_columns(df)
    df = clean_data(df, mapping)

    st.sidebar.header("🎛 Filters")

    # -----------------------------
    # Filters (dynamic)
    # -----------------------------
    if mapping["vendor"]:
        vendors = df[mapping["vendor"]].dropna().unique()
        vendor_filter = st.sidebar.multiselect("Vendor", vendors)
    else:
        vendor_filter = []

    if mapping["category"]:
        cats = df[mapping["category"]].dropna().unique()
        cat_filter = st.sidebar.multiselect("Category", cats)
    else:
        cat_filter = []

    if mapping["store"]:
        stores = df[mapping["store"]].dropna().unique()
        store_filter = st.sidebar.multiselect("Store", stores)
    else:
        store_filter = []

    # -----------------------------
    # Apply filters
    # -----------------------------
    filtered = df.copy()

    if vendor_filter and mapping["vendor"]:
        filtered = filtered[filtered[mapping["vendor"]].isin(vendor_filter)]

    if cat_filter and mapping["category"]:
        filtered = filtered[filtered[mapping["category"]].isin(cat_filter)]

    if store_filter and mapping["store"]:
        filtered = filtered[filtered[mapping["store"]].isin(store_filter)]

    # -----------------------------
    # KPI SECTION
    # -----------------------------
    st.subheader("📌 Key Metrics")

    col1, col2, col3 = st.columns(3)

    qty_val = mapping["qty"]
    value_val = mapping["value"]

    with col1:
        st.metric("Total Rows", len(filtered))

    with col2:
        if qty_val:
            st.metric("Total Qty", int(filtered[qty_val].fillna(0).sum()))
        else:
            st.metric("Total Qty", "N/A")

    with col3:
        if value_val:
            st.metric("Total Value", float(filtered[value_val].fillna(0).sum()))
        else:
            st.metric("Total Value", "N/A")

    # -----------------------------
    # CHARTS
    # -----------------------------
    st.subheader("📈 Analytics")

    chart1, chart2 = st.columns(2)

    # Vendor chart
    if mapping["vendor"] and value_val:
        with chart1:
            fig = px.bar(
                filtered.groupby(mapping["vendor"])[value_val].sum().reset_index(),
                x=mapping["vendor"],
                y=value_val,
                title="Value by Vendor"
            )
            st.plotly_chart(fig, use_container_width=True)

    # Category chart
    if mapping["category"] and value_val:
        with chart2:
            fig = px.pie(
                filtered.groupby(mapping["category"])[value_val].sum().reset_index(),
                names=mapping["category"],
                values=value_val,
                title="Value Distribution by Category"
            )
            st.plotly_chart(fig, use_container_width=True)

    # Time series
    if mapping["date"] and value_val:
        st.subheader("📅 Time Trend")

        time_df = filtered.groupby("Month")[value_val].sum().reset_index()
        fig = px.line(time_df, x="Month", y=value_val, markers=True)
        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------
    # DOWNLOAD
    # -----------------------------
    st.subheader("⬇ Export")

    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("Download Filtered Data", csv, "filtered_data.csv", "text/csv")