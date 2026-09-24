# SPDX-License-Identifier: GPL-3.0-or-later
"""Native trust and explicit CA isolation, without modifying system certificates."""
from pathlib import Path
import ssl
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sdk/tools'))
from https_diagnostics import probe
from store_client import StoreClient, StoreError
from tls_context import client_context, TrustError
from test_sdk_https_worker import tls_server


def test_native_context_does_not_patch_global_ssl_and_requires_verification():
    import truststore
    original = ssl.SSLContext
    context = client_context()
    assert isinstance(context, truststore.SSLContext)
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2
    assert ssl.SSLContext is original


def test_unavailable_native_trust_does_not_fall_back_to_ambient_ca_files(monkeypatch):
    monkeypatch.setitem(sys.modules, 'truststore', None)
    with pytest.raises(TrustError, match='Native HTTPS trust is unavailable'):
        client_context()
    # StoreClient constructs certificate contexts in its disposable child;
    # unavailable-trust propagation across that boundary is tested separately.


def test_store_rejects_untrusted_chain_and_wrong_hostname_before_credentials(tls_server):
    origin, cert, requests = tls_server
    count = len(requests)
    token = 'lfsdk1_' + 'a' * 64
    for target, ca in ((origin, None), (origin.replace('localhost', '127.0.0.1'), cert)):
        with pytest.raises(StoreError, match='securely') as error:
            StoreClient(target, ca_file=ca, token=token).request('/sdk/me')
        assert error.value.status == 0 and token not in str(error.value) and cert not in str(error.value)
    assert len(requests) == count


def test_explicit_ca_is_a_local_context_without_changing_native_trust(tls_server):
    origin, cert, requests = tls_server
    context = client_context(cert)
    assert type(context) is ssl.SSLContext and context.check_hostname
    count = len(requests)
    token = 'lfsdk1_' + 'b' * 64
    # This fixture intentionally serves binary data. Reaching its HTTP response
    # verifies TLS; the store client's separate content validator must still fail.
    with pytest.raises(StoreError, match='invalid response') as error:
        StoreClient(origin, ca_file=cert, token=token).request('/sdk/me')
    assert error.value.status == 200
    assert len(requests) == count + 1 and requests[-1][2]['Authorization'] == 'Bearer ' + token
    with pytest.raises(StoreError, match='securely'):
        StoreClient(origin, token=token).request('/sdk/me')
    assert len(requests) == count + 1


def test_explicit_ca_works_when_native_trust_dependency_is_unavailable(monkeypatch, tls_server):
    _, cert, _ = tls_server
    monkeypatch.setitem(sys.modules, 'truststore', None)
    assert type(client_context(cert)) is ssl.SSLContext


def test_spawned_diagnostic_checks_tls_without_claiming_http_application_health(tls_server):
    origin, cert, requests = tls_server
    # BaseHTTPRequestHandler returns 501 for this fixture's unimplemented HEAD.
    result = probe(origin, cert)
    assert result == {'origin': origin, 'trust': 'explicit-ca', 'status': 'passed',
                      'http_status': 501, 'error': None, 'worker_stopped': True}
    assert not any(request[0] == 'HEAD' for request in requests)
    result = probe(origin)
    assert result['status'] == 'failed' and result['error'] == 'tls'
    assert result['http_status'] is None and result['worker_stopped']
