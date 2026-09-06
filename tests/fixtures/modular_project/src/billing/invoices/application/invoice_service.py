from __future__ import annotations

from dataclasses import dataclass

from billing.invoices.domain.model.invoice import Invoice
from billing.invoices.domain.model.ports import InvoiceRepository
from billing.shared.ids import InvoiceId


@dataclass(frozen=True)
class CreateInvoice:
    invoice_id: str
    amount: float


class InvoiceService:
    def __init__(self, invoices: InvoiceRepository) -> None:
        self._invoices = invoices

    def create_invoice(self, command: CreateInvoice) -> None:
        self._invoices.add(Invoice(id=InvoiceId(command.invoice_id), amount=command.amount, status="pending"))
