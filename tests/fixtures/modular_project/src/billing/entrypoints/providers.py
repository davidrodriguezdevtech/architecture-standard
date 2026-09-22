from __future__ import annotations

from billing.invoices.application.invoice import InvoiceService
from billing.invoices.domain.model.ports import InvoiceRepository


def invoice_service(invoices: InvoiceRepository) -> InvoiceService:
    """Wire InvoiceService from the repository singleton the bootstrap container built.

    entrypoints/cli.py and entrypoints/http.py get their wired InvoiceService
    from this module only, never by constructing it themselves.
    """
    return InvoiceService(invoices)
