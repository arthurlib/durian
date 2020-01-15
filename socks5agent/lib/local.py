SOCKS5_CONN = 1
SOCKS5_AUTH = 2
SOCKS5_CONFIRM = 3
SOCKS5_DONE = 4


class LocalSocket(object):
    def __init__(self, sock, socks5_status=0):
        self.sock = sock
        # 标识 socks5 协议进行到哪一步
        self.socks5_protocol_status = socks5_status  # 0: 无效

    def __getattr__(self, item):
        return getattr(self.sock, item)


BUFFER_SIZE = 1024
