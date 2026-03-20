import json
import logging


LOGGER = logging.getLogger(__name__)


def send_msg(sock, **kwargs):
    """Serialize a message as JSON plus a newline and send it over TCP."""
    # Newline framing lets the receiver use readline() safely over a TCP stream.
    payload = json.dumps(kwargs, ensure_ascii=False) + "\n"
    sock.sendall(payload.encode("utf-8"))


def recv_msg(file_obj):
    """
    Read one newline-delimited JSON message.
    Returns a dict on success, or None on EOF / malformed input.
    """
    line = file_obj.readline()
    if not line:
        return None

    line = line.strip()
    if not line:
        return None

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        LOGGER.warning("Failed to decode JSON message: %r", line)
        return None

    if not isinstance(data, dict):
        LOGGER.warning("Expected JSON object but got: %r", data)
        return None

    return data
