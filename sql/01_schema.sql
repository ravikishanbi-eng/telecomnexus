create database if not exists telecomnexus_db;

CREATE SCHEMA IF NOT EXISTS crm;
CREATE SCHEMA IF NOT EXISTS prd;
CREATE SCHEMA IF NOT EXISTS inv;
CREATE SCHEMA IF NOT EXISTS fin;
CREATE SCHEMA IF NOT EXISTS trx;
CREATE SCHEMA IF NOT EXISTS network;

-- =========================
-- CRM
-- =========================
CREATE TABLE IF NOT EXISTS crm.customer (
    customer_id          BIGINT PRIMARY KEY,
    customer_number      VARCHAR(30) UNIQUE NOT NULL,
    customer_type        VARCHAR(20) NOT NULL CHECK (customer_type IN ('RESIDENTIAL','SMB','ENTERPRISE')),
    first_name            VARCHAR(80) NOT NULL,
    last_name             VARCHAR(80) NOT NULL,
    email                 VARCHAR(255) NOT NULL,
    phone                 VARCHAR(20) NOT NULL,
    address_line1         VARCHAR(255) NOT NULL,
    city                  VARCHAR(80) NOT NULL,
    state                 VARCHAR(80) NOT NULL,
    postal_code           VARCHAR(10) NOT NULL,
    country               VARCHAR(80) NOT NULL DEFAULT 'India',
    customer_status       VARCHAR(20) NOT NULL CHECK (customer_status IN ('ACTIVE','INACTIVE','PROSPECT','SUSPENDED')),
    customer_since        DATE NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL,
    updated_at             TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS crm.billing (
    billing_account_id    BIGINT PRIMARY KEY,
    customer_id           BIGINT NOT NULL REFERENCES crm.customer(customer_id),
    billing_cycle         VARCHAR(20) NOT NULL CHECK (billing_cycle IN ('MONTHLY','QUARTERLY','ANNUAL')),
    billing_day            SMALLINT NOT NULL CHECK (billing_day BETWEEN 1 AND 28),
    payment_method         VARCHAR(30) NOT NULL CHECK (payment_method IN ('UPI','CARD','NET_BANKING','AUTO_DEBIT','BANK_TRANSFER','CASH')),
    credit_limit           NUMERIC(14,2) NOT NULL DEFAULT 0,
    currency               CHAR(3) NOT NULL DEFAULT 'INR',
    billing_status         VARCHAR(20) NOT NULL CHECK (billing_status IN ('ACTIVE','SUSPENDED','CLOSED')),
    created_at             TIMESTAMPTZ NOT NULL,
    updated_at             TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS crm.service (
    service_id             BIGINT PRIMARY KEY,
    customer_id            BIGINT NOT NULL REFERENCES crm.customer(customer_id),
    contract_id            BIGINT,
    product_id             BIGINT,
    service_number         VARCHAR(30) UNIQUE NOT NULL,
    service_type           VARCHAR(30) NOT NULL DEFAULT 'BROADBAND',
    technology             VARCHAR(20) NOT NULL CHECK (technology IN ('FTTH','FTTB','FWA')),
    activation_date        DATE NOT NULL,
    deactivation_date      DATE,
    service_status         VARCHAR(20) NOT NULL CHECK (service_status IN ('ACTIVE','SUSPENDED','DISCONNECTED','PENDING')),
    installation_address   VARCHAR(255) NOT NULL,
    city                   VARCHAR(80) NOT NULL,
    state                  VARCHAR(80) NOT NULL,
    postal_code            VARCHAR(10) NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL,
    updated_at             TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS crm.contract (
    contract_id            BIGINT PRIMARY KEY,
    contract_number        VARCHAR(30) UNIQUE NOT NULL,
    customer_id            BIGINT NOT NULL REFERENCES crm.customer(customer_id),
    contract_type          VARCHAR(20) NOT NULL CHECK (contract_type IN ('MONTHLY','12_MONTH','24_MONTH')),
    start_date             DATE NOT NULL,
    end_date               DATE,
    contract_status        VARCHAR(20) NOT NULL CHECK (contract_status IN ('ACTIVE','EXPIRED','CANCELLED','PENDING')),
    auto_renew             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at             TIMESTAMPTZ NOT NULL,
    updated_at             TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS crm.contract_detail (
    contract_detail_id     BIGINT PRIMARY KEY,
    contract_id            BIGINT NOT NULL REFERENCES crm.contract(contract_id),
    line_number             INTEGER NOT NULL,
    product_id             BIGINT NOT NULL,
    quantity                INTEGER NOT NULL CHECK (quantity > 0),
    agreed_monthly_price   NUMERIC(14,2) NOT NULL,
    discount_amount        NUMERIC(14,2) NOT NULL DEFAULT 0,
    tax_percent             NUMERIC(5,2) NOT NULL DEFAULT 18.00,
    effective_from         DATE NOT NULL,
    effective_to           DATE,
    UNIQUE(contract_id, line_number)
);

CREATE TABLE IF NOT EXISTS crm.contract_rate_schedule (
    contract_rate_schedule_id BIGINT PRIMARY KEY,
    contract_id                BIGINT NOT NULL REFERENCES crm.contract(contract_id),
    contract_detail_id         BIGINT NOT NULL REFERENCES crm.contract_detail(contract_detail_id),
    rate_schedule_id           BIGINT NOT NULL,
    effective_from              DATE NOT NULL,
    effective_to                DATE,
    agreed_rate                NUMERIC(14,2) NOT NULL
);

-- =========================
-- PRODUCT
-- =========================
CREATE TABLE IF NOT EXISTS prd.product (
    product_id             BIGINT PRIMARY KEY,
    product_code            VARCHAR(30) UNIQUE NOT NULL,
    product_name            VARCHAR(120) NOT NULL,
    product_category        VARCHAR(30) NOT NULL,
    technology              VARCHAR(20) NOT NULL,
    download_speed_mbps     INTEGER NOT NULL CHECK (download_speed_mbps > 0),
    upload_speed_mbps       INTEGER NOT NULL CHECK (upload_speed_mbps > 0),
    installation_fee        NUMERIC(14,2) NOT NULL DEFAULT 0,
    product_status          VARCHAR(20) NOT NULL CHECK (product_status IN ('ACTIVE','RETIRED','FUTURE')),
    created_at              TIMESTAMPTZ NOT NULL,
    updated_at              TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS prd.rate_schedule (
    rate_schedule_id       BIGINT PRIMARY KEY,
    product_id             BIGINT NOT NULL REFERENCES prd.product(product_id),
    rate_code               VARCHAR(40) UNIQUE NOT NULL,
    monthly_charge          NUMERIC(14,2) NOT NULL,
    activation_charge       NUMERIC(14,2) NOT NULL DEFAULT 0,
    tax_percentage          NUMERIC(5,2) NOT NULL DEFAULT 18.00,
    currency                CHAR(3) NOT NULL DEFAULT 'INR',
    effective_from          DATE NOT NULL,
    effective_to            DATE,
    status                  VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE','EXPIRED','FUTURE')),
    UNIQUE(product_id, effective_from)
);

-- =========================
-- INVOICE
-- =========================
CREATE TABLE IF NOT EXISTS inv.invoice (
    invoice_id              BIGINT PRIMARY KEY,
    invoice_number          VARCHAR(40) UNIQUE NOT NULL,
    billing_account_id      BIGINT NOT NULL REFERENCES crm.billing(billing_account_id),
    customer_id             BIGINT NOT NULL REFERENCES crm.customer(customer_id),
    invoice_date            DATE NOT NULL,
    due_date                DATE NOT NULL,
    billing_period_start    DATE NOT NULL,
    billing_period_end      DATE NOT NULL,
    subtotal                NUMERIC(14,2) NOT NULL,
    discount_amount         NUMERIC(14,2) NOT NULL DEFAULT 0,
    tax_amount              NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_amount             NUMERIC(14,2) NOT NULL,
    invoice_status          VARCHAR(20) NOT NULL CHECK (invoice_status IN ('ISSUED','PARTIALLY_PAID','PAID','OVERDUE','VOID')),
    created_at              TIMESTAMPTZ NOT NULL,
    updated_at              TIMESTAMPTZ NOT NULL,
    CHECK (total_amount >= 0),
    CHECK (billing_period_end >= billing_period_start)
);

CREATE TABLE IF NOT EXISTS inv.invoice_detail (
    invoice_detail_id       BIGINT PRIMARY KEY,
    invoice_id              BIGINT NOT NULL REFERENCES inv.invoice(invoice_id),
    line_number              INTEGER NOT NULL,
    service_id              BIGINT REFERENCES crm.service(service_id),
    product_id              BIGINT REFERENCES prd.product(product_id),
    charge_type              VARCHAR(30) NOT NULL CHECK (charge_type IN ('RECURRING','INSTALLATION','ACTIVATION','ADJUSTMENT','DISCOUNT')),
    description             VARCHAR(255) NOT NULL,
    quantity                NUMERIC(12,2) NOT NULL,
    unit_price               NUMERIC(14,2) NOT NULL,
    discount_amount         NUMERIC(14,2) NOT NULL DEFAULT 0,
    tax_amount               NUMERIC(14,2) NOT NULL DEFAULT 0,
    line_total               NUMERIC(14,2) NOT NULL,
    UNIQUE(invoice_id, line_number)
);

-- =========================
-- FINANCE
-- =========================
CREATE TABLE IF NOT EXISTS fin.payment (
    payment_id              BIGINT PRIMARY KEY,
    payment_number          VARCHAR(40) UNIQUE NOT NULL,
    customer_id             BIGINT NOT NULL REFERENCES crm.customer(customer_id),
    payment_date            DATE NOT NULL,
    payment_method          VARCHAR(30) NOT NULL,
    payment_status          VARCHAR(20) NOT NULL CHECK (payment_status IN ('SUCCESS','PENDING','FAILED','REFUNDED')),
    amount                  NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
    currency                CHAR(3) NOT NULL DEFAULT 'INR',
    gateway_reference       VARCHAR(80),
    created_at              TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS fin.payment_detail (
    payment_detail_id       BIGINT PRIMARY KEY,
    payment_id              BIGINT NOT NULL REFERENCES fin.payment(payment_id),
    invoice_id              BIGINT NOT NULL REFERENCES inv.invoice(invoice_id),
    allocated_amount        NUMERIC(14,2) NOT NULL CHECK (allocated_amount >= 0),
    allocation_status       VARCHAR(20) NOT NULL CHECK (allocation_status IN ('ALLOCATED','UNALLOCATED','REVERSED')),
    created_at              TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS fin.gl_ledger (
    gl_entry_id             BIGINT PRIMARY KEY,
    transaction_id          BIGINT,
    entry_date              DATE NOT NULL,
    account_code             VARCHAR(30) NOT NULL,
    account_name             VARCHAR(100) NOT NULL,
    debit_amount             NUMERIC(14,2) NOT NULL DEFAULT 0,
    credit_amount            NUMERIC(14,2) NOT NULL DEFAULT 0,
    currency                CHAR(3) NOT NULL DEFAULT 'INR',
    reference_number        VARCHAR(60) NOT NULL,
    description             VARCHAR(255) NOT NULL,
    created_at               TIMESTAMPTZ NOT NULL,
    CHECK (debit_amount >= 0 AND credit_amount >= 0),
    CHECK (NOT (debit_amount > 0 AND credit_amount > 0))
);

-- =========================
-- TRANSACTIONS
-- =========================
CREATE TABLE IF NOT EXISTS trx.transaction (
    transaction_id          BIGINT PRIMARY KEY,
    transaction_number      VARCHAR(40) UNIQUE NOT NULL,
    customer_id             BIGINT NOT NULL REFERENCES crm.customer(customer_id),
    service_id              BIGINT REFERENCES crm.service(service_id),
    transaction_type        VARCHAR(30) NOT NULL CHECK (transaction_type IN (
        'NEW_CONNECTION','ACTIVATION','UPGRADE','DOWNGRADE','RENEWAL',
        'DISCONNECTION','RECONNECTION','SUSPENSION','PAYMENT','REFUND','ADJUSTMENT'
    )),
    transaction_date        TIMESTAMPTZ NOT NULL,
    transaction_status      VARCHAR(20) NOT NULL CHECK (transaction_status IN ('COMPLETED','PENDING','FAILED','CANCELLED')),
    amount                  NUMERIC(14,2) NOT NULL DEFAULT 0,
    currency                CHAR(3) NOT NULL DEFAULT 'INR',
    channel                 VARCHAR(30) NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS trx.transaction_detail (
    transaction_detail_id   BIGINT PRIMARY KEY,
    transaction_id          BIGINT NOT NULL REFERENCES trx.transaction(transaction_id),
    line_number              INTEGER NOT NULL,
    product_id              BIGINT REFERENCES prd.product(product_id),
    old_product_id          BIGINT REFERENCES prd.product(product_id),
    new_product_id          BIGINT REFERENCES prd.product(product_id),
    quantity                INTEGER NOT NULL DEFAULT 1,
    unit_price               NUMERIC(14,2) NOT NULL DEFAULT 0,
    discount_amount          NUMERIC(14,2) NOT NULL DEFAULT 0,
    tax_amount               NUMERIC(14,2) NOT NULL DEFAULT 0,
    amount                  NUMERIC(14,2) NOT NULL DEFAULT 0,
    UNIQUE(transaction_id, line_number)
);

-- =========================
-- NETWORK - capacity planning
-- =========================
CREATE TABLE IF NOT EXISTS network.network_site (
    site_id                 BIGINT PRIMARY KEY,
    site_code               VARCHAR(30) UNIQUE NOT NULL,
    site_name               VARCHAR(120) NOT NULL,
    city                    VARCHAR(80) NOT NULL,
    state                   VARCHAR(80) NOT NULL,
    postal_code             VARCHAR(10) NOT NULL,
    latitude                NUMERIC(9,6) NOT NULL,
    longitude               NUMERIC(9,6) NOT NULL,
    site_status              VARCHAR(20) NOT NULL CHECK (site_status IN ('ACTIVE','PLANNED','DECOMMISSIONED')),
    created_at              TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS network.pop (
    pop_id                  BIGINT PRIMARY KEY,
    site_id                 BIGINT NOT NULL REFERENCES network.network_site(site_id),
    pop_code                VARCHAR(30) UNIQUE NOT NULL,
    pop_name                VARCHAR(120) NOT NULL,
    capacity_gbps           NUMERIC(12,2) NOT NULL,
    used_capacity_gbps      NUMERIC(12,2) NOT NULL,
    redundancy_level        VARCHAR(20) NOT NULL,
    status                  VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE','PLANNED','DEGRADED')),
    created_at              TIMESTAMPTZ NOT NULL,
    CHECK (used_capacity_gbps <= capacity_gbps)
);

CREATE TABLE IF NOT EXISTS network.olt (
    olt_id                  BIGINT PRIMARY KEY,
    pop_id                  BIGINT NOT NULL REFERENCES network.pop(pop_id),
    olt_code                VARCHAR(40) UNIQUE NOT NULL,
    vendor                   VARCHAR(40) NOT NULL,
    model                    VARCHAR(80) NOT NULL,
    total_pon_ports          INTEGER NOT NULL,
    used_pon_ports           INTEGER NOT NULL,
    total_capacity_gbps      NUMERIC(12,2) NOT NULL,
    status                   VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE','PLANNED','MAINTENANCE','RETIRED')),
    created_at               TIMESTAMPTZ NOT NULL,
    CHECK (used_pon_ports <= total_pon_ports)
);

CREATE TABLE IF NOT EXISTS network.pon_port (
    pon_port_id              BIGINT PRIMARY KEY,
    olt_id                   BIGINT NOT NULL REFERENCES network.olt(olt_id),
    port_number               INTEGER NOT NULL,
    technology               VARCHAR(20) NOT NULL,
    capacity_gbps             NUMERIC(8,2) NOT NULL,
    used_capacity_gbps       NUMERIC(8,2) NOT NULL,
    status                   VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE','AVAILABLE','FAULT','PLANNED')),
    UNIQUE(olt_id, port_number),
    CHECK (used_capacity_gbps <= capacity_gbps)
);

CREATE TABLE IF NOT EXISTS network.network_resource (
    resource_id              BIGINT PRIMARY KEY,
    service_id               BIGINT UNIQUE NOT NULL REFERENCES crm.service(service_id),
    pon_port_id              BIGINT REFERENCES network.pon_port(pon_port_id),
    resource_type             VARCHAR(30) NOT NULL CHECK (resource_type IN ('FTTH','FTTB','FWA')),
    provisioned_speed_mbps   INTEGER NOT NULL,
    committed_speed_mbps     INTEGER NOT NULL,
    status                   VARCHAR(20) NOT NULL CHECK (status IN ('PROVISIONED','SUSPENDED','RELEASED')),
    activated_at              DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS network.bandwidth_allocation (
    allocation_id             BIGINT PRIMARY KEY,
    service_id                BIGINT NOT NULL REFERENCES crm.service(service_id),
    resource_id               BIGINT NOT NULL REFERENCES network.network_resource(resource_id),
    peak_bandwidth_mbps       INTEGER NOT NULL,
    committed_bandwidth_mbps  INTEGER NOT NULL,
    utilization_percent       NUMERIC(6,2) NOT NULL,
    measurement_date          DATE NOT NULL,
    UNIQUE(service_id, measurement_date)
);

CREATE TABLE IF NOT EXISTS network.ip_pool (
    ip_pool_id                BIGINT PRIMARY KEY,
    pool_name                 VARCHAR(80) UNIQUE NOT NULL,
    cidr                      VARCHAR(40) NOT NULL,
    address_family             VARCHAR(10) NOT NULL CHECK (address_family IN ('IPv4','IPv6')),
    total_addresses           INTEGER NOT NULL,
    allocated_addresses       INTEGER NOT NULL,
    region                    VARCHAR(80) NOT NULL,
    status                    VARCHAR(20) NOT NULL CHECK (status IN ('ACTIVE','EXHAUSTED','PLANNED')),
    created_at                TIMESTAMPTZ NOT NULL,
    CHECK (allocated_addresses <= total_addresses)
);

CREATE TABLE IF NOT EXISTS network.ip_assignment (
    ip_assignment_id          BIGINT PRIMARY KEY,
    ip_pool_id                BIGINT NOT NULL REFERENCES network.ip_pool(ip_pool_id),
    service_id                BIGINT UNIQUE NOT NULL REFERENCES crm.service(service_id),
    ip_address                VARCHAR(64) UNIQUE NOT NULL,
    assignment_type           VARCHAR(20) NOT NULL CHECK (assignment_type IN ('DYNAMIC','STATIC')),
    assigned_at               DATE NOT NULL,
    released_at               DATE
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS ix_customer_status ON crm.customer(customer_status);
CREATE INDEX IF NOT EXISTS ix_service_customer ON crm.service(customer_id);
CREATE INDEX IF NOT EXISTS ix_service_status ON crm.service(service_status);
CREATE INDEX IF NOT EXISTS ix_contract_customer ON crm.contract(customer_id);
CREATE INDEX IF NOT EXISTS ix_invoice_customer_date ON inv.invoice(customer_id, invoice_date);
CREATE INDEX IF NOT EXISTS ix_invoice_status_due ON inv.invoice(invoice_status, due_date);
CREATE INDEX IF NOT EXISTS ix_payment_customer_date ON fin.payment(customer_id, payment_date);
CREATE INDEX IF NOT EXISTS ix_transaction_customer_date ON trx.transaction(customer_id, transaction_date);
CREATE INDEX IF NOT EXISTS ix_gl_date_account ON fin.gl_ledger(entry_date, account_code);
CREATE INDEX IF NOT EXISTS ix_bandwidth_date ON network.bandwidth_allocation(measurement_date);


-- Cross-domain foreign keys added after all tables exist.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_service_contract') THEN
        ALTER TABLE crm.service
        ADD CONSTRAINT fk_service_contract
        FOREIGN KEY (contract_id) REFERENCES crm.contract(contract_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_service_product') THEN
        ALTER TABLE crm.service
        ADD CONSTRAINT fk_service_product
        FOREIGN KEY (product_id) REFERENCES prd.product(product_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_contract_detail_product') THEN
        ALTER TABLE crm.contract_detail
        ADD CONSTRAINT fk_contract_detail_product
        FOREIGN KEY (product_id) REFERENCES prd.product(product_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_contract_rate_schedule') THEN
        ALTER TABLE crm.contract_rate_schedule
        ADD CONSTRAINT fk_contract_rate_schedule
        FOREIGN KEY (rate_schedule_id) REFERENCES prd.rate_schedule(rate_schedule_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_gl_transaction') THEN
        ALTER TABLE fin.gl_ledger
        ADD CONSTRAINT fk_gl_transaction
        FOREIGN KEY (transaction_id) REFERENCES trx.transaction(transaction_id);
    END IF;
END $$;
