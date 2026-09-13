from datetime import date

import pandas as pd
import streamlit as st

from db import get_connection


# ============================================================
# CONSTANTS
# ============================================================

IP_STATUSES = [
    "ASSIGNED",
    "AVAILABLE",
    "RESERVED",
    "RELEASED",
]

RESOURCE_STATUSES = [
    "AVAILABLE",
    "ALLOCATED",
    "RESERVED",
    "MAINTENANCE",
    "DECOMMISSIONED",
]

BANDWIDTH_STATUSES = [
    "ACTIVE",
    "SUSPENDED",
    "RELEASED",
]


# ============================================================
# DATABASE HELPERS
# ============================================================

def execute_query(query, params=None, fetch=True):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                query,
                params or (),
            )

            if fetch:

                rows = cur.fetchall()

                columns = [
                    desc[0]
                    for desc in cur.description
                ]

                return pd.DataFrame(
                    rows,
                    columns=columns,
                )

            conn.commit()

            return None

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# SCHEMA CHECK
# ============================================================

def get_table_columns(schema, table):

    query = """
        SELECT
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position
    """

    return execute_query(
        query,
        (schema, table),
    )


def network_schema_check():

    tables = [
        "ip_assignment",
        "ip_pool",
        "bandwidth_allocation",
        "network_resource",
        "pon_port",
        "olt",
        "pop",
        "network_site",
    ]

    results = []

    for table in tables:

        try:

            df = get_table_columns(
                "network",
                table,
            )

            results.append(
                {
                    "table": f"network.{table}",
                    "exists": not df.empty,
                    "columns": (
                        ", ".join(
                            df["column_name"].tolist()
                        )
                        if not df.empty
                        else ""
                    ),
                }
            )

        except Exception as e:

            results.append(
                {
                    "table": f"network.{table}",
                    "exists": False,
                    "columns": str(e),
                }
            )

    return pd.DataFrame(results)


# ============================================================
# SERVICES
# ============================================================

def get_active_services():

    query = """
        SELECT
            s.service_id,
            s.service_number,
            s.customer_id,
            c.customer_number,
            c.first_name,
            c.last_name,
            s.contract_id,
            s.product_id,
            s.service_type,
            s.technology,
            s.service_status

        FROM crm.service s

        JOIN crm.customer c
            ON c.customer_id =
               s.customer_id

        WHERE s.service_status
              IN ('ACTIVE', 'PENDING', 'SUSPENDED')

        ORDER BY s.service_id DESC
    """

    return execute_query(query)


# ============================================================
# CUSTOMER / SERVICE LOOKUP
# ============================================================

def get_service_details(service_id):

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
            s.service_type,
            s.technology,
            s.activation_date,
            s.service_status,
            s.installation_address,
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

        WHERE s.service_id = %s
    """

    df = execute_query(
        query,
        (service_id,),
    )

    if df.empty:

        return None

    return df.iloc[0].to_dict()


# ============================================================
# IP POOL
# ============================================================

def get_ip_pools():

    query = """
        SELECT *
        FROM network.ip_pool
        ORDER BY 1
    """

    return execute_query(query)


# ============================================================
# IP ASSIGNMENTS
# ============================================================

def get_ip_assignments():

    query = """
        SELECT
            ia.*,
            s.service_number

        FROM network.ip_assignment ia

        LEFT JOIN crm.service s
            ON s.service_id =
               ia.service_id

        ORDER BY ia.ip_assignment_id DESC

        LIMIT 500
    """

    return execute_query(query)


def get_available_ips(ip_pool_id):

    """
    Retrieves currently available IP addresses.

    This assumes ip_assignment contains ip_address
    and ip_pool contains cidr/network information.

    If your design creates IPs in a separate inventory
    table, replace this query with that inventory table.
    """

    query = """
        SELECT
            ia.ip_assignment_id,
            ia.ip_pool_id,
            ia.ip_address,
            ia.status

        FROM network.ip_assignment ia

        WHERE ia.ip_pool_id = %s

          AND ia.status = 'AVAILABLE'

        ORDER BY ia.ip_address
    """

    return execute_query(
        query,
        (ip_pool_id,),
    )


# ============================================================
# ASSIGN IP
# ============================================================

def assign_ip(
    service_id,
    ip_assignment_id,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # ------------------------------------------------
            # Lock IP
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    ip_assignment_id,
                    ip_pool_id,
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
                    "IP assignment record not found."
                )

            if ip[3] != "AVAILABLE":

                raise ValueError(
                    "Selected IP is no longer available."
                )

            # ------------------------------------------------
            # Validate service
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    service_id,
                    service_status
                FROM crm.service
                WHERE service_id = %s
                """,
                (service_id,),
            )

            service = cur.fetchone()

            if not service:

                raise ValueError(
                    "Service does not exist."
                )

            if service[1] not in (
                "ACTIVE",
                "PENDING",
            ):

                raise ValueError(
                    "IP cannot be assigned to "
                    "an inactive service."
                )

            # ------------------------------------------------
            # Prevent duplicate IP assignment
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    ip_assignment_id
                FROM network.ip_assignment
                WHERE service_id = %s
                  AND status = 'ASSIGNED'
                LIMIT 1
                """,
                (service_id,),
            )

            existing = cur.fetchone()

            if existing:

                raise ValueError(
                    "This service already has "
                    "an assigned IP."
                )

            # ------------------------------------------------
            # Update IP
            # ------------------------------------------------

            cur.execute(
                """
                UPDATE network.ip_assignment
                SET
                    service_id = %s,
                    status = 'ASSIGNED',
                    assigned_at =
                        CURRENT_TIMESTAMP,
                    released_at = NULL
                WHERE ip_assignment_id = %s
                """,
                (
                    service_id,
                    ip_assignment_id,
                ),
            )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# RELEASE IP
# ============================================================

def release_ip(ip_assignment_id):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    status
                FROM network.ip_assignment
                WHERE ip_assignment_id = %s
                FOR UPDATE
                """,
                (ip_assignment_id,),
            )

            row = cur.fetchone()

            if not row:

                raise ValueError(
                    "IP assignment not found."
                )

            if row[0] != "ASSIGNED":

                raise ValueError(
                    "Only an assigned IP "
                    "can be released."
                )

            cur.execute(
                """
                UPDATE network.ip_assignment
                SET
                    service_id = NULL,
                    status = 'AVAILABLE',
                    released_at =
                        CURRENT_TIMESTAMP
                WHERE ip_assignment_id = %s
                """,
                (ip_assignment_id,),
            )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# BANDWIDTH
# ============================================================

def get_bandwidth_allocations():

    query = """
        SELECT
            ba.*,
            s.service_number

        FROM network.bandwidth_allocation ba

        LEFT JOIN crm.service s
            ON s.service_id =
               ba.service_id

        ORDER BY 1 DESC

        LIMIT 500
    """

    return execute_query(query)


def get_bandwidth_summary():

    query = """
        SELECT

            COUNT(*) AS allocations,

            COALESCE(
                SUM(allocated_mbps),
                0
            ) AS allocated_mbps

        FROM network.bandwidth_allocation

        WHERE status = 'ACTIVE'
    """

    return execute_query(query)


def create_bandwidth_allocation(
    service_id,
    allocated_mbps,
):

    if allocated_mbps <= 0:

        raise ValueError(
            "Bandwidth must be greater than zero."
        )

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # ------------------------------------------------
            # Validate service
            # ------------------------------------------------

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

            service = cur.fetchone()

            if not service:

                raise ValueError(
                    "Service does not exist."
                )

            if service[0] != "ACTIVE":

                raise ValueError(
                    "Bandwidth can only be "
                    "allocated to ACTIVE services."
                )

            # ------------------------------------------------
            # Check existing allocation
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    COUNT(*)
                FROM network.bandwidth_allocation

                WHERE service_id = %s

                  AND status = 'ACTIVE'
                """,
                (service_id,),
            )

            if cur.fetchone()[0] > 0:

                raise ValueError(
                    "Service already has an "
                    "active bandwidth allocation."
                )

            # ------------------------------------------------
            # Generate ID
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    COALESCE(
                        MAX(bandwidth_allocation_id),
                        0
                    ) + 1
                FROM network.bandwidth_allocation
                """
            )

            allocation_id = cur.fetchone()[0]

            # ------------------------------------------------
            # Insert
            # ------------------------------------------------

            cur.execute(
                """
                INSERT INTO
                    network.bandwidth_allocation (
                        bandwidth_allocation_id,
                        service_id,
                        allocated_mbps,
                        effective_from,
                        effective_to,
                        status
                    )

                VALUES (
                    %s,
                    %s,
                    %s,
                    CURRENT_DATE,
                    NULL,
                    'ACTIVE'
                )
                """,
                (
                    allocation_id,
                    service_id,
                    allocated_mbps,
                ),
            )

        conn.commit()

        return allocation_id

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# OLT
# ============================================================

def get_olts():

    query = """
        SELECT *
        FROM network.olt
        ORDER BY 1
    """

    return execute_query(query)


def get_pon_ports(olt_id):

    query = """
        SELECT *
        FROM network.pon_port
        WHERE olt_id = %s
        ORDER BY 1
    """

    return execute_query(
        query,
        (olt_id,),
    )


# ============================================================
# PON ALLOCATION
# ============================================================

def allocate_pon_port(
    service_id,
    pon_port_id,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # ------------------------------------------------
            # Lock PON
            # ------------------------------------------------

            cur.execute(
                """
                SELECT *
                FROM network.pon_port
                WHERE pon_port_id = %s
                FOR UPDATE
                """,
                (pon_port_id,),
            )

            pon = cur.fetchone()

            if not pon:

                raise ValueError(
                    "PON port not found."
                )

            # ------------------------------------------------
            # Validate service
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    service_status,
                    technology
                FROM crm.service
                WHERE service_id = %s
                """,
                (service_id,),
            )

            service = cur.fetchone()

            if not service:

                raise ValueError(
                    "Service not found."
                )

            if service[0] != "ACTIVE":

                raise ValueError(
                    "PON port can only be allocated "
                    "to an ACTIVE service."
                )

            # ------------------------------------------------
            # Check whether port is already allocated
            # ------------------------------------------------

            cur.execute(
                """
                SELECT *
                FROM network.network_resource

                WHERE resource_type = 'PON'

                  AND resource_id = %s

                  AND status = 'ALLOCATED'
                """,
                (pon_port_id,),
            )

            existing = cur.fetchone()

            if existing:

                raise ValueError(
                    "PON port is already allocated."
                )

            # ------------------------------------------------
            # Update PON
            # ------------------------------------------------

            cur.execute(
                """
                UPDATE network.pon_port
                SET
                    status = 'ALLOCATED'
                WHERE pon_port_id = %s
                """,
                (pon_port_id,),
            )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# NETWORK RESOURCES
# ============================================================

def get_network_resources():

    query = """
        SELECT *
        FROM network.network_resource
        ORDER BY 1
        LIMIT 500
    """

    return execute_query(query)


def get_available_resources():

    query = """
        SELECT *
        FROM network.network_resource

        WHERE status = 'AVAILABLE'

        ORDER BY 1

        LIMIT 500
    """

    return execute_query(query)


# ============================================================
# RESOURCE ALLOCATION
# ============================================================

def allocate_network_resource(
    service_id,
    resource_id,
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            # ------------------------------------------------
            # Lock resource
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    *
                FROM network.network_resource

                WHERE network_resource_id = %s

                FOR UPDATE
                """,
                (resource_id,),
            )

            resource = cur.fetchone()

            if not resource:

                raise ValueError(
                    "Network resource not found."
                )

            # ------------------------------------------------
            # Get column information
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    column_name
                FROM information_schema.columns

                WHERE table_schema = 'network'
                  AND table_name =
                      'network_resource'

                ORDER BY ordinal_position
                """
            )

            columns = [
                row[0]
                for row in cur.fetchall()
            ]

            # ------------------------------------------------
            # Locate status column
            # ------------------------------------------------

            if "status" not in columns:

                raise ValueError(
                    "network.network_resource "
                    "does not contain a status column."
                )

            # ------------------------------------------------
            # Validate service
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    service_status
                FROM crm.service
                WHERE service_id = %s
                """,
                (service_id,),
            )

            service = cur.fetchone()

            if not service:

                raise ValueError(
                    "Service not found."
                )

            if service[0] != "ACTIVE":

                raise ValueError(
                    "Resource can only be allocated "
                    "to an ACTIVE service."
                )

            # ------------------------------------------------
            # Allocate
            # ------------------------------------------------

            cur.execute(
                """
                UPDATE network.network_resource
                SET
                    status = 'ALLOCATED'
                WHERE network_resource_id = %s
                """,
                (resource_id,),
            )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# IP ASSIGNMENT SCREEN
# ============================================================

def ip_assignment_screen():

    st.subheader("IP Assignment")

    tab1, tab2 = st.tabs(
        [
            "Assign IP",
            "IP Inventory",
        ]
    )

    with tab1:

        services = get_active_services()

        if services.empty:

            st.warning(
                "No active services available."
            )

            return

        service_options = {}

        for row in services.itertuples():

            label = (
                f"{row.service_number} | "
                f"{row.customer_number} | "
                f"{row.first_name} "
                f"{row.last_name} | "
                f"{row.technology}"
            )

            service_options[label] = (
                row.service_id
            )

        selected_service = st.selectbox(
            "Service",
            list(service_options.keys()),
        )

        service_id = service_options[
            selected_service
        ]

        pools = get_ip_pools()

        if pools.empty:

            st.warning(
                "No IP pools found."
            )

        else:

            pool_options = {}

            for index, row in pools.iterrows():

                values = row.to_dict()

                pool_id = values.get(
                    "ip_pool_id",
                    values.get(
                        "pool_id",
                        index,
                    ),
                )

                cidr = values.get(
                    "cidr",
                    values.get(
                        "network_cidr",
                        "",
                    ),
                )

                status = values.get(
                    "status",
                    "",
                )

                label = (
                    f"Pool {pool_id} | "
                    f"{cidr} | "
                    f"{status}"
                )

                pool_options[label] = pool_id

            selected_pool = st.selectbox(
                "IP Pool",
                list(pool_options.keys()),
            )

            pool_id = pool_options[
                selected_pool
            ]

            ips = get_available_ips(
                pool_id
            )

            if ips.empty:

                st.warning(
                    "No available IP addresses "
                    "exist in this pool."
                )

            else:

                ip_options = {}

                for row in ips.itertuples():

                    label = (
                        f"{row.ip_address}"
                    )

                    ip_options[label] = (
                        row.ip_assignment_id
                    )

                selected_ip = st.selectbox(
                    "Available IP",
                    list(ip_options.keys()),
                )

                ip_assignment_id = ip_options[
                    selected_ip
                ]

                st.info(
                    f"Assign **{selected_ip}** "
                    f"to **{selected_service}**"
                )

                if st.button(
                    "Assign IP",
                    type="primary",
                    use_container_width=True,
                ):

                    try:

                        assign_ip(
                            service_id,
                            ip_assignment_id,
                        )

                        st.success(
                            "IP assigned successfully."
                        )

                        st.rerun()

                    except Exception as e:

                        st.error(
                            f"IP assignment failed: {e}"
                        )

    with tab2:

        try:

            df = get_ip_assignments()

            if df.empty:

                st.info(
                    "No IP assignments found."
                )

            else:

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                )

        except Exception as e:

            st.error(
                f"Unable to load IP inventory: {e}"
            )


# ============================================================
# BANDWIDTH SCREEN
# ============================================================

def bandwidth_screen():

    st.subheader("Bandwidth Management")

    tab1, tab2 = st.tabs(
        [
            "Allocate Bandwidth",
            "Bandwidth Inventory",
        ]
    )

    with tab1:

        services = get_active_services()

        if services.empty:

            st.warning(
                "No active services available."
            )

            return

        service_options = {}

        for row in services.itertuples():

            label = (
                f"{row.service_number} | "
                f"{row.customer_number} | "
                f"{row.first_name} "
                f"{row.last_name} | "
                f"{row.technology}"
            )

            service_options[label] = (
                row.service_id
            )

        selected = st.selectbox(
            "Service",
            list(service_options.keys()),
            key="bandwidth_service",
        )

        service_id = service_options[
            selected
        ]

        allocated_mbps = st.number_input(
            "Allocated Bandwidth (Mbps)",
            min_value=1,
            max_value=100000,
            value=100,
            step=10,
        )

        c1, c2 = st.columns(2)

        c1.metric(
            "Service",
            selected.split("|")[0].strip(),
        )

        c2.metric(
            "Bandwidth",
            f"{allocated_mbps:,} Mbps",
        )

        if st.button(
            "Allocate Bandwidth",
            type="primary",
            use_container_width=True,
        ):

            try:

                allocation_id = (
                    create_bandwidth_allocation(
                        service_id,
                        allocated_mbps,
                    )
                )

                st.success(
                    "Bandwidth allocated successfully."
                )

                st.info(
                    f"Allocation ID: "
                    f"{allocation_id}"
                )

            except Exception as e:

                st.error(
                    f"Bandwidth allocation failed: {e}"
                )

    with tab2:

        try:

            summary = get_bandwidth_summary()

            if not summary.empty:

                c1, c2 = st.columns(2)

                c1.metric(
                    "Active Allocations",
                    int(
                        summary.iloc[0][
                            "allocations"
                        ]
                    ),
                )

                c2.metric(
                    "Allocated Mbps",
                    f"{float(summary.iloc[0]['allocated_mbps']):,.0f}",
                )

            df = get_bandwidth_allocations()

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

        except Exception as e:

            st.error(
                f"Unable to load bandwidth data: {e}"
            )


# ============================================================
# OLT / PON SCREEN
# ============================================================

def olt_pon_screen():

    st.subheader("OLT / PON Management")

    tab1, tab2, tab3 = st.tabs(
        [
            "OLT Inventory",
            "PON Ports",
            "Allocate PON",
        ]
    )

    # --------------------------------------------------------
    # OLT
    # --------------------------------------------------------

    with tab1:

        try:

            olts = get_olts()

            if olts.empty:

                st.info(
                    "No OLT records found."
                )

            else:

                st.dataframe(
                    olts,
                    use_container_width=True,
                    hide_index=True,
                )

        except Exception as e:

            st.error(
                f"Unable to load OLT inventory: {e}"
            )

    # --------------------------------------------------------
    # PON
    # --------------------------------------------------------

    with tab2:

        try:

            olts = get_olts()

            if olts.empty:

                st.warning(
                    "No OLTs available."
                )

            else:

                options = {}

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

                    options[
                        f"{olt_id} | {olt_name}"
                    ] = olt_id

                selected = st.selectbox(
                    "OLT",
                    list(options.keys()),
                    key="pon_olt",
                )

                olt_id = options[selected]

                ports = get_pon_ports(
                    olt_id
                )

                if ports.empty:

                    st.info(
                        "No PON ports found "
                        "for this OLT."
                    )

                else:

                    st.dataframe(
                        ports,
                        use_container_width=True,
                        hide_index=True,
                    )

        except Exception as e:

            st.error(
                f"Unable to load PON ports: {e}"
            )

    # --------------------------------------------------------
    # Allocate PON
    # --------------------------------------------------------

    with tab3:

        try:

            services = get_active_services()

            olts = get_olts()

            if services.empty:

                st.warning(
                    "No active services."
                )

            elif olts.empty:

                st.warning(
                    "No OLTs available."
                )

            else:

                service_options = {}

                for row in services.itertuples():

                    label = (
                        f"{row.service_number} | "
                        f"{row.customer_number} | "
                        f"{row.first_name} "
                        f"{row.last_name}"
                    )

                    service_options[label] = (
                        row.service_id
                    )

                service_label = st.selectbox(
                    "Service",
                    list(service_options.keys()),
                    key="pon_service",
                )

                service_id = service_options[
                    service_label
                ]

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

                olt_label = st.selectbox(
                    "OLT",
                    list(olt_options.keys()),
                    key="allocate_olt",
                )

                olt_id = olt_options[
                    olt_label
                ]

                ports = get_pon_ports(
                    olt_id
                )

                if ports.empty:

                    st.warning(
                        "No PON ports found."
                    )

                else:

                    port_options = {}

                    for index, row in ports.iterrows():

                        values = row.to_dict()

                        port_id = values.get(
                            "pon_port_id",
                            index,
                        )

                        port_number = values.get(
                            "port_number",
                            values.get(
                                "pon_port_number",
                                port_id,
                            ),
                        )

                        status = values.get(
                            "status",
                            "",
                        )

                        if status in (
                            "AVAILABLE",
                            "FREE",
                            "",
                        ):

                            label = (
                                f"Port {port_number} | "
                                f"{status}"
                            )

                            port_options[
                                label
                            ] = port_id

                    if not port_options:

                        st.warning(
                            "No available PON "
                            "ports found."
                        )

                    else:

                        port_label = st.selectbox(
                            "Available PON Port",
                            list(
                                port_options.keys()
                            ),
                        )

                        pon_port_id = port_options[
                            port_label
                        ]

                        if st.button(
                            "Allocate PON Port",
                            type="primary",
                            use_container_width=True,
                        ):

                            try:

                                allocate_pon_port(
                                    service_id,
                                    pon_port_id,
                                )

                                st.success(
                                    "PON port allocated "
                                    "successfully."
                                )

                                st.rerun()

                            except Exception as e:

                                st.error(
                                    f"PON allocation failed: {e}"
                                )

        except Exception as e:

            st.error(
                f"Unable to load PON allocation data: {e}"
            )


# ============================================================
# RESOURCE ALLOCATION SCREEN
# ============================================================

def resource_allocation_screen():

    st.subheader(
        "Network Resource Allocation"
    )

    tab1, tab2 = st.tabs(
        [
            "Allocate Resource",
            "Resource Inventory",
        ]
    )

    with tab1:

        try:

            services = get_active_services()

            resources = get_available_resources()

            if services.empty:

                st.warning(
                    "No active services available."
                )

                return

            if resources.empty:

                st.warning(
                    "No available network resources."
                )

                return

            service_options = {}

            for row in services.itertuples():

                label = (
                    f"{row.service_number} | "
                    f"{row.customer_number} | "
                    f"{row.first_name} "
                    f"{row.last_name}"
                )

                service_options[label] = (
                    row.service_id
                )

            service_label = st.selectbox(
                "Service",
                list(service_options.keys()),
                key="resource_service",
            )

            service_id = service_options[
                service_label
            ]

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
                        str(resource_id),
                    ),
                )

                capacity = values.get(
                    "capacity",
                    values.get(
                        "capacity_mbps",
                        "",
                    ),
                )

                label = (
                    f"{resource_type} | "
                    f"{resource_code} | "
                    f"Capacity: {capacity}"
                )

                resource_options[
                    label
                ] = resource_id

            resource_label = st.selectbox(
                "Available Resource",
                list(resource_options.keys()),
                key="network_resource",
            )

            resource_id = resource_options[
                resource_label
            ]

            st.info(
                f"Allocate **{resource_label}** "
                f"to **{service_label}**"
            )

            if st.button(
                "Allocate Network Resource",
                type="primary",
                use_container_width=True,
            ):

                try:

                    allocate_network_resource(
                        service_id,
                        resource_id,
                    )

                    st.success(
                        "Network resource allocated "
                        "successfully."
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        f"Resource allocation failed: {e}"
                    )

        except Exception as e:

            st.error(
                f"Unable to load resources: {e}"
            )

    with tab2:

        try:

            df = get_network_resources()

            if df.empty:

                st.info(
                    "No network resources found."
                )

            else:

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                )

        except Exception as e:

            st.error(
                f"Unable to load network resources: {e}"
            )


# ============================================================
# NETWORK DASHBOARD
# ============================================================

def network_dashboard():

    st.markdown(
        "### Network Overview"
    )

    try:

        services = get_active_services()

        ip_df = get_ip_assignments()

        bandwidth_df = get_bandwidth_allocations()

        olts = get_olts()

        resources = get_network_resources()

        # ----------------------------------------------------
        # KPIs
        # ----------------------------------------------------

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Active Services",
            len(services),
        )

        if not ip_df.empty and "status" in ip_df.columns:

            assigned_ips = len(
                ip_df[
                    ip_df["status"]
                    == "ASSIGNED"
                ]
            )

        else:

            assigned_ips = 0

        c2.metric(
            "Assigned IPs",
            assigned_ips,
        )

        if (
            not bandwidth_df.empty
            and "allocated_mbps"
            in bandwidth_df.columns
        ):

            total_bandwidth = (
                pd.to_numeric(
                    bandwidth_df[
                        "allocated_mbps"
                    ],
                    errors="coerce",
                )
                .fillna(0)
                .sum()
            )

        else:

            total_bandwidth = 0

        c3.metric(
            "Allocated Bandwidth",
            f"{total_bandwidth:,.0f} Mbps",
        )

        c4.metric(
            "OLT Count",
            len(olts),
        )

        st.divider()

        # ----------------------------------------------------
        # Resource status
        # ----------------------------------------------------

        if (
            not resources.empty
            and "status"
            in resources.columns
        ):

            st.markdown(
                "### Resource Status"
            )

            resource_status = (
                resources[
                    "status"
                ]
                .value_counts()
                .reset_index()
            )

            resource_status.columns = [
                "Status",
                "Count",
            ]

            st.dataframe(
                resource_status,
                use_container_width=True,
                hide_index=True,
            )

    except Exception as e:

        st.warning(
            f"Dashboard data unavailable: {e}"
        )


# ============================================================
# MAIN NETWORK MANAGEMENT
# ============================================================

def network_management_screen():

    st.title(
        "🌐 Network Management"
    )

    st.caption(
        "Manage IP addressing, bandwidth, "
        "OLT/PON capacity and network resources."
    )

    modes = [
        "Overview",
        "IP Assignment",
        "Bandwidth",
        "OLT / PON",
        "Resource Allocation",
    ]

    current_mode = st.session_state.get(
        "network_management_mode",
        "Overview",
    )

    if current_mode not in modes:

        current_mode = "Overview"

    selected_mode = st.radio(
        "Network",
        modes,
        index=modes.index(
            current_mode
        ),
        horizontal=True,
    )

    st.session_state[
        "network_management_mode"
    ] = selected_mode

    st.divider()

    if selected_mode == "Overview":

        network_dashboard()

    elif selected_mode == "IP Assignment":

        ip_assignment_screen()

    elif selected_mode == "Bandwidth":

        bandwidth_screen()

    elif selected_mode == "OLT / PON":

        olt_pon_screen()

    elif selected_mode == "Resource Allocation":

        resource_allocation_screen()