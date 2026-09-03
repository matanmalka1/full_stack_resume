"""Vocabulary shared by the domain's bounded contexts."""

from __future__ import annotations

from enum import StrEnum


class Track(StrEnum):
    DEVELOPMENT = "development"
    SALES = "sales"
    TECH_SALES = "tech-sales"


class ProfileName(StrEnum):
    DEVELOPMENT = "development"
    FIELD_SALES = "field-sales"
    ACCOUNT_MANAGER = "account-manager"
    KEY_ACCOUNT_MANAGER = "key-account-manager"
    SDR_BDR = "sdr-bdr"
    ACCOUNT_EXECUTIVE = "account-executive"
    BUSINESS_DEVELOPMENT = "business-development"
    SALES_MANAGEMENT = "sales-management"
    TECH_SALES = "tech-sales"
    PRE_SALES = "pre-sales-solutions-consultant"


class Emphasis(StrEnum):
    DEVELOPMENT_BALANCED = "development-balanced"
    DEVELOPMENT_BACKEND = "development-backend"
    DEVELOPMENT_AI = "development-ai"
    NEW_BUSINESS = "new-business"
    ACCOUNT_GROWTH = "account-growth"
    LEADERSHIP = "leadership"
    TECH_CONSULTATIVE = "tech-consultative-sales"
    BALANCED_SALES = "balanced-sales"
