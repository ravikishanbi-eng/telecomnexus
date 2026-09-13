# Internet Planning Platform - Production-Grade Synthetic Data

This project creates a realistic synthetic ISP/Broadband data platform based on:

CRM: Customer, Billing, Service, Contract, ContractDetail, ContractRateSchedule
PRD: Product, RateSchedule
INV: Invoice, InvoiceDetail
FIN: Payment, PaymentDetail, GLLedger
TRX: Transaction, TransactionDetail

It also includes a NETWORK domain for genuine internet capacity planning:
NetworkSite, Pop, Olt, PonPort, NetworkResource, BandwidthAllocation, IpPool, IpAssignment.

## Architecture

CRM/PRD/INV/FIN/TRX/NETWORK
        |
        v
   PostgreSQL RAW-like schemas
        |
        v
Analytics / Snowflake ingestion
        |
        v
Customer 360 / Billing / Revenue Assurance / Internet Planning

## Data characteristics

- Synthetic only; no real customer PII.
- India-focused ISP geography and INR pricing.
- Realistic broadband products: FTTH 100 Mbps, 300 Mbps, 500 Mbps, 1 Gbps, 2 Gbps.
- Customer lifecycle events: activation, upgrade, downgrade, renewal, suspension, reconnection, disconnection.
- Monthly invoices for configurable historical months.
- Partial/full payments and a small population of overdue invoices.
- GL postings with debit/credit accounting entries.
- Network capacity entities: POP, OLT, PON, bandwidth and IP allocations.
- Deterministic generation using SEED so the same run can be reproduced.
- Foreign keys, checks, unique constraints, indexes, audit timestamps.

## Quick start

### 1. Create database

```bash
createdb -h localhost -p 5432 -U postgres internet_planning
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` for your PostgreSQL connection.

### 4. Create schemas/tables

```bash
psql -h localhost -p 5432 -U postgres -d internet_planning -f sql/01_schema.sql
```

### 5. Generate and load

```bash
python src/generate_and_load.py
```

The default is 10,000 customers and 12 months of billing history.

For a larger run:

```bash
CUSTOMERS=100000 HISTORICAL_MONTHS=24 python src/generate_and_load.py
```

### 6. Validate

```bash
psql -h localhost -p 5432 -U postgres -d internet_planning -f sql/02_validation.sql
```

## Production migration path

For Snowflake/Matillion:
1. Land source extracts in RAW.
2. Add ingestion metadata: batch_id, source_system, source_file, ingested_at.
3. Use MERGE/CDC into staging/core.
4. Apply SCD2 to customer/product/contract/service dimensions.
5. Build FACT_INVOICE, FACT_PAYMENT, FACT_REVENUE, FACT_SUBSCRIPTION.
6. Build planning marts for subscribers, ARPU, churn, revenue and network capacity.
7. Add orchestration, alerting, data-quality gates and CI/CD.

This generator is intended for development, demos, testing and architecture workshops; it does not contain real-world personal data.
