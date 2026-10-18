from urllib.parse import quote

from . import transport

kinds = ("AccumulationRegister_", "AccountingRegister_")


def register(entity):
    transport.object_name(entity)
    if not entity.startswith(kinds):
        raise ValueError("entity must start with AccumulationRegister_ or AccountingRegister_")
    return entity


def virtual(entity, table, args, offset, limit):
    inner = ",".join(f"{k}={v}" for k, v in args.items())
    path = quote(f"{register(entity)}/{table}({inner})", safe="/()'=,")
    try:
        return transport.rows(path, {}, offset, limit)
    except LookupError as exc:
        raise LookupError(
            f"virtual table {entity}/{table} is not available, the register may be unpublished. "
            "Try onec_postings for raw records"
        ) from exc


def balances(entity, at, condition, offset, limit):
    args = {"Period": f"datetime'{transport.moment(at)}'"}
    if condition:
        args["Condition"] = transport.literal(condition)
    return virtual(entity, "Balance", args, offset, limit)


def turnovers(entity, since, until, condition, offset, limit):
    args = {
        "StartPeriod": f"datetime'{transport.moment(since)}'",
        "EndPeriod": f"datetime'{transport.moment(until, day_end=True)}'",
    }
    if condition:
        args["Condition"] = transport.literal(condition)
    return virtual(entity, "Turnovers", args, offset, limit)
