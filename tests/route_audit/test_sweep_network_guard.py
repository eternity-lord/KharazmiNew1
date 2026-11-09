import subprocess
import sys


def test_independent_runner_guard_blocks_http_urllib_and_socket_calls():
    code = r"""
import socket
import urllib.request
import requests
from tests.route_audit.sweep.common import block_external_network_calls

block_external_network_calls()
sock = socket.socket()
calls = [
    lambda: requests.post("not-a-url"),
    lambda: requests.request("GET", "not-a-url"),
    lambda: requests.sessions.Session().request("GET", "not-a-url"),
    lambda: urllib.request.urlopen("not a url"),
    lambda: socket.create_connection(None),
    lambda: sock.connect(None),
    lambda: sock.connect_ex(None),
]
for call in calls:
    try:
        call()
    except AssertionError as error:
        assert "blocked an external network call" in str(error)
    else:
        raise AssertionError("network guard allowed an attempted call")
sock.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
