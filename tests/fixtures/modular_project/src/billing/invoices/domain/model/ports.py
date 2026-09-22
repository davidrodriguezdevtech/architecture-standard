from __future__ import annotations

from abc import ABC, abstractmethod

from billing.invoices.domain.model.aggregate import Invoice
from billing.shared.ids import InvoiceId


class InvoiceRepository(ABC):
    @abstractmethod
    def get(self, invoice_id: InvoiceId) -> Invoice: ...
    @abstractmethod
    def add(self, invoice: Invoice) -> None: ...
