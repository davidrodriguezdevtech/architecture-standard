from __future__ import annotations

from pathlib import Path

from arch_standard.checks.ast_rules import AstRulesCheck
from arch_standard.checks.base import CheckReport, Outcome, ProjectLayout
from arch_standard.rules.catalog import Catalog, packaged_rules_dir

FIX = Path(__file__).parent.parent / "fixtures"
RULES = packaged_rules_dir()


def _reports(project_name: str) -> dict[str, CheckReport]:
    layout = ProjectLayout.detect(FIX / project_name)
    return {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}


def test_good_project_events_and_vos_pass() -> None:
    reports = _reports("good_project")
    assert reports["ARCH-023"].outcome is Outcome.PASS
    assert reports["ARCH-031"].outcome is Outcome.PASS


def test_bad_project_event_not_frozen_or_past_tense() -> None:
    r = _reports("bad_project")["ARCH-023"]
    assert r.outcome is Outcome.FAIL
    assert any("PlaceOrder" in f.message for f in r.findings)


def test_bad_project_value_object_not_frozen() -> None:
    r = _reports("bad_project")["ARCH-031"]
    assert r.outcome is Outcome.FAIL
    assert any("Email" in f.message for f in r.findings)


def test_good_test_naming_passes() -> None:
    assert _reports("good_project")["ARCH-040"].outcome is Outcome.PASS


def test_bad_test_naming_warns() -> None:
    r = _reports("bad_project")["ARCH-040"]
    assert r.outcome is Outcome.WARN
    assert any("test_add_line_works" in f.message for f in r.findings)


def test_promotion_thresholds_pass_on_small_fixture() -> None:
    assert _reports("good_project")["ARCH-041"].outcome is Outcome.PASS


def test_good_aggregate_encapsulation_passes() -> None:
    reports = _reports("good_project")
    assert reports["ARCH-019"].outcome is Outcome.PASS
    assert reports["ARCH-018"].outcome is Outcome.PASS


def test_bad_aggregate_public_collection_warns_arch_019() -> None:
    # ARCH-019 is level: SHOULD in the catalog, so a violation WARNs (does not
    # affect exit code) rather than FAILing — outcome comes from Rule.level.
    r = _reports("bad_project")["ARCH-019"]
    assert r.outcome is Outcome.WARN
    assert any("lines" in f.message for f in r.findings)


def test_bad_service_size_warns_arch_030() -> None:
    r = _reports("bad_project")["ARCH-030"]
    assert r.outcome is Outcome.WARN
    assert any("method" in f.message.lower() or "param" in f.message.lower() for f in r.findings)


def test_good_service_size_passes() -> None:
    assert _reports("good_project")["ARCH-030"].outcome is Outcome.PASS


def test_given_a_service_with_8_async_public_methods__when_checked__then_arch_030_warns(
    tmp_path: Path,
) -> None:
    # I6: async def methods were invisible to ARCH-030's method-count
    # threshold before (ast.AsyncFunctionDef is not a subclass of
    # ast.FunctionDef) — an all-async service of any size silently PASSed.
    root = tmp_path / "p"
    app_dir = root / "src/sales/orders/application"
    app_dir.mkdir(parents=True)
    methods = "\n".join(f"    async def op_{i}(self): ...\n" for i in range(8))
    (app_dir / "order_service.py").write_text(f"class OrderService:\n{methods}", encoding="utf-8")
    layout = ProjectLayout.detect(root)
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}
    r = reports["ARCH-030"]
    assert r.outcome is Outcome.WARN
    assert any("8 public methods" in f.message for f in r.findings)


def test_given_the_modular_fixture__when_checked__then_all_ast_rules_pass() -> None:
    layout = ProjectLayout.detect(FIX / "modular_project")
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}
    for rid in ("ARCH-018", "ARCH-019", "ARCH-023", "ARCH-031", "ARCH-049"):
        assert reports[rid].outcome is Outcome.PASS, rid


def test_given_a_module_with_two_aggregate_files__when_checked__then_arch_049_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "p"
    model = root / "src/sales/users/domain/model"
    model.mkdir(parents=True)
    (root / "src/sales/users/application").mkdir(parents=True)
    (model / "user.py").write_text("class User:\n    pass\n", encoding="utf-8")
    (model / "profile.py").write_text("class Profile:\n    pass\n", encoding="utf-8")
    layout = ProjectLayout.detect(root)
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-049"].outcome is Outcome.FAIL


def _app_module(tmp_path: Path, body: str) -> ProjectLayout:
    app = tmp_path / "src" / "sales" / "orders" / "application"
    app.mkdir(parents=True)
    (tmp_path / "src" / "sales" / "orders" / "domain").mkdir(parents=True)
    (app / "order_service.py").write_text(body, encoding="utf-8")
    return ProjectLayout.detect(tmp_path)


def test_given_a_direct_session_commit__when_checked__then_arch_033_fails(
    tmp_path: Path,
) -> None:
    layout = _app_module(
        tmp_path,
        "class OrderService:\n"
        "    def cancel(self, cmd):\n"
        "        order = self._orders.get(cmd.id)\n"
        "        self._orders.session.commit()\n",
    )
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-033"].outcome is Outcome.FAIL


def test_given_a_uow_block__when_checked__then_arch_033_passes(tmp_path: Path) -> None:
    layout = _app_module(
        tmp_path,
        "class OrderService:\n"
        "    def cancel(self, cmd):\n"
        "        with self._uow as uow:\n"
        "            order = self._orders.get(cmd.id)\n"
        "            uow.commit()\n",
    )
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-033"].outcome is Outcome.PASS


def test_given_no_commit_at_all__when_checked__then_arch_033_passes(tmp_path: Path) -> None:
    layout = _app_module(
        tmp_path,
        "class OrderService:\n    def find(self, cmd):\n        return self._orders.get(cmd.id)\n",
    )
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-033"].outcome is Outcome.PASS


def test_bad_project_commits_outside_unit_of_work() -> None:
    r = _reports("bad_project")["ARCH-033"]
    assert r.outcome is Outcome.FAIL
    assert any("cancel" in f.message for f in r.findings)


def test_given_the_modular_fixture__when_checked__then_arch_033_passes() -> None:
    assert _reports("modular_project")["ARCH-033"].outcome is Outcome.PASS


def test_given_the_good_fixture__when_checked__then_arch_033_passes() -> None:
    assert _reports("good_project")["ARCH-033"].outcome is Outcome.PASS


def test_given_an_async_with_uow_block__when_checked__then_arch_033_passes(
    tmp_path: Path,
) -> None:
    layout = _app_module(
        tmp_path,
        "class OrderService:\n"
        "    async def cancel(self, cmd):\n"
        "        async with self._uow as uow:\n"
        "            uow.commit()\n",
    )
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-033"].outcome is Outcome.PASS


def test_given_a_nested_with_binding__when_checked__then_arch_033_still_fails_on_outer_commit(
    tmp_path: Path,
) -> None:
    layout = _app_module(
        tmp_path,
        "class OrderService:\n"
        "    def cancel(self, cmd):\n"
        "        session = self._orders.session\n"
        "        session.commit()\n"
        "        def helper():\n"
        "            with self._uow as session:\n"
        "                session.commit()\n",
    )
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}
    r = reports["ARCH-033"]
    assert r.outcome is Outcome.FAIL
    assert any(f.line == 4 for f in r.findings)


def test_given_a_tuple_target_uow_binding__when_checked__then_arch_033_passes(
    tmp_path: Path,
) -> None:
    layout = _app_module(
        tmp_path,
        "class OrderService:\n"
        "    def cancel(self, cmd):\n"
        "        with self._uow as (uow, ctx):\n"
        "            uow.commit()\n",
    )
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-033"].outcome is Outcome.PASS


def test_given_a_with_block_with_no_as_clause__when_checked__then_arch_033_passes(
    tmp_path: Path,
) -> None:
    layout = _app_module(
        tmp_path,
        "class OrderService:\n"
        "    def cancel(self, cmd):\n"
        "        with self._uow:\n"
        "            self._uow.commit()\n",
    )
    reports = {r.rule_id: r for r in AstRulesCheck().run(layout, Catalog.load(RULES))}
    assert reports["ARCH-033"].outcome is Outcome.PASS
