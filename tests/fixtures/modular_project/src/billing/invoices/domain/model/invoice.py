from __future__ import annotations

from dataclasses import dataclass

from billing.shared.ids import InvoiceId


@dataclass
class Invoice:
    id: InvoiceId
    amount: float
    status: str

    def mark_paid(self) -> None:
        self.status = "paid"
