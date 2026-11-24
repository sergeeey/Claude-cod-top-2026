import sys
from decimal import Decimal

sys.path.insert(0, sys.argv[1])
import client_lib as L  # noqa: E402

print(L.parse_record("A-100, Widget, 4, 2.50"))
print(L.format_price(Decimal("19.9")), L.format_price("19.9"), L.format_price(19.9))
