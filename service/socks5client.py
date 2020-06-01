import tornado.ioloop
from tornado.iostream import IOStream
from tornado.tcpclient import TCPClient
from tornado.tcpserver import TCPServer
from tornado.gen import multi
from proxy.lib.local import ProxyStream
from proxy.lib.log import logger
from proxy.lib.model import Address
from proxy.lib.netutil import read_and_send


class Listener(TCPServer):
    def __init__(self, address, *args, **kwargs):
        self.remote_addr = address

        super(Listener, self).__init__(*args, **kwargs)

    async def handle_stream(self, stream, address):
        try:
            remote_stream = None
            try:
                # 连接远程
                tcp_client = TCPClient()
                remote_stream = await tcp_client.connect(self.remote_addr[0], self.remote_addr[1])
                remote_stream = ProxyStream(remote_stream)
            except Exception as e:
                logger.debug('remote connect error')
                stream.close()
                if remote_stream:
                    remote_stream.close()
                return None

            # 交换协议
            await self.exchange_agreement(stream, remote_stream)

            # 开始交换数据
            await multi([read_and_send(stream, remote_stream), read_and_send(remote_stream, stream)])
        except tornado.iostream.StreamClosedError:
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


def listen(local_port, remote_host, remote_port):
    app = Listener(address=Address(remote_host, remote_port))
    app.listen(local_port)
    print('socks5 proxy client is runing at %s, remote at %s:%s' % (local_port, remote_host, remote_port))


def start():
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    listen(7002, "127.0.0.1", 8090)
    start()
