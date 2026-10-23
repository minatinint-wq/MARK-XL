"""Classify nested Live API failures without dropping the microphone on 1011."""

def failure_details(error):
    leaves = []
    pending = [error]
    while pending:
        current = pending.pop()
        children = getattr(current, 'exceptions', None)
        if children:
            pending.extend(children)
        else:
            leaves.append(current)
    descriptions = ' '.join(str(e) for e in leaves).lower()
    codes = {str(getattr(e, 'code', '')) for e in leaves}
    if '429' in codes or any(s in descriptions for s in ('429', 'resource_exhausted', 'quota', 'rate limit')):
        return 'quota', '429'
    if codes.intersection({'1011', '1006', '500', '502', '503', '504'}) or any(
        s in descriptions for s in ('1011', '1006', 'internal error', 'connection closed', 'timed out', 'timeout')
    ) or any(isinstance(e, (ConnectionError, TimeoutError)) for e in leaves):
        return 'transient', '1011' if '1011' in descriptions or '1011' in codes else 'conexao'
    if '1008' in codes or '1008' in descriptions or 'policy violation' in descriptions:
        return 'policy', '1008'
    return 'other', type(leaves[0]).__name__ if leaves else type(error).__name__


def retry_delay(kind, attempt):
    exponent = min(max(int(attempt) - 1, 0), 6)
    if kind == 'quota':
        return min(10.0 * 2 ** exponent, 60.0)
    if kind == 'transient':
        return min(0.75 * 2 ** exponent, 15.0)
    return min(1.0 * 2 ** exponent, 30.0)
