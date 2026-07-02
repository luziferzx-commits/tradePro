import socket

from gqos.live.process_lock import SingleInstanceLock


def _free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_single_instance_lock_blocks_second_holder():
    port = _free_port()
    first = SingleInstanceLock("test-live", port)
    second = SingleInstanceLock("test-live", port)

    try:
        assert first.acquire()
        assert not second.acquire()
    finally:
        first.release()
        second.release()
