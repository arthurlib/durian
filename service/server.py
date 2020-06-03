import socket
import struct

import tornado
from tornado.gen import multi
from tornado.iostream import StreamClosedError
from tornado.tcpclient import TCPClient
from tornado.tcpserver import TCPServer

from lib.log import logger
from lib.netutil import read_and_send

from lib.base import TunnelStream, ProxyStream, Address, TCP_REVERSE_PROXY, SYNC_CONFIG, HEART_BEAT, TCP_FORWARD_AGENT, \
    BUFFER_SIZE, TunnelListener


class Socks5Agent(TCPServer):
    async def handle_stream(self, stream, address):
        local_stream = stream
        try:
            # 交换协议
            remote_stream = await self.exchange_agreement(local_stream)
            if remote_stream:
                # 交换数据
                await multi([read_and_send(local_stream, remote_stream), read_and_send(remote_stream, local_stream)])
        except StreamClosedError:
            pass
        except Exception as e:
            logger.exception('error')

    async def exchange_agreement(self, local_stream):

        # 获取数据
        buf = await local_stream.read_bytes(1024, True)
        logger.debug(buf)
        if (buf is None) or (not buf or buf[0] != 0x05):  # 验证版本
            local_stream.close()
            return

        # 认证逻辑保留
        # if password:
        #     # 要认证
        #     await stream.write(bytes((0x05, 0x02)))
        #     buf = await stream.read_bytes(1024, True)
        #     if (buf is None) or (not buf or buf[0] != 0x05):  # 验证版本
        #         local_stream.close()
        #         return
        #     # 获取用户名
        #     u_end = 2 + buf[1]
        #     username = buf[2:u_end]
        #     # 获取密码
        #     passwd = buf[u_end + 1: u_end + 1 + buf[u_end]]
        #     if 'zzy' == username and '1234' == passwd:
        #         # 登录成功
        #         await stream.write(bytes((0x05, 0x00)))
        #     else:
        #         # 登录失败
        #         await stream.write(bytes((0x05, 0x01)))
        #         stream.close()
        # else:
        await local_stream.write(bytes((0x05, 0x00)))

        buf = await local_stream.read_bytes(1024, True)
        logger.debug(buf)
        if (buf is None) or (not buf or buf[0] != 0x05):  # 验证版本
            local_stream.close()
            return
        if len(buf) < 7:
            local_stream.close()
            return

        if buf[1] != 0x01:
            local_stream.close()
            return

        dst_ip = None

        dst_port = buf[-2:]
        dst_port = int(dst_port.hex(), 16)

        dst_family = None

        if buf[3] == 0x01:
            # ipv4
            dst_ip = socket.inet_ntop(socket.AF_INET, buf[4:4 + 4])
            dst_address = Address(ip=dst_ip, port=dst_port)
            dst_family = socket.AF_INET
        elif buf[3] == 0x03:
            # domain
            dst_ip = buf[5:-2].decode()
            dst_address = Address(ip=dst_ip, port=dst_port)
            dst_family = 0
        elif buf[3] == 0x04:
            # ipv6
            dst_ip = socket.inet_ntop(socket.AF_INET6, buf[4:4 + 16])
            dst_address = (dst_ip, dst_port, 0, 0)
            dst_family = socket.AF_INET6
        else:
            local_stream.close()
            return

        if dst_family is None:
            # 协议错误
            local_stream.close()
            return

        # 创建iostream
        remote_stream = None
        try:
            tcp_client = TCPClient()
            if dst_family:
                remote_stream = await tcp_client.connect(dst_address[0], dst_address[1], af=dst_family)
            else:
                remote_stream = await tcp_client.connect(dst_address[0], dst_address[1])
        except Exception as e:
            # logger.exception('remote connect error')
            if remote_stream:
                remote_stream.close()
            local_stream.close()
            return None

        await local_stream.write(bytes((0x05, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        return remote_stream


class TCPForwardServer(TCPServer):
    def __init__(self, *args, **kwargs):
        super(TCPForwardServer, self).__init__(*args, **kwargs)
        self.remote_addr = None

    def set_remote_address(self, host, port):
        self.remote_addr = (host, port)

    async def handle_stream(self, stream, address):
        try:
            remote_stream = None
            try:
                # 连接远程
                tcp_client = TCPClient()
                remote_stream = await tcp_client.connect(self.remote_addr[0], self.remote_addr[1])
            except Exception as e:
                logger.exception('remote connect error')
                stream.close()
                if remote_stream:
                    remote_stream.close()
                return None

            # 开始交换数据
            await multi([read_and_send(stream, remote_stream), read_and_send(remote_stream, stream)])
        except StreamClosedError:
            pass
        except Exception as e:
            logger.exception('error')


class Http2Socks5Server(TCPServer):
    def __init__(self, *args, **kwargs):
        super(Http2Socks5Server, self).__init__(*args, **kwargs)
        self.remote_addr = None

    def set_remote_address(self, host, port):
        self.remote_addr = (host, port)

    async def handle_stream(self, stream, address):
        try:
            remote_stream = await self.exchange_agreement(stream)
            if remote_stream:
                await multi([read_and_send(stream, remote_stream), read_and_send(remote_stream, stream)])
        except StreamClosedError:
            pass
        except Exception as e:
            logger.exception('error')

    async def exchange_agreement(self, local_stream):
        # 获取连接
        conn_content = await local_stream.read_bytes(1024, True)
        buf = conn_content.decode()

        host = ""
        port = 0
        for line in buf.split('\r\n'):
            if line.startswith("Host"):
                addr = line[6:]
                if ":" in addr:
                    host, port = addr.split(':')
                    port = int(port)
                else:
                    host = addr
                    port = 80
                break

        host = host.encode()
        host_len = struct.pack('B', len(host))

        # 创建iostream
        remote_stream = None
        try:
            tcp_client = TCPClient()
            remote_stream = await tcp_client.connect(self.remote_addr[0], self.remote_addr[1])
        except Exception as e:
            logger.exception('remote connect error')
            local_stream.close()
            if remote_stream:
                remote_stream.close()
            return None

        # handle socks5
        await remote_stream.write(bytes((0x05, 0x01, 0x00)))  # 发送socks5连接协议
        buf = await remote_stream.read_bytes(1024, True)
        if (buf is None) or (not buf or buf[0] != 0x05):  # 验证版本
            remote_stream.close()
            return
        if not buf[1] == 0x00:
            remote_stream.close()
            return

        # 包装socks5协议，发送确认协议
        data = bytes((0x05, 0x01, 0x00, 0x03)) + host_len + host + struct.pack('>H', port)
        await remote_stream.write(data)  # 发送给socks5代理服务器
        buf = await remote_stream.read_bytes(1024, True)  # 接收响应
        if (buf is None) or (not buf or buf[0] != 0x05):  # 验证版本
            remote_stream.close()
            return

        if buf[1] == 0x00 and port == 443:  # 如果连接是https的话就处理一下https响应
            await local_stream.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        else:
            await remote_stream.write(conn_content)  # 不是https的话就直接把收到的数据发送出去
        return remote_stream


class TunnerlServer(TCPServer):

    def __init__(self, *args, **kwargs):
        super(TunnerlServer, self).__init__(*args, **kwargs)
        self.configs = None  # 服务端的配置信息
        self.streams = {}  # 记录连接上来的隧道
        self.listeners = {}  # 启动的监听，记录在这里
        self.callback = {
            HEART_BEAT: self.handle_pong,
            SYNC_CONFIG: self.handle_sync_config,
            TCP_REVERSE_PROXY: self.handle_tcp_reverse_proxy,
            TCP_FORWARD_AGENT: self.handle_tcp_forward_agent,
        }

    def set_config(self, configs):
        self.configs = configs
        for key, listeners in self.listeners.items():
            for cfg_id, listener in listeners.items():
                listener.close()
        self.listeners = {}
        self.init_confg()

    def init_confg(self):
        for key, cfgs in self.configs.items():
            self.listeners[key] = {}
            for cfg_id, cfg in cfgs.items():
                if cfg['ty'] == TCP_REVERSE_PROXY:
                    listener = TunnelListener(cfg_id, TCP_REVERSE_PROXY)
                    listener.listen(cfg['port'], cfg['host'])
                    self.listeners[key][cfg_id] = listener

    async def handle_stream(self, tunnel_stream, address):
        tunnel_stream = TunnelStream(tunnel_stream)

        while True:
            # print("测试内存泄漏")
            # print(len(self.streams))
            # print(len(tunnel_stream.streams))
            try:
                buf_list = await tunnel_stream.read_bytes(BUFFER_SIZE, True)
                if buf_list is None:
                    continue
                for buf in buf_list:
                    await self.callback[buf['ty']](tunnel_stream, buf)
            except StreamClosedError:
                await self.handle_error(tunnel_stream)
                return
            except Exception as e:
                logger.exception('error')
                await self.handle_error(tunnel_stream)
                return

    # 异常的结束处理
    async def handle_error(self, tunnel_stream):
        tunnel_stream.close()
        for s in tunnel_stream.streams.values():
            s.close()
        # 出错移除隧道
        self.streams.pop(tunnel_stream.key, None)

    async def handle_pong(self, tunnel_stream, buf):
        await tunnel_stream.write({'ty': HEART_BEAT})

    async def handle_sync_config(self, tunnel_stream, buf):
        tunnel_stream_key = buf['key']

        if tunnel_stream_key not in self.configs:  # key不存在直接close
            await tunnel_stream.write({'ty': SYNC_CONFIG, tunnel_stream_key: None})
            tunnel_stream.close()
            return

        # 如果已经被连接了，不能重复连接
        if self.streams.get(tunnel_stream_key):
            await tunnel_stream.write({'ty': SYNC_CONFIG, tunnel_stream_key: None})
            tunnel_stream.close()
            return

        await tunnel_stream.write({'ty': SYNC_CONFIG, tunnel_stream_key: self.configs[tunnel_stream_key]})
        # 设置下发隧道
        for cfg_id, listener in self.listeners[tunnel_stream_key].items():
            listener.set_remote_stream(tunnel_stream)
        self.streams[tunnel_stream_key] = tunnel_stream  # 记录隧道
        tunnel_stream.key = tunnel_stream_key  # 隧道记录自己的key

    async def handle_tcp_reverse_proxy(self, tunnel_stream, buf):
        if buf['data'] != b'':
            await tunnel_stream.streams[buf['id']].write(buf['data'])
        else:
            user_stream = tunnel_stream.streams.pop(buf['id'], None)
            if user_stream:  # 穿透服务记录下的stream
                user_stream.close()

    async def handle_tcp_forward_agent(self, tunnel_stream, buf):
        stream_id = buf['id']
        if buf['data'] == b'':  # 客户端上传的关闭请求
            remote_stream = tunnel_stream.streams.pop(stream_id, None)
            if remote_stream:
                remote_stream.close()
            return

        if stream_id not in tunnel_stream.streams:  # 被关闭的时候有个空数据包
            cfg_id = buf['cfg_id']
            cfg = self.configs[tunnel_stream.key][cfg_id]

            remote_stream = await TCPClient().connect(cfg['remote_host'], cfg['remote_port'])
            tunnel_stream.streams[stream_id] = remote_stream  # 隧道记录请求stream

            async def read_and_send():
                data = {'ty': TCP_FORWARD_AGENT, 'id': stream_id}
                try:
                    while True:
                        buf = await remote_stream.read_bytes(BUFFER_SIZE, True)
                        if buf == b'':
                            remote_stream.close()
                            tunnel_stream.streams.pop(stream_id, None)  # 隧道移除当前stream

                        data['data'] = buf
                        await tunnel_stream.write(data)  # 向隧道写数据

                except StreamClosedError:
                    remote_stream.close()
                    tunnel_stream.streams.pop(stream_id, None)
                    data['data'] = b''
                    if tunnel_stream and not tunnel_stream.closed():  # 隧道可能被外部close
                        await tunnel_stream.write(data)

            tornado.ioloop.IOLoop.current().spawn_callback(read_and_send)  # 异步运行，不断向隧道写数据

        await tunnel_stream.streams[stream_id].write(buf['data'])


class Socks5Server(TCPServer):
    def __init__(self, *args, **kwargs):
        super(Socks5Server, self).__init__(*args, **kwargs)
        self.cipher = None

    def set_cipher(self, cipher):
        self.cipher = cipher

    async def handle_stream(self, stream, address):
        local_stream = ProxyStream(stream, self.cipher)
        try:
            # 交换协议
            remote_stream = await self.exchange_agreement(local_stream)
            if remote_stream:
                # 交换数据
                await multi([read_and_send(local_stream, remote_stream), read_and_send(remote_stream, local_stream)])
        except StreamClosedError:
            pass
        except Exception as e:
            logger.exception('error')

    async def exchange_agreement(self, local_stream):

        # 获取数据
        buf = await local_stream.read_bytes(1024, True)
        logger.debug(buf)
        if (buf is None) or (not buf or buf[0] != 0x05):  # 验证版本
            local_stream.close()
            return

        # 认证逻辑保留
        # if password:
        #     # 要认证
        #     await stream.write(bytes((0x05, 0x02)))
        #     buf = await stream.read_bytes(1024, True)
        #     if (buf is None) or (not buf or buf[0] != 0x05):  # 验证版本
        #         local_stream.close()
        #         return
        #     # 获取用户名
        #     u_end = 2 + buf[1]
        #     username = buf[2:u_end]
        #     # 获取密码
        #     passwd = buf[u_end + 1: u_end + 1 + buf[u_end]]
        #     if 'zzy' == username and '1234' == passwd:
        #         # 登录成功
        #         await stream.write(bytes((0x05, 0x00)))
        #     else:
        #         # 登录失败
        #         await stream.write(bytes((0x05, 0x01)))
        #         stream.close()
        # else:
        await local_stream.write(bytes((0x05, 0x00)))

        buf = await local_stream.read_bytes(1024, True)
        logger.debug(buf)
        if (buf is None) or (not buf or buf[0] != 0x05):  # 验证版本
            local_stream.close()
            return
        if len(buf) < 7:
            local_stream.close()
            return

        if buf[1] != 0x01:
            local_stream.close()
            return

        dst_ip = None

        dst_port = buf[-2:]
        dst_port = int(dst_port.hex(), 16)

        dst_family = None

        if buf[3] == 0x01:
            # ipv4
            dst_ip = socket.inet_ntop(socket.AF_INET, buf[4:4 + 4])
            dst_address = Address(ip=dst_ip, port=dst_port)
            dst_family = socket.AF_INET
        elif buf[3] == 0x03:
            # domain
            dst_ip = buf[5:-2].decode()
            dst_address = Address(ip=dst_ip, port=dst_port)
            dst_family = 0
        elif buf[3] == 0x04:
            # ipv6
            dst_ip = socket.inet_ntop(socket.AF_INET6, buf[4:4 + 16])
            dst_address = (dst_ip, dst_port, 0, 0)
            dst_family = socket.AF_INET6
        else:
            local_stream.close()
            return

        if dst_family is None:
            # 协议错误
            local_stream.close()
            return

        # 创建iostream
        remote_stream = None
        try:
            tcp_client = TCPClient()
            if dst_family:
                remote_stream = await tcp_client.connect(dst_address[0], dst_address[1], af=dst_family)
            else:
                remote_stream = await tcp_client.connect(dst_address[0], dst_address[1])
        except Exception as e:
            # logger.exception('remote connect error')
            if remote_stream:
                remote_stream.close()
            local_stream.close()
            return None

        await local_stream.write(bytes((0x05, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        return remote_stream
