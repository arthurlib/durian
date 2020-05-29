import struct
from proxy.lib import cipher

# cipher = None  # 加密对象
from proxy.lib.model import BUFFER_SIZE


class ProxyStream(object):
    def __init__(self, stream):
        self.stream = stream
        # 缓存
        self.buffer = bytes()

    def __getattr__(self, item):
        return getattr(self.stream, item)

    async def read_bytes(self, num_bytes=BUFFER_SIZE, partial=True):
        buf = await self.stream.read_bytes(num_bytes, partial)
        # print('recv' + str(buf))

        if not cipher.cipher:
            return buf
        else:
            if not len(buf):  # 被close的时候会收到 b'',单独处理
                return buf

            self.buffer = self.buffer + buf
            data = bytes()
            while True:
                if len(self.buffer) >= 2:
                    length = struct.unpack(">H", self.buffer[:2])[0]
                    if len(self.buffer) >= length + 2:
                        buf = self.buffer[2:length + 2]
                        # if cipher.cipher:
                        buf = cipher.cipher.decrypt(buf)
                        self.buffer = self.buffer[length + 2:]
                        data += buf  # 这里可能返回 b''
                    else:
                        # 完整数据未到
                        if not data:
                            data = None
                        break
                else:
                    # 完整数据未到
                    if not data:
                        data = None
                    break

            # if data:
            #     print(self.buffer)
            #     if len(self.buffer) >= 2:
            #         length = struct.unpack(">H", self.buffer[:2])[0]
            #         print(length)
            #         print(len(self.buffer))
            return data

    async def write(self, data):
        # print('send' + str(data))
        if not cipher.cipher:
            await self.stream.write(data)
        else:
            # if cipher.cipher:
            data = cipher.cipher.encrypt(data)
            length = len(data)
            data = struct.pack(">H", length) + data
            # print('send' + str(data))
            await self.stream.write(data)
