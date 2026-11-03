from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AccountStateCode = Literal[
    'active',
    'manual_disabled',
    'access_restricted',
    'expired',
    'expiring_soon',
    'rate_limited',
    'quota_limited',
    'unavailable',
]
AccountStateSeverity = Literal['success', 'warning', 'danger', 'muted']
AccountListStatus = Literal[
    'all',
    'active',
    'manual_disabled',
    'access_restricted',
    'expired',
    'expiring_soon',
    'rate_limited',
    'quota_limited',
    'unavailable',
]


class StrictModel(BaseModel):
    class Config:
        extra = 'forbid'


class QuotaStatusPayload(StrictModel):
    available: bool
    remaining_seconds: int | None = None
    reason: str | None = None
    daily_used: int | None = None
    daily_limit: int | None = None


class AccountQuotaBucketsPayload(StrictModel):
    text: QuotaStatusPayload
    images: QuotaStatusPayload
    videos: QuotaStatusPayload


class AccountQuotaStatusPayload(StrictModel):
    quotas: AccountQuotaBucketsPayload
    limited_count: int
    total_count: int
    is_expired: bool


class AccountStatePayload(StrictModel):
    code: AccountStateCode
    label: str
    severity: AccountStateSeverity
    reason: str | None = None
    cooldown_seconds: int
    can_enable: bool
    can_disable: bool
    can_delete: bool


class AdminAccountPayload(StrictModel):
    id: str
    state: AccountStatePayload
    status: str
    expires_at: str
    remaining_hours: float | None = None
    remaining_display: str
    is_available: bool
    failure_count: int
    disabled: bool
    disabled_reason: str | None = None
    cooldown_seconds: int
    cooldown_reason: str | None = None
    conversation_count: int
    session_usage_count: int
    quota_status: AccountQuotaStatusPayload
    trial_end: str | None = None
    trial_days_remaining: int | None = None


class AccountsListPayload(StrictModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    query: str
    status: AccountListStatus
    accounts: list[AdminAccountPayload] = Field(default_factory=list)


class AccountMutationPayload(StrictModel):
    status: str
    message: str
    account_count: int


class BulkAccountMutationPayload(StrictModel):
    status: str
    success_count: int
    errors: list[str] = Field(default_factory=list)


for model in (
    QuotaStatusPayload,
    AccountQuotaBucketsPayload,
    AccountQuotaStatusPayload,
    AccountStatePayload,
    AdminAccountPayload,
    AccountsListPayload,
    AccountMutationPayload,
    BulkAccountMutationPayload,
):
    model.model_rebuild()
