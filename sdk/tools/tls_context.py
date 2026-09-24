# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit HTTPS trust policy shared by the store client and app companion."""
import ssl


class TrustError(ValueError):
    pass


def client_context(ca_file=None):
    """Native system trust by default; an explicit CA file replaces that policy.

    Use truststore's context directly, without changing Python's global SSL
    classes. Explicit fixture/private CAs retain normal OpenSSL verification and
    do not add anchors to the user's system trust store.
    """
    if ca_file is not None:
        context = ssl.create_default_context(cafile=ca_file)
    else:
        try:
            import truststore
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except (ImportError, OSError, RuntimeError):
            raise TrustError('Native HTTPS trust is unavailable; install the SDK host dependencies or reinstall the desktop bundle') from None
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.set_alpn_protocols(['http/1.1'])
    return context
