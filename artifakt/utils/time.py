def duration_string(amount: int, units='seconds', res=2) -> str:
    """Human readable duration.
    Based on: http://stackoverflow.com/a/26781642/11722
    """

    if amount < 1 and units == 'seconds':
        return '0 ' + units

    def process_time(_amount: int, _units: str) -> str:

        intervals = [1, 60,
                     60 * 60,
                     60 * 60 * 24,
                     60 * 60 * 24 * 7,
                     60 * 60 * 24 * 7 * 4,
                     60 * 60 * 24 * 7 * 4 * 12,
                     60 * 60 * 24 * 7 * 4 * 12 * 100,
                     60 * 60 * 24 * 7 * 4 * 12 * 100 * 10]
        names = [('second', 'seconds'),
                 ('minute', 'minutes'),
                 ('hour', 'hours'),
                 ('day', 'days'),
                 ('week', 'weeks'),
                 ('month', 'months'),
                 ('year', 'years'),
                 ('century', 'centuries'),
                 ('millennium', 'millennia')]

        result = []

        unit = list(map(lambda x: x[1], names)).index(_units)
        # Convert to seconds
        _amount *= intervals[unit]

        for _i in range(len(names) - 1, -1, -1):
            a = int(_amount // intervals[_i])
            if a > 0:
                result.append((a, names[_i][1 % a]))
                _amount -= a * intervals[_i]

        return result

    rd = process_time(amount, units)
    cont = 0
    for u in rd:
        if u[0] > 0:
            cont += 1

    cont = min(res, cont)

    buf = ''
    i = 0
    for u in rd:
        if u[0] > 0:
            buf += "%s %s" % (u[0], u[1])
            cont -= 1

        if i+1 == res:
            break

        if i < (len(rd) - 1):
            if cont > 1:
                buf += ", "
            else:
                buf += " and "

        i += 1

    return buf
