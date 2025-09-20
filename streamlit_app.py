import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Vendor Demand Forecasting", layout="wide")

# ---------------- Session State ----------------
if "vendor_data" not in st.session_state:
    st.session_state.vendor_data = {}
if "current_vendor" not in st.session_state:
    st.session_state.current_vendor = None
if "current_projection" not in st.session_state:
    st.session_state.current_projection = None

# ---------------- File Upload ----------------
st.title("📦 Vendor Demand Forecasting System")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])
if uploaded_file:
    excel_file = pd.ExcelFile(uploaded_file)
    vendor_data = {}
    for sheet in excel_file.sheet_names:
        raw = pd.read_excel(excel_file, sheet_name=sheet, header=None).iloc[:, :4]
        rows = []
        for _, r in raw.iterrows():
            name = str(r.iloc[0]) if not pd.isna(r.iloc[0]) else ""
            p1 = float(r.iloc[1]) if not pd.isna(r.iloc[1]) else 0.0
            p2 = float(r.iloc[2]) if not pd.isna(r.iloc[2]) else 0.0
            p3 = float(r.iloc[3]) if not pd.isna(r.iloc[3]) else 0.0
            if name.strip():
                rows.append([name, p1, p2, p3])
        vendor_data[sheet] = rows

    st.session_state.vendor_data = vendor_data
    st.success(f"Imported {len(vendor_data)} vendors")

# ---------------- Search Vendor ----------------
if st.session_state.vendor_data:
    vendor_list = list(st.session_state.vendor_data.keys())
    vendor_name = st.selectbox("Search Vendor", vendor_list)

    if vendor_name:
        st.session_state.current_vendor = vendor_name
        data = st.session_state.vendor_data[vendor_name]

        df = pd.DataFrame(data, columns=["Product", "1 Day", "2 Days", "5 Days"])
        df["On Hand"] = 0
        st.session_state.df = df

        st.write("### Vendor Products")
        st.dataframe(df, use_container_width=True)

        # ---------------- Projections ----------------
        st.write("### Select Projection")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("1 Day Projection"):
                st.session_state.current_projection = "1"
        with col2:
            if st.button("2 Days Projection"):
                st.session_state.current_projection = "2"
        with col3:
            if st.button("5 Days Projection"):
                st.session_state.current_projection = "5"

        if st.session_state.current_projection:
            df = st.session_state.df.copy()
            base_col = {"1": "1 Day", "2": "2 Days", "5": "5 Days"}[st.session_state.current_projection]
            df["Projection"] = df[base_col] - df["On Hand"]
            df["Projection"] = df["Projection"].apply(lambda x: max(0, int(x)))
            st.session_state.df = df

            st.success(f"Showing {st.session_state.current_projection} Day Projection")
            st.dataframe(df, use_container_width=True)

            # ---------------- Save Invoice ----------------
            if st.button("Save Invoice"):
                items = df[df["Projection"] > 0][["Product", "Projection"]].values.tolist()

                if not items:
                    st.warning("⚠️ No demand to save from the selected projection.")
                else:
                    st.write("## 🧾 Vendor Demand Invoice")
                    st.write(f"**Vendor:** {vendor_name}")
                    st.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                    invoice_df = pd.DataFrame(items, columns=["Item", "Order Qty"])
                    st.table(invoice_df)

                    total_qty = invoice_df["Order Qty"].sum()
                    st.write(f"**Total Items:** {len(invoice_df)}")
                    st.write(f"**Total Qty:** {total_qty}")

                    # Copy invoice text for WhatsApp
                    invoice_text = [
                        "*Vendor Demand Invoice*",
                        f"*Vendor:* {vendor_name}",
                        f"*Date:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        "",
                        "*ITEMS:*"
                    ]
                    for product, qty in items:
                        invoice_text.append(f"- {product}: {qty}")
                    invoice_text.append("")
                    invoice_text.append(f"*Total Items:* {len(invoice_df)}")
                    invoice_text.append(f"*Total Qty:* {total_qty}")

                    st.code("\n".join(invoice_text), language="markdown")
                    st.info("📋 Copy the above text and paste it directly into WhatsApp.")
