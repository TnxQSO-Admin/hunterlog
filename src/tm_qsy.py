"""
Local patch: offload QSY to TeensyMaestro CE.

Not intended for upstream. This module is new, so it can never conflict
during a rebase onto upstream/dev10.

When the environment variable HUNTERLOG_TM_RCS is set to "host:port", a
frequency click first asks TeensyMaestro to load the matching global radio
profile and then tune. When the variable is unset, or the device declines
because no profile exists for that band and mode, the caller falls back to
its normal CAT path.
"""

import logging
import os
import socket

log = logging.getLogger(__name__)

ENV_KEY = "HUNTERLOG_TM_RCS"

# The remote command server replies as soon as it has validated the request;
# it never waits for the radio. A short timeout is therefore safe and keeps
# the user interface responsive.
TIMEOUT_S = 1.0


def _endpoint():
    """Parse HUNTERLOG_TM_RCS into (host, port), or None when disabled."""
    raw = os.environ.get(ENV_KEY, "").strip()
    if not raw:
        return None

    host, sep, port = raw.rpartition(":")
    if not sep or not host:
        log.warning("%s is set but not in host:port form: %r", ENV_KEY, raw)
        return None

    try:
        return (host, int(port))
    except ValueError:
        log.warning("%s has a non numeric port: %r", ENV_KEY, raw)
        return None


def qsy(freq_hz, mode):
    """
    Ask TeensyMaestro to load a global profile and tune to freq_hz.

    :param freq_hz: frequency in hertz
    :param mode str: mode string as it arrives from spot data
    :returns: True when the device accepted the request, meaning the caller
              should skip its own frequency and mode commands. False in
              every other case, including when the feature is disabled.
    """
    endpoint = _endpoint()
    if endpoint is None:
        return False

    line = "QSY {0} {1}\r\n".format(int(freq_hz), str(mode).upper())

    try:
        with socket.create_connection(endpoint, timeout=TIMEOUT_S) as sock:
            sock.settimeout(TIMEOUT_S)
            sock.sendall(line.encode("ascii"))
            reply = sock.recv(128).decode("ascii", "replace").strip()
    except OSError as ex:
        log.warning("TM RCS unreachable at %s:%s: %s",
                    endpoint[0], endpoint[1], ex)
        return False

    if reply.startswith("OK"):
        log.debug("TM RCS accepted: %s", line.strip())
        return True

    # ERR no_profile, ERR unknown_band and friends all land here. The caller
    # then performs a normal CAT qsy, which also sets the mode.
    log.info("TM RCS declined '%s': %s", line.strip(), reply)
    return False
