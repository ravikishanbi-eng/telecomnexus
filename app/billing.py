# pages/billing.py

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from db import get_connection


# ============================================================
# Constants
# ============================================================

TAX_RATE = Decimal("0.18")


# ============================================================
# Helpers
# ============================================================

def money(value):
    """
    Convert a value to Decimal with 2 decimal places.
    """
    if value is None:
        return Decimal("0.00")

    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def get_next_id(cur, table_name, id_column):
    """
    Development-friendly ID generator.

    Production recommendation:
    use PostgreSQL IDENTITY / SEQUENCE.
    """

    cur.execute(
        f"""
        SELECT COALESCE(MAX({id_column}), 0) + 1
        FROM {table_name}
        """
    )

    return cur.fetchone()[0]


def get_next_invoice_number(cur):
    next_id = get_next_id(
        cur,
        "inv.invoice",
        "invoice_id"
    )

    return next_id, f"INV-{next_id:010d}"


def get_next_payment_number(cur):
    next_id = get_next_id(
        cur,
        "fin.payment",
        "payment_id"
    )

    return next_id, f"PAY-{next_id:010d}"


# ============================================================
# Customer / Billing Account
# ============================================================

def load_customers():
    conn = get_connection()

    try:
        query = """
            SELECT
                c.customer_id,
                c.customer_number,
                c.first_name,
                c.last_name,
                c.customer_type,
                c.customer_status,
                b.billing_account_id,
                b.billing_cycle,
                b.billing_day,
                b.payment_method,
                b.credit_limit,
                b.currency,
                b.billing_status
            FROM crm.customer c
            JOIN crm.billing b
                ON b.customer_id = c.customer_id
            ORDER BY c.customer_id
        """

        return pd.read_sql(query, conn)

    finally:
        conn.close()


# ============================================================
# Active Services
# ============================================================

def load_customer_services(customer_id):
    conn = get_connection()

    try:
        query = """
            SELECT
                s.service_id,
                s.service_number,
                s.customer_id,
                s.contract_id,
                s.product_id,
                s.service_type,
                s.technology,
                s.activation_date,
                s.service_status,
                s.installation_address,
                s.city,
                s.state,
                p.product_code,
                p.product_name,
                p.download_speed_mbps,
                p.upload_speed_mbps,
                cd.agreed_monthly_price,
                cd.discount_amount,
                cd.tax_percent
            FROM crm.service s
            LEFT JOIN prd.product p
                ON p.product_id = s.product_id
            LEFT JOIN crm.contract_detail cd
                ON cd.contract_id = s.contract_id
               AND cd.product_id = s.product_id
            WHERE s.customer_id = %s
              AND s.service_status IN (
                  'ACTIVE',
                  'PROVISIONED'
              )
            ORDER BY s.service_id
        """

        return pd.read_sql(
            query,
            conn,
            params=(customer_id,)
        )

    finally:
        conn.close()


# ============================================================
# Generate Invoice
# ============================================================

def generate_invoice(
    customer_id,
    billing_account_id,
    billing_period_start,
    billing_period_end,
    selected_services
):

    conn = get_connection()

    try:
        conn.autocommit = False

        cur = conn.cursor()

        # ----------------------------------------------------
        # Prevent duplicate invoice for same billing account
        # and billing period.
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT invoice_id, invoice_number
            FROM inv.invoice
            WHERE billing_account_id = %s
              AND billing_period_start = %s
              AND billing_period_end = %s
            LIMIT 1
            """,
            (
                billing_account_id,
                billing_period_start,
                billing_period_end
            )
        )

        existing = cur.fetchone()

        if existing:
            raise ValueError(
                f"Invoice {existing[1]} already exists "
                f"for this billing period."
            )

        # ----------------------------------------------------
        # Invoice ID
        # ----------------------------------------------------

        invoice_id, invoice_number = get_next_invoice_number(cur)

        invoice_date = date.today()
        due_date = invoice_date + timedelta(days=15)

        subtotal = Decimal("0.00")
        total_discount = Decimal("0.00")
        total_tax = Decimal("0.00")

        invoice_details = []

        # ----------------------------------------------------
        # Calculate invoice lines
        # ----------------------------------------------------

        for line_number, service in enumerate(
            selected_services,
            start=1
        ):

            service_id = int(service["service_id"])
            product_id = int(service["product_id"])

            product_name = service["product_name"]

            unit_price = money(
                service["agreed_monthly_price"]
            )

            discount = money(
                service["discount_amount"]
            )

            tax_percent = (
                Decimal(str(service["tax_percent"]))
                if service["tax_percent"] is not None
                else TAX_RATE * 100
            )

            taxable_amount = money(
                unit_price - discount
            )

            tax_amount = money(
                taxable_amount *
                tax_percent /
                Decimal("100")
            )

            line_total = money(
                taxable_amount + tax_amount
            )

            subtotal += unit_price
            total_discount += discount
            total_tax += tax_amount

            invoice_details.append(
                (
                    line_number,
                    service_id,
                    product_id,
                    product_name,
                    unit_price,
                    discount,
                    tax_amount,
                    line_total
                )
            )

        total_amount = money(
            subtotal -
            total_discount +
            total_tax
        )

        # ----------------------------------------------------
        # Insert invoice
        # ----------------------------------------------------

        cur.execute(
            """
            INSERT INTO inv.invoice
            (
                invoice_id,
                invoice_number,
                billing_account_id,
                customer_id,
                invoice_date,
                due_date,
                billing_period_start,
                billing_period_end,
                subtotal,
                discount_amount,
                tax_amount,
                total_amount,
                invoice_status,
                created_at,
                updated_at
            )
            VALUES
            (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                NOW(), NOW()
            )
            """,
            (
                invoice_id,
                invoice_number,
                billing_account_id,
                customer_id,
                invoice_date,
                due_date,
                billing_period_start,
                billing_period_end,
                subtotal,
                total_discount,
                total_tax,
                total_amount,
                "OPEN"
            )
        )

        # ----------------------------------------------------
        # Insert invoice details
        # ----------------------------------------------------

        for (
            line_number,
            service_id,
            product_id,
            product_name,
            unit_price,
            discount,
            tax_amount,
            line_total
        ) in invoice_details:

            cur.execute(
                """
                INSERT INTO inv.invoice_detail
                (
                    invoice_detail_id,
                    invoice_id,
                    line_number,
                    service_id,
                    product_id,
                    charge_type,
                    description,
                    quantity,
                    unit_price,
                    discount_amount,
                    tax_amount,
                    line_total
                )
                VALUES
                (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    get_next_id(
                        cur,
                        "inv.invoice_detail",
                        "invoice_detail_id"
                    ),
                    invoice_id,
                    line_number,
                    service_id,
                    product_id,
                    "RECURRING",
                    f"Monthly broadband service - {product_name}",
                    1,
                    unit_price,
                    discount,
                    tax_amount,
                    line_total
                )
            )

        # ----------------------------------------------------
        # Commit
        # ----------------------------------------------------

        conn.commit()

        return invoice_id, invoice_number, total_amount

    except Exception:

        conn.rollback()

        raise

    finally:

        cur.close()
        conn.close()


# ============================================================
# Invoice Search
# ============================================================

def search_invoices(
    customer_id=None,
    invoice_status="ALL"
):

    conn = get_connection()

    try:

        query = """
            SELECT
                i.invoice_id,
                i.invoice_number,
                i.billing_account_id,
                i.customer_id,
                c.customer_number,
                c.first_name || ' ' || c.last_name AS customer_name,
                i.invoice_date,
                i.due_date,
                i.billing_period_start,
                i.billing_period_end,
                i.subtotal,
                i.discount_amount,
                i.tax_amount,
                i.total_amount,
                i.invoice_status
            FROM inv.invoice i
            JOIN crm.customer c
                ON c.customer_id = i.customer_id
            WHERE 1 = 1
        """

        params = []

        if customer_id:
            query += """
                AND i.customer_id = %s
            """

            params.append(customer_id)

        if invoice_status != "ALL":

            query += """
                AND i.invoice_status = %s
            """

            params.append(invoice_status)

        query += """
            ORDER BY i.invoice_date DESC,
                     i.invoice_id DESC
        """

        return pd.read_sql(
            query,
            conn,
            params=params
        )

    finally:
        conn.close()


# ============================================================
# Invoice Details
# ============================================================

def load_invoice_details(invoice_id):

    conn = get_connection()

    try:

        query = """
            SELECT
                i.invoice_number,
                i.invoice_date,
                i.due_date,
                i.billing_period_start,
                i.billing_period_end,
                i.subtotal,
                i.discount_amount AS invoice_discount,
                i.tax_amount AS invoice_tax,
                i.total_amount,
                i.invoice_status,

                d.invoice_detail_id,
                d.line_number,
                d.service_id,
                s.service_number,
                d.product_id,
                p.product_code,
                p.product_name,
                d.charge_type,
                d.description,
                d.quantity,
                d.unit_price,
                d.discount_amount,
                d.tax_amount,
                d.line_total

            FROM inv.invoice i

            JOIN inv.invoice_detail d
                ON d.invoice_id = i.invoice_id

            LEFT JOIN crm.service s
                ON s.service_id = d.service_id

            LEFT JOIN prd.product p
                ON p.product_id = d.product_id

            WHERE i.invoice_id = %s

            ORDER BY d.line_number
        """

        return pd.read_sql(
            query,
            conn,
            params=(invoice_id,)
        )

    finally:
        conn.close()


# ============================================================
# Payment History
# ============================================================

def load_invoice_payments(invoice_id):

    conn = get_connection()

    try:

        query = """
            SELECT
                p.payment_id,
                p.payment_number,
                p.customer_id,
                p.payment_date,
                p.payment_method,
                p.payment_status,
                p.amount,
                p.currency,
                p.gateway_reference,
                pd.payment_detail_id,
                pd.invoice_id,
                pd.allocated_amount,
                pd.allocation_status
            FROM fin.payment p

            JOIN fin.payment_detail pd
                ON pd.payment_id = p.payment_id

            WHERE pd.invoice_id = %s

            ORDER BY p.payment_date DESC,
                     p.payment_id DESC
        """

        return pd.read_sql(
            query,
            conn,
            params=(invoice_id,)
        )

    finally:
        conn.close()


# ============================================================
# Record Payment
# ============================================================

def record_payment(
    invoice_id,
    customer_id,
    amount,
    payment_method
):

    amount = money(amount)

    if amount <= 0:

        raise ValueError(
            "Payment amount must be greater than zero."
        )

    conn = get_connection()

    try:

        conn.autocommit = False

        cur = conn.cursor()

        # ----------------------------------------------------
        # Lock invoice row
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT
                total_amount,
                invoice_status
            FROM inv.invoice
            WHERE invoice_id = %s
            FOR UPDATE
            """,
            (invoice_id,)
        )

        invoice = cur.fetchone()

        if not invoice:

            raise ValueError(
                "Invoice not found."
            )

        total_amount = money(invoice[0])

        # ----------------------------------------------------
        # Existing allocated payments
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT
                COALESCE(
                    SUM(pd.allocated_amount),
                    0
                )
            FROM fin.payment_detail pd
            JOIN fin.payment p
                ON p.payment_id = pd.payment_id
            WHERE pd.invoice_id = %s
              AND pd.allocation_status = 'ALLOCATED'
              AND p.payment_status = 'SUCCESS'
            """,
            (invoice_id,)
        )

        paid_amount = money(
            cur.fetchone()[0]
        )

        outstanding = money(
            total_amount - paid_amount
        )

        if amount > outstanding:

            raise ValueError(
                f"Payment exceeds outstanding balance "
                f"of ₹{outstanding:,.2f}"
            )

        # ----------------------------------------------------
        # Payment ID
        # ----------------------------------------------------

        payment_id, payment_number = (
            get_next_payment_number(cur)
        )

        gateway_reference = (
            f"GW-{payment_id:012d}"
        )

        payment_date = date.today()

        # ----------------------------------------------------
        # Insert payment
        # ----------------------------------------------------

        cur.execute(
            """
            INSERT INTO fin.payment
            (
                payment_id,
                payment_number,
                customer_id,
                payment_date,
                payment_method,
                payment_status,
                amount,
                currency,
                gateway_reference,
                created_at
            )
            VALUES
            (
                %s, %s, %s, %s, %s,
                'SUCCESS', %s, 'INR',
                %s, NOW()
            )
            """,
            (
                payment_id,
                payment_number,
                customer_id,
                payment_date,
                payment_method,
                amount,
                gateway_reference
            )
        )

        # ----------------------------------------------------
        # Payment allocation
        # ----------------------------------------------------

        payment_detail_id = get_next_id(
            cur,
            "fin.payment_detail",
            "payment_detail_id"
        )

        cur.execute(
            """
            INSERT INTO fin.payment_detail
            (
                payment_detail_id,
                payment_id,
                invoice_id,
                allocated_amount,
                allocation_status,
                created_at
            )
            VALUES
            (
                %s, %s, %s, %s,
                'ALLOCATED', NOW()
            )
            """,
            (
                payment_detail_id,
                payment_id,
                invoice_id,
                amount
            )
        )

        # ----------------------------------------------------
        # New balance
        # ----------------------------------------------------

        new_paid_amount = money(
            paid_amount + amount
        )

        new_balance = money(
            total_amount - new_paid_amount
        )

        if new_balance == Decimal("0.00"):

            new_status = "PAID"

        else:

            new_status = "PARTIALLY_PAID"

        cur.execute(
            """
            UPDATE inv.invoice
            SET
                invoice_status = %s,
                updated_at = NOW()
            WHERE invoice_id = %s
            """,
            (
                new_status,
                invoice_id
            )
        )

        conn.commit()

        return (
            payment_id,
            payment_number,
            new_paid_amount,
            new_balance,
            new_status
        )

    except Exception:

        conn.rollback()

        raise

    finally:

        cur.close()
        conn.close()


# ============================================================
# Outstanding Balance
# ============================================================

def load_outstanding_balances():

    conn = get_connection()

    try:

        query = """
            WITH payments AS
            (
                SELECT
                    pd.invoice_id,
                    SUM(pd.allocated_amount) AS paid_amount
                FROM fin.payment_detail pd
                JOIN fin.payment p
                    ON p.payment_id = pd.payment_id
                WHERE pd.allocation_status = 'ALLOCATED'
                  AND p.payment_status = 'SUCCESS'
                GROUP BY pd.invoice_id
            )

            SELECT
                i.invoice_id,
                i.invoice_number,
                i.customer_id,
                c.customer_number,

                c.first_name ||
                ' ' ||
                c.last_name AS customer_name,

                i.invoice_date,
                i.due_date,
                i.total_amount,

                COALESCE(
                    p.paid_amount,
                    0
                ) AS paid_amount,

                (
                    i.total_amount -
                    COALESCE(
                        p.paid_amount,
                        0
                    )
                ) AS outstanding_amount,

                CASE
                    WHEN
                        i.due_date < CURRENT_DATE
                        AND
                        (
                            i.total_amount -
                            COALESCE(
                                p.paid_amount,
                                0
                            )
                        ) > 0
                    THEN 'OVERDUE'

                    WHEN
                        (
                            i.total_amount -
                            COALESCE(
                                p.paid_amount,
                                0
                            )
                        ) > 0
                    THEN 'OPEN'

                    ELSE 'PAID'
                END AS balance_status

            FROM inv.invoice i

            JOIN crm.customer c
                ON c.customer_id = i.customer_id

            LEFT JOIN payments p
                ON p.invoice_id = i.invoice_id

            WHERE
                (
                    i.total_amount -
                    COALESCE(
                        p.paid_amount,
                        0
                    )
                ) > 0

            ORDER BY
                i.due_date,
                i.invoice_id
        """

        return pd.read_sql(
            query,
            conn
        )

    finally:

        conn.close()


# ============================================================
# Billing Dashboard
# ============================================================

def billing_dashboard():

    st.title("💳 Billing Management")

    st.caption(
        "Invoice generation, invoice details, payments "
        "and outstanding balance"
    )

    # --------------------------------------------------------
    # Load customer information
    # --------------------------------------------------------

    customers = load_customers()

    if customers.empty:

        st.warning(
            "No billing accounts found."
        )

        return

    # --------------------------------------------------------
    # KPI section
    # --------------------------------------------------------

    outstanding_df = load_outstanding_balances()

    total_outstanding = (
        outstanding_df["outstanding_amount"]
        .sum()
        if not outstanding_df.empty
        else 0
    )

    overdue_df = (
        outstanding_df[
            outstanding_df["balance_status"] == "OVERDUE"
        ]
        if not outstanding_df.empty
        else pd.DataFrame()
    )

    overdue_amount = (
        overdue_df["outstanding_amount"].sum()
        if not overdue_df.empty
        else 0
    )

    invoices_df = search_invoices()

    total_invoices = len(invoices_df)

    paid_invoices = (
        len(
            invoices_df[
                invoices_df["invoice_status"] == "PAID"
            ]
        )
        if not invoices_df.empty
        else 0
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Invoices",
        f"{total_invoices:,}"
    )

    col2.metric(
        "Paid Invoices",
        f"{paid_invoices:,}"
    )

    col3.metric(
        "Outstanding",
        f"₹{total_outstanding:,.2f}"
    )

    col4.metric(
        "Overdue",
        f"₹{overdue_amount:,.2f}"
    )

    st.divider()

    # --------------------------------------------------------
    # Tabs
    # --------------------------------------------------------

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "🧾 Generate Invoice",
            "📄 Invoice Details",
            "💰 Payment",
            "⚠️ Outstanding Balance"
        ]
    )

    # ========================================================
    # TAB 1 - Generate Invoice
    # ========================================================

    with tab1:

        st.subheader("Generate Invoice")

        customer_labels = {}

        for _, row in customers.iterrows():

            label = (
                f"{row['customer_number']} | "
                f"{row['first_name']} "
                f"{row['last_name']}"
            )

            customer_labels[label] = row

        selected_customer_label = st.selectbox(
            "Customer",
            list(customer_labels.keys()),
            key="billing_customer"
        )

        customer = customer_labels[
            selected_customer_label
        ]

        customer_id = int(
            customer["customer_id"]
        )

        billing_account_id = int(
            customer["billing_account_id"]
        )

        st.info(
            f"Billing Account: "
            f"{billing_account_id} | "
            f"Currency: {customer['currency']} | "
            f"Cycle: {customer['billing_cycle']}"
        )

        services = load_customer_services(
            customer_id
        )

        if services.empty:

            st.warning(
                "No active/provisioned services "
                "are available for billing."
            )

        else:

            st.write("### Select Services")

            service_options = {}

            for _, row in services.iterrows():

                label = (
                    f"{row['service_number']} | "
                    f"{row['product_name']} | "
                    f"₹{row['agreed_monthly_price']:,.2f}"
                )

                service_options[label] = row

            selected_labels = st.multiselect(
                "Services to invoice",
                list(service_options.keys()),
                default=list(service_options.keys())
            )

            selected_services = [
                service_options[label]
                for label in selected_labels
            ]

            col1, col2 = st.columns(2)

            with col1:

                billing_period_start = st.date_input(
                    "Billing Period Start",
                    value=date.today().replace(day=1)
                )

            with col2:

                billing_period_end = st.date_input(
                    "Billing Period End",
                    value=(
                        billing_period_start
                        + timedelta(days=30)
                    )
                )

            # ------------------------------------------------
            # Preview
            # ------------------------------------------------

            if selected_services:

                st.write("### Invoice Preview")

                preview_rows = []

                preview_subtotal = Decimal("0")
                preview_discount = Decimal("0")
                preview_tax = Decimal("0")
                preview_total = Decimal("0")

                for service in selected_services:

                    price = money(
                        service[
                            "agreed_monthly_price"
                        ]
                    )

                    discount = money(
                        service[
                            "discount_amount"
                        ]
                    )

                    tax_percent = (
                        Decimal(
                            str(
                                service[
                                    "tax_percent"
                                ]
                            )
                        )
                        if service[
                            "tax_percent"
                        ] is not None
                        else Decimal("18")
                    )

                    taxable = money(
                        price - discount
                    )

                    tax = money(
                        taxable *
                        tax_percent /
                        Decimal("100")
                    )

                    total = money(
                        taxable + tax
                    )

                    preview_subtotal += price
                    preview_discount += discount
                    preview_tax += tax
                    preview_total += total

                    preview_rows.append(
                        {
                            "Service":
                                service[
                                    "service_number"
                                ],
                            "Product":
                                service[
                                    "product_name"
                                ],
                            "Unit Price":
                                float(price),
                            "Discount":
                                float(discount),
                            "Tax":
                                float(tax),
                            "Line Total":
                                float(total)
                        }
                    )

                st.dataframe(
                    pd.DataFrame(preview_rows),
                    use_container_width=True,
                    hide_index=True
                )

                c1, c2, c3, c4 = st.columns(4)

                c1.metric(
                    "Subtotal",
                    f"₹{preview_subtotal:,.2f}"
                )

                c2.metric(
                    "Discount",
                    f"₹{preview_discount:,.2f}"
                )

                c3.metric(
                    "Tax",
                    f"₹{preview_tax:,.2f}"
                )

                c4.metric(
                    "Total",
                    f"₹{preview_total:,.2f}"
                )

                if st.button(
                    "Generate Invoice",
                    type="primary",
                    use_container_width=True
                ):

                    try:

                        invoice_id, invoice_number, total = (
                            generate_invoice(
                                customer_id,
                                billing_account_id,
                                billing_period_start,
                                billing_period_end,
                                selected_services
                            )
                        )

                        st.success(
                            f"Invoice {invoice_number} "
                            f"generated successfully."
                        )

                        st.info(
                            f"Invoice ID: {invoice_id} | "
                            f"Amount: ₹{total:,.2f}"
                        )

                        st.rerun()

                    except Exception as exc:

                        st.error(
                            f"Invoice generation failed: "
                            f"{exc}"
                        )

    # ========================================================
    # TAB 2 - Invoice Details
    # ========================================================

    with tab2:

        st.subheader("Invoice Details")

        invoice_status = st.selectbox(
            "Invoice Status",
            [
                "ALL",
                "OPEN",
                "PAID",
                "OVERDUE",
                "PARTIALLY_PAID"
            ],
            key="invoice_status_filter"
        )

        invoice_df = search_invoices(
            invoice_status=invoice_status
        )

        if invoice_df.empty:

            st.info(
                "No invoices found."
            )

        else:

            display_df = invoice_df[
                [
                    "invoice_id",
                    "invoice_number",
                    "customer_number",
                    "customer_name",
                    "invoice_date",
                    "due_date",
                    "total_amount",
                    "invoice_status"
                ]
            ].copy()

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )

            invoice_options = {}

            for _, row in invoice_df.iterrows():

                label = (
                    f"{row['invoice_number']} | "
                    f"{row['customer_name']} | "
                    f"₹{row['total_amount']:,.2f}"
                )

                invoice_options[label] = int(
                    row["invoice_id"]
                )

            if invoice_options:

                selected_invoice_label = st.selectbox(
                    "Select Invoice",
                    list(invoice_options.keys()),
                    key="invoice_detail_selector"
                )

                selected_invoice_id = invoice_options[
                    selected_invoice_label
                ]

                details = load_invoice_details(
                    selected_invoice_id
                )

                if not details.empty:

                    first = details.iloc[0]

                    c1, c2, c3, c4 = st.columns(4)

                    c1.metric(
                        "Invoice",
                        first["invoice_number"]
                    )

                    c2.metric(
                        "Invoice Date",
                        str(first["invoice_date"])
                    )

                    c3.metric(
                        "Due Date",
                        str(first["due_date"])
                    )

                    c4.metric(
                        "Status",
                        first["invoice_status"]
                    )

                    st.write("### Invoice Lines")

                    st.dataframe(
                        details[
                            [
                                "line_number",
                                "service_number",
                                "product_name",
                                "charge_type",
                                "quantity",
                                "unit_price",
                                "discount_amount",
                                "tax_amount",
                                "line_total"
                            ]
                        ],
                        use_container_width=True,
                        hide_index=True
                    )

                    c1, c2, c3, c4 = st.columns(4)

                    c1.metric(
                        "Subtotal",
                        f"₹{money(first['subtotal']):,.2f}"
                    )

                    c2.metric(
                        "Discount",
                        f"₹{money(first['invoice_discount']):,.2f}"
                    )

                    c3.metric(
                        "Tax",
                        f"₹{money(first['invoice_tax']):,.2f}"
                    )

                    c4.metric(
                        "Total",
                        f"₹{money(first['total_amount']):,.2f}"
                    )

                    st.write("### Payments")

                    payments = load_invoice_payments(
                        selected_invoice_id
                    )

                    if payments.empty:

                        st.info(
                            "No payments allocated "
                            "to this invoice."
                        )

                    else:

                        st.dataframe(
                            payments[
                                [
                                    "payment_number",
                                    "payment_date",
                                    "payment_method",
                                    "payment_status",
                                    "amount",
                                    "allocated_amount",
                                    "gateway_reference"
                                ]
                            ],
                            use_container_width=True,
                            hide_index=True
                        )

    # ========================================================
    # TAB 3 - Payment
    # ========================================================

    with tab3:

        st.subheader("Record Payment")

        payment_invoices = search_invoices(
            invoice_status="OPEN"
        )

        partial_invoices = search_invoices(
            invoice_status="PARTIALLY_PAID"
        )

        payment_invoices = pd.concat(
            [
                payment_invoices,
                partial_invoices
            ],
            ignore_index=True
        )

        if payment_invoices.empty:

            st.success(
                "No outstanding invoices require payment."
            )

        else:

            invoice_options = {}

            for _, row in payment_invoices.iterrows():

                label = (
                    f"{row['invoice_number']} | "
                    f"{row['customer_name']} | "
                    f"₹{row['total_amount']:,.2f}"
                )

                invoice_options[label] = row

            selected_payment_invoice = st.selectbox(
                "Invoice",
                list(invoice_options.keys()),
                key="payment_invoice"
            )

            invoice = invoice_options[
                selected_payment_invoice
            ]

            invoice_id = int(
                invoice["invoice_id"]
            )

            customer_id = int(
                invoice["customer_id"]
            )

            total_amount = money(
                invoice["total_amount"]
            )

            payment_history = load_invoice_payments(
                invoice_id
            )

            already_paid = money(
                payment_history[
                    "allocated_amount"
                ].sum()
                if not payment_history.empty
                else 0
            )

            outstanding = money(
                total_amount - already_paid
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Invoice Amount",
                f"₹{total_amount:,.2f}"
            )

            c2.metric(
                "Paid",
                f"₹{already_paid:,.2f}"
            )

            c3.metric(
                "Outstanding",
                f"₹{outstanding:,.2f}"
            )

            st.divider()

            payment_amount = st.number_input(
                "Payment Amount (INR)",
                min_value=0.01,
                max_value=float(outstanding),
                value=float(outstanding),
                step=100.00
            )

            payment_method = st.selectbox(
                "Payment Method",
                [
                    "UPI",
                    "CARD",
                    "NETBANKING",
                    "AUTOPAY",
                    "CASH",
                    "BANK_TRANSFER"
                ]
            )

            if st.button(
                "Record Payment",
                type="primary",
                use_container_width=True
            ):

                try:

                    (
                        payment_id,
                        payment_number,
                        new_paid,
                        new_balance,
                        new_status
                    ) = record_payment(
                        invoice_id,
                        customer_id,
                        payment_amount,
                        payment_method
                    )

                    st.success(
                        f"Payment {payment_number} "
                        f"recorded successfully."
                    )

                    c1, c2, c3 = st.columns(3)

                    c1.metric(
                        "Payment",
                        payment_number
                    )

                    c2.metric(
                        "Total Paid",
                        f"₹{new_paid:,.2f}"
                    )

                    c3.metric(
                        "Balance",
                        f"₹{new_balance:,.2f}"
                    )

                    st.info(
                        f"Invoice status: {new_status}"
                    )

                    st.rerun()

                except Exception as exc:

                    st.error(
                        f"Payment failed: {exc}"
                    )

    # ========================================================
    # TAB 4 - Outstanding Balance
    # ========================================================

    with tab4:

        st.subheader("Outstanding Balance")

        balance_df = load_outstanding_balances()

        if balance_df.empty:

            st.success(
                "🎉 No outstanding balances."
            )

        else:

            total_outstanding = (
                balance_df[
                    "outstanding_amount"
                ].sum()
            )

            overdue_df = balance_df[
                balance_df["balance_status"]
                == "OVERDUE"
            ]

            overdue_balance = (
                overdue_df[
                    "outstanding_amount"
                ].sum()
            )

            open_df = balance_df[
                balance_df["balance_status"]
                == "OPEN"
            ]

            open_balance = (
                open_df[
                    "outstanding_amount"
                ].sum()
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Total Outstanding",
                f"₹{total_outstanding:,.2f}"
            )

            c2.metric(
                "Overdue",
                f"₹{overdue_balance:,.2f}"
            )

            c3.metric(
                "Current",
                f"₹{open_balance:,.2f}"
            )

            st.divider()

            # ------------------------------------------------
            # Filters
            # ------------------------------------------------

            balance_filter = st.selectbox(
                "Balance Status",
                [
                    "ALL",
                    "OPEN",
                    "OVERDUE"
                ],
                key="balance_filter"
            )

            filtered = balance_df.copy()

            if balance_filter != "ALL":

                filtered = filtered[
                    filtered[
                        "balance_status"
                    ] == balance_filter
                ]

            st.dataframe(
                filtered[
                    [
                        "invoice_number",
                        "customer_number",
                        "customer_name",
                        "invoice_date",
                        "due_date",
                        "total_amount",
                        "paid_amount",
                        "outstanding_amount",
                        "balance_status"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )