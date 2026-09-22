from sales.orders.domain.model.aggregate import Order  # ARCH-058: flattened, not mirrored


def test_given_new_order__when_created__then_lines_empty() -> None:
    order = Order(id="1")
    assert order.lines == []
