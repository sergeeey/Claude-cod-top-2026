import threading

from orders import Order, OrderService, PaymentGateway
from warehouse import Warehouse, transfer


def main():
    central = Warehouse("central", {"apple": 50, "pear": 30})
    north = Warehouse("north", {"apple": 20, "pear": 5})
    service = OrderService(central, PaymentGateway(failure_rate=0.1, seed=7), workers=4)
    service.start()

    for i in range(40):
        sku = "apple" if i % 2 else "pear"
        service.submit(Order(f"o{i}", sku, 1 + i % 3, 2.5))

    movers = [
        threading.Thread(target=transfer, args=(north, central, "apple", 5)),
        threading.Thread(target=transfer, args=(central, north, "pear", 3)),
    ]
    for t in movers:
        t.start()
    central.restock_many({"apple": 10, "plum": 4})
    for t in movers:
        t.join()

    service.stop()
    print(central.report())
    print(north.report())
    print("processed:", service.processed)
    print("results:", len(service.drain_results()))


if __name__ == "__main__":
    main()
