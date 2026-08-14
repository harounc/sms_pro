import re


LOCAL_PHONE_REGEX = re.compile(r"^0\d{9}$")
INTERNATIONAL_CI_PHONE_REGEX = re.compile(r"^\+2250\d{9}$")


def normalize_phone(phone):
    value = str(phone or "").strip().replace(" ", "")
    if INTERNATIONAL_CI_PHONE_REGEX.fullmatch(value):
        return value[4:]
    return value


def is_valid_phone(phone):
    return bool(LOCAL_PHONE_REGEX.fullmatch(normalize_phone(phone)))


def phone_lookup_values(phone):
    local_phone = normalize_phone(phone)
    values = [local_phone]
    if LOCAL_PHONE_REGEX.fullmatch(local_phone):
        values.append(f"+225{local_phone}")
    return values
