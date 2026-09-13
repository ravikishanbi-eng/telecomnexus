from datetime import datetime
import re

import pandas as pd
import streamlit as st

from db import get_connection


# =========================================================
# CONSTANTS
# =========================================================

CUSTOMER_TYPES = [
    "RESIDENTIAL",
    "BUSINESS",
]

CUSTOMER_STATUSES = [
    "ACTIVE",
    "INACTIVE",
    "SUSPENDED",
]


INDIAN_STATES = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]


# =========================================================
# VALIDATION
# =========================================================

def validate_email(email: str) -> bool:

    pattern = (
        r"^[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    )

    return bool(
        re.match(
            pattern,
            email.strip(),
        )
    )


def validate_phone(phone: str) -> bool:

    digits = re.sub(
        r"\D",
        "",
        phone,
    )

    return len(digits) >= 10


# =========================================================
# DATABASE FUNCTIONS
# =========================================================

def get_customer_count():

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT COUNT(*)
                FROM crm.customer
                """
            )

            return cur.fetchone()[0]

    finally:

        conn.close()


def search_customers(
    search_text="",
    customer_status=None,
    customer_type=None,
    limit=100,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            query = """
                SELECT
                    customer_id,
                    customer_number,
                    customer_type,
                    first_name,
                    last_name,
                    email,
                    phone,
                    address_line1,
                    city,
                    state,
                    postal_code,
                    country,
                    customer_status,
                    customer_since,
                    created_at,
                    updated_at
                FROM crm.customer
                WHERE 1 = 1
            """

            params = []

            if search_text:

                query += """
                    AND (
                        customer_number ILIKE %s
                        OR first_name ILIKE %s
                        OR last_name ILIKE %s
                        OR email ILIKE %s
                        OR phone ILIKE %s
                    )
                """

                search_value = f"%{search_text}%"

                params.extend(
                    [
                        search_value,
                        search_value,
                        search_value,
                        search_value,
                        search_value,
                    ]
                )

            if customer_status:

                query += """
                    AND customer_status = %s
                """

                params.append(customer_status)

            if customer_type:

                query += """
                    AND customer_type = %s
                """

                params.append(customer_type)

            query += """
                ORDER BY customer_id DESC
                LIMIT %s
            """

            params.append(limit)

            cur.execute(
                query,
                params,
            )

            rows = cur.fetchall()

            columns = [
                "customer_id",
                "customer_number",
                "customer_type",
                "first_name",
                "last_name",
                "email",
                "phone",
                "address_line1",
                "city",
                "state",
                "postal_code",
                "country",
                "customer_status",
                "customer_since",
                "created_at",
                "updated_at",
            ]

            return pd.DataFrame(
                rows,
                columns=columns,
            )

    finally:

        conn.close()


def get_customer(customer_id):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    customer_id,
                    customer_number,
                    customer_type,
                    first_name,
                    last_name,
                    email,
                    phone,
                    address_line1,
                    city,
                    state,
                    postal_code,
                    country,
                    customer_status,
                    customer_since,
                    created_at,
                    updated_at
                FROM crm.customer
                WHERE customer_id = %s
                """,
                (customer_id,),
            )

            row = cur.fetchone()

            if not row:
                return None

            columns = [
                "customer_id",
                "customer_number",
                "customer_type",
                "first_name",
                "last_name",
                "email",
                "phone",
                "address_line1",
                "city",
                "state",
                "postal_code",
                "country",
                "customer_status",
                "customer_since",
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


def email_or_phone_exists_for_other_customer(
    customer_id,
    email,
    phone,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT customer_id
                FROM crm.customer
                WHERE customer_id <> %s
                  AND (
                        LOWER(email) = LOWER(%s)
                        OR phone = %s
                  )
                LIMIT 1
                """,
                (
                    customer_id,
                    email,
                    phone,
                ),
            )

            return cur.fetchone()

    finally:

        conn.close()


def create_customer(data):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # Protect MAX + 1 ID generation.
            cur.execute(
                "SELECT pg_advisory_xact_lock(1001)"
            )

            cur.execute(
                """
                SELECT COALESCE(
                    MAX(customer_id),
                    0
                ) + 1
                FROM crm.customer
                """
            )

            customer_id = cur.fetchone()[0]

            customer_number = (
                f"CUST-{customer_id:08d}"
            )

            now = datetime.now()

            cur.execute(
                """
                INSERT INTO crm.customer (
                    customer_id,
                    customer_number,
                    customer_type,
                    first_name,
                    last_name,
                    email,
                    phone,
                    address_line1,
                    city,
                    state,
                    postal_code,
                    country,
                    customer_status,
                    customer_since,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, CURRENT_DATE,
                    %s, %s
                )
                """,
                (
                    customer_id,
                    customer_number,
                    data["customer_type"],
                    data["first_name"],
                    data["last_name"],
                    data["email"],
                    data["phone"],
                    data["address_line1"],
                    data["city"],
                    data["state"],
                    data["postal_code"],
                    data["country"],
                    data["customer_status"],
                    now,
                    now,
                ),
            )

        conn.commit()

        return (
            customer_id,
            customer_number,
        )

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


def update_customer(
    customer_id,
    data,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE crm.customer
                SET
                    customer_type = %s,
                    first_name = %s,
                    last_name = %s,
                    email = %s,
                    phone = %s,
                    address_line1 = %s,
                    city = %s,
                    state = %s,
                    postal_code = %s,
                    country = %s,
                    customer_status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE customer_id = %s
                """,
                (
                    data["customer_type"],
                    data["first_name"],
                    data["last_name"],
                    data["email"],
                    data["phone"],
                    data["address_line1"],
                    data["city"],
                    data["state"],
                    data["postal_code"],
                    data["country"],
                    data["customer_status"],
                    customer_id,
                ),
            )

            if cur.rowcount == 0:

                raise ValueError(
                    "Customer was not found."
                )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# =========================================================
# CUSTOMER 360 QUERIES
# =========================================================

def get_customer_contracts(customer_id):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    c.contract_id,
                    c.contract_number,
                    c.contract_type,
                    c.start_date,
                    c.end_date,
                    c.contract_status,
                    c.auto_renew,

                    cd.contract_detail_id,
                    cd.line_number,
                    cd.quantity,
                    cd.agreed_monthly_price,
                    cd.discount_amount,
                    cd.tax_percent,

                    p.product_code,
                    p.product_name,
                    p.product_category,
                    p.technology,
                    p.download_speed_mbps,
                    p.upload_speed_mbps

                FROM crm.contract c

                LEFT JOIN crm.contract_detail cd
                    ON cd.contract_id =
                       c.contract_id

                LEFT JOIN prd.product p
                    ON p.product_id =
                       cd.product_id

                WHERE c.customer_id = %s

                ORDER BY
                    c.contract_id DESC,
                    cd.line_number
                """,
                (customer_id,),
            )

            rows = cur.fetchall()

            columns = [
                "contract_id",
                "contract_number",
                "contract_type",
                "start_date",
                "end_date",
                "contract_status",
                "auto_renew",
                "contract_detail_id",
                "line_number",
                "quantity",
                "agreed_monthly_price",
                "discount_amount",
                "tax_percent",
                "product_code",
                "product_name",
                "product_category",
                "technology",
                "download_speed_mbps",
                "upload_speed_mbps",
            ]

            return pd.DataFrame(
                rows,
                columns=columns,
            )

    finally:

        conn.close()


def get_customer_contract_summary(
    customer_id,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    COUNT(
                        DISTINCT c.contract_id
                    ) AS total_contracts,

                    COUNT(
                        DISTINCT CASE
                            WHEN c.contract_status =
                                 'ACTIVE'
                            THEN c.contract_id
                        END
                    ) AS active_contracts,

                    COUNT(
                        DISTINCT cd.contract_detail_id
                    ) AS total_contract_lines,

                    COALESCE(
                        SUM(
                            (
                                cd.agreed_monthly_price
                                * cd.quantity
                            )
                            - cd.discount_amount
                        ),
                        0
                    ) AS monthly_recurring_value

                FROM crm.contract c

                LEFT JOIN crm.contract_detail cd
                    ON cd.contract_id =
                       c.contract_id

                WHERE c.customer_id = %s
                """,
                (customer_id,),
            )

            row = cur.fetchone()

            return {
                "total_contracts": row[0],
                "active_contracts": row[1],
                "total_contract_lines": row[2],
                "monthly_recurring_value": row[3],
            }

    finally:

        conn.close()


# =========================================================
# CREATE CUSTOMER SCREEN
# =========================================================

def create_customer_screen():

    st.subheader("Create Customer")

    st.caption(
        "Create a new ISP customer profile."
    )

    with st.form(
        "create_customer_form",
        clear_on_submit=True,
    ):

        st.markdown("### Customer Information")

        col1, col2, col3 = st.columns(3)

        with col1:

            first_name = st.text_input(
                "First Name *"
            )

        with col2:

            last_name = st.text_input(
                "Last Name *"
            )

        with col3:

            customer_type = st.selectbox(
                "Customer Type *",
                CUSTOMER_TYPES,
            )

        col1, col2 = st.columns(2)

        with col1:

            email = st.text_input(
                "Email *"
            )

        with col2:

            phone = st.text_input(
                "Phone *"
            )

        address_line1 = st.text_input(
            "Address *"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            city = st.text_input(
                "City *"
            )

        with col2:

            state = st.selectbox(
                "State *",
                INDIAN_STATES,
            )

        with col3:

            postal_code = st.text_input(
                "Postal Code *"
            )

        col1, col2 = st.columns(2)

        with col1:

            country = st.text_input(
                "Country",
                value="India",
            )

        with col2:

            customer_status = st.selectbox(
                "Status",
                CUSTOMER_STATUSES,
                index=0,
            )

        st.divider()

        submitted = st.form_submit_button(
            "Create Customer",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    errors = []

    if not first_name.strip():
        errors.append(
            "First name is required."
        )

    if not last_name.strip():
        errors.append(
            "Last name is required."
        )

    if not validate_email(email):
        errors.append(
            "Enter a valid email address."
        )

    if not validate_phone(phone):
        errors.append(
            "Enter a valid phone number."
        )

    if not address_line1.strip():
        errors.append(
            "Address is required."
        )

    if not city.strip():
        errors.append(
            "City is required."
        )

    if not postal_code.strip():
        errors.append(
            "Postal code is required."
        )

    if errors:

        for error in errors:
            st.error(error)

        return

    try:

        # Duplicate check
        conn = get_connection()

        try:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        customer_id,
                        customer_number
                    FROM crm.customer
                    WHERE LOWER(email) =
                          LOWER(%s)
                       OR phone = %s
                    LIMIT 1
                    """,
                    (
                        email.strip(),
                        phone.strip(),
                    ),
                )

                existing = cur.fetchone()

        finally:

            conn.close()

        if existing:

            st.error(
                f"Customer already exists: "
                f"{existing[1]} "
                f"(ID: {existing[0]})"
            )

            return

        customer_id, customer_number = (
            create_customer(
                {
                    "customer_type": customer_type,
                    "first_name": first_name.strip(),
                    "last_name": last_name.strip(),
                    "email": email.strip(),
                    "phone": phone.strip(),
                    "address_line1":
                        address_line1.strip(),
                    "city": city.strip(),
                    "state": state,
                    "postal_code":
                        postal_code.strip(),
                    "country":
                        country.strip(),
                    "customer_status":
                        customer_status,
                }
            )
        )

        st.success(
            "Customer created successfully."
        )

        col1, col2 = st.columns(2)

        col1.metric(
            "Customer ID",
            customer_id,
        )

        col2.metric(
            "Customer Number",
            customer_number,
        )

    except Exception as e:

        st.error(
            f"Unable to create customer: {e}"
        )


# =========================================================
# SEARCH CUSTOMER SCREEN
# =========================================================

def search_customer_screen():

    st.subheader("Search Customer")

    st.caption(
        "Search customers by number, name, email or phone."
    )

    with st.form("customer_search_form"):

        col1, col2, col3 = st.columns(3)

        with col1:

            search_text = st.text_input(
                "Search",
                placeholder=(
                    "Customer number / name / "
                    "email / phone"
                ),
            )

        with col2:

            status_filter = st.selectbox(
                "Status",
                ["All"] + CUSTOMER_STATUSES,
            )

        with col3:

            type_filter = st.selectbox(
                "Customer Type",
                ["All"] + CUSTOMER_TYPES,
            )

        search_button = st.form_submit_button(
            "Search",
            type="primary",
        )

    if search_button:

        status = (
            None
            if status_filter == "All"
            else status_filter
        )

        customer_type = (
            None
            if type_filter == "All"
            else type_filter
        )

        try:

            df = search_customers(
                search_text=search_text.strip(),
                customer_status=status,
                customer_type=customer_type,
            )

            st.session_state[
                "customer_search_results"
            ] = df

        except Exception as e:

            st.error(
                f"Search failed: {e}"
            )

    df = st.session_state.get(
        "customer_search_results"
    )

    if df is None:
        return

    if df.empty:

        st.warning(
            "No customers found."
        )

        return

    st.success(
        f"{len(df)} customer(s) found."
    )

    display_columns = [
        "customer_id",
        "customer_number",
        "customer_type",
        "first_name",
        "last_name",
        "email",
        "phone",
        "city",
        "state",
        "customer_status",
    ]

    st.dataframe(
        df[display_columns],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(
        "### Select Customer"
    )

    options = {
        (
            f"{row.customer_number} | "
            f"{row.first_name} "
            f"{row.last_name} | "
            f"{row.email}"
        ): row.customer_id
        for row in df.itertuples()
    }

    selected = st.selectbox(
        "Customer",
        list(options.keys()),
    )

    selected_id = options[selected]

    if st.button(
        "Open Customer 360",
        use_container_width=True,
    ):

        st.session_state[
            "selected_customer_id"
        ] = int(selected_id)

        st.session_state[
            "customer_management_mode"
        ] = "Customer 360"

        st.rerun()


# =========================================================
# EDIT CUSTOMER SCREEN
# =========================================================

def edit_customer_screen():

    st.subheader("Edit Customer")

    st.caption(
        "Update an existing customer profile."
    )

    search_text = st.text_input(
        "Find Customer",
        placeholder=(
            "Customer number, name, email or phone"
        ),
        key="edit_customer_search",
    )

    if search_text:

        try:

            df = search_customers(
                search_text=search_text,
                limit=20,
            )

        except Exception as e:

            st.error(
                f"Unable to search customers: {e}"
            )

            return

        if df.empty:

            st.warning(
                "No customers found."
            )

            return

        options = {
            (
                f"{row.customer_number} | "
                f"{row.first_name} "
                f"{row.last_name} | "
                f"{row.email}"
            ): int(row.customer_id)
            for row in df.itertuples()
        }

        selected = st.selectbox(
            "Select Customer",
            list(options.keys()),
            key="edit_customer_selector",
        )

        customer_id = options[selected]

        customer = get_customer(
            customer_id
        )

        if not customer:

            st.error(
                "Customer no longer exists."
            )

            return

        st.divider()

        st.markdown(
            f"### Editing "
            f"`{customer['customer_number']}`"
        )

        with st.form(
            "edit_customer_form"
        ):

            col1, col2, col3 = st.columns(3)

            with col1:

                first_name = st.text_input(
                    "First Name *",
                    value=customer[
                        "first_name"
                    ],
                )

            with col2:

                last_name = st.text_input(
                    "Last Name *",
                    value=customer[
                        "last_name"
                    ],
                )

            with col3:

                customer_type = st.selectbox(
                    "Customer Type *",
                    CUSTOMER_TYPES,
                    index=(
                        CUSTOMER_TYPES.index(
                            customer[
                                "customer_type"
                            ]
                        )
                        if customer[
                            "customer_type"
                        ] in CUSTOMER_TYPES
                        else 0
                    ),
                )

            col1, col2 = st.columns(2)

            with col1:

                email = st.text_input(
                    "Email *",
                    value=customer["email"],
                )

            with col2:

                phone = st.text_input(
                    "Phone *",
                    value=customer["phone"],
                )

            address_line1 = st.text_input(
                "Address *",
                value=customer[
                    "address_line1"
                ],
            )

            col1, col2, col3 = st.columns(3)

            with col1:

                city = st.text_input(
                    "City *",
                    value=customer["city"],
                )

            with col2:

                current_state = customer[
                    "state"
                ]

                state_index = (
                    INDIAN_STATES.index(
                        current_state
                    )
                    if current_state
                    in INDIAN_STATES
                    else 0
                )

                state = st.selectbox(
                    "State *",
                    INDIAN_STATES,
                    index=state_index,
                )

            with col3:

                postal_code = st.text_input(
                    "Postal Code *",
                    value=customer[
                        "postal_code"
                    ],
                )

            col1, col2 = st.columns(2)

            with col1:

                country = st.text_input(
                    "Country",
                    value=customer[
                        "country"
                    ],
                )

            with col2:

                current_status = customer[
                    "customer_status"
                ]

                status_index = (
                    CUSTOMER_STATUSES.index(
                        current_status
                    )
                    if current_status
                    in CUSTOMER_STATUSES
                    else 0
                )

                customer_status = st.selectbox(
                    "Status",
                    CUSTOMER_STATUSES,
                    index=status_index,
                )

            st.divider()

            update_button = (
                st.form_submit_button(
                    "Update Customer",
                    type="primary",
                    use_container_width=True,
                )
            )

        if update_button:

            errors = []

            if not first_name.strip():
                errors.append(
                    "First name is required."
                )

            if not last_name.strip():
                errors.append(
                    "Last name is required."
                )

            if not validate_email(email):
                errors.append(
                    "Invalid email address."
                )

            if not validate_phone(phone):
                errors.append(
                    "Invalid phone number."
                )

            if not address_line1.strip():
                errors.append(
                    "Address is required."
                )

            if not city.strip():
                errors.append(
                    "City is required."
                )

            if not postal_code.strip():
                errors.append(
                    "Postal code is required."
                )

            duplicate = (
                email_or_phone_exists_for_other_customer(
                    customer_id,
                    email.strip(),
                    phone.strip(),
                )
            )

            if duplicate:

                errors.append(
                    "Email or phone belongs to "
                    "another customer."
                )

            if errors:

                for error in errors:
                    st.error(error)

                return

            try:

                update_customer(
                    customer_id,
                    {
                        "customer_type":
                            customer_type,
                        "first_name":
                            first_name.strip(),
                        "last_name":
                            last_name.strip(),
                        "email":
                            email.strip(),
                        "phone":
                            phone.strip(),
                        "address_line1":
                            address_line1.strip(),
                        "city":
                            city.strip(),
                        "state":
                            state,
                        "postal_code":
                            postal_code.strip(),
                        "country":
                            country.strip(),
                        "customer_status":
                            customer_status,
                    },
                )

                st.success(
                    "Customer updated successfully."
                )

                st.rerun()

            except Exception as e:

                st.error(
                    f"Unable to update customer: {e}"
                )


# =========================================================
# CUSTOMER 360
# =========================================================

def customer_360_screen():

    st.subheader("Customer 360")

    st.caption(
        "Complete customer and contract view."
    )

    customer_id = st.session_state.get(
        "selected_customer_id"
    )

    if not customer_id:

        st.info(
            "Select a customer from Search Customer."
        )

        return

    customer = get_customer(
        customer_id
    )

    if not customer:

        st.error(
            "Customer was not found."
        )

        return

    # -----------------------------------------------------
    # CUSTOMER HEADER
    # -----------------------------------------------------

    st.markdown(
        f"""
        ## {customer["first_name"]}
        {customer["last_name"]}

        **Customer Number:** `{customer["customer_number"]}`
        """
    )

    # -----------------------------------------------------
    # KPI SUMMARY
    # -----------------------------------------------------

    summary = (
        get_customer_contract_summary(
            customer_id
        )
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Customer Status",
        customer["customer_status"],
    )

    col2.metric(
        "Total Contracts",
        summary["total_contracts"],
    )

    col3.metric(
        "Active Contracts",
        summary["active_contracts"],
    )

    col4.metric(
        "Monthly Recurring Value",
        f"₹{summary['monthly_recurring_value']:,.2f}",
    )

    st.divider()

    # -----------------------------------------------------
    # CUSTOMER DETAILS
    # -----------------------------------------------------

    st.markdown(
        "### Customer Profile"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            f"**Customer ID:** "
            f"{customer['customer_id']}"
        )

        st.write(
            f"**Customer Type:** "
            f"{customer['customer_type']}"
        )

        st.write(
            f"**Email:** "
            f"{customer['email']}"
        )

        st.write(
            f"**Phone:** "
            f"{customer['phone']}"
        )

    with col2:

        st.write(
            f"**Address:** "
            f"{customer['address_line1']}"
        )

        st.write(
            f"**City:** "
            f"{customer['city']}"
        )

        st.write(
            f"**State:** "
            f"{customer['state']}"
        )

        st.write(
            f"**Postal Code:** "
            f"{customer['postal_code']}"
        )

    st.divider()

    # -----------------------------------------------------
    # CONTRACTS
    # -----------------------------------------------------

    st.markdown(
        "### Contracts & Services Purchased"
    )

    contracts = get_customer_contracts(
        customer_id
    )

    if contracts.empty:

        st.info(
            "This customer has no contracts."
        )

        return

    st.dataframe(
        contracts[
            [
                "contract_number",
                "contract_type",
                "start_date",
                "end_date",
                "contract_status",
                "product_code",
                "product_name",
                "technology",
                "download_speed_mbps",
                "upload_speed_mbps",
                "quantity",
                "agreed_monthly_price",
                "discount_amount",
                "tax_percent",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    # -----------------------------------------------------
    # CONTRACT BREAKDOWN
    # -----------------------------------------------------

    st.markdown(
        "### Contract Breakdown"
    )

    contract_numbers = (
        contracts[
            "contract_number"
        ]
        .dropna()
        .unique()
        .tolist()
    )

    selected_contract = st.selectbox(
        "Select Contract",
        contract_numbers,
        key="customer_360_contract",
    )

    selected_contract_df = contracts[
        contracts["contract_number"]
        == selected_contract
    ]

    for _, row in selected_contract_df.iterrows():

        with st.expander(
            f"{row['contract_number']} | "
            f"{row['product_name']}",
            expanded=True,
        ):

            col1, col2, col3, col4 = (
                st.columns(4)
            )

            col1.metric(
                "Contract",
                row["contract_number"],
            )

            col2.metric(
                "Status",
                row["contract_status"],
            )

            col3.metric(
                "Download",
                f"{row['download_speed_mbps']} Mbps",
            )

            col4.metric(
                "Upload",
                f"{row['upload_speed_mbps']} Mbps",
            )

            st.write(
                f"**Product:** "
                f"{row['product_code']} - "
                f"{row['product_name']}"
            )

            st.write(
                f"**Technology:** "
                f"{row['technology']}"
            )

            st.write(
                f"**Contract Type:** "
                f"{row['contract_type']}"
            )

            st.write(
                f"**Start Date:** "
                f"{row['start_date']}"
            )

            st.write(
                f"**End Date:** "
                f"{row['end_date'] or 'Open-ended'}"
            )

            st.write(
                f"**Quantity:** "
                f"{row['quantity']}"
            )

            st.write(
                f"**Agreed Monthly Price:** "
                f"₹{row['agreed_monthly_price']:,.2f}"
            )

            st.write(
                f"**Discount:** "
                f"₹{row['discount_amount']:,.2f}"
            )

            st.write(
                f"**Tax:** "
                f"{row['tax_percent']}%"
            )

    st.divider()

    if st.button(
        "← Back to Search",
        use_container_width=True,
    ):

        st.session_state[
            "customer_management_mode"
        ] = "Search"

        st.rerun()


# =========================================================
# MAIN CUSTOMER MANAGEMENT SCREEN
# =========================================================

def customer_management_screen():

    st.title(
        "👤 Customer Management"
    )

    st.caption(
        "Manage the complete ISP customer lifecycle."
    )

    # -----------------------------------------------------
    # Top-level navigation
    # -----------------------------------------------------

    modes = [
        "Create",
        "Search",
        "Edit",
        "Customer 360",
    ]

    current_mode = st.session_state.get(
        "customer_management_mode",
        "Create",
    )

    if current_mode not in modes:
        current_mode = "Create"

    selected_mode = st.radio(
        "Customer Management",
        modes,
        index=modes.index(current_mode),
        horizontal=True,
    )

    st.session_state[
        "customer_management_mode"
    ] = selected_mode

    st.divider()

    # -----------------------------------------------------
    # Dashboard KPIs
    # -----------------------------------------------------

    try:

        customer_count = (
            get_customer_count()
        )

        st.metric(
            "Total Customers",
            f"{customer_count:,}",
        )

    except Exception as e:

        st.warning(
            f"Unable to load customer count: {e}"
        )

    st.divider()

    # -----------------------------------------------------
    # Screen
    # -----------------------------------------------------

    if selected_mode == "Create":

        create_customer_screen()

    elif selected_mode == "Search":

        search_customer_screen()

    elif selected_mode == "Edit":

        edit_customer_screen()

    elif selected_mode == "Customer 360":

        customer_360_screen()