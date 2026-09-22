from __future__ import annotations

import dataclasses
from datetime import datetime

from commons.ids import InvoiceId


@dataclasses.dataclass(frozen=True)
class InvoiceCreated:
    invoice_id: InvoiceId
    amount: float
    occurred_at: datetime
