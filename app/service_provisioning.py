import ipaddress
from datetime import date

import pandas as pd
import streamlit as st

from db import get_connection


# ============================================================
# CONSTANTS
# ============================================================

PROVISIONED_STATUS = "PROVISIONED"

ACTIVE_SERVICE_STATUSES = (
    "ACTIVE",
    "PENDING",
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def fetch_dataframe(query, params=None):

    conn = get_connection()

    try:

        return pd.read_sql_query(
            query,
            conn,
            params=params or (),
        )

    finally:

        conn.close()


# ============================================================
# SERVICE LOOKUP
# ============================================================

def get_provisionable_services():

    query = """
        SELECT
            s.service_id,
            s.service_number,
            s.customer_id,
            c.customer_number,
            c.first_name,
            c.last_name,
            c.email,
            c.phone,
            s.contract_id,
            ct.contract_number,
            s.product_id,
            p.product_code,
            p.product_name,
            p.download_speed_mbps,
            p.upload_speed_mbps,
            s.service_type,
            s.technology,
            s.service_status

        FROM crm.service s

        JOIN crm.customer c
            ON c.customer_id = s.customer_id

        LEFT JOIN crm.contract ct
            ON ct.contract_id = s.contract_id

        LEFT JOIN prd.product p
            ON p.product_id = s.product_id

        WHERE s.service_status IN (
            'ACTIVE',
            'PENDING'
        )

        ORDER BY s.service_id DESC
    """

    return fetch_dataframe(query)


# ============================================================
# SERVICE 360
# ============================================================

def get_service_360(service_id):

    query = """
        SELECT
            s.service_id,
            s.service_number,
            s.service_status,
            s.service_type,
            s.technology,

            c.customer_id,
            c.customer_number,
            c.first_name,
            c.last_name,
            c.email,
            c.phone,

            ct.contract_id,
            ct.contract_number,
            ct.contract_type,
            ct.start_date,
            ct.end_date,
            ct.contract_status,

            p.product_id,
            p.product_code,
            p.product_name,
            p.download_speed_mbps,
            p.upload_speed_mbps

        FROM crm.service s

        JOIN crm.customer c
            ON c.customer_id = s.customer_id

        LEFT JOIN crm.contract ct
            ON ct.contract_id = s.contract_id

        LEFT JOIN prd.product p
            ON p.product_id = s.product_id

        WHERE s.service_id = %s
    """

    df = fetch_dataframe(
        query,
        (service_id,),
    )

    if df.empty:
        return None

    return df.iloc[0].to_dict()


# ============================================================
# IP INFORMATION
# ============================================================

def get_available_ip_pools():

    query = """
        SELECT *
        FROM network.ip_pool
        WHERE status = 'ACTIVE'
        ORDER BY 1
    """

    return fetch_dataframe(query)


def get_available_ips(ip_pool_id):

    query = """
        SELECT
            ip_assignment_id,
            ip_pool_id,
            ip_address,
            status

        FROM network.ip_assignment

        WHERE ip_pool_id = %s
          AND status = 'AVAILABLE'

        ORDER BY ip_address
    """

    return fetch_dataframe(
        query,
        (ip_pool_id,),
    )


def get_existing_service_ip(service_id):

    query = """
        SELECT
            ip_assignment_id,
            ip_pool_id,
            ip_address,
            status,
            assigned_at

        FROM network.ip_assignment

        WHERE service_id = %s
          AND status = 'ASSIGNED'

        ORDER BY assigned_at DESC
    """

    return fetch_dataframe(
        query,
        (service_id,),
    )


# ============================================================
# BANDWIDTH
# ============================================================

def get_existing_bandwidth(service_id):

    query = """
        SELECT
            *

        FROM network.bandwidth_allocation

        WHERE service_id = %s
          AND status = 'ACTIVE'

        ORDER BY 1 DESC
    """

    return fetch_dataframe(
        query,
        (service_id,),
    )


# ============================================================
# OLT
# ============================================================

def get_olts():

    query = """
        SELECT *
        FROM network.olt
        ORDER BY 1
    """

    return fetch_dataframe(query)


def get_available_pon_ports(olt_id):

    query = """
        SELECT
            pp.*

        FROM network.pon_port pp

        WHERE pp.olt_id = %s

          AND (
                pp.status = 'AVAILABLE'
                OR pp.status = 'FREE'
                OR pp.status IS NULL
          )

        ORDER BY 1
    """

    return fetch_dataframe(
        query,
        (olt_id,),
    )


def get_existing_pon(service_id):

    query = """
        SELECT
            nr.*

        FROM network.network_resource nr

        WHERE nr.service_id = %s
          AND nr.resource_type = 'PON'
          AND nr.status = 'ALLOCATED'

        ORDER BY 1 DESC
    """

    return fetch_dataframe(
        query,
        (service_id,),
    )


# ============================================================
# NETWORK RESOURCE
# ============================================================

def get_available_network_resources():

    query = """
        SELECT *
        FROM network.network_resource

        WHERE status = 'AVAILABLE'

        ORDER BY 1
    """

    return fetch_dataframe(query)


def get_existing_resources(service_id):

    query = """
        SELECT *
        FROM network.network_resource

        WHERE service_id = %s

          AND status = 'ALLOCATED'

        ORDER BY 1
    """

    return fetch_dataframe(
        query,
        (service_id,),
    )


# ============================================================
# PROVISIONING VALIDATION
# ============================================================

def validate_provisioning(
    service_id,
    ip_assignment_id,
    bandwidth_mbps,
    pon_port_id,
    resource_id,
):

    errors = []

    # --------------------------------------------------------
    # Service
    # --------------------------------------------------------

    service = get_service_360(
        service_id
    )

    if not service:

        errors.append(
            "Service does not exist."
        )

        return errors

    if service["service_status"] not in (
        "ACTIVE",
        "PENDING",
    ):

        errors.append(
            f"Service status is "
            f"{service['service_status']}."
        )

    # --------------------------------------------------------
    # IP
    # --------------------------------------------------------

    if ip_assignment_id is None:

        errors.append(
            "IP address must be selected."
        )

    # --------------------------------------------------------
    # Bandwidth
    # --------------------------------------------------------

    if bandwidth_mbps is None:

        errors.append(
            "Bandwidth must be specified."
        )

    elif bandwidth_mbps <= 0:

        errors.append(
            "Bandwidth must be greater than zero."
        )

    # --------------------------------------------------------
    # PON
    # --------------------------------------------------------

    if pon_port_id is None:

        errors.append(
            "PON port must be selected."
        )

    # --------------------------------------------------------
    # Resource
    # --------------------------------------------------------

    if resource_id is None:

        errors.append(
            "Network resource must be selected."
        )

    return errors


# ============================================================
# GENERATE NETWORK RESOURCE ID
# ============================================================

def get_next_id(cur, table, column):

    # This is acceptable for the current local application.
    #
    # For a multi-user production environment, replace
    # MAX()+1 with PostgreSQL SEQUENCE/IDENTITY.

    query = f"""
        SELECT
            COALESCE(
                MAX({column}),
                0
            ) + 1
        FROM {table}
    """

    cur.execute(query)

    return cur.fetchone()[0]


# ============================================================
# PROVISION SERVICE
# ============================================================

def provision_service(
    service_id,
    ip_assignment_id,
    bandwidth_mbps,
    pon_port_id,
    network_resource_id,
):
    """
    Complete service provisioning.

    All changes happen in ONE PostgreSQL transaction.

    If any step fails:
        ROLLBACK

    If everything succeeds:
        COMMIT
    """

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # =================================================
            # STEP 1 - LOCK SERVICE
            # =================================================

            cur.execute(
                """
                SELECT
                    service_id,
                    service_number,
                    service_status,
                    technology

                FROM crm.service

                WHERE service_id = %s

                FOR UPDATE
                """,
                (service_id,),
            )

            service = cur.fetchone()

            if not service:

                raise ValueError(
                    "Service does not exist."
                )

            if service[2] not in (
                "ACTIVE",
                "PENDING",
            ):

                raise ValueError(
                    f"Service status is "
                    f"{service[2]}."
                )

            # =================================================
            # STEP 2 - CHECK EXISTING IP
            # =================================================

            cur.execute(
                """
                SELECT
                    ip_assignment_id,
                    ip_address

                FROM network.ip_assignment

                WHERE service_id = %s
                  AND status = 'ASSIGNED'

                FOR UPDATE
                """,
                (service_id,),
            )

            existing_ip = cur.fetchone()

            if existing_ip:

                raise ValueError(
                    f"Service already has IP "
                    f"{existing_ip[1]}."
                )

            # =================================================
            # STEP 3 - LOCK IP
            # =================================================

            cur.execute(
                """
                SELECT
                    ip_assignment_id,
                    ip_address,
                    status

                FROM network.ip_assignment

                WHERE ip_assignment_id = %s

                FOR UPDATE
                """,
                (ip_assignment_id,),
            )

            ip = cur.fetchone()

            if not ip:

                raise ValueError(
                    "Selected IP does not exist."
                )

            if ip[2] != "AVAILABLE":

                raise ValueError(
                    f"IP {ip[1]} is no longer "
                    f"available."
                )

            # =================================================
            # STEP 4 - CHECK EXISTING BANDWIDTH
            # =================================================

            cur.execute(
                """
                SELECT
                    bandwidth_allocation_id,
                    allocated_mbps

                FROM network.bandwidth_allocation

                WHERE service_id = %s
                  AND status = 'ACTIVE'

                FOR UPDATE
                """,
                (service_id,),
            )

            existing_bw = cur.fetchone()

            if existing_bw:

                raise ValueError(
                    "Service already has active "
                    "bandwidth allocation."
                )

            # =================================================
            # STEP 5 - CHECK EXISTING PON
            # =================================================

            cur.execute(
                """
                SELECT
                    network_resource_id

                FROM network.network_resource

                WHERE service_id = %s
                  AND resource_type = 'PON'
                  AND status = 'ALLOCATED'

                FOR UPDATE
                """,
                (service_id,),
            )

            existing_pon = cur.fetchone()

            if existing_pon:

                raise ValueError(
                    "Service already has an "
                    "allocated PON resource."
                )

            # =================================================
            # STEP 6 - LOCK PON PORT
            # =================================================

            cur.execute(
                """
                SELECT
                    pon_port_id,
                    status

                FROM network.pon_port

                WHERE pon_port_id = %s

                FOR UPDATE
                """,
                (pon_port_id,),
            )

            pon = cur.fetchone()

            if not pon:

                raise ValueError(
                    "Selected PON port does not exist."
                )

            if pon[1] not in (
                "AVAILABLE",
                "FREE",
                None,
            ):

                raise ValueError(
                    "Selected PON port is not available."
                )

            # =================================================
            # STEP 7 - LOCK NETWORK RESOURCE
            # =================================================

            cur.execute(
                """
                SELECT
                    network_resource_id,
                    resource_type,
                    status

                FROM network.network_resource

                WHERE network_resource_id = %s

                FOR UPDATE
                """,
                (network_resource_id,),
            )

            resource = cur.fetchone()

            if not resource:

                raise ValueError(
                    "Network resource does not exist."
                )

            if resource[2] != "AVAILABLE":

                raise ValueError(
                    "Selected network resource "
                    "is no longer available."
                )

            # =================================================
            # STEP 8 - ASSIGN IP
            # =================================================

            cur.execute(
                """
                UPDATE network.ip_assignment

                SET
                    service_id = %s,
                    status = 'ASSIGNED',
                    assigned_at = CURRENT_TIMESTAMP,
                    released_at = NULL

                WHERE ip_assignment_id = %s
                """,
                (
                    service_id,
                    ip_assignment_id,
                ),
            )

            # =================================================
            # STEP 9 - CREATE BANDWIDTH ALLOCATION
            # =================================================

            bandwidth_id = get_next_id(
                cur,
                "network.bandwidth_allocation",
                "bandwidth_allocation_id",
            )

            cur.execute(
                """
                INSERT INTO
                    network.bandwidth_allocation
                (
                    bandwidth_allocation_id,
                    service_id,
                    allocated_mbps,
                    effective_from,
                    effective_to,
                    status
                )

                VALUES
                (
                    %s,
                    %s,
                    %s,
                    CURRENT_DATE,
                    NULL,
                    'ACTIVE'
                )
                """,
                (
                    bandwidth_id,
                    service_id,
                    bandwidth_mbps,
                ),
            )

            # =================================================
            # STEP 10 - MARK PON PORT
            # =================================================

            cur.execute(
                """
                UPDATE network.pon_port

                SET
                    status = 'ALLOCATED'

                WHERE pon_port_id = %s
                """,
                (pon_port_id,),
            )

            # =================================================
            # STEP 11 - ALLOCATE NETWORK RESOURCE
            # =================================================

            cur.execute(
                """
                UPDATE network.network_resource

                SET
                    service_id = %s,
                    status = 'ALLOCATED'

                WHERE network_resource_id = %s
                """,
                (
                    service_id,
                    network_resource_id,
                ),
            )

            # =================================================
            # STEP 12 - CREATE PON RESOURCE RECORD
            # =================================================

            pon_resource_id = get_next_id(
                cur,
                "network.network_resource",
                "network_resource_id",
            )

            # NOTE:
            # If your network_resource table already uses
            # network_resource_id for the selected PON,
            # remove this INSERT and use the existing record.

            cur.execute(
                """
                INSERT INTO
                    network.network_resource
                (
                    network_resource_id,
                    service_id,
                    resource_type,
                    resource_id,
                    status
                )

                VALUES
                (
                    %s,
                    %s,
                    'PON',
                    %s,
                    'ALLOCATED'
                )
                """,
                (
                    pon_resource_id,
                    service_id,
                    pon_port_id,
                ),
            )

            # =================================================
            # STEP 13 - UPDATE SERVICE
            # =================================================

            cur.execute(
                """
                UPDATE crm.service

                SET
                    service_status = 'PROVISIONED',
                    updated_at = CURRENT_TIMESTAMP

                WHERE service_id = %s
                """,
                (service_id,),
            )

        # =====================================================
        # COMMIT EVERYTHING
        # =====================================================

        conn.commit()

        return {
            "service_id": service_id,
            "service_number": service[1],
            "ip_address": ip[1],
            "bandwidth_id": bandwidth_id,
            "bandwidth_mbps": bandwidth_mbps,
            "pon_port_id": pon_port_id,
            "network_resource_id": network_resource_id,
            "status": PROVISIONED_STATUS,
        }

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# PROVISIONING AUDIT
# ============================================================

def get_provisioning_status(service_id):

    result = {
        "service": False,
        "ip": False,
        "bandwidth": False,
        "pon": False,
        "resource": False,
    }

    # --------------------------------------------------------
    # Service
    # --------------------------------------------------------

    service = get_service_360(
        service_id
    )

    if service:

        result["service"] = service[
            "service_status"
        ] in (
            "ACTIVE",
            "PROVISIONED",
        )

    # --------------------------------------------------------
    # IP
    # --------------------------------------------------------

    ip = get_existing_service_ip(
        service_id
    )

    result["ip"] = not ip.empty

    # --------------------------------------------------------
    # Bandwidth
    # --------------------------------------------------------

    bandwidth = get_existing_bandwidth(
        service_id
    )

    result["bandwidth"] = not bandwidth.empty

    # --------------------------------------------------------
    # PON
    # --------------------------------------------------------

    pon = get_existing_pon(
        service_id
    )

    result["pon"] = not pon.empty

    # --------------------------------------------------------
    # Resource
    # --------------------------------------------------------

    resources = get_existing_resources(
        service_id
    )

    result["resource"] = not resources.empty

    return result


# ============================================================
# UI HELPERS
# ============================================================

def status_icon(value):

    return "✅" if value else "❌"


# ============================================================
# SERVICE SUMMARY
# ============================================================

def display_service_summary(service):

    st.markdown(
        "### Service Details"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Service",
        service["service_number"],
    )

    c2.metric(
        "Customer",
        service["customer_number"],
    )

    c3.metric(
        "Technology",
        service["technology"],
    )

    c4.metric(
        "Status",
        service["service_status"],
    )

    st.write(
        f"**Customer:** "
        f"{service['first_name']} "
        f"{service['last_name']}"
    )

    st.write(
        f"**Product:** "
        f"{service['product_code']} - "
        f"{service['product_name']}"
    )

    st.write(
        f"**Contract:** "
        f"{service['contract_number']}"
    )

    c1, c2 = st.columns(2)

    c1.metric(
        "Download",
        f"{service['download_speed_mbps']} Mbps",
    )

    c2.metric(
        "Upload",
        f"{service['upload_speed_mbps']} Mbps",
    )


# ============================================================
# PROVISIONING STATUS
# ============================================================

def display_provisioning_status(
    service_id
):

    status = get_provisioning_status(
        service_id
    )

    st.markdown(
        "### Provisioning Status"
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Service",
        status_icon(
            status["service"]
        ),
    )

    c2.metric(
        "IP",
        status_icon(
            status["ip"]
        ),
    )

    c3.metric(
        "Bandwidth",
        status_icon(
            status["bandwidth"]
        ),
    )

    c4.metric(
        "OLT / PON",
        status_icon(
            status["pon"]
        ),
    )

    c5.metric(
        "Resource",
        status_icon(
            status["resource"]
        ),
    )

    return status


# ============================================================
# MAIN PROVISIONING SCREEN
# ============================================================

def service_provisioning_screen():

    st.title(
        "🚀 Service Provisioning"
    )

    st.caption(
        "End-to-end network provisioning for ISP services"
    )

    # ========================================================
    # LOAD SERVICES
    # ========================================================

    try:

        services = get_provisionable_services()

    except Exception as e:

        st.error(
            f"Unable to load services: {e}"
        )

        return

    if services.empty:

        st.warning(
            "No ACTIVE or PENDING services "
            "are available for provisioning."
        )

        return

    # ========================================================
    # SERVICE SELECTOR
    # ========================================================

    service_options = {}

    for row in services.itertuples():

        label = (
            f"{row.service_number} | "
            f"{row.customer_number} | "
            f"{row.first_name} "
            f"{row.last_name} | "
            f"{row.product_code} | "
            f"{row.technology}"
        )

        service_options[label] = row.service_id

    selected_service = st.selectbox(
        "Select Service",
        list(service_options.keys()),
    )

    service_id = service_options[
        selected_service
    ]

    # ========================================================
    # SERVICE DETAILS
    # ========================================================

    service = get_service_360(
        service_id
    )

    if not service:

        st.error(
            "Unable to retrieve service."
        )

        return

    display_service_summary(
        service
    )

    st.divider()

    # ========================================================
    # CURRENT PROVISIONING STATUS
    # ========================================================

    current_status = (
        display_provisioning_status(
            service_id
        )
    )

    if all(
        current_status.values()
    ):

        st.success(
            "This service is already fully provisioned."
        )

        return

    st.divider()

    # ========================================================
    # PROVISIONING CONFIGURATION
    # ========================================================

    st.markdown(
        "## 1. IP Assignment"
    )

    existing_ip = get_existing_service_ip(
        service_id
    )

    if not existing_ip.empty:

        st.success(
            f"Existing IP: "
            f"{existing_ip.iloc[0]['ip_address']}"
        )

        selected_ip_assignment_id = (
            int(
                existing_ip.iloc[0][
                    "ip_assignment_id"
                ]
            )
        )

    else:

        pools = get_available_ip_pools()

        if pools.empty:

            st.error(
                "No active IP pools available."
            )

            return

        pool_options = {}

        for index, row in pools.iterrows():

            values = row.to_dict()

            pool_id = values.get(
                "ip_pool_id",
                index,
            )

            cidr = values.get(
                "cidr",
                values.get(
                    "network_cidr",
                    "",
                ),
            )

            pool_name = values.get(
                "pool_name",
                values.get(
                    "pool_code",
                    f"POOL-{pool_id}",
                ),
            )

            pool_options[
                f"{pool_name} | {cidr}"
            ] = pool_id

        selected_pool = st.selectbox(
            "IP Pool",
            list(pool_options.keys()),
            key="provisioning_ip_pool",
        )

        ip_pool_id = pool_options[
            selected_pool
        ]

        ips = get_available_ips(
            ip_pool_id
        )

        if ips.empty:

            st.warning(
                "No available IP addresses "
                "in the selected pool."
            )

            selected_ip_assignment_id = None

        else:

            ip_options = {}

            for row in ips.itertuples():

                ip_options[
                    str(row.ip_address)
                ] = row.ip_assignment_id

            selected_ip = st.selectbox(
                "Available IP",
                list(ip_options.keys()),
                key="provisioning_ip",
            )

            selected_ip_assignment_id = (
                ip_options[selected_ip]
            )

    # ========================================================
    # BANDWIDTH
    # ========================================================

    st.markdown(
        "## 2. Bandwidth Allocation"
    )

    existing_bw = get_existing_bandwidth(
        service_id
    )

    if not existing_bw.empty:

        existing_mbps = existing_bw.iloc[
            0
        ]["allocated_mbps"]

        st.success(
            f"Existing bandwidth: "
            f"{existing_mbps} Mbps"
        )

        bandwidth_mbps = float(
            existing_mbps
        )

    else:

        default_bw = service.get(
            "download_speed_mbps"
        )

        if pd.isna(default_bw):

            default_bw = 100

        bandwidth_mbps = st.number_input(
            "Bandwidth (Mbps)",
            min_value=1.0,
            max_value=100000.0,
            value=float(default_bw),
            step=10.0,
            key="provisioning_bandwidth",
        )

        st.caption(
            "Default is based on the product "
            "download speed."
        )

    # ========================================================
    # OLT / PON
    # ========================================================

    st.markdown(
        "## 3. OLT / PON Allocation"
    )

    existing_pon = get_existing_pon(
        service_id
    )

    if not existing_pon.empty:

        pon_resource = existing_pon.iloc[0]

        st.success(
            "PON resource already allocated."
        )

        selected_pon_port_id = int(
            pon_resource.get(
                "resource_id"
            )
        )

    else:

        olts = get_olts()

        if olts.empty:

            st.error(
                "No OLTs are available."
            )

            return

        olt_options = {}

        for index, row in olts.iterrows():

            values = row.to_dict()

            olt_id = values.get(
                "olt_id",
                index,
            )

            olt_name = values.get(
                "olt_name",
                values.get(
                    "name",
                    f"OLT-{olt_id}",
                ),
            )

            olt_options[
                f"{olt_id} | {olt_name}"
            ] = olt_id

        selected_olt = st.selectbox(
            "OLT",
            list(olt_options.keys()),
            key="provisioning_olt",
        )

        olt_id = olt_options[
            selected_olt
        ]

        ports = get_available_pon_ports(
            olt_id
        )

        if ports.empty:

            st.warning(
                "No available PON ports "
                "for the selected OLT."
            )

            selected_pon_port_id = None

        else:

            pon_options = {}

            for index, row in ports.iterrows():

                values = row.to_dict()

                pon_id = values.get(
                    "pon_port_id",
                    index,
                )

                port_number = values.get(
                    "port_number",
                    values.get(
                        "pon_port_number",
                        pon_id,
                    ),
                )

                pon_options[
                    f"PON-{port_number}"
                ] = pon_id

            selected_pon = st.selectbox(
                "Available PON Port",
                list(pon_options.keys()),
                key="provisioning_pon",
            )

            selected_pon_port_id = (
                pon_options[selected_pon]
            )

    # ========================================================
    # NETWORK RESOURCE
    # ========================================================

    st.markdown(
        "## 4. Network Resource"
    )

    existing_resources = (
        get_existing_resources(
            service_id
        )
    )

    if not existing_resources.empty:

        st.success(
            "Network resource already allocated."
        )

        selected_resource_id = int(
            existing_resources.iloc[0][
                "network_resource_id"
            ]
        )

    else:

        resources = (
            get_available_network_resources()
        )

        if resources.empty:

            st.warning(
                "No available network resources."
            )

            selected_resource_id = None

        else:

            resource_options = {}

            for index, row in resources.iterrows():

                values = row.to_dict()

                resource_id = values.get(
                    "network_resource_id",
                    index,
                )

                resource_type = values.get(
                    "resource_type",
                    "NETWORK",
                )

                resource_code = values.get(
                    "resource_code",
                    values.get(
                        "resource_name",
                        resource_id,
                    ),
                )

                resource_options[
                    f"{resource_type} | "
                    f"{resource_code}"
                ] = resource_id

            selected_resource = st.selectbox(
                "Network Resource",
                list(resource_options.keys()),
                key="provisioning_resource",
            )

            selected_resource_id = (
                resource_options[
                    selected_resource
                ]
            )

    # ========================================================
    # PROVISIONING SUMMARY
    # ========================================================

    st.divider()

    st.markdown(
        "## 5. Provisioning Summary"
    )

    summary_col1, summary_col2 = (
        st.columns(2)
    )

    with summary_col1:

        st.write(
            f"**Service:** "
            f"{service['service_number']}"
        )

        st.write(
            f"**Customer:** "
            f"{service['customer_number']} - "
            f"{service['first_name']} "
            f"{service['last_name']}"
        )

        st.write(
            f"**Technology:** "
            f"{service['technology']}"
        )

        st.write(
            f"**Product:** "
            f"{service['product_code']}"
        )

    with summary_col2:

        st.write(
            f"**Bandwidth:** "
            f"{bandwidth_mbps:,.0f} Mbps"
        )

        if selected_ip_assignment_id:

            ip_df = fetch_dataframe(
                """
                SELECT ip_address
                FROM network.ip_assignment
                WHERE ip_assignment_id = %s
                """,
                (selected_ip_assignment_id,),
            )

            if not ip_df.empty:

                st.write(
                    f"**IP Address:** "
                    f"{ip_df.iloc[0]['ip_address']}"
                )

        st.write(
            f"**PON Port:** "
            f"{selected_pon_port_id}"
        )

        st.write(
            f"**Network Resource:** "
            f"{selected_resource_id}"
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    errors = validate_provisioning(
        service_id,
        selected_ip_assignment_id,
        bandwidth_mbps,
        selected_pon_port_id,
        selected_resource_id,
    )

    if errors:

        st.warning(
            "Provisioning cannot be completed:"
        )

        for error in errors:

            st.write(
                f"❌ {error}"
            )

    else:

        st.success(
            "All provisioning prerequisites "
            "are satisfied."
        )

    # ========================================================
    # PROVISION BUTTON
    # ========================================================

    st.divider()

    provision = st.button(
        "🚀 Provision Service",
        type="primary",
        use_container_width=True,
        disabled=len(errors) > 0,
    )

    if provision:

        with st.spinner(
            "Provisioning service..."
        ):

            try:

                result = provision_service(
                    service_id=service_id,
                    ip_assignment_id=(
                        selected_ip_assignment_id
                    ),
                    bandwidth_mbps=(
                        bandwidth_mbps
                    ),
                    pon_port_id=(
                        selected_pon_port_id
                    ),
                    network_resource_id=(
                        selected_resource_id
                    ),
                )

                st.success(
                    "🎉 Service provisioned successfully!"
                )

                # ------------------------------------------------
                # Result
                # ------------------------------------------------

                st.markdown(
                    "### Provisioning Result"
                )

                c1, c2, c3 = st.columns(3)

                c1.metric(
                    "Service",
                    result[
                        "service_number"
                    ],
                )

                c2.metric(
                    "IP Address",
                    result[
                        "ip_address"
                    ],
                )

                c3.metric(
                    "Status",
                    result["status"],
                )

                st.info(
                    f"""
                    **Provisioning completed**

                    Service: `{result['service_number']}`

                    IP: `{result['ip_address']}`

                    Bandwidth:
                    `{result['bandwidth_mbps']} Mbps`

                    PON Port:
                    `{result['pon_port_id']}`

                    Network Resource:
                    `{result['network_resource_id']}`
                    """
                )

                st.balloons()

                # Refresh data

                st.rerun()

            except Exception as e:

                st.error(
                    "❌ Service provisioning failed."
                )

                st.exception(e)