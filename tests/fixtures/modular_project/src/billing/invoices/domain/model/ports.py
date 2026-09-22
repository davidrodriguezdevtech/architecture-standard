from __future__ import annotations

from typing import Protocol

from billing.invoices.domain.model.aggregate import Invoice
from billing.shared.ids import InvoiceId


class InvoiceRepository(Protocol):
    def get(self, invoice_id: InvoiceId) -> Invoice: ...
    def add(self, invoice: Invoice) -> None: ...
