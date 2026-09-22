from sales.orders.domain.model.aggregate import Order


def test_given_new_order__when_add_line__then_line_recorded() -> None:
    order = Order(id=None, _lines=[])
    order.add_line("sku-1")
    assert order._lines == ["sku-1"]
