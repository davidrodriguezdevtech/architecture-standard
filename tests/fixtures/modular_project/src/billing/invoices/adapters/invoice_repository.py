from __future__ import annotations

from billing.invoices.domain.model.aggregate import Invoice
from billing.invoices.domain.model.ports import InvoiceRepository
from billing.shared.ids import InvoiceId


class InMemoryInvoiceRepository(InvoiceRepository):
    def __init__(self) -> None:
        self._store: dict[str, Invoice] = {}

    def get(self, invoice_id: InvoiceId) -> Invoice:
        return self._store[invoice_id.value]

    def add(self, invoice: Invoice) -> None:
        self._store[invoice.id.value] = invoice
