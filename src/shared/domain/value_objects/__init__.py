# -*- coding: utf-8 -*-
"""Shared domain value objects."""

from .country_code import CountryCode, InvalidCountryCodeError

__all__ = [
    "CountryCode",
    "InvalidCountryCodeError",
]
