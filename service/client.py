import functools

import tornado
from tornado.gen import multi, sleep
from tornado.tcpclient import TCPClient
from tornado.tcpserver import TCPServer
from tornado.ioloop import PeriodicCallback
from tornado.iostream import StreamClosedError

from lib.log import logger
from lib.netutil import read_and_send
from lib.base import TunnelStream, ProxyStream, TCP_REVERSE_PROXY, SYNC_CONFIG, HEART_BEAT, TCP_FORWARD_AGENT, BUFFER_SIZE, TunnelKeyError, TunnelListener


class Socks5Client(TCPServer):
    def __init__(self, *args, **kwargs):
        super(Socks5Client, self).__init__(*args, **kwargs)
        self.remote_addr = None
        self.cipher = None

    def set_remote_address(self, host, port):
        self.remote_addr = (host, port)

    def set_cipher(self, cipher):
        self.cipher = cipher

    async def handle_stream(self, stream, address):
        try:
            remote_stream = None
            try:
                # 连接远程
                tcp_client = TCPClient()
                remote_stream = await tcp_client.connect(self.remote_addr[0], self.remote_addr[1])
                remote_stream = ProxyStream(remote_stream, self.cipher)
            except Exception as e:
                # logger.exception('remote connect error')
                stream.close()
                if remote_stream:
                    remote_stream.close()
                return None

            # 交换协议
            await self.exchange_agreement(stream, remote_stream)

            # 开始交换数据
            await multi([read_and_send(stream, remote_stream), read_and_send(remote_stream, stream)])
        except StreamClosedError:
            pass
        except Exception as e:
            logger.exception('error')

    async def exchange_agreement(self, local_stream, remote_stream):
        # 获取数据, socks5 conn协议
        buf = await local_stream.read_bytes(1024, True)
        logger.debug(buf)
        await remote_stream.write(buf)
        buf = await remote_stream.read_bytes(1024, True)
        logger.debug(buf)
        if (buf is None) or (not buf or buf[0] != 0x05):  # 验证版本
            remote_stream.close()
            local_stream.close()
            return

        # if buf[1] == 0x00:
        # 不验证
        await local_stream.write(buf)
        # 认证逻辑保留
        # elif buf[1] == 0x02:
        #     # 要验证
        #     data = bytes((0x05, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02))
        #     await remote_stream.write(data)  # 发送socks5认证协议
        #     buf = await remote_stream.read_bytes(1024, True)
        #     if (buf is None) or (not buf or buf[0] != 0x05):  # 验证版本
        #         remote_stream.close()
        #         local_stream.close()
        #         return
        #
        #     check_login = buf[1]
        #     if not check_login:
        #         # 本地验证结束，返回不验证
        #         buf = bytes((0x05, 0x00))
        #         await local_stream.write(buf)

        # socks5 发送确认协议
        buf = await local_stream.read_bytes(1024, True)
        logger.debug(buf)
        await remote_stream.write(buf)
        buf = await remote_stream.read_bytes(1024, True)
        logger.debug(buf)
        await local_stream.write(buf)


class TunnelClient(TunnelStream):
    def __init__(self, key='test'):
        super(TunnelClient, self).__init__()
        self.remote_addr = None  # 远程的地址
        self.key = key  # 客户端唯一标识
        self.config = None  # 保存同步下来的配置信息
        self.ping_task = None  # 隔一段时间就ping一下
        self.listeners = {}  # 本地启动的监听服务列表
        self.callback = {
            HEART_BEAT: self.handle_pong,
            SYNC_CONFIG: self.handle_sync_config,
            TCP_REVERSE_PROXY: self.handle_tcp_reverse_proxy,
            TCP_FORWARD_AGENT: self.handle_tcp_forward_agent,
        }

    def set_remote_address(self, host, port):
        self.remote_addr = (host, port)

    async def connect(self):
        if self.ping_task:
            self.ping_task.stop()

        while True:
            try:
                # 设置隧道流
                self.stream = await TCPClient().connect(self.remote_addr[0], self.remote_addr[1])
                logger.info('tunnel connected')

                # 定时任务ping一下
                self.ping_task = PeriodicCallback(functools.partial(self.ping), 30000)
                self.ping_task.start()

                await self.write({'ty': SYNC_CONFIG, 'key': self.key})
                break
            except StreamClosedError:
                if self.stream:
                    self.stream.close()
                logger.warning('Retry after 10 seconds')
                await sleep(10)

    async def start(self):
        await self.connect()
        while True:
            # print("测试内存泄漏" + str(self.key))
            # print(len(self.streams))
            try:
                buf_list = await self.read_bytes(BUFFER_SIZE, True)
                if buf_list is None:
                    continue
                for buf in buf_list:
                    await self.callback[buf['ty']](buf)
            except StreamClosedError:
                await self.connect()
            except TunnelKeyError as e:
                # 可能是key不存在服务端，或者key重复连接了
                print(e)
                break
            except Exception as e:
                logger.exception('error')
                await self.connect()

    async def ping(self):
        try:
            await self.write({'ty': HEART_BEAT})
        except StreamClosedError:
            self.stream.close()
            if self.ping_task:  # 定时ping任务停止
                self.ping_task.stop()

    async def handle_pong(self, buf):
        # print(buf)
        pass

    async def handle_sync_config(self, buf):
        """同步配置，并初始化"""
        self.config = buf[self.key]
        if not self.config:
            self.close()
            raise TunnelKeyError

        # 检查已有的listener是否在配置中，没有则移除
        for cfg_id in self.listeners.keys():
            if cfg_id not in self.config:
                listener = self.listeners.pop(cfg_id)
                listener.close()

        for cfg_id, cfg in self.config.items():
            if cfg['ty'] == TCP_FORWARD_AGENT:
                if cfg_id in self.listeners:
                    # 服务已经启动了,不重复监听
                    continue
                listener = TunnelListener(cfg_id, TCP_FORWARD_AGENT)
                listener.listen(cfg['port'], cfg['host'])
                listener.set_remote_stream(self)  # 设置隧道对象
                self.listeners[cfg_id] = listener  # 当前隧道记录启动的监听服务

    async def handle_tcp_reverse_proxy(self, buf):
        # 收到服务端发来的请求
        stream_id = buf['id']
        if buf['data'] == b'':  # 服务器下发的关闭请求
            remote_stream = self.streams.pop(stream_id, None)
            if remote_stream:
                remote_stream.close()
            return

        if stream_id not in self.streams:
            cfg_id = buf['cfg_id']
            cfg = self.config[cfg_id]

            remote_stream = await TCPClient().connect(cfg['remote_host'], cfg['remote_port'])
            self.streams[stream_id] = remote_stream  # 隧道记录请求stream

            async def read_and_send():
                data = {'ty': TCP_REVERSE_PROXY, 'id': stream_id}
                try:
                    while True:
                        buf = await remote_stream.read_bytes(BUFFER_SIZE, True)
                        if buf == b'':
                            remote_stream.close()
                            self.streams.pop(stream_id, None)  # 隧道移除当前stream
                        data['data'] = buf
                        await self.write(data)  # 向隧道写数据

                except StreamClosedError:
                    remote_stream.close()
                    self.streams.pop(stream_id, None)
                    data['data'] = b''
                    await self.write(data)  # 这边如果报错会被外部捕获

            tornado.ioloop.IOLoop.current().spawn_callback(read_and_send)  # 异步运行，不断向隧道写数据

        await self.streams[stream_id].write(buf['data'])

    async def handle_tcp_forward_agent(self, buf):
        if buf['data'] != b'':
            await self.streams[buf['id']].write(buf['data'])
        else:
            user_stream = self.streams.pop(buf['id'], None)
            if user_stream:  # 转发服务记录下的stream
                user_stream.close()
