import struct

import tornado.ioloop
import tornado.web
import tornado.iostream
from tornado.tcpclient import TCPClient
from tornado.tcpserver import TCPServer

from tornado.gen import multi

from proxy.lib.log import logger
from proxy.lib.model import Address
from proxy.lib.netutil import read_and_send


class Listener(TCPServer):
    def __init__(self, address, *args, **kwargs):
        self.remote_addr = address

        super(Listener, self).__init__(*args, **kwargs)

    async def handle_stream(self, stream, address):
        try:
            remote_stream = await self.exchange_agreement(stream)
            if remote_stream:
                await multi([read_and_send(stream, remote_stream), read_and_send(remote_stream, stream)])
        except tornado.iostream.StreamClosedError:
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
            logger.debug('remote connect error')
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


def listen(local_port, remote_host, remote_port):
    app = Listener(address=Address(remote_host, remote_port))
    app.listen(local_port)
    print('http proxy client is runing at %s, remote at %s:%s' % (local_port, remote_host, remote_port))


def start():
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    listen(7003, "127.0.0.1", 7002)
    start()
