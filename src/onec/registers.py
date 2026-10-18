from . import transport

VIRTUALS = ("Balance", "Turnovers", "BalanceAndTurnovers", "Records")


def _strip_kind(entity):
    for kind in ("AccumulationRegister_", "AccountingRegister_"):
        if entity.startswith(kind):
            return kind[:-1], entity[len(kind):]
    raise ValueError("entity must start with AccumulationRegister_ or AccountingRegister_")


def available_virtuals(entity):
    # entity example: AccumulationRegister_ТоварыНаСкладах
    _kind, name = _strip_kind(entity)
    meta = transport.get("$metadata")
    found = []
    for v in VIRTUALS:
        # function import or entity set like AccumulationRegister_ТоварыНаСкладах_Balance
        if f'Name="{name}_{v}"' in meta or f'Name="{entity}_{v}"' in meta:
            found.append(v)
    return found


def balances(entity, since, until, offset=0, limit=100, extra_filter=""):
    _kind, name = _strip_kind(entity)
    f = f"Period ge datetime'{since}' and Period le datetime'{until}'"
    if extra_filter:
        f += f" and {extra_filter}"
    # virtual table syntax: <Register>_Balance(Period=..., Condition=...)
    params = {
        "Period": f"datetime'{since}'",
        "Condition": extra_filter or "",
        "$top": limit,
        "$skip": offset,
    }
    url = f"{entity}_Balance"
    try:
        rows = transport.get(url, params, cache=False, entity_encoded=True)
    except Exception as e:
        raise RuntimeError(
            f"virtual table {entity}_Balance is not available via OData "
            f"({e.__class__.__name__}). The configuration may not publish register "
            "virtual tables. Use onec_postings on the plain register or check publication."
        ) from e
    total, next_offset = transport.page(rows, offset, limit)[1:]
    return {"items": rows, "total": total, "next_offset": next_offset}


def turnovers(entity, since, until, offset=0, limit=100, extra_filter=""):
    _kind, name = _strip_kind(entity)
    params = {
        "StartPeriod": f"datetime'{since}'",
        "EndPeriod": f"datetime'{until}'",
        "Condition": extra_filter or "",
        "$top": limit,
        "$skip": offset,
    }
    try:
        rows = transport.get(f"{entity}_Turnovers", params, cache=False, entity_encoded=True)
    except Exception as e:
        raise RuntimeError(
            f"virtual table {entity}_Turnovers is not available via OData "
            f"({e.__class__.__name__}). The configuration may not publish register "
            "virtual tables. Use onec_postings on the plain register or check publication."
        ) from e
    total, next_offset = transport.page(rows, offset, limit)[1:]
    return {"items": rows, "total": total, "next_offset": next_offset}
