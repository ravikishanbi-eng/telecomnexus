import re
from datetime import date


def validate_email(email: str) -> bool:
    if not email:
        return False

    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    return re.match(pattern, email) is not None


def validate_phone(phone: str) -> bool:
    if not phone:
        return False

    digits = re.sub(r"\D", "", phone)

    return len(digits) >= 10


def validate_customer(
    first_name,
    last_name,
    email,
    phone,
    city,
    state,
    postal_code,
):
    errors = []

    if not first_name.strip():
        errors.append("First name is required.")

    if not last_name.strip():
        errors.append("Last name is required.")

    if not validate_email(email):
        errors.append("Enter a valid email address.")

    if not validate_phone(phone):
        errors.append("Enter a valid phone number.")

    if not city.strip():
        errors.append("City is required.")

    if not state.strip():
        errors.append("State is required.")

    if not postal_code.strip():
        errors.append("Postal code is required.")

    return errors


def validate_contract(
    contract_type,
    start_date,
    product_id,
    quantity,
    discount,
):
    errors = []

    if not contract_type:
        errors.append("Contract type is required.")

    if not start_date:
        errors.append("Contract start date is required.")

    if not product_id:
        errors.append("Product is required.")

    if quantity < 1:
        errors.append("Quantity must be at least 1.")

    if discount < 0:
        errors.append("Discount cannot be negative.")

    return errors