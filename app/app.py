import sys
from pathlib import Path
from decimal import Decimal

import streamlit as st

# Allow imports from app/
APP_DIR = Path(__file__).resolve().parent

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from db import get_connection
from customer_management import customer_management_screen
from contract_management import contract_management_screen
from service_management import service_management_screen
from network_management import network_management_screen
from service_provisioning import service_provisioning_screen
from billing import billing_dashboard
from dashboard import dashboard

from services.customer_service import (
    customer_exists,
    create_customer,
)
from services.contract_service import (
    get_products,
    create_contract,
)
from utils.validation import (
    validate_customer,
    validate_contract,
)


# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------

st.set_page_config(
    page_title="TelecomNexus Customer Management",
    page_icon="🌐",
    layout="wide",
)


# ---------------------------------------------------------
# Styling
# ---------------------------------------------------------

st.markdown(
    """
    <style>

    .main-title {
        font-size: 32px;
        font-weight: 700;
        margin-bottom: 0px;
    }

    .sub-title {
        color: #6b7280;
        font-size: 15px;
        margin-bottom: 25px;
    }

    .section-header {
        font-size: 21px;
        font-weight: 650;
        margin-top: 15px;
        margin-bottom: 10px;
    }

    .success-box {
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #22c55e;
        background-color: #f0fdf4;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.markdown(
    '<div class="main-title">🌐 TelecomNexus</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="sub-title">Customer & Contract Management</div>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------

with st.sidebar:
    st.header("Application")

    page = st.radio(
        "Navigate",
        [
            "Dashboard",
            "Customer Management",
            "Contract Management",
            "Service Management",
            "Service Provisioning",
            "Network Management",
            "Billing",
            "Create Customer & Contract",
            "Database Health",
        ],
    )


if page == "Dashboard":
    dashboard()

    st.stop()


if page == "Customer Management":
    customer_management_screen()

    st.stop()

if page == "Contract Management":
    contract_management_screen()

    st.stop()

if page == "Service Management":
    service_management_screen()

    st.stop()

if page == "Service Provisioning":
    service_provisioning_screen()

    st.stop()

if page == "Network Management":
    network_management_screen()

    st.stop()

if page == "Billing":
    billing_dashboard()

    st.stop()

    st.divider()

    st.caption("TelecomNexus")
    st.caption("ISP Customer Management")
    st.caption("Version 1.0.0")


# =========================================================
# DATABASE HEALTH
# =========================================================

if page == "Database Health":
    st.header("Database Health")

    try:
        conn = get_connection()

        with conn.cursor() as cur:
            cur.execute("SELECT CURRENT_DATABASE(), CURRENT_USER")

            database, user = cur.fetchone()

            cur.execute("SELECT version()")

            version = cur.fetchone()[0]

        conn.close()

        col1, col2 = st.columns(2)

        col1.metric(
            "Database",
            database,
        )

        col2.metric(
            "User",
            user,
        )

        st.success("PostgreSQL connection is healthy.")

        with st.expander("PostgreSQL Version"):
            st.code(version)

    except Exception as e:
        st.error(f"Database connection failed: {e}")


# =========================================================
# CREATE CUSTOMER + CONTRACT
# =========================================================

if page == "Create Customer & Contract":
    st.header("Create Customer & Contract")

    st.info(
        "Customer, contract, contract detail and rate "
        "schedule are created together in a single database transaction."
    )

    # -----------------------------------------------------
    # CUSTOMER
    # -----------------------------------------------------

    st.markdown(
        '<div class="section-header">1. Customer Information</div>',
        unsafe_allow_html=True,
    )

    with st.container():
        col1, col2, col3 = st.columns(3)

        with col1:
            first_name = st.text_input(
                "First Name *",
                placeholder="Ravi",
            )

        with col2:
            last_name = st.text_input(
                "Last Name *",
                placeholder="Kishan",
            )

        with col3:
            customer_type = st.selectbox(
                "Customer Type *",
                [
                    "RESIDENTIAL",
                    "BUSINESS",
                ],
            )

        col1, col2 = st.columns(2)

        with col1:
            email = st.text_input(
                "Email *",
                placeholder="customer@example.com",
            )

        with col2:
            phone = st.text_input(
                "Phone *",
                placeholder="9876543210",
            )

        address_line1 = st.text_input(
            "Address *",
            placeholder="123 Main Street",
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            city = st.text_input(
                "City *",
                placeholder="Hyderabad",
            )

        with col2:
            state = st.selectbox(
                "State *",
                [
                    "Telangana",
                    "Andhra Pradesh",
                    "Karnataka",
                    "Maharashtra",
                    "Tamil Nadu",
                    "Kerala",
                    "Delhi",
                    "Punjab",
                    "Gujarat",
                    "West Bengal",
                    "Rajasthan",
                    "Uttar Pradesh",
                ],
            )

        with col3:
            postal_code = st.text_input(
                "Postal Code *",
                placeholder="500001",
            )

    st.divider()

    # -----------------------------------------------------
    # CONTRACT
    # -----------------------------------------------------

    st.markdown(
        '<div class="section-header">2. Contract Information</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        contract_type = st.selectbox(
            "Contract Type *",
            [
                "MONTHLY",
                "12_MONTH",
                "24_MONTH",
            ],
        )

    with col2:
        contract_status = st.selectbox(
            "Contract Status *",
            [
                "ACTIVE",
                "PENDING",
                "DE-ACTIVE",
            ],
        )

    with col3:
        auto_renew = st.checkbox(
            "Auto Renew",
            value=True,
        )

    start_date = st.date_input("Contract Start Date *")

    st.divider()

    # -----------------------------------------------------
    # CONTRACT DETAIL
    # -----------------------------------------------------

    st.markdown(
        '<div class="section-header">3. Contract Detail</div>',
        unsafe_allow_html=True,
    )

    try:
        products = get_products()

    except Exception as e:
        st.error(f"Unable to load products: {e}")

        st.stop()

    if not products:
        st.warning("No active products/rate schedules found.")

        st.stop()

    product_options = {}

    for row in products:
        (
            product_id,
            product_code,
            product_name,
            product_category,
            technology,
            download_speed,
            upload_speed,
            rate_schedule_id,
            monthly_charge,
            activation_charge,
            tax_percentage,
            currency,
        ) = row

        label = (
            f"{product_code} - "
            f"{product_name} | "
            f"{download_speed} Mbps ↓ / "
            f"{upload_speed} Mbps ↑ | "
            f"{currency} {monthly_charge}/month"
        )

        product_options[label] = {
            "product_id": product_id,
            "product_code": product_code,
            "product_name": product_name,
            "product_category": product_category,
            "technology": technology,
            "download_speed": download_speed,
            "upload_speed": upload_speed,
            "rate_schedule_id": rate_schedule_id,
            "monthly_charge": Decimal(str(monthly_charge)),
            "activation_charge": Decimal(str(activation_charge)),
            "tax_percentage": Decimal(str(tax_percentage)),
            "currency": currency,
        }

    selected_product_label = st.selectbox(
        "Internet Plan / Product *",
        list(product_options.keys()),
    )

    selected_product = product_options[selected_product_label]

    col1, col2, col3 = st.columns(3)

    with col1:
        quantity = st.number_input(
            "Quantity",
            min_value=1,
            max_value=100,
            value=1,
            step=1,
        )

    with col2:
        monthly_price = st.number_input(
            "Agreed Monthly Price",
            min_value=0.0,
            value=float(selected_product["monthly_charge"]),
            step=10.0,
        )

    with col3:
        discount_amount = st.number_input(
            "Discount Amount",
            min_value=0.0,
            value=0.0,
            step=10.0,
        )

    tax_percent = float(selected_product["tax_percentage"])

    # -----------------------------------------------------
    # PRICE CALCULATION
    # -----------------------------------------------------

    base_amount = Decimal(str(monthly_price)) * Decimal(str(quantity))

    discount = Decimal(str(discount_amount))

    taxable_amount = max(
        Decimal("0"),
        base_amount - discount,
    )

    tax_amount = taxable_amount * Decimal(str(tax_percent)) / Decimal("100")

    total_monthly = taxable_amount + tax_amount

    st.markdown("### Monthly Billing Preview")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Base Monthly",
        f"₹{base_amount:,.2f}",
    )

    col2.metric(
        "Discount",
        f"₹{discount:,.2f}",
    )

    col3.metric(
        f"Tax ({tax_percent:.2f}%)",
        f"₹{tax_amount:,.2f}",
    )

    col4.metric(
        "Total Monthly",
        f"₹{total_monthly:,.2f}",
    )

    st.divider()

    # -----------------------------------------------------
    # SELECTED PRODUCT INFORMATION
    # -----------------------------------------------------

    with st.expander("Selected Product Information"):
        col1, col2, col3, col4 = st.columns(4)

        col1.write(f"**Product:** {selected_product['product_name']}")

        col2.write(f"**Technology:** {selected_product['technology']}")

        col3.write(f"**Download:** {selected_product['download_speed']} Mbps")

        col4.write(f"**Upload:** {selected_product['upload_speed']} Mbps")

        st.write(f"**Activation Fee:** ₹{selected_product['activation_charge']:,.2f}")

        st.write(f"**Tax:** {selected_product['tax_percentage']}%")

    st.divider()

    # -----------------------------------------------------
    # SUBMIT
    # -----------------------------------------------------

    create_button = st.button(
        "🚀 Create Customer & Contract",
        type="primary",
        use_container_width=True,
    )

    if create_button:
        # ---------------------------------------------
        # Validate customer
        # ---------------------------------------------

        customer_errors = validate_customer(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            city=city,
            state=state,
            postal_code=postal_code,
        )

        # ---------------------------------------------
        # Validate contract
        # ---------------------------------------------

        contract_errors = validate_contract(
            contract_type=contract_type,
            start_date=start_date,
            product_id=selected_product["product_id"],
            quantity=quantity,
            discount=discount,
        )

        all_errors = customer_errors + contract_errors

        # ---------------------------------------------
        # Price validation
        # ---------------------------------------------

        if discount > base_amount:
            all_errors.append(
                "Discount cannot be greater than the base monthly amount."
            )

        # ---------------------------------------------
        # Show validation errors
        # ---------------------------------------------

        if all_errors:
            for error in all_errors:
                st.error(error)

            st.stop()

        # ---------------------------------------------
        # Duplicate customer check
        # ---------------------------------------------

        existing_customer = customer_exists(
            email,
            phone,
        )

        if existing_customer:
            (
                existing_id,
                existing_number,
                existing_email,
                existing_phone,
            ) = existing_customer

            st.error("Customer already exists.")

            st.warning(
                f"Customer ID: {existing_id} | Customer Number: {existing_number}"
            )

            st.stop()

        # ---------------------------------------------
        # Database transaction
        # ---------------------------------------------

        conn = None

        try:
            conn = get_connection()

            # psycopg2 transaction starts automatically
            # when the first SQL statement is executed.

            with conn.cursor() as cur:
                # -----------------------------
                # Customer
                # -----------------------------

                customer_id, customer_number = create_customer(
                    cur=cur,
                    first_name=first_name.strip(),
                    last_name=last_name.strip(),
                    email=email.strip(),
                    phone=phone.strip(),
                    address_line1=address_line1.strip(),
                    city=city.strip(),
                    state=state,
                    postal_code=postal_code.strip(),
                    customer_type=customer_type,
                    country="India",
                )

                # -----------------------------
                # Contract
                # -----------------------------

                contract_result = create_contract(
                    cur=cur,
                    customer_id=customer_id,
                    contract_type=contract_type,
                    start_date=start_date,
                    contract_status=contract_status,
                    auto_renew=auto_renew,
                    product_id=selected_product["product_id"],
                    rate_schedule_id=selected_product["rate_schedule_id"],
                    quantity=quantity,
                    agreed_monthly_price=monthly_price,
                    discount_amount=discount_amount,
                    tax_percent=tax_percent,
                )

            # ---------------------------------
            # Commit only after EVERYTHING
            # succeeded.
            # ---------------------------------

            conn.commit()

            st.success("Customer and contract created successfully.")

            # ---------------------------------
            # Result
            # ---------------------------------

            st.markdown("### Created Records")

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Customer ID",
                customer_id,
            )

            col2.metric(
                "Contract ID",
                contract_result["contract_id"],
            )

            col3.metric(
                "Contract Detail ID",
                contract_result["contract_detail_id"],
            )

            st.info(
                f"""
                **Customer Number:** {customer_number}

                **Contract Number:** {contract_result["contract_number"]}

                **Contract End Date:** {
                    contract_result["end_date"]
                    if contract_result["end_date"]
                    else "Open-ended"
                }

                **Product:** {selected_product["product_name"]}

                **Monthly Amount:** ₹{total_monthly:,.2f}
                """
            )

            st.balloons()

        except Exception as e:
            if conn:
                conn.rollback()

            st.error("Transaction failed. No customer/contract records were committed.")

            st.exception(e)

        finally:
            if conn:
                conn.close()
