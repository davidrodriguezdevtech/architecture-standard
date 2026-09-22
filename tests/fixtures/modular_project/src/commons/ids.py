from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InvoiceId:
    value: str


@dataclass(frozen=True)
class OrderId:
    value: str


@dataclass(frozen=True)
class UserId:
    value: str
