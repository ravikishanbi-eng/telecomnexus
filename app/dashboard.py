# pages/dashboard.py

import streamlit as st
import pandas as pd
import plotly.express as px

from db import get_connection


# ============================================================
# DATABASE HELPER
# ============================================================

def run_query(query, params=None):
    conn = get_connection()

    try:
        return pd.read_sql(
            query,
            conn,
            params=params
        )

    finally:
        conn.close()


# ============================================================
# KPI - TOTAL CUSTOMERS
# ============================================================

def get_total_customers():

    query = """
        SELECT COUNT(*) AS total_customers
        FROM crm.customer
        WHERE customer_status <> 'DELETED'
    """

    df = run_query(query)

    return int(df.iloc[0]["total_customers"])


# ============================================================
# KPI - ACTIVE CONTRACTS
# ============================================================

def get_active_contracts():

    query = """
        SELECT COUNT(*) AS active_contracts
        FROM crm.contract
        WHERE contract_status = 'ACTIVE'
    """

    df = run_query(query)

    return int(df.iloc[0]["active_contracts"])


# ============================================================
# KPI - ACTIVE SERVICES
# ============================================================

def get_active_services():

    query = """
        SELECT COUNT(*) AS active_services
        FROM crm.service
        WHERE service_status = 'ACTIVE'
    """

    df = run_query(query)

    return int(df.iloc[0]["active_services"])


# ============================================================
# KPI - MRR
# ============================================================

def get_mrr():

    query = """
        SELECT
            COALESCE(
                SUM(
                    cd.agreed_monthly_price
                    - COALESCE(cd.discount_amount, 0)
                ),
                0
            ) AS mrr

        FROM crm.service s

        JOIN crm.contract_detail cd
            ON cd.contract_id = s.contract_id
           AND cd.product_id = s.product_id

        WHERE s.service_status = 'ACTIVE'

          AND (
                cd.effective_from IS NULL
                OR cd.effective_from <= CURRENT_DATE
              )

          AND (
                cd.effective_to IS NULL
                OR cd.effective_to >= CURRENT_DATE
              )
    """

    df = run_query(query)

    return float(df.iloc[0]["mrr"])


# ============================================================
# KPI - ARPU
# ============================================================

def get_arpu():

    query = """
        WITH active_customers AS
        (
            SELECT COUNT(DISTINCT customer_id) AS customer_count
            FROM crm.service
            WHERE service_status = 'ACTIVE'
        ),

        mrr AS
        (
            SELECT
                COALESCE(
                    SUM(
                        cd.agreed_monthly_price
                        - COALESCE(cd.discount_amount, 0)
                    ),
                    0
                ) AS monthly_revenue

            FROM crm.service s

            JOIN crm.contract_detail cd
                ON cd.contract_id = s.contract_id
               AND cd.product_id = s.product_id

            WHERE s.service_status = 'ACTIVE'

              AND (
                    cd.effective_from IS NULL
                    OR cd.effective_from <= CURRENT_DATE
                  )

              AND (
                    cd.effective_to IS NULL
                    OR cd.effective_to >= CURRENT_DATE
                  )
        )

        SELECT
            CASE
                WHEN active_customers.customer_count = 0
                THEN 0
                ELSE
                    mrr.monthly_revenue
                    /
                    active_customers.customer_count
            END AS arpu

        FROM active_customers
        CROSS JOIN mrr
    """

    df = run_query(query)

    return float(df.iloc[0]["arpu"])


# ============================================================
# KPI - OUTSTANDING INVOICES
# ============================================================

def get_outstanding_invoices():

    query = """
        WITH payments AS
        (
            SELECT
                pd.invoice_id,
                SUM(pd.allocated_amount) AS paid_amount

            FROM fin.payment_detail pd

            JOIN fin.payment p
                ON p.payment_id = pd.payment_id

            WHERE p.payment_status = 'SUCCESS'
              AND pd.allocation_status = 'ALLOCATED'

            GROUP BY pd.invoice_id
        )

        SELECT
            COALESCE(
                SUM(
                    i.total_amount
                    -
                    COALESCE(p.paid_amount, 0)
                ),
                0
            ) AS outstanding_amount

        FROM inv.invoice i

        LEFT JOIN payments p
            ON p.invoice_id = i.invoice_id

        WHERE
            (
                i.total_amount
                -
                COALESCE(p.paid_amount, 0)
            ) > 0
    """

    df = run_query(query)

    return float(
        df.iloc[0]["outstanding_amount"]
    )


# ============================================================
# KPI - CHURN
# ============================================================

def get_churn_rate():

    query = """
        WITH period_data AS
        (
            SELECT

                COUNT(*) FILTER
                (
                    WHERE
                        deactivation_date >=
                        CURRENT_DATE - INTERVAL '30 days'
                        AND deactivation_date <= CURRENT_DATE
                ) AS churned_services,

                COUNT(*) FILTER
                (
                    WHERE
                        activation_date <
                        CURRENT_DATE - INTERVAL '30 days'
                        AND
                        (
                            deactivation_date IS NULL
                            OR deactivation_date >
                               CURRENT_DATE - INTERVAL '30 days'
                        )
                ) AS opening_services

            FROM crm.service
        )

        SELECT

            CASE
                WHEN opening_services = 0
                THEN 0

                ELSE
                    (
                        churned_services::numeric
                        /
                        opening_services::numeric
                    ) * 100

            END AS churn_rate

        FROM period_data
    """

    df = run_query(query)

    return float(
        df.iloc[0]["churn_rate"]
    )


# ============================================================
# NETWORK CAPACITY
# ============================================================

def get_network_capacity():

    query = """
        SELECT

            COALESCE(
                SUM(capacity_gbps),
                0
            ) AS total_capacity_gbps,

            COALESCE(
                SUM(used_capacity_gbps),
                0
            ) AS used_capacity_gbps,

            COALESCE(
                SUM(
                    capacity_gbps
                    -
                    used_capacity_gbps
                ),
                0
            ) AS available_capacity_gbps

        FROM network.pop

        WHERE status = 'ACTIVE'
    """

    df = run_query(query)

    row = df.iloc[0]

    total = float(
        row["total_capacity_gbps"]
    )

    used = float(
        row["used_capacity_gbps"]
    )

    available = float(
        row["available_capacity_gbps"]
    )

    utilization = (
        (used / total) * 100
        if total > 0
        else 0
    )

    return {
        "total": total,
        "used": used,
        "available": available,
        "utilization": utilization
    }


# ============================================================
# CUSTOMER / SERVICE DISTRIBUTION
# ============================================================

def get_customer_status():

    query = """
        SELECT
            customer_status,
            COUNT(*) AS customer_count

        FROM crm.customer

        GROUP BY customer_status

        ORDER BY customer_count DESC
    """

    return run_query(query)


# ============================================================
# SERVICE TECHNOLOGY
# ============================================================

def get_service_technology():

    query = """
        SELECT
            technology,
            COUNT(*) AS service_count

        FROM crm.service

        WHERE service_status = 'ACTIVE'

        GROUP BY technology

        ORDER BY service_count DESC
    """

    return run_query(query)


# ============================================================
# MRR BY PRODUCT
# ============================================================

def get_mrr_by_product():

    query = """
        SELECT

            p.product_code,
            p.product_name,

            COUNT(DISTINCT s.service_id)
                AS active_services,

            COALESCE(
                SUM(
                    cd.agreed_monthly_price
                    -
                    COALESCE(cd.discount_amount, 0)
                ),
                0
            ) AS mrr

        FROM crm.service s

        JOIN crm.contract_detail cd
            ON cd.contract_id = s.contract_id
           AND cd.product_id = s.product_id

        JOIN prd.product p
            ON p.product_id = s.product_id

        WHERE s.service_status = 'ACTIVE'

        GROUP BY
            p.product_code,
            p.product_name

        ORDER BY mrr DESC
    """

    return run_query(query)


# ============================================================
# CHURN TREND
# ============================================================

def get_churn_trend():

    query = """
        WITH months AS
        (
            SELECT
                DATE_TRUNC(
                    'month',
                    CURRENT_DATE
                ) - INTERVAL '5 months'
                + (
                    n || ' months'
                )::interval AS month_start

            FROM generate_series(
                0,
                5
            ) AS n
        ),

        churn AS
        (
            SELECT

                DATE_TRUNC(
                    'month',
                    deactivation_date
                ) AS month_start,

                COUNT(*) AS churned

            FROM crm.service

            WHERE deactivation_date IS NOT NULL

            GROUP BY
                DATE_TRUNC(
                    'month',
                    deactivation_date
                )
        )

        SELECT

            TO_CHAR(
                m.month_start,
                'Mon YYYY'
            ) AS month,

            COALESCE(
                c.churned,
                0
            ) AS churned_services

        FROM months m

        LEFT JOIN churn c
            ON c.month_start = m.month_start

        ORDER BY
            m.month_start
    """

    return run_query(query)


# ============================================================
# NETWORK CAPACITY BY POP
# ============================================================

def get_capacity_by_pop():

    query = """
        SELECT

            p.pop_id,
            p.pop_code,
            p.pop_name,

            ns.city,
            ns.state,

            p.capacity_gbps,
            p.used_capacity_gbps,

            (
                p.capacity_gbps
                -
                p.used_capacity_gbps
            ) AS available_capacity_gbps,

            CASE

                WHEN p.capacity_gbps = 0
                THEN 0

                ELSE
                    (
                        p.used_capacity_gbps
                        /
                        p.capacity_gbps
                    ) * 100

            END AS utilization_percent

        FROM network.pop p

        JOIN network.network_site ns
            ON ns.site_id = p.site_id

        WHERE p.status = 'ACTIVE'

        ORDER BY
            utilization_percent DESC
    """

    return run_query(query)


# ============================================================
# NETWORK CAPACITY BY TECHNOLOGY
# ============================================================

def get_capacity_by_technology():

    query = """
        SELECT

            pp.technology,

            COUNT(*) AS total_ports,

            COUNT(*) FILTER
            (
                WHERE pp.status = 'ACTIVE'
            ) AS active_ports,

            COUNT(*) FILTER
            (
                WHERE pp.status = 'AVAILABLE'
            ) AS available_ports,

            COALESCE(
                SUM(pp.capacity_gbps),
                0
            ) AS total_capacity_gbps,

            COALESCE(
                SUM(pp.used_capacity_gbps),
                0
            ) AS used_capacity_gbps

        FROM network.pon_port pp

        GROUP BY
            pp.technology

        ORDER BY
            total_capacity_gbps DESC
    """

    return run_query(query)


# ============================================================
# DASHBOARD
# ============================================================

def dashboard():

    st.set_page_config(
        page_title="TelecomNexus Dashboard",
        page_icon="📊",
        layout="wide"
    )

    # ========================================================
    # HEADER
    # ========================================================

    st.title(
        "📊 TelecomNexus Executive Dashboard"
    )

    st.caption(
        "Customer • Revenue • Billing • Network Capacity"
    )

    # ========================================================
    # REFRESH
    # ========================================================

    col1, col2 = st.columns(
        [6, 1]
    )

    with col2:

        if st.button(
            "🔄 Refresh",
            use_container_width=True
        ):

            st.cache_data.clear()
            st.rerun()

    # ========================================================
    # KPI DATA
    # ========================================================

    try:

        total_customers = (
            get_total_customers()
        )

        active_contracts = (
            get_active_contracts()
        )

        active_services = (
            get_active_services()
        )

        mrr = get_mrr()

        arpu = get_arpu()

        outstanding = (
            get_outstanding_invoices()
        )

        churn = get_churn_rate()

        capacity = (
            get_network_capacity()
        )

    except Exception as exc:

        st.error(
            "Unable to load dashboard data."
        )

        st.exception(exc)

        return

    # ========================================================
    # KPI ROW
    # ========================================================

    st.subheader(
        "Business KPIs"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "👥 Total Customers",
        f"{total_customers:,}"
    )

    c2.metric(
        "📑 Active Contracts",
        f"{active_contracts:,}"
    )

    c3.metric(
        "🌐 Active Services",
        f"{active_services:,}"
    )

    c4.metric(
        "💰 MRR",
        f"₹{mrr:,.0f}"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "👤 ARPU",
        f"₹{arpu:,.2f}"
    )

    c2.metric(
        "⚠️ Outstanding Invoices",
        f"₹{outstanding:,.0f}"
    )

    c3.metric(
        "📉 Churn - 30 Days",
        f"{churn:.2f}%"
    )

    c4.metric(
        "📡 Network Utilization",
        f"{capacity['utilization']:.1f}%"
    )

    st.divider()

    # ========================================================
    # CUSTOMER / REVENUE
    # ========================================================

    st.subheader(
        "Customer & Revenue Overview"
    )

    left, right = st.columns(2)

    # --------------------------------------------------------
    # Customer Status
    # --------------------------------------------------------

    with left:

        st.markdown(
            "### Customer Status"
        )

        customer_status = (
            get_customer_status()
        )

        if not customer_status.empty:

            fig = px.pie(
                customer_status,
                names="customer_status",
                values="customer_count",
                hole=0.45
            )

            fig.update_layout(
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=20
                ),
                legend_title="Status"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

    # --------------------------------------------------------
    # MRR by Product
    # --------------------------------------------------------

    with right:

        st.markdown(
            "### MRR by Product"
        )

        product_mrr = (
            get_mrr_by_product()
        )

        if not product_mrr.empty:

            fig = px.bar(
                product_mrr,
                x="product_code",
                y="mrr",
                text_auto=".2s"
            )

            fig.update_layout(
                xaxis_title="Product",
                yaxis_title="MRR (INR)",
                margin=dict(
                    l=20,
                    r=20,
                    t=20,
                    b=20
                )
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

    # ========================================================
    # SERVICE / CHURN
    # ========================================================

    st.subheader(
        "Service & Churn Overview"
    )

    left, right = st.columns(2)

    # --------------------------------------------------------
    # Service Technology
    # --------------------------------------------------------

    with left:

        st.markdown(
            "### Active Services by Technology"
        )

        technology_df = (
            get_service_technology()
        )

        if not technology_df.empty:

            fig = px.bar(
                technology_df,
                x="technology",
                y="service_count",
                text_auto=True
            )

            fig.update_layout(
                xaxis_title="Technology",
                yaxis_title="Active Services"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

    # --------------------------------------------------------
    # Churn
    # --------------------------------------------------------

    with right:

        st.markdown(
            "### Churn Trend"
        )

        churn_df = (
            get_churn_trend()
        )

        if not churn_df.empty:

            fig = px.line(
                churn_df,
                x="month",
                y="churned_services",
                markers=True
            )

            fig.update_layout(
                xaxis_title="Month",
                yaxis_title="Churned Services"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

    # ========================================================
    # NETWORK CAPACITY
    # ========================================================

    st.divider()

    st.subheader(
        "📡 Network Capacity"
    )

    # --------------------------------------------------------
    # Capacity KPI
    # --------------------------------------------------------

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Total Capacity",
        f"{capacity['total']:,.2f} Gbps"
    )

    c2.metric(
        "Used Capacity",
        f"{capacity['used']:,.2f} Gbps"
    )

    c3.metric(
        "Available Capacity",
        f"{capacity['available']:,.2f} Gbps"
    )

    c4.metric(
        "Utilization",
        f"{capacity['utilization']:.1f}%"
    )

    # --------------------------------------------------------
    # Capacity Gauge
    # --------------------------------------------------------

    gauge_df = pd.DataFrame(
        {
            "Metric": ["Network Utilization"],
            "Utilization": [
                capacity["utilization"]
            ]
        }
    )

    fig = px.bar(
        gauge_df,
        x="Metric",
        y="Utilization",
        range_y=[0, 100],
        text="Utilization"
    )

    fig.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside"
    )

    fig.update_layout(
        yaxis_title="Utilization %",
        xaxis_title="",
        margin=dict(
            l=20,
            r=20,
            t=30,
            b=20
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # ========================================================
    # POP CAPACITY
    # ========================================================

    st.markdown(
        "### Capacity by POP"
    )

    pop_capacity = (
        get_capacity_by_pop()
    )

    if not pop_capacity.empty:

        display = pop_capacity[
            [
                "pop_code",
                "pop_name",
                "city",
                "state",
                "capacity_gbps",
                "used_capacity_gbps",
                "available_capacity_gbps",
                "utilization_percent"
            ]
        ].copy()

        display.columns = [
            "POP",
            "POP Name",
            "City",
            "State",
            "Capacity (Gbps)",
            "Used (Gbps)",
            "Available (Gbps)",
            "Utilization %"
        ]

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Capacity (Gbps)": st.column_config.NumberColumn(
                    format="%.2f"
                ),
                "Used (Gbps)": st.column_config.NumberColumn(
                    format="%.2f"
                ),
                "Available (Gbps)": st.column_config.NumberColumn(
                    format="%.2f"
                ),
                "Utilization %": st.column_config.ProgressColumn(
                    format="%.1f%%",
                    min_value=0,
                    max_value=100
                )
            }
        )

    # ========================================================
    # PON TECHNOLOGY
    # ========================================================

    st.markdown(
        "### PON Capacity by Technology"
    )

    technology_capacity = (
        get_capacity_by_technology()
    )

    if not technology_capacity.empty:

        st.dataframe(
            technology_capacity,
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # FOOTER
    # ========================================================

    st.divider()

    st.caption(
        "TelecomNexus | ISP Internet Planning & Operations Platform"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    dashboard()