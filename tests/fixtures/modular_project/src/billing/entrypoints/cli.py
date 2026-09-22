from __future__ import annotations

from billing.invoices.application.invoice import CreateInvoice, InvoiceService


def create(service: InvoiceService, invoice_id: str, amount: float) -> None:
    service.create_invoice(CreateInvoice(invoice_id=invoice_id, amount=amount))
