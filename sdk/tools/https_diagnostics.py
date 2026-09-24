# SPDX-License-Identifier: GPL-3.0-or-later
"""An explicit, read-only HTTPS HEAD check through the companion's worker."""
import time
from https_worker import Exchange, Policy
from store_client import store_origin


def probe(origin, ca_file=None):
    origin = store_origin(origin)
    status = None
    policy = Policy((origin,), methods=('HEAD',), ca_file=str(ca_file) if ca_file is not None else None)
    with Exchange(policy, origin + '/', method='HEAD', response_limit=0, timeout_ms=10000) as exchange:
        while True:
            event = exchange.poll()
            if event is None:
                time.sleep(.005)
                continue
            if event['kind'] == 'response':
                status = event['status']
            elif event['kind'] in ('done', 'error'):
                return {'origin': origin, 'trust': 'explicit-ca' if ca_file is not None else 'native-system',
                        'status': 'passed' if event['kind'] == 'done' else 'failed',
                        'http_status': status, 'error': event.get('code'),
                        'worker_stopped': not exchange.process.is_alive()}
            exchange.acknowledge()
