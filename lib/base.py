import uuid
import struct
from collections import namedtuple

import msgpack
from tornado.tcpserver import TCPServer
from tornado.iostream import StreamClosedError

Address = namedtuple('Address', 'ip port')

BUFFER_SIZE = 4096

# 隧道所有的交互类型
HEART_BEAT = '1'
SYNC_CONFIG = '2'
TCP_REVERSE_PROXY = '3'
TCP_FORWARD_AGENT = '4'


class TunnelKeyError(Exception):
    def __init__(self):
        super().__init__(self)  # 初始化父类
        self.errorinfo = "tunnel's key is not in server or repeat connection"

    def __str__(self):
        return self.errorinfo


# cipher = None  # 加密对象
class BaseStream(object):
    def __init__(self, stream):
        self.stream = stream  # 必须初始化流
        self.buffer = bytes()  # 数据缓存

    def __getattr__(self, item):
        return getattr(self.stream, item)

    async def read_bytes(self, num_bytes, partial):
        raise NotImplementedError

    async def write(self, data):
        raise NotImplementedError


class ProxyStream(BaseStream):
    def __init__(self, stream, cipher=None):
        super(ProxyStream, self).__init__(stream)
        self.cipher = cipher

    async def read_bytes(self, num_bytes=BUFFER_SIZE, partial=True):
        buf = await self.stream.read_bytes(num_bytes, partial)
        # print('recv' + str(buf))
        if not self.cipher:
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
                        buf = self.cipher.decrypt(buf)
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
        if not self.cipher:
            await self.stream.write(data)
        else:
            data = self.cipher.encrypt(data)
            data = struct.pack(">H", len(data)) + data
            # print('send' + str(data))
            await self.stream.write(data)


# 如果有需要再添加加密逻辑
class TunnelStream(BaseStream):
    def __init__(self, stream=None):
        super(TunnelStream, self).__init__(stream)
        self.key = None  # 客户端唯一标识
        self.streams = {}  # 存放所有通过隧道的临时stream,包括流入和流出的stream

    async def read_bytes(self, num_bytes=BUFFER_SIZE, partial=True):
        buf = await self.stream.read_bytes(num_bytes, partial)
        # print('recv' + str(buf))
        if not len(buf):  # 被close的时候会收到 b'',单独处理
            return buf

        self.buffer = self.buffer + buf
        data_list = []
        while True:
            if len(self.buffer) >= 2:
                length = struct.unpack(">H", self.buffer[:2])[0]
                if len(self.buffer) >= length + 2:
                    buf = self.buffer[2:length + 2]
                    self.buffer = self.buffer[length + 2:]
                    data_list.append(msgpack.loads(buf))  # 这里可能返回 b''
                else:
                    # 完整数据未到
                    if not data_list:
                        data_list = None
                    break
            else:
                # 完整数据未到
                if not data_list:
                    data_list = None
                break
        return data_list

    async def write(self, data):
        # print('send' + str(data))
        data = msgpack.dumps(data)
        data = struct.pack(">H", len(data)) + data
        await self.stream.write(data)


# 隧道服务用到的监听类
class TunnelListener(TCPServer):
    def __init__(self, cfg_id, method, *args, **kwargs):
        self.cfg_id = cfg_id  # 对应客户端配置的 id
        self.method = method  # 目前是 正向还是反向代理
        self.tunnel_stream = None  # 对应的隧道

        super(TunnelListener, self).__init__(*args, **kwargs)

    # 设置隧道流
    def set_remote_stream(self, stream):
        self.tunnel_stream = stream

    async def handle_stream(self, user_stream, address):
        # 没有隧道就直接返回
        if not self.tunnel_stream:
            user_stream.close()
            return

        # 用户请求的id
        user_stream_id = str(uuid.uuid1())
        # 隧道记录请求
        self.tunnel_stream.streams[user_stream_id] = user_stream
        data = {'ty': self.method, 'id': user_stream_id, 'cfg_id': self.cfg_id}

        try:
            # 先处理一下 cfg_id 的交互,这样后面就不用带 cfg_id
            buf = await user_stream.read_bytes(BUFFER_SIZE, True)
            data['data'] = buf
            await self.tunnel_stream.write(data)
            data.pop('cfg_id')

            while True:
                buf = await user_stream.read_bytes(BUFFER_SIZE, True)
                if buf == b"":
                    user_stream.close()
                    self.tunnel_stream.streams.pop(user_stream_id, None)
                data['data'] = buf
                await self.tunnel_stream.write(data)

        except StreamClosedError as e:
            user_stream.close()
            data['data'] = b''
            # 从隧道移除当前user_stream
            self.tunnel_stream.streams.pop(user_stream_id, None)
            # 检查尝试发送关闭请求
            if self.tunnel_stream and not self.tunnel_stream.closed():
                await self.tunnel_stream.write(data)
