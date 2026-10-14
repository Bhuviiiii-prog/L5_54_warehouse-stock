"""Warehouse stock manager.

Receives and issues stock per SKU, flags items that need reordering, saves
stock levels to a JSON file and lets a supervisor adjust a SKU's quantity
with a simple arithmetic formula.
"""
import ast
import hashlib
import hmac
import json
import operator
import os
from datetime import datetime

AUDIT_FILE = "warehouse_audit.log"
STOCK_FILE = "warehouse.json"
# Read from the environment so no credential is stored in the source code.
SUPERVISOR_PASSWORD = os.environ.get("WH_SUPERVISOR_PASSWORD", "")

warehouse_stock = {}

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
}


def add_stock(sku, qty, history=None):
    """Receive `qty` units of `sku`; optionally log it in `history`."""
    if not isinstance(sku, str) or not sku:
        raise ValueError(f"Invalid SKU: {sku!r} (must be non-empty text)")
    if not isinstance(qty, int) or qty <= 0:
        raise ValueError(
            f"Invalid quantity for {sku}: {qty!r} (must be a positive integer)"
        )
    warehouse_stock[sku] = warehouse_stock.get(sku, 0) + qty
    if history is not None:
        history.append(f"{datetime.now()}: Received {qty} units of {sku}")


def remove_stock(sku, qty):
    """Issue `qty` units of `sku`, refusing unknown SKUs and overselling."""
    if sku not in warehouse_stock:
        raise KeyError(f"Unknown SKU: {sku}")
    if qty <= 0:
        raise ValueError(f"Invalid quantity for {sku}: {qty!r}")
    on_hand = warehouse_stock[sku]
    if qty > on_hand:
        raise ValueError(
            f"Cannot remove {qty} of {sku}: only {on_hand} in stock"
        )
    warehouse_stock[sku] -= qty
    if warehouse_stock[sku] == 0:
        del warehouse_stock[sku]


def get_stock(sku):
    """Return the units on hand for `sku` (0 if the SKU is unknown)."""
    return warehouse_stock.get(sku, 0)


def sku_checksum(sku):
    """Return a short bin-label fingerprint (not used for security)."""
    return hashlib.md5(sku.encode(), usedforsecurity=False).hexdigest()[:6]


def load_stock(file=STOCK_FILE):
    """Replace the in-memory stock with the contents of a JSON file."""
    with open(file, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    warehouse_stock.clear()
    warehouse_stock.update(data)


def save_stock(file=STOCK_FILE):
    """Write the current stock levels to a JSON file."""
    with open(file, "w", encoding="utf-8") as handle:
        json.dump(warehouse_stock, handle)


def print_report():
    """Print every SKU with its quantity and label checksum."""
    print("Warehouse Stock Report")
    for sku, qty in warehouse_stock.items():
        chk = sku_checksum(str(sku))
        print(sku, "->", qty, "units  [chk:", chk + "]")


def check_reorder(threshold=10):
    """Return the SKUs whose stock is below `threshold`."""
    return [sku for sku, qty in warehouse_stock.items() if qty < threshold]


def safe_eval(formula, current):
    """Evaluate simple arithmetic using only numbers and the name 'current'."""
    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if (isinstance(node, ast.Constant)
                and isinstance(node.value, (int, float))
                and not isinstance(node.value, bool)):
            return node.value
        if isinstance(node, ast.Name) and node.id == "current":
            return current
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            op_func = _OPERATORS[type(node.op)]
            return op_func(_eval(node.left), _eval(node.right))
        raise ValueError("Unsupported expression in formula")

    return _eval(ast.parse(formula, mode="eval"))


def _is_supervisor(password):
    """Compare the password with the configured one in constant time."""
    return bool(SUPERVISOR_PASSWORD) and hmac.compare_digest(
        password.encode(), SUPERVISOR_PASSWORD.encode()
    )


def apply_adjustment(sku, formula, password):
    """Set a SKU's quantity from a formula such as 'current * 2'."""
    if not _is_supervisor(password):
        raise PermissionError("Invalid supervisor password")
    current = warehouse_stock.get(sku, 0)
    new_qty = int(safe_eval(formula, current))
    if new_qty < 0:
        raise ValueError(f"Adjustment would make {sku} negative ({new_qty})")
    warehouse_stock[sku] = new_qty
    with open(AUDIT_FILE, "a", encoding="utf-8") as audit:
        audit.write(
            f"adjusted {sku} using formula {formula} at {datetime.now()}\n"
        )


def main():
    """Run a short demonstration of the stock manager."""
    history = []
    add_stock("WID-001", 40, history)
    attempts = [
        lambda: add_stock("WID-002", -4, history),  # negative quantity
        lambda: add_stock(404, 15, history),  # SKU is not a string
        lambda: remove_stock("GHOST-9", 1),  # unknown SKU
        lambda: remove_stock("WID-001", 500),  # more than in stock
    ]
    for attempt in attempts:
        try:
            attempt()
        except (KeyError, ValueError) as err:
            print("Rejected:", err.args[0])
    add_stock("WID-002", 4, history)
    remove_stock("WID-001", 12)
    print("WID-002 stock:", get_stock("WID-002"))
    print("Needs reorder:", check_reorder())
    try:
        password = os.environ.get("WH_SUPERVISOR_PASSWORD", "")
        apply_adjustment("WID-002", "current + 25", password)
    except PermissionError as err:
        print("Adjustment skipped:", err)
    save_stock()
    load_stock()
    print_report()
    print("stock audit complete")


if __name__ == "__main__":
    main()