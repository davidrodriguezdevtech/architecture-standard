from __future__ import annotations

from arch_standard.checks.ast_rules import AstRulesCheck
from arch_standard.checks.banned_symbols import BannedSymbolsCheck
from arch_standard.checks.base import Check
from arch_standard.checks.import_contracts import ImportContractsCheck
from arch_standard.checks.schemas import IntegrationEventSchemaCheck


def all_checks() -> list[Check]:
    return [
        ImportContractsCheck(),
        AstRulesCheck(),
        BannedSymbolsCheck(),
        IntegrationEventSchemaCheck(),
    ]
