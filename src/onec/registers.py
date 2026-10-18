from urllib.parse import quote

from . import transport

totals_kinds = ("AccumulationRegister_", "AccountingRegister_")


def register(entity, prefixes):
    transport.object_name(entity)
    if not entity.startswith(prefixes):
        raise ValueError(f"entity must start with {' or '.join(prefixes)}")
    return entity


def virtual(entity, table, args, prefixes, offset, limit, query=None):
    inner = ",".join(f"{k}={v}" for k, v in args.items())
    path = quote(f"{register(entity, prefixes)}/{table}({inner})", safe="/()'=,")
    try:
        return transport.rows(path, query or {}, offset, limit)
    except LookupError as exc:
        raise LookupError(
            f"virtual table {entity}/{table} is not available, the register may be unpublished. "
            "Try onec_postings for raw records"
        ) from exc


def with_condition(args, condition):
    if condition:
        args["Condition"] = transport.literal(condition)
    return args


def balances(entity, at, condition, offset, limit):
    args = with_condition({"Period": f"datetime'{transport.moment(at)}'"}, condition)
    return virtual(entity, "Balance", args, totals_kinds, offset, limit)


def turnovers(entity, since, until, condition, offset, limit):
    args = with_condition({
        "StartPeriod": f"datetime'{transport.moment(since)}'",
        "EndPeriod": f"datetime'{transport.moment(until, day_end=True)}'",
    }, condition)
    return virtual(entity, "Turnovers", args, totals_kinds, offset, limit)


def balance_turnovers(entity, since, until, condition, offset, limit):
    args = with_condition({
        "StartPeriod": f"datetime'{transport.moment(since)}'",
        "EndPeriod": f"datetime'{transport.moment(until, day_end=True)}'",
    }, condition)
    return virtual(entity, "BalanceAndTurnovers", args, totals_kinds, offset, limit)


def slice_of(entity, edge, at, condition, offset, limit):
    if edge not in ("last", "first"):
        raise ValueError("edge is last or first")
    args = with_condition({"Period": f"datetime'{transport.moment(at, day_end=edge == 'last')}'"}, condition)
    return virtual(entity, "SliceLast" if edge == "last" else "SliceFirst", args, ("InformationRegister_",), offset, limit)
