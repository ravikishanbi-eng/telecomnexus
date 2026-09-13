from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import streamlit as st

from db import get_connection


# ============================================================
# CONSTANTS
# ============================================================

CONTRACT_TYPES = [
    "MONTHLY",
    "12_MONTH",
    "24_MONTH",
]

CONTRACT_STATUSES = [
    "ACTIVE",
    "PENDING",
    "SUSPENDED",
    "TERMINATED",
    "EXPIRED",
]


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def calculate_end_date(contract_type, start_date):

    if contract_type == "MONTHLY":
        return None

    if contract_type == "12_MONTH":
        return start_date + timedelta(days=365)

    if contract_type == "24_MONTH":
        return start_date + timedelta(days=730)

    return None


def format_currency(value):

    if value is None:
        return "₹0.00"

    return f"₹{Decimal(str(value)):,.2f}"


# ============================================================
# CUSTOMER LOOKUP
# ============================================================

def get_customers():

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    customer_id,
                    customer_number,
                    first_name,
                    last_name,
                    email,
                    customer_status
                FROM crm.customer
                ORDER BY customer_id DESC
                """
            )

            rows = cur.fetchall()

            columns = [
                "customer_id",
                "customer_number",
                "first_name",
                "last_name",
                "email",
                "customer_status",
            ]

            return pd.DataFrame(
                rows,
                columns=columns,
            )

    finally:

        conn.close()


# ============================================================
# PRODUCT / RATE LOOKUP
# ============================================================

def get_active_products():

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    p.product_id,
                    p.product_code,
                    p.product_name,
                    p.product_category,
                    p.technology,
                    p.download_speed_mbps,
                    p.upload_speed_mbps,

                    rs.rate_schedule_id,
                    rs.monthly_charge,
                    rs.activation_charge,
                    rs.tax_percentage,
                    rs.currency

                FROM prd.product p

                JOIN prd.rate_schedule rs
                    ON rs.product_id =
                       p.product_id

                WHERE p.product_status = 'ACTIVE'

                  AND rs.status = 'ACTIVE'

                  AND rs.effective_from <= CURRENT_DATE

                  AND (
                      rs.effective_to IS NULL
                      OR rs.effective_to >= CURRENT_DATE
                  )

                ORDER BY
                    p.product_id
                """
            )

            rows = cur.fetchall()

            columns = [
                "product_id",
                "product_code",
                "product_name",
                "product_category",
                "technology",
                "download_speed_mbps",
                "upload_speed_mbps",
                "rate_schedule_id",
                "monthly_charge",
                "activation_charge",
                "tax_percentage",
                "currency",
            ]

            return pd.DataFrame(
                rows,
                columns=columns,
            )

    finally:

        conn.close()


# ============================================================
# CONTRACT SEARCH
# ============================================================

def search_contracts(
    search_text="",
    status=None,
    contract_type=None,
    limit=100,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            query = """
                SELECT DISTINCT
                    c.contract_id,
                    c.contract_number,

                    cu.customer_id,
                    cu.customer_number,

                    cu.first_name,
                    cu.last_name,
                    cu.email,

                    c.contract_type,
                    c.start_date,
                    c.end_date,
                    c.contract_status,
                    c.auto_renew,

                    COALESCE(
                        SUM(
                            (
                                cd.agreed_monthly_price
                                * cd.quantity
                            )
                            - cd.discount_amount
                        ),
                        0
                    ) AS monthly_value,

                    COUNT(
                        cd.contract_detail_id
                    ) AS contract_lines

                FROM crm.contract c

                JOIN crm.customer cu
                    ON cu.customer_id =
                       c.customer_id

                LEFT JOIN crm.contract_detail cd
                    ON cd.contract_id =
                       c.contract_id

                WHERE 1 = 1
            """

            params = []

            if search_text:

                query += """
                    AND (
                        c.contract_number ILIKE %s
                        OR cu.customer_number ILIKE %s
                        OR cu.first_name ILIKE %s
                        OR cu.last_name ILIKE %s
                        OR cu.email ILIKE %s
                    )
                """

                value = f"%{search_text}%"

                params.extend(
                    [
                        value,
                        value,
                        value,
                        value,
                        value,
                    ]
                )

            if status:

                query += """
                    AND c.contract_status = %s
                """

                params.append(status)

            if contract_type:

                query += """
                    AND c.contract_type = %s
                """

                params.append(contract_type)

            query += """
                GROUP BY
                    c.contract_id,
                    c.contract_number,
                    cu.customer_id,
                    cu.customer_number,
                    cu.first_name,
                    cu.last_name,
                    cu.email,
                    c.contract_type,
                    c.start_date,
                    c.end_date,
                    c.contract_status,
                    c.auto_renew

                ORDER BY c.contract_id DESC

                LIMIT %s
            """

            params.append(limit)

            cur.execute(
                query,
                params,
            )

            rows = cur.fetchall()

            columns = [
                "contract_id",
                "contract_number",
                "customer_id",
                "customer_number",
                "first_name",
                "last_name",
                "email",
                "contract_type",
                "start_date",
                "end_date",
                "contract_status",
                "auto_renew",
                "monthly_value",
                "contract_lines",
            ]

            return pd.DataFrame(
                rows,
                columns=columns,
            )

    finally:

        conn.close()


# ============================================================
# CONTRACT DETAILS
# ============================================================

def get_contract_details(contract_id):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    cd.contract_detail_id,
                    cd.contract_id,
                    cd.line_number,

                    cd.product_id,
                    p.product_code,
                    p.product_name,
                    p.product_category,
                    p.technology,
                    p.download_speed_mbps,
                    p.upload_speed_mbps,

                    cd.quantity,
                    cd.agreed_monthly_price,
                    cd.discount_amount,
                    cd.tax_percent,
                    cd.effective_from,
                    cd.effective_to,

                    crs.rate_schedule_id,
                    crs.agreed_rate

                FROM crm.contract_detail cd

                JOIN prd.product p
                    ON p.product_id =
                       cd.product_id

                LEFT JOIN crm.contract_rate_schedule crs
                    ON crs.contract_detail_id =
                       cd.contract_detail_id

                WHERE cd.contract_id = %s

                ORDER BY cd.line_number
                """,
                (contract_id,),
            )

            rows = cur.fetchall()

            columns = [
                "contract_detail_id",
                "contract_id",
                "line_number",
                "product_id",
                "product_code",
                "product_name",
                "product_category",
                "technology",
                "download_speed_mbps",
                "upload_speed_mbps",
                "quantity",
                "agreed_monthly_price",
                "discount_amount",
                "tax_percent",
                "effective_from",
                "effective_to",
                "rate_schedule_id",
                "agreed_rate",
            ]

            return pd.DataFrame(
                rows,
                columns=columns,
            )

    finally:

        conn.close()


# ============================================================
# CONTRACT HEADER
# ============================================================

def get_contract(contract_id):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    c.contract_id,
                    c.contract_number,
                    c.customer_id,
                    cu.customer_number,
                    cu.first_name,
                    cu.last_name,
                    cu.email,
                    c.contract_type,
                    c.start_date,
                    c.end_date,
                    c.contract_status,
                    c.auto_renew,
                    c.created_at,
                    c.updated_at

                FROM crm.contract c

                JOIN crm.customer cu
                    ON cu.customer_id =
                       c.customer_id

                WHERE c.contract_id = %s
                """,
                (contract_id,),
            )

            row = cur.fetchone()

            if not row:
                return None

            columns = [
                "contract_id",
                "contract_number",
                "customer_id",
                "customer_number",
                "first_name",
                "last_name",
                "email",
                "contract_type",
                "start_date",
                "end_date",
                "contract_status",
                "auto_renew",
                "created_at",
                "updated_at",
            ]

            return dict(
                zip(
                    columns,
                    row,
                )
            )

    finally:

        conn.close()


# ============================================================
# CREATE CONTRACT
# ============================================================

def create_contract(
    customer_id,
    contract_type,
    start_date,
    contract_status,
    auto_renew,
    details,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # ------------------------------------------------
            # Generate contract ID
            # ------------------------------------------------

            cur.execute(
                """
                SELECT pg_advisory_xact_lock(1002)
                """
            )

            cur.execute(
                """
                SELECT
                    COALESCE(
                        MAX(contract_id),
                        0
                    ) + 1
                FROM crm.contract
                """
            )

            contract_id = cur.fetchone()[0]

            contract_number = (
                f"CON-{contract_id:09d}"
            )

            end_date = calculate_end_date(
                contract_type,
                start_date,
            )

            # ------------------------------------------------
            # Contract
            # ------------------------------------------------

            cur.execute(
                """
                INSERT INTO crm.contract (
                    contract_id,
                    contract_number,
                    customer_id,
                    contract_type,
                    start_date,
                    end_date,
                    contract_status,
                    auto_renew,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    contract_id,
                    contract_number,
                    customer_id,
                    contract_type,
                    start_date,
                    end_date,
                    contract_status,
                    auto_renew,
                ),
            )

            # ------------------------------------------------
            # Contract Details
            # ------------------------------------------------

            for line_number, detail in enumerate(
                details,
                start=1,
            ):

                cur.execute(
                    """
                    SELECT
                        pg_advisory_xact_lock(1003)
                    """
                )

                cur.execute(
                    """
                    SELECT
                        COALESCE(
                            MAX(
                                contract_detail_id
                            ),
                            0
                        ) + 1
                    FROM crm.contract_detail
                    """
                )

                contract_detail_id = (
                    cur.fetchone()[0]
                )

                cur.execute(
                    """
                    INSERT INTO crm.contract_detail (
                        contract_detail_id,
                        contract_id,
                        line_number,
                        product_id,
                        quantity,
                        agreed_monthly_price,
                        discount_amount,
                        tax_percent,
                        effective_from,
                        effective_to
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        contract_detail_id,
                        contract_id,
                        line_number,
                        detail["product_id"],
                        detail["quantity"],
                        detail["monthly_price"],
                        detail["discount"],
                        detail["tax_percent"],
                        start_date,
                        end_date,
                    ),
                )

                # ------------------------------------------------
                # Contract Rate Schedule
                # ------------------------------------------------

                cur.execute(
                    """
                    SELECT
                        pg_advisory_xact_lock(1004)
                    """
                )

                cur.execute(
                    """
                    SELECT
                        COALESCE(
                            MAX(
                                contract_rate_schedule_id
                            ),
                            0
                        ) + 1
                    FROM crm.contract_rate_schedule
                    """
                )

                rate_schedule_id = (
                    cur.fetchone()[0]
                )

                cur.execute(
                    """
                    INSERT INTO
                        crm.contract_rate_schedule (
                            contract_rate_schedule_id,
                            contract_id,
                            contract_detail_id,
                            rate_schedule_id,
                            effective_from,
                            effective_to,
                            agreed_rate
                        )
                    VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s
                    )
                    """,
                    (
                        rate_schedule_id,
                        contract_id,
                        contract_detail_id,
                        detail[
                            "rate_schedule_id"
                        ],
                        start_date,
                        end_date,
                        detail["monthly_price"],
                    ),
                )

        conn.commit()

        return {
            "contract_id": contract_id,
            "contract_number": contract_number,
            "end_date": end_date,
        }

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# EDIT CONTRACT
# ============================================================

def update_contract(
    contract_id,
    contract_status,
    auto_renew,
    end_date,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE crm.contract
                SET
                    contract_status = %s,
                    auto_renew = %s,
                    end_date = %s,
                    updated_at =
                        CURRENT_TIMESTAMP
                WHERE contract_id = %s
                """,
                (
                    contract_status,
                    auto_renew,
                    end_date,
                    contract_id,
                ),
            )

            if cur.rowcount == 0:

                raise ValueError(
                    "Contract not found."
                )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# RENEW CONTRACT
# ============================================================

def renew_contract(
    contract_id,
    new_start_date,
    contract_type,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    contract_status
                FROM crm.contract
                WHERE contract_id = %s
                FOR UPDATE
                """,
                (contract_id,),
            )

            row = cur.fetchone()

            if not row:

                raise ValueError(
                    "Contract not found."
                )

            if row[0] == "TERMINATED":

                raise ValueError(
                    "A terminated contract "
                    "cannot be renewed."
                )

            new_end_date = calculate_end_date(
                contract_type,
                new_start_date,
            )

            cur.execute(
                """
                UPDATE crm.contract
                SET
                    contract_type = %s,
                    start_date = %s,
                    end_date = %s,
                    contract_status = 'ACTIVE',
                    updated_at =
                        CURRENT_TIMESTAMP
                WHERE contract_id = %s
                """,
                (
                    contract_type,
                    new_start_date,
                    new_end_date,
                    contract_id,
                ),
            )

        conn.commit()

        return new_end_date

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# CHANGE PLAN
# ============================================================

def change_plan(
    contract_id,
    new_product_id,
    new_rate_schedule_id,
    new_monthly_price,
    new_tax_percent,
    effective_date,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # --------------------------------------------
            # Lock contract
            # --------------------------------------------

            cur.execute(
                """
                SELECT
                    end_date,
                    contract_status
                FROM crm.contract
                WHERE contract_id = %s
                FOR UPDATE
                """,
                (contract_id,),
            )

            contract = cur.fetchone()

            if not contract:

                raise ValueError(
                    "Contract not found."
                )

            contract_end_date = contract[0]
            contract_status = contract[1]

            if contract_status in (
                "TERMINATED",
                "EXPIRED",
            ):

                raise ValueError(
                    "Plan cannot be changed "
                    "for a terminated or "
                    "expired contract."
                )

            # --------------------------------------------
            # Close current active detail
            # --------------------------------------------

            cur.execute(
                """
                UPDATE crm.contract_detail
                SET
                    effective_to = %s
                WHERE contract_id = %s
                  AND (
                        effective_to IS NULL
                        OR effective_to >= %s
                  )
                """,
                (
                    effective_date - timedelta(days=1),
                    contract_id,
                    effective_date,
                ),
            )

            # --------------------------------------------
            # New detail ID
            # --------------------------------------------

            cur.execute(
                """
                SELECT pg_advisory_xact_lock(1003)
                """
            )

            cur.execute(
                """
                SELECT
                    COALESCE(
                        MAX(contract_detail_id),
                        0
                    ) + 1
                FROM crm.contract_detail
                """
            )

            new_detail_id = (
                cur.fetchone()[0]
            )

            # --------------------------------------------
            # New line number
            # --------------------------------------------

            cur.execute(
                """
                SELECT
                    COALESCE(
                        MAX(line_number),
                        0
                    ) + 1
                FROM crm.contract_detail
                WHERE contract_id = %s
                """,
                (contract_id,),
            )

            new_line_number = (
                cur.fetchone()[0]
            )

            # --------------------------------------------
            # New contract detail
            # --------------------------------------------

            cur.execute(
                """
                INSERT INTO crm.contract_detail (
                    contract_detail_id,
                    contract_id,
                    line_number,
                    product_id,
                    quantity,
                    agreed_monthly_price,
                    discount_amount,
                    tax_percent,
                    effective_from,
                    effective_to
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                """,
                (
                    new_detail_id,
                    contract_id,
                    new_line_number,
                    new_product_id,
                    1,
                    new_monthly_price,
                    0,
                    new_tax_percent,
                    effective_date,
                    contract_end_date,
                ),
            )

            # --------------------------------------------
            # New rate schedule
            # --------------------------------------------

            cur.execute(
                """
                SELECT
                    pg_advisory_xact_lock(1004)
                """
            )

            cur.execute(
                """
                SELECT
                    COALESCE(
                        MAX(
                            contract_rate_schedule_id
                        ),
                        0
                    ) + 1
                FROM crm.contract_rate_schedule
                """
            )

            new_rate_id = (
                cur.fetchone()[0]
            )

            cur.execute(
                """
                INSERT INTO
                    crm.contract_rate_schedule (
                        contract_rate_schedule_id,
                        contract_id,
                        contract_detail_id,
                        rate_schedule_id,
                        effective_from,
                        effective_to,
                        agreed_rate
                    )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                """,
                (
                    new_rate_id,
                    contract_id,
                    new_detail_id,
                    new_rate_schedule_id,
                    effective_date,
                    contract_end_date,
                    new_monthly_price,
                ),
            )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# CREATE SCREEN
# ============================================================

def create_contract_screen():

    st.subheader("Create Contract")

    st.caption(
        "Create a contract for an existing customer."
    )

    # --------------------------------------------------------
    # Load customers
    # --------------------------------------------------------

    try:

        customers = get_customers()

    except Exception as e:

        st.error(
            f"Unable to load customers: {e}"
        )

        return

    if customers.empty:

        st.warning(
            "No customers exist. "
            "Create a customer first."
        )

        return

    # --------------------------------------------------------
    # Load products
    # --------------------------------------------------------

    try:

        products = get_active_products()

    except Exception as e:

        st.error(
            f"Unable to load products: {e}"
        )

        return

    if products.empty:

        st.warning(
            "No active products/rate schedules found."
        )

        return

    # --------------------------------------------------------
    # Customer
    # --------------------------------------------------------

    customer_options = {}

    for row in customers.itertuples():

        label = (
            f"{row.customer_number} | "
            f"{row.first_name} "
            f"{row.last_name} | "
            f"{row.email}"
        )

        customer_options[label] = int(
            row.customer_id
        )

    selected_customer = st.selectbox(
        "Customer *",
        list(customer_options.keys()),
    )

    customer_id = customer_options[
        selected_customer
    ]

    # --------------------------------------------------------
    # Contract Header
    # --------------------------------------------------------

    st.markdown(
        "### Contract Information"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        contract_type = st.selectbox(
            "Contract Type *",
            CONTRACT_TYPES,
        )

    with col2:

        contract_status = st.selectbox(
            "Contract Status *",
            [
                "ACTIVE",
                "PENDING",
            ],
        )

    with col3:

        auto_renew = st.checkbox(
            "Auto Renew",
            value=True,
        )

    start_date = st.date_input(
        "Start Date *",
        value=date.today(),
    )

    end_date = calculate_end_date(
        contract_type,
        start_date,
    )

    if end_date:

        st.info(
            f"Contract End Date: "
            f"**{end_date}**"
        )

    else:

        st.info(
            "Monthly contract: "
            "**Open-ended**"
        )

    st.divider()

    # --------------------------------------------------------
    # Contract Lines
    # --------------------------------------------------------

    st.markdown(
        "### Contract Details"
    )

    number_of_lines = st.number_input(
        "Number of Contract Details",
        min_value=1,
        max_value=10,
        value=1,
        step=1,
    )

    detail_rows = []

    for line_number in range(
        1,
        number_of_lines + 1,
    ):

        st.markdown(
            f"#### Line {line_number}"
        )

        col1, col2 = st.columns(2)

        product_options = {}

        for row in products.itertuples():

            label = (
                f"{row.product_code} - "
                f"{row.product_name} | "
                f"{row.download_speed_mbps} Mbps | "
                f"{row.currency} "
                f"{row.monthly_charge}/month"
            )

            product_options[label] = row

        with col1:

            selected_label = st.selectbox(
                "Product",
                list(product_options.keys()),
                key=f"product_{line_number}",
            )

        product = product_options[
            selected_label
        ]

        with col2:

            quantity = st.number_input(
                "Quantity",
                min_value=1,
                max_value=100,
                value=1,
                step=1,
                key=f"quantity_{line_number}",
            )

        col1, col2, col3 = st.columns(3)

        default_price = float(
            product.monthly_charge
        )

        with col1:

            monthly_price = st.number_input(
                "Agreed Monthly Price",
                min_value=0.0,
                value=default_price,
                step=10.0,
                key=f"monthly_price_{line_number}",
            )

        with col2:

            discount = st.number_input(
                "Discount",
                min_value=0.0,
                value=0.0,
                step=10.0,
                key=f"discount_{line_number}",
            )

        with col3:

            tax_percent = float(
                product.tax_percentage
            )

            st.number_input(
                "Tax %",
                min_value=0.0,
                value=tax_percent,
                disabled=True,
                key=f"tax_{line_number}",
            )

        base = (
            Decimal(str(monthly_price))
            * quantity
        )

        discount_decimal = Decimal(
            str(discount)
        )

        taxable = max(
            Decimal("0"),
            base - discount_decimal,
        )

        tax = (
            taxable
            * Decimal(str(tax_percent))
            / Decimal("100")
        )

        total = taxable + tax

        c1, c2, c3 = st.columns(3)

        c1.metric(
            f"Line {line_number} Base",
            format_currency(base),
        )

        c2.metric(
            f"Line {line_number} Tax",
            format_currency(tax),
        )

        c3.metric(
            f"Line {line_number} Total",
            format_currency(total),
        )

        if discount_decimal > base:

            st.error(
                f"Line {line_number}: "
                "discount cannot exceed "
                "base amount."
            )

        detail_rows.append(
            {
                "product_id":
                    int(product.product_id),
                "rate_schedule_id":
                    int(product.rate_schedule_id),
                "quantity":
                    int(quantity),
                "monthly_price":
                    monthly_price,
                "discount":
                    discount,
                "tax_percent":
                    tax_percent,
            }
        )

        st.divider()

    # --------------------------------------------------------
    # Contract Total
    # --------------------------------------------------------

    total_monthly = Decimal("0")

    for detail in detail_rows:

        base = (
            Decimal(
                str(detail["monthly_price"])
            )
            * detail["quantity"]
        )

        discount = Decimal(
            str(detail["discount"])
        )

        taxable = max(
            Decimal("0"),
            base - discount,
        )

        tax = (
            taxable
            * Decimal(
                str(detail["tax_percent"])
            )
            / Decimal("100")
        )

        total_monthly += (
            taxable + tax
        )

    st.markdown(
        "### Contract Billing Summary"
    )

    c1, c2 = st.columns(2)

    c1.metric(
        "Total Monthly Recurring Charge",
        format_currency(total_monthly),
    )

    c2.metric(
        "Contract Lines",
        len(detail_rows),
    )

    # --------------------------------------------------------
    # Create
    # --------------------------------------------------------

    if st.button(
        "🚀 Create Contract",
        type="primary",
        use_container_width=True,
    ):

        invalid = False

        for detail in detail_rows:

            base = (
                Decimal(
                    str(detail["monthly_price"])
                )
                * detail["quantity"]
            )

            discount = Decimal(
                str(detail["discount"])
            )

            if discount > base:

                invalid = True

        if invalid:

            st.error(
                "Please correct the discount "
                "values before creating the contract."
            )

            return

        try:

            result = create_contract(
                customer_id=customer_id,
                contract_type=contract_type,
                start_date=start_date,
                contract_status=contract_status,
                auto_renew=auto_renew,
                details=detail_rows,
            )

            st.success(
                "Contract created successfully."
            )

            st.markdown(
                "### Contract Created"
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Contract ID",
                result["contract_id"],
            )

            c2.metric(
                "Contract Number",
                result["contract_number"],
            )

            c3.metric(
                "Monthly Charge",
                format_currency(
                    total_monthly
                ),
            )

        except Exception as e:

            st.error(
                "Contract creation failed."
            )

            st.exception(e)


# ============================================================
# SEARCH SCREEN
# ============================================================

def search_contract_screen():

    st.subheader("Search Contract")

    st.caption(
        "Search contracts by contract number "
        "or customer information."
    )

    with st.form(
        "contract_search_form"
    ):

        c1, c2, c3 = st.columns(3)

        with c1:

            search_text = st.text_input(
                "Search",
                placeholder=(
                    "Contract number / customer "
                    "number / name / email"
                ),
            )

        with c2:

            status = st.selectbox(
                "Status",
                ["All"] + CONTRACT_STATUSES,
            )

        with c3:

            contract_type = st.selectbox(
                "Contract Type",
                ["All"] + CONTRACT_TYPES,
            )

        submitted = st.form_submit_button(
            "Search Contracts",
            type="primary",
        )

    if submitted:

        try:

            df = search_contracts(
                search_text=search_text.strip(),
                status=(
                    None
                    if status == "All"
                    else status
                ),
                contract_type=(
                    None
                    if contract_type == "All"
                    else contract_type
                ),
            )

            st.session_state[
                "contract_search_results"
            ] = df

        except Exception as e:

            st.error(
                f"Search failed: {e}"
            )

    df = st.session_state.get(
        "contract_search_results"
    )

    if df is None:
        return

    if df.empty:

        st.warning(
            "No contracts found."
        )

        return

    st.success(
        f"{len(df)} contract(s) found."
    )

    display_df = df.copy()

    display_df[
        "customer_name"
    ] = (
        display_df["first_name"]
        + " "
        + display_df["last_name"]
    )

    display_df[
        "monthly_value"
    ] = display_df[
        "monthly_value"
    ].apply(format_currency)

    st.dataframe(
        display_df[
            [
                "contract_number",
                "customer_number",
                "customer_name",
                "contract_type",
                "start_date",
                "end_date",
                "contract_status",
                "auto_renew",
                "monthly_value",
                "contract_lines",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    # --------------------------------------------------------
    # Open Contract
    # --------------------------------------------------------

    options = {}

    for row in df.itertuples():

        label = (
            f"{row.contract_number} | "
            f"{row.customer_number} | "
            f"{row.first_name} "
            f"{row.last_name}"
        )

        options[label] = int(
            row.contract_id
        )

    selected = st.selectbox(
        "Select Contract",
        list(options.keys()),
    )

    selected_contract_id = options[
        selected
    ]

    if st.button(
        "Open Contract 360",
        use_container_width=True,
    ):

        st.session_state[
            "selected_contract_id"
        ] = selected_contract_id

        st.session_state[
            "contract_management_mode"
        ] = "Contract 360"

        st.rerun()


# ============================================================
# EDIT CONTRACT
# ============================================================

def edit_contract_screen():

    st.subheader("Edit Contract")

    st.caption(
        "Update contract status, renewal setting "
        "and end date."
    )

    search_text = st.text_input(
        "Find Contract",
        placeholder=(
            "Contract number / customer number"
        ),
    )

    if not search_text:

        return

    try:

        df = search_contracts(
            search_text=search_text,
            limit=20,
        )

    except Exception as e:

        st.error(
            f"Search failed: {e}"
        )

        return

    if df.empty:

        st.warning(
            "No contracts found."
        )

        return

    options = {}

    for row in df.itertuples():

        label = (
            f"{row.contract_number} | "
            f"{row.customer_number} | "
            f"{row.first_name} "
            f"{row.last_name}"
        )

        options[label] = int(
            row.contract_id
        )

    selected = st.selectbox(
        "Select Contract",
        list(options.keys()),
        key="edit_contract_selector",
    )

    contract_id = options[selected]

    contract = get_contract(
        contract_id
    )

    if not contract:

        st.error(
            "Contract not found."
        )

        return

    st.divider()

    st.markdown(
        f"### Editing "
        f"`{contract['contract_number']}`"
    )

    st.write(
        f"Customer: "
        f"**{contract['customer_number']} - "
        f"{contract['first_name']} "
        f"{contract['last_name']}**"
    )

    with st.form(
        "edit_contract_form"
    ):

        col1, col2 = st.columns(2)

        with col1:

            status_index = (
                CONTRACT_STATUSES.index(
                    contract[
                        "contract_status"
                    ]
                )
                if contract[
                    "contract_status"
                ] in CONTRACT_STATUSES
                else 0
            )

            contract_status = st.selectbox(
                "Contract Status",
                CONTRACT_STATUSES,
                index=status_index,
            )

        with col2:

            auto_renew = st.checkbox(
                "Auto Renew",
                value=bool(
                    contract["auto_renew"]
                ),
            )

        end_date = st.date_input(
            "Contract End Date",
            value=(
                contract["end_date"]
                if contract["end_date"]
                else date.today()
            ),
        )

        update_button = (
            st.form_submit_button(
                "Update Contract",
                type="primary",
                use_container_width=True,
            )
        )

    if update_button:

        try:

            update_contract(
                contract_id=contract_id,
                contract_status=contract_status,
                auto_renew=auto_renew,
                end_date=end_date,
            )

            st.success(
                "Contract updated successfully."
            )

        except Exception as e:

            st.error(
                f"Update failed: {e}"
            )


# ============================================================
# RENEW CONTRACT
# ============================================================

def renew_contract_screen():

    st.subheader("Renew Contract")

    st.caption(
        "Renew an existing contract."
    )

    search_text = st.text_input(
        "Find Contract",
        placeholder="CON-000000001",
        key="renew_contract_search",
    )

    if not search_text:

        return

    try:

        df = search_contracts(
            search_text=search_text,
            limit=20,
        )

    except Exception as e:

        st.error(
            f"Search failed: {e}"
        )

        return

    if df.empty:

        st.warning(
            "No contracts found."
        )

        return

    options = {}

    for row in df.itertuples():

        label = (
            f"{row.contract_number} | "
            f"{row.customer_number} | "
            f"{row.first_name} "
            f"{row.last_name}"
        )

        options[label] = int(
            row.contract_id
        )

    selected = st.selectbox(
        "Contract",
        list(options.keys()),
        key="renew_contract_selector",
    )

    contract_id = options[selected]

    contract = get_contract(
        contract_id
    )

    if not contract:

        return

    st.info(
        f"Current contract: "
        f"**{contract['contract_number']}**"
    )

    col1, col2 = st.columns(2)

    with col1:

        new_contract_type = st.selectbox(
            "Renewal Contract Type",
            CONTRACT_TYPES,
            index=(
                CONTRACT_TYPES.index(
                    contract["contract_type"]
                )
                if contract["contract_type"]
                in CONTRACT_TYPES
                else 0
            ),
        )

    with col2:

        new_start_date = st.date_input(
            "Renewal Start Date",
            value=date.today(),
        )

    new_end_date = calculate_end_date(
        new_contract_type,
        new_start_date,
    )

    if new_end_date:

        st.info(
            f"New end date: **{new_end_date}**"
        )

    else:

        st.info(
            "Renewal will be open-ended."
        )

    if st.button(
        "🔄 Renew Contract",
        type="primary",
        use_container_width=True,
    ):

        try:

            end_date = renew_contract(
                contract_id=contract_id,
                new_start_date=new_start_date,
                contract_type=new_contract_type,
            )

            st.success(
                f"Contract {contract['contract_number']} "
                "renewed successfully."
            )

            st.info(
                f"New end date: "
                f"**{end_date or 'Open-ended'}**"
            )

        except Exception as e:

            st.error(
                f"Renewal failed: {e}"
            )


# ============================================================
# CHANGE PLAN
# ============================================================

def change_plan_screen():

    st.subheader("Upgrade / Downgrade Plan")

    st.caption(
        "Change the product associated with an "
        "active contract."
    )

    search_text = st.text_input(
        "Find Contract",
        placeholder="CON-000000001",
        key="change_plan_search",
    )

    if not search_text:

        return

    try:

        contracts = search_contracts(
            search_text=search_text,
            limit=20,
        )

        products = get_active_products()

    except Exception as e:

        st.error(
            f"Unable to load data: {e}"
        )

        return

    if contracts.empty:

        st.warning(
            "No contracts found."
        )

        return

    options = {}

    for row in contracts.itertuples():

        label = (
            f"{row.contract_number} | "
            f"{row.customer_number} | "
            f"{row.first_name} "
            f"{row.last_name}"
        )

        options[label] = int(
            row.contract_id
        )

    selected_contract = st.selectbox(
        "Contract",
        list(options.keys()),
        key="change_plan_contract",
    )

    contract_id = options[
        selected_contract
    ]

    contract = get_contract(
        contract_id
    )

    details = get_contract_details(
        contract_id
    )

    if contract is None:

        return

    st.markdown(
        "### Current Plan"
    )

    if not details.empty:

        current = details.iloc[-1]

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Product",
            current["product_code"],
        )

        c2.metric(
            "Download",
            f"{current['download_speed_mbps']} Mbps",
        )

        c3.metric(
            "Monthly Price",
            format_currency(
                current["agreed_monthly_price"]
            ),
        )

    st.divider()

    st.markdown(
        "### New Plan"
    )

    product_options = {}

    for row in products.itertuples():

        label = (
            f"{row.product_code} - "
            f"{row.product_name} | "
            f"{row.download_speed_mbps} Mbps | "
            f"₹{row.monthly_charge}/month"
        )

        product_options[label] = row

    selected_product = st.selectbox(
        "New Product",
        list(product_options.keys()),
        key="new_plan_product",
    )

    product = product_options[
        selected_product
    ]

    new_monthly_price = st.number_input(
        "Agreed Monthly Price",
        min_value=0.0,
        value=float(
            product.monthly_charge
        ),
        step=10.0,
        key="change_plan_price",
    )

    effective_date = st.date_input(
        "Effective Date",
        value=date.today(),
        key="change_plan_effective_date",
    )

    if st.button(
        "Change Plan",
        type="primary",
        use_container_width=True,
    ):

        try:

            change_plan(
                contract_id=contract_id,
                new_product_id=int(
                    product.product_id
                ),
                new_rate_schedule_id=int(
                    product.rate_schedule_id
                ),
                new_monthly_price=
                    new_monthly_price,
                new_tax_percent=float(
                    product.tax_percentage
                ),
                effective_date=effective_date,
            )

            st.success(
                "Plan changed successfully."
            )

        except Exception as e:

            st.error(
                f"Plan change failed: {e}"
            )


# ============================================================
# CONTRACT 360
# ============================================================

def contract_360_screen():

    st.subheader("Contract 360")

    contract_id = st.session_state.get(
        "selected_contract_id"
    )

    if not contract_id:

        st.info(
            "Select a contract from Search Contract."
        )

        return

    contract = get_contract(
        contract_id
    )

    if not contract:

        st.error(
            "Contract not found."
        )

        return

    details = get_contract_details(
        contract_id
    )

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    st.markdown(
        f"""
        ## {contract["contract_number"]}

        **Customer:** {contract["customer_number"]}
        - {contract["first_name"]}
        {contract["last_name"]}
        """
    )

    # --------------------------------------------------------
    # KPI
    # --------------------------------------------------------

    monthly_value = Decimal("0")

    for _, row in details.iterrows():

        price = Decimal(
            str(row["agreed_monthly_price"])
        )

        quantity = int(
            row["quantity"]
        )

        discount = Decimal(
            str(row["discount_amount"])
        )

        monthly_value += (
            price * quantity
        ) - discount

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Status",
        contract["contract_status"],
    )

    c2.metric(
        "Contract Type",
        contract["contract_type"],
    )

    c3.metric(
        "Contract Lines",
        len(details),
    )

    c4.metric(
        "Monthly Value",
        format_currency(
            monthly_value
        ),
    )

    st.divider()

    # --------------------------------------------------------
    # Contract Header
    # --------------------------------------------------------

    st.markdown(
        "### Contract Information"
    )

    c1, c2, c3 = st.columns(3)

    c1.write(
        f"**Contract ID:** "
        f"{contract['contract_id']}"
    )

    c2.write(
        f"**Customer ID:** "
        f"{contract['customer_id']}"
    )

    c3.write(
        f"**Auto Renew:** "
        f"{'Yes' if contract['auto_renew'] else 'No'}"
    )

    c1, c2, c3 = st.columns(3)

    c1.write(
        f"**Start Date:** "
        f"{contract['start_date']}"
    )

    c2.write(
        f"**End Date:** "
        f"{contract['end_date'] or 'Open-ended'}"
    )

    c3.write(
        f"**Status:** "
        f"{contract['contract_status']}"
    )

    st.divider()

    # --------------------------------------------------------
    # Customer
    # --------------------------------------------------------

    st.markdown(
        "### Customer"

    )

    c1, c2 = st.columns(2)

    with c1:

        st.write(
            f"**Customer Number:** "
            f"{contract['customer_number']}"
        )

        st.write(
            f"**Customer Name:** "
            f"{contract['first_name']} "
            f"{contract['last_name']}"
        )

    with c2:

        st.write(
            f"**Email:** "
            f"{contract['email']}"
        )

    st.divider()

    # --------------------------------------------------------
    # Contract Details
    # --------------------------------------------------------

    st.markdown(
        "### Contract Details"
    )

    if details.empty:

        st.info(
            "No contract details found."
        )

        return

    display = details.copy()

    display["monthly_value"] = (
        display["agreed_monthly_price"]
        * display["quantity"]
        - display["discount_amount"]
    )

    display[
        "monthly_value"
    ] = display[
        "monthly_value"
    ].apply(format_currency)

    display[
        "agreed_monthly_price"
    ] = display[
        "agreed_monthly_price"
    ].apply(format_currency)

    display[
        "discount_amount"
    ] = display[
        "discount_amount"
    ].apply(format_currency)

    st.dataframe(
        display[
            [
                "line_number",
                "product_code",
                "product_name",
                "technology",
                "download_speed_mbps",
                "upload_speed_mbps",
                "quantity",
                "agreed_monthly_price",
                "discount_amount",
                "tax_percent",
                "effective_from",
                "effective_to",
                "monthly_value",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # --------------------------------------------------------
    # Product Cards
    # --------------------------------------------------------

    st.markdown(
        "### Product Details"
    )

    for _, row in details.iterrows():

        with st.expander(
            f"Line {row['line_number']} - "
            f"{row['product_code']} - "
            f"{row['product_name']}",
            expanded=True,
        ):

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Technology",
                row["technology"],
            )

            c2.metric(
                "Download",
                f"{row['download_speed_mbps']} Mbps",
            )

            c3.metric(
                "Upload",
                f"{row['upload_speed_mbps']} Mbps",
            )

            c4.metric(
                "Quantity",
                row["quantity"],
            )

            st.write(
                f"**Monthly Price:** "
                f"{format_currency(row['agreed_monthly_price'])}"
            )

            st.write(
                f"**Discount:** "
                f"{format_currency(row['discount_amount'])}"
            )

            st.write(
                f"**Tax:** "
                f"{row['tax_percent']}%"
            )

            st.write(
                f"**Effective From:** "
                f"{row['effective_from']}"
            )

            st.write(
                f"**Effective To:** "
                f"{row['effective_to'] or 'Open-ended'}"
            )

    st.divider()

    if st.button(
        "← Back to Contract Search",
        use_container_width=True,
    ):

        st.session_state[
            "contract_management_mode"
        ] = "Search"

        st.rerun()


# ============================================================
# MAIN CONTRACT MANAGEMENT SCREEN
# ============================================================

def contract_management_screen():

    st.title(
        "📄 Contract Management"
    )

    st.caption(
        "Manage ISP contracts, contract details, "
        "renewals and plan changes."
    )

    modes = [
        "Create",
        "Search",
        "Edit",
        "Renew",
        "Change Plan",
        "Contract 360",
    ]

    current_mode = st.session_state.get(
        "contract_management_mode",
        "Create",
    )

    if current_mode not in modes:

        current_mode = "Create"

    selected_mode = st.radio(
        "Contract Management",
        modes,
        index=modes.index(
            current_mode
        ),
        horizontal=True,
    )

    st.session_state[
        "contract_management_mode"
    ] = selected_mode

    st.divider()

    if selected_mode == "Create":

        create_contract_screen()

    elif selected_mode == "Search":

        search_contract_screen()

    elif selected_mode == "Edit":

        edit_contract_screen()

    elif selected_mode == "Renew":

        renew_contract_screen()

    elif selected_mode == "Change Plan":

        change_plan_screen()

    elif selected_mode == "Contract 360":

        contract_360_screen()