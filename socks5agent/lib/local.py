import struct

from proxy.socks5agent.lib import cipher

SOCKS5_CONN = '1'
SOCKS5_AUTH = '2'
SOCKS5_AUTH_REPL = '2_1'
SOCKS5_CONFIRM = '3'
SOCKS5_CONFIRM_REPL = '3_1'
SOCKS5_DONE = '4'

# cipher = None  # 加密对象
BUFFER_SIZE = 1024


class LocalSocket(object):
    def __init__(self, sock, socks5_status=None):
        self.sock = sock
        # 标识 socks5 协议进行到哪一步
        self.socks5_protocol_status = socks5_status  # None: 表示不走协议的socket
        # 缓存
        self.buffer = bytes()

    def __getattr__(self, item):
        return getattr(self.sock, item)

    def recv_with_head(self):
        buf = self.sock.recv(BUFFER_SIZE)
        # print('recv' + str(buf))

        if not cipher.cipher:
            return buf
        else:
            if not len(buf):  # 被close的时候会收到 b'',单独处理
                return buf

            self.buffer = self.buffer + buf
            data = bytes()
            for i in range(2):
                if len(self.buffer) >= 2:
                    length = struct.unpack(">H", self.buffer[:2])[0]
                    if len(self.buffer) >= length + 2:
                        buf = self.buffer[2:length + 2]
                        # if cipher.cipher:
                        buf = cipher.cipher.decrypt(buf)
                        self.buffer = self.buffer[length + 2:]
                        data += buf  # 这里可能返回 b''
                    elif i == 0:
                        # 数据未到
                        data = None
                        break
                elif i == 0:
                    # 数据未到
                    data = None
                    break
            return data

    def sendall_with_head(self, data):
        # print('send' + str(data))
        if not cipher.cipher:
            self.sock.sendall(data)
        else:
            # if cipher.cipher:
            data = cipher.cipher.encrypt(data)
            length = len(data)
            data = struct.pack(">H", length) + data
            self.sock.sendall(data)
