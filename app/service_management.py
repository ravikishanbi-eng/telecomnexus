from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from db import get_connection


# ============================================================
# CONSTANTS
# ============================================================

SERVICE_STATUSES = [
    "ACTIVE",
    "PENDING",
    "SUSPENDED",
    "TERMINATED",
]

SERVICE_TYPES = [
    "BROADBAND",
]


# ============================================================
# HELPERS
# ============================================================

def format_currency(value):

    if value is None:
        return "₹0.00"

    return f"₹{Decimal(str(value)):,.2f}"


def safe_value(value):

    if value is None:
        return ""

    return str(value)


# ============================================================
# GET CUSTOMERS
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
                    phone,
                    address_line1,
                    city,
                    state,
                    postal_code,
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
                "phone",
                "address_line1",
                "city",
                "state",
                "postal_code",
                "customer_status",
            ]

            return pd.DataFrame(
                rows,
                columns=columns,
            )

    finally:

        conn.close()


# ============================================================
# GET ACTIVE CONTRACTS
# ============================================================

def get_customer_contracts(customer_id):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    c.contract_id,
                    c.contract_number,
                    c.customer_id,
                    c.contract_type,
                    c.start_date,
                    c.end_date,
                    c.contract_status,
                    c.auto_renew

                FROM crm.contract c

                WHERE c.customer_id = %s

                  AND c.contract_status
                      IN ('ACTIVE', 'PENDING')

                ORDER BY c.contract_id DESC
                """,
                (customer_id,),
            )

            rows = cur.fetchall()

            columns = [
                "contract_id",
                "contract_number",
                "customer_id",
                "contract_type",
                "start_date",
                "end_date",
                "contract_status",
                "auto_renew",
            ]

            return pd.DataFrame(
                rows,
                columns=columns,
            )

    finally:

        conn.close()


# ============================================================
# GET CONTRACT DETAILS
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
                    cd.effective_to

                FROM crm.contract_detail cd

                JOIN prd.product p
                    ON p.product_id =
                       cd.product_id

                WHERE cd.contract_id = %s

                ORDER BY
                    cd.line_number
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
            ]

            return pd.DataFrame(
                rows,
                columns=columns,
            )

    finally:

        conn.close()


# ============================================================
# GET SERVICE
# ============================================================

def get_service(service_id):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    s.service_id,
                    s.customer_id,
                    s.contract_id,
                    s.product_id,
                    s.service_number,
                    s.service_type,
                    s.technology,
                    s.activation_date,
                    s.deactivation_date,
                    s.service_status,
                    s.installation_address,
                    s.city,
                    s.state,
                    s.postal_code,

                    s.created_at,
                    s.updated_at,

                    c.customer_number,
                    c.first_name,
                    c.last_name,
                    c.email,
                    c.phone,

                    ct.contract_number,

                    p.product_code,
                    p.product_name,
                    p.download_speed_mbps,
                    p.upload_speed_mbps

                FROM crm.service s

                JOIN crm.customer c
                    ON c.customer_id =
                       s.customer_id

                LEFT JOIN crm.contract ct
                    ON ct.contract_id =
                       s.contract_id

                LEFT JOIN prd.product p
                    ON p.product_id =
                       s.product_id

                WHERE s.service_id = %s
                """,
                (service_id,),
            )

            row = cur.fetchone()

            if not row:
                return None

            columns = [
                "service_id",
                "customer_id",
                "contract_id",
                "product_id",
                "service_number",
                "service_type",
                "technology",
                "activation_date",
                "deactivation_date",
                "service_status",
                "installation_address",
                "city",
                "state",
                "postal_code",
                "created_at",
                "updated_at",
                "customer_number",
                "first_name",
                "last_name",
                "email",
                "phone",
                "contract_number",
                "product_code",
                "product_name",
                "download_speed_mbps",
                "upload_speed_mbps",
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
# SEARCH SERVICES
# ============================================================

def search_services(
    search_text="",
    status=None,
    service_type=None,
    limit=100,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            query = """
                SELECT
                    s.service_id,
                    s.service_number,

                    c.customer_id,
                    c.customer_number,
                    c.first_name,
                    c.last_name,

                    ct.contract_number,

                    p.product_code,
                    p.product_name,

                    s.service_type,
                    s.technology,
                    s.activation_date,
                    s.deactivation_date,
                    s.service_status,

                    s.city,
                    s.state,
                    s.postal_code

                FROM crm.service s

                JOIN crm.customer c
                    ON c.customer_id =
                       s.customer_id

                LEFT JOIN crm.contract ct
                    ON ct.contract_id =
                       s.contract_id

                LEFT JOIN prd.product p
                    ON p.product_id =
                       s.product_id

                WHERE 1 = 1
            """

            params = []

            if search_text:

                query += """
                    AND (
                        s.service_number ILIKE %s
                        OR c.customer_number ILIKE %s
                        OR c.first_name ILIKE %s
                        OR c.last_name ILIKE %s
                        OR c.email ILIKE %s
                        OR ct.contract_number ILIKE %s
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
                        value,
                    ]
                )

            if status:

                query += """
                    AND s.service_status = %s
                """

                params.append(status)

            if service_type:

                query += """
                    AND s.service_type = %s
                """

                params.append(service_type)

            query += """
                ORDER BY
                    s.service_id DESC

                LIMIT %s
            """

            params.append(limit)

            cur.execute(
                query,
                params,
            )

            rows = cur.fetchall()

            columns = [
                "service_id",
                "service_number",
                "customer_id",
                "customer_number",
                "first_name",
                "last_name",
                "contract_number",
                "product_code",
                "product_name",
                "service_type",
                "technology",
                "activation_date",
                "deactivation_date",
                "service_status",
                "city",
                "state",
                "postal_code",
            ]

            return pd.DataFrame(
                rows,
                columns=columns,
            )

    finally:

        conn.close()


# ============================================================
# CHECK DUPLICATE ACTIVE SERVICE
# ============================================================

def check_existing_service(
    customer_id,
    contract_id,
    product_id,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    service_id,
                    service_number,
                    service_status
                FROM crm.service

                WHERE customer_id = %s

                  AND contract_id = %s

                  AND product_id = %s

                  AND service_status
                      IN ('ACTIVE', 'PENDING', 'SUSPENDED')
                """,
                (
                    customer_id,
                    contract_id,
                    product_id,
                ),
            )

            return cur.fetchone()

    finally:

        conn.close()


# ============================================================
# CREATE SERVICE
# ============================================================

def create_service(
    customer_id,
    contract_id,
    product_id,
    service_type,
    technology,
    activation_date,
    installation_address,
    city,
    state,
    postal_code,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # ------------------------------------------------
            # Validate customer
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    customer_id
                FROM crm.customer
                WHERE customer_id = %s
                """,
                (customer_id,),
            )

            if not cur.fetchone():

                raise ValueError(
                    "Customer does not exist."
                )

            # ------------------------------------------------
            # Validate contract
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    contract_id,
                    contract_status
                FROM crm.contract
                WHERE contract_id = %s
                  AND customer_id = %s
                FOR UPDATE
                """,
                (
                    contract_id,
                    customer_id,
                ),
            )

            contract = cur.fetchone()

            if not contract:

                raise ValueError(
                    "Contract does not belong "
                    "to the selected customer."
                )

            if contract[1] not in (
                "ACTIVE",
                "PENDING",
            ):

                raise ValueError(
                    "Service cannot be created "
                    "for an inactive contract."
                )

            # ------------------------------------------------
            # Validate product
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    product_id,
                    product_status,
                    technology
                FROM prd.product
                WHERE product_id = %s
                """,
                (product_id,),
            )

            product = cur.fetchone()

            if not product:

                raise ValueError(
                    "Product does not exist."
                )

            if product[1] != "ACTIVE":

                raise ValueError(
                    "Selected product is not active."
                )

            # ------------------------------------------------
            # Prevent duplicate service
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    service_id,
                    service_number
                FROM crm.service

                WHERE customer_id = %s
                  AND contract_id = %s
                  AND product_id = %s

                  AND service_status
                      IN (
                          'ACTIVE',
                          'PENDING',
                          'SUSPENDED'
                      )

                LIMIT 1
                """,
                (
                    customer_id,
                    contract_id,
                    product_id,
                ),
            )

            existing = cur.fetchone()

            if existing:

                raise ValueError(
                    f"An active service already exists: "
                    f"{existing[1]}"
                )

            # ------------------------------------------------
            # Generate service ID
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    pg_advisory_xact_lock(2001)
                """
            )

            cur.execute(
                """
                SELECT
                    COALESCE(
                        MAX(service_id),
                        0
                    ) + 1
                FROM crm.service
                """
            )

            service_id = cur.fetchone()[0]

            service_number = (
                f"SVC-{service_id:010d}"
            )

            # ------------------------------------------------
            # Insert service
            # ------------------------------------------------

            cur.execute(
                """
                INSERT INTO crm.service (
                    service_id,
                    customer_id,
                    contract_id,
                    product_id,
                    service_number,
                    service_type,
                    technology,
                    activation_date,
                    deactivation_date,
                    service_status,
                    installation_address,
                    city,
                    state,
                    postal_code,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, NULL, %s,
                    %s, %s, %s, %s,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    service_id,
                    customer_id,
                    contract_id,
                    product_id,
                    service_number,
                    service_type,
                    technology,
                    activation_date,
                    "ACTIVE",
                    installation_address,
                    city,
                    state,
                    postal_code,
                ),
            )

        conn.commit()

        return {
            "service_id": service_id,
            "service_number": service_number,
        }

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# UPDATE SERVICE
# ============================================================

def update_service(
    service_id,
    service_status,
    installation_address,
    city,
    state,
    postal_code,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    service_status
                FROM crm.service
                WHERE service_id = %s
                FOR UPDATE
                """,
                (service_id,),
            )

            row = cur.fetchone()

            if not row:

                raise ValueError(
                    "Service not found."
                )

            # ------------------------------------------------
            # Deactivation date
            # ------------------------------------------------

            if service_status == "TERMINATED":

                cur.execute(
                    """
                    UPDATE crm.service
                    SET
                        service_status = %s,
                        deactivation_date =
                            CURRENT_DATE,
                        installation_address = %s,
                        city = %s,
                        state = %s,
                        postal_code = %s,
                        updated_at =
                            CURRENT_TIMESTAMP
                    WHERE service_id = %s
                    """,
                    (
                        service_status,
                        installation_address,
                        city,
                        state,
                        postal_code,
                        service_id,
                    ),
                )

            else:

                cur.execute(
                    """
                    UPDATE crm.service
                    SET
                        service_status = %s,
                        installation_address = %s,
                        city = %s,
                        state = %s,
                        postal_code = %s,
                        updated_at =
                            CURRENT_TIMESTAMP
                    WHERE service_id = %s
                    """,
                    (
                        service_status,
                        installation_address,
                        city,
                        state,
                        postal_code,
                        service_id,
                    ),
                )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# SUSPEND / RESUME
# ============================================================

def change_service_status(
    service_id,
    new_status,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    service_status
                FROM crm.service
                WHERE service_id = %s
                FOR UPDATE
                """,
                (service_id,),
            )

            row = cur.fetchone()

            if not row:

                raise ValueError(
                    "Service not found."
                )

            current_status = row[0]

            if current_status == "TERMINATED":

                raise ValueError(
                    "A terminated service "
                    "cannot be changed."
                )

            if new_status == "SUSPENDED":

                if current_status != "ACTIVE":

                    raise ValueError(
                        "Only ACTIVE services "
                        "can be suspended."
                    )

            elif new_status == "ACTIVE":

                if current_status != "SUSPENDED":

                    raise ValueError(
                        "Only SUSPENDED services "
                        "can be resumed."
                    )

            elif new_status == "TERMINATED":

                if current_status not in (
                    "ACTIVE",
                    "SUSPENDED",
                ):

                    raise ValueError(
                        "Service cannot be terminated "
                        "from its current state."
                    )

            cur.execute(
                """
                UPDATE crm.service
                SET
                    service_status = %s,
                    deactivation_date =
                        CASE
                            WHEN %s = 'TERMINATED'
                            THEN CURRENT_DATE
                            ELSE deactivation_date
                        END,
                    updated_at =
                        CURRENT_TIMESTAMP
                WHERE service_id = %s
                """,
                (
                    new_status,
                    new_status,
                    service_id,
                ),
            )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# CREATE SERVICE SCREEN
# ============================================================

def create_service_screen():

    st.subheader("Create Service")

    st.caption(
        "Create an ISP service from an existing "
        "customer contract."
    )

    # --------------------------------------------------------
    # Customers
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
            "No customers available."
        )

        return

    customer_options = {}

    for row in customers.itertuples():

        label = (
            f"{row.customer_number} | "
            f"{row.first_name} "
            f"{row.last_name} | "
            f"{row.email}"
        )

        customer_options[label] = row

    selected_customer = st.selectbox(
        "Customer *",
        list(customer_options.keys()),
        key="service_customer",
    )

    customer = customer_options[
        selected_customer
    ]

    customer_id = int(
        customer.customer_id
    )

    # --------------------------------------------------------
    # Contract
    # --------------------------------------------------------

    try:

        contracts = get_customer_contracts(
            customer_id
        )

    except Exception as e:

        st.error(
            f"Unable to load contracts: {e}"
        )

        return

    if contracts.empty:

        st.warning(
            "This customer does not have an "
            "ACTIVE or PENDING contract."
        )

        return

    contract_options = {}

    for row in contracts.itertuples():

        label = (
            f"{row.contract_number} | "
            f"{row.contract_type} | "
            f"{row.contract_status} | "
            f"{row.start_date}"
        )

        contract_options[label] = row

    selected_contract = st.selectbox(
        "Contract *",
        list(contract_options.keys()),
        key="service_contract",
    )

    contract = contract_options[
        selected_contract
    ]

    contract_id = int(
        contract.contract_id
    )

    # --------------------------------------------------------
    # Contract Details
    # --------------------------------------------------------

    try:

        details = get_contract_details(
            contract_id
        )

    except Exception as e:

        st.error(
            f"Unable to load contract details: {e}"
        )

        return

    if details.empty:

        st.warning(
            "No contract details exist for "
            "this contract."
        )

        return

    st.markdown(
        "### Contract Product"
    )

    detail_options = {}

    for row in details.itertuples():

        label = (
            f"Line {row.line_number} | "
            f"{row.product_code} - "
            f"{row.product_name} | "
            f"{row.download_speed_mbps} Mbps | "
            f"{row.technology}"
        )

        detail_options[label] = row

    selected_detail = st.selectbox(
        "Product / Contract Detail *",
        list(detail_options.keys()),
        key="service_contract_detail",
    )

    detail = detail_options[
        selected_detail
    ]

    product_id = int(
        detail.product_id
    )

    # --------------------------------------------------------
    # Product information
    # --------------------------------------------------------

    st.markdown(
        "### Product Information"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Product",
        detail.product_code,
    )

    c2.metric(
        "Download",
        f"{detail.download_speed_mbps} Mbps",
    )

    c3.metric(
        "Upload",
        f"{detail.upload_speed_mbps} Mbps",
    )

    c4.metric(
        "Technology",
        detail.technology,
    )

    # --------------------------------------------------------
    # Service Information
    # --------------------------------------------------------

    st.markdown(
        "### Service Information"
    )

    col1, col2 = st.columns(2)

    with col1:

        service_type = st.selectbox(
            "Service Type *",
            SERVICE_TYPES,
            index=0,
        )

    with col2:

        technology = st.text_input(
            "Technology *",
            value=safe_value(
                detail.technology
            ),
            disabled=True,
        )

    activation_date = st.date_input(
        "Activation Date *",
        value=date.today(),
    )

    # --------------------------------------------------------
    # Installation Address
    # --------------------------------------------------------

    st.markdown(
        "### Installation Address"
    )

    use_customer_address = st.checkbox(
        "Use customer address",
        value=True,
    )

    if use_customer_address:

        default_address = safe_value(
            customer.address_line1
        )

        default_city = safe_value(
            customer.city
        )

        default_state = safe_value(
            customer.state
        )

        default_postal = safe_value(
            customer.postal_code
        )

    else:

        default_address = ""
        default_city = ""
        default_state = ""
        default_postal = ""

    installation_address = st.text_input(
        "Installation Address *",
        value=default_address,
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        city = st.text_input(
            "City *",
            value=default_city,
        )

    with c2:

        state = st.text_input(
            "State *",
            value=default_state,
        )

    with c3:

        postal_code = st.text_input(
            "Postal Code *",
            value=default_postal,
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    st.markdown(
        "### Service Summary"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Customer",
        customer.customer_number,
    )

    c2.metric(
        "Contract",
        contract.contract_number,
    )

    c3.metric(
        "Product",
        detail.product_code,
    )

    # --------------------------------------------------------
    # Create
    # --------------------------------------------------------

    if st.button(
        "🚀 Create Service",
        type="primary",
        use_container_width=True,
    ):

        errors = []

        if not installation_address.strip():

            errors.append(
                "Installation address is required."
            )

        if not city.strip():

            errors.append(
                "City is required."
            )

        if not state.strip():

            errors.append(
                "State is required."
            )

        if not postal_code.strip():

            errors.append(
                "Postal code is required."
            )

        if activation_date < date.today():

            errors.append(
                "Activation date cannot be "
                "in the past."
            )

        if errors:

            for error in errors:

                st.error(error)

            return

        try:

            result = create_service(
                customer_id=customer_id,
                contract_id=contract_id,
                product_id=product_id,
                service_type=service_type,
                technology=technology,
                activation_date=activation_date,
                installation_address=
                    installation_address.strip(),
                city=city.strip(),
                state=state.strip(),
                postal_code=postal_code.strip(),
            )

            st.success(
                "Service created successfully."
            )

            c1, c2 = st.columns(2)

            c1.metric(
                "Service ID",
                result["service_id"],
            )

            c2.metric(
                "Service Number",
                result["service_number"],
            )

        except Exception as e:

            st.error(
                "Service creation failed."
            )

            st.exception(e)


# ============================================================
# SEARCH SERVICE SCREEN
# ============================================================

def search_service_screen():

    st.subheader("Search Service")

    with st.form(
        "service_search_form"
    ):

        c1, c2, c3 = st.columns(3)

        with c1:

            search_text = st.text_input(
                "Search",
                placeholder=(
                    "Service number / customer / "
                    "contract"
                ),
            )

        with c2:

            status = st.selectbox(
                "Status",
                ["All"] + SERVICE_STATUSES,
            )

        with c3:

            service_type = st.selectbox(
                "Service Type",
                ["All"] + SERVICE_TYPES,
            )

        submitted = st.form_submit_button(
            "Search",
            type="primary",
        )

    if submitted:

        try:

            df = search_services(
                search_text=search_text.strip(),
                status=(
                    None
                    if status == "All"
                    else status
                ),
                service_type=(
                    None
                    if service_type == "All"
                    else service_type
                ),
            )

            st.session_state[
                "service_search_results"
            ] = df

        except Exception as e:

            st.error(
                f"Search failed: {e}"
            )

    df = st.session_state.get(
        "service_search_results"
    )

    if df is None:

        return

    if df.empty:

        st.warning(
            "No services found."
        )

        return

    st.success(
        f"{len(df)} service(s) found."
    )

    display = df.copy()

    display["customer_name"] = (
        display["first_name"]
        + " "
        + display["last_name"]
    )

    st.dataframe(
        display[
            [
                "service_number",
                "customer_number",
                "customer_name",
                "contract_number",
                "product_code",
                "product_name",
                "service_type",
                "technology",
                "activation_date",
                "deactivation_date",
                "service_status",
                "city",
                "state",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    # --------------------------------------------------------
    # Open Service 360
    # --------------------------------------------------------

    options = {}

    for row in df.itertuples():

        label = (
            f"{row.service_number} | "
            f"{row.customer_number} | "
            f"{row.product_code}"
        )

        options[label] = int(
            row.service_id
        )

    selected = st.selectbox(
        "Select Service",
        list(options.keys()),
    )

    service_id = options[selected]

    if st.button(
        "Open Service 360",
        use_container_width=True,
    ):

        st.session_state[
            "selected_service_id"
        ] = service_id

        st.session_state[
            "service_management_mode"
        ] = "Service 360"

        st.rerun()


# ============================================================
# EDIT SERVICE
# ============================================================

def edit_service_screen():

    st.subheader("Edit Service")

    search_text = st.text_input(
        "Find Service",
        placeholder="SVC-0000000001",
    )

    if not search_text:

        return

    try:

        df = search_services(
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
            "No service found."
        )

        return

    options = {}

    for row in df.itertuples():

        label = (
            f"{row.service_number} | "
            f"{row.customer_number} | "
            f"{row.product_code}"
        )

        options[label] = int(
            row.service_id
        )

    selected = st.selectbox(
        "Service",
        list(options.keys()),
    )

    service_id = options[selected]

    service = get_service(
        service_id
    )

    if not service:

        return

    st.divider()

    st.markdown(
        f"### {service['service_number']}"
    )

    st.write(
        f"Customer: "
        f"**{service['customer_number']} - "
        f"{service['first_name']} "
        f"{service['last_name']}**"
    )

    with st.form(
        "edit_service_form"
    ):

        status_index = 0

        if service["service_status"] in SERVICE_STATUSES:

            status_index = SERVICE_STATUSES.index(
                service["service_status"]
            )

        service_status = st.selectbox(
            "Service Status",
            SERVICE_STATUSES,
            index=status_index,
        )

        installation_address = st.text_input(
            "Installation Address",
            value=safe_value(
                service[
                    "installation_address"
                ]
            ),
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            city = st.text_input(
                "City",
                value=safe_value(
                    service["city"]
                ),
            )

        with c2:

            state = st.text_input(
                "State",
                value=safe_value(
                    service["state"]
                ),
            )

        with c3:

            postal_code = st.text_input(
                "Postal Code",
                value=safe_value(
                    service["postal_code"]
                ),
            )

        submitted = st.form_submit_button(
            "Update Service",
            type="primary",
            use_container_width=True,
        )

    if submitted:

        try:

            update_service(
                service_id=service_id,
                service_status=service_status,
                installation_address=
                    installation_address,
                city=city,
                state=state,
                postal_code=postal_code,
            )

            st.success(
                "Service updated successfully."
            )

        except Exception as e:

            st.error(
                f"Update failed: {e}"
            )


# ============================================================
# SUSPEND / RESUME
# ============================================================

def service_status_screen():

    st.subheader(
        "Suspend / Resume / Deactivate"
    )

    search_text = st.text_input(
        "Find Service",
        placeholder="SVC-0000000001",
        key="status_service_search",
    )

    if not search_text:

        return

    try:

        df = search_services(
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
            "No service found."
        )

        return

    options = {}

    for row in df.itertuples():

        label = (
            f"{row.service_number} | "
            f"{row.customer_number} | "
            f"{row.product_code} | "
            f"{row.service_status}"
        )

        options[label] = int(
            row.service_id
        )

    selected = st.selectbox(
        "Service",
        list(options.keys()),
        key="status_service_selector",
    )

    service_id = options[selected]

    service = get_service(
        service_id
    )

    if not service:

        return

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Service",
        service["service_number"],
    )

    c2.metric(
        "Current Status",
        service["service_status"],
    )

    c3.metric(
        "Product",
        service["product_code"] or "-",
    )

    current_status = service[
        "service_status"
    ]

    st.divider()

    if current_status == "ACTIVE":

        if st.button(
            "⏸ Suspend Service",
            type="primary",
            use_container_width=True,
        ):

            try:

                change_service_status(
                    service_id,
                    "SUSPENDED",
                )

                st.success(
                    "Service suspended successfully."
                )

            except Exception as e:

                st.error(
                    f"Unable to suspend service: {e}"
                )

    elif current_status == "SUSPENDED":

        if st.button(
            "▶ Resume Service",
            type="primary",
            use_container_width=True,
        ):

            try:

                change_service_status(
                    service_id,
                    "ACTIVE",
                )

                st.success(
                    "Service resumed successfully."
                )

            except Exception as e:

                st.error(
                    f"Unable to resume service: {e}"
                )

    if current_status in (
        "ACTIVE",
        "SUSPENDED",
    ):

        st.warning(
            "Deactivation permanently changes "
            "the service to TERMINATED."
        )

        if st.button(
            "Terminate Service",
            use_container_width=True,
        ):

            try:

                change_service_status(
                    service_id,
                    "TERMINATED",
                )

                st.success(
                    "Service terminated successfully."
                )

            except Exception as e:

                st.error(
                    f"Unable to terminate service: {e}"
                )


# ============================================================
# SERVICE 360
# ============================================================

def service_360_screen():

    st.subheader("Service 360")

    service_id = st.session_state.get(
        "selected_service_id"
    )

    if not service_id:

        st.info(
            "Select a service from Search."
        )

        return

    service = get_service(
        service_id
    )

    if not service:

        st.error(
            "Service not found."
        )

        return

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    st.markdown(
        f"""
        # {service["service_number"]}

        **{service["product_code"] or "-"} -
        {service["product_name"] or "-"}**
        """
    )

    # --------------------------------------------------------
    # KPI cards
    # --------------------------------------------------------

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Status",
        service["service_status"],
    )

    c2.metric(
        "Technology",
        service["technology"],
    )

    c3.metric(
        "Download",
        f"{service['download_speed_mbps'] or 0} Mbps",
    )

    c4.metric(
        "Upload",
        f"{service['upload_speed_mbps'] or 0} Mbps",
    )

    st.divider()

    # --------------------------------------------------------
    # Service information
    # --------------------------------------------------------

    st.markdown(
        "### Service Information"
    )

    c1, c2, c3 = st.columns(3)

    c1.write(
        f"**Service ID:** "
        f"{service['service_id']}"
    )

    c2.write(
        f"**Service Number:** "
        f"{service['service_number']}"
    )

    c3.write(
        f"**Service Type:** "
        f"{service['service_type']}"
    )

    c1.write(
        f"**Technology:** "
        f"{service['technology']}"
    )

    c2.write(
        f"**Activation Date:** "
        f"{service['activation_date']}"
    )

    c3.write(
        f"**Deactivation Date:** "
        f"{service['deactivation_date'] or 'Active'}"
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
            f"{service['customer_number']}"
        )

        st.write(
            f"**Name:** "
            f"{service['first_name']} "
            f"{service['last_name']}"
        )

        st.write(
            f"**Phone:** "
            f"{service['phone']}"
        )

    with c2:

        st.write(
            f"**Email:** "
            f"{service['email']}"
        )

        st.write(
            f"**Customer ID:** "
            f"{service['customer_id']}"
        )

    st.divider()

    # --------------------------------------------------------
    # Contract
    # --------------------------------------------------------

    st.markdown(
        "### Contract"
    )

    c1, c2, c3 = st.columns(3)

    c1.write(
        f"**Contract Number:** "
        f"{service['contract_number'] or '-'}"
    )

    c2.write(
        f"**Contract ID:** "
        f"{service['contract_id'] or '-'}"
    )

    c3.write(
        f"**Product:** "
        f"{service['product_code'] or '-'}"
    )

    st.divider()

    # --------------------------------------------------------
    # Product
    # --------------------------------------------------------

    st.markdown(
        "### Product"

    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Product",
        service["product_code"] or "-",
    )

    c2.metric(
        "Technology",
        service["technology"] or "-",
    )

    c3.metric(
        "Download",
        f"{service['download_speed_mbps'] or 0} Mbps",
    )

    c4.metric(
        "Upload",
        f"{service['upload_speed_mbps'] or 0} Mbps",
    )

    st.divider()

    # --------------------------------------------------------
    # Installation Address
    # --------------------------------------------------------

    st.markdown(
        "### Installation Address"
    )

    st.info(
        f"""
        **{service['installation_address']}**

        {service['city']},
        {service['state']} -
        {service['postal_code']}
        """
    )

    st.divider()

    # --------------------------------------------------------
    # Audit
    # --------------------------------------------------------

    st.markdown(
        "### Audit Information"
    )

    c1, c2 = st.columns(2)

    c1.write(
        f"**Created:** "
        f"{service['created_at']}"
    )

    c2.write(
        f"**Last Updated:** "
        f"{service['updated_at']}"
    )

    st.divider()

    if st.button(
        "← Back to Service Search",
        use_container_width=True,
    ):

        st.session_state[
            "service_management_mode"
        ] = "Search"

        st.rerun()


# ============================================================
# MAIN SCREEN
# ============================================================

def service_management_screen():

    st.title(
        "📡 Service Management"
    )

    st.caption(
        "Manage broadband services from "
        "activation through termination."
    )

    modes = [
        "Create",
        "Search",
        "Edit",
        "Suspend / Resume",
        "Service 360",
    ]

    current_mode = st.session_state.get(
        "service_management_mode",
        "Create",
    )

    if current_mode not in modes:

        current_mode = "Create"

    selected_mode = st.radio(
        "Service Management",
        modes,
        index=modes.index(
            current_mode
        ),
        horizontal=True,
    )

    st.session_state[
        "service_management_mode"
    ] = selected_mode

    st.divider()

    if selected_mode == "Create":

        create_service_screen()

    elif selected_mode == "Search":

        search_service_screen()

    elif selected_mode == "Edit":

        edit_service_screen()

    elif selected_mode == "Suspend / Resume":

        service_status_screen()

    elif selected_mode == "Service 360":

        service_360_screen()