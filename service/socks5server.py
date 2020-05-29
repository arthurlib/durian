import socket

import tornado.ioloop
import tornado.web
from tornado.iostream import IOStream
from tornado.tcpclient import TCPClient
from tornado.tcpserver import TCPServer

from tornado.gen import multi

from proxy.lib.local import ProxyStream
from proxy.lib.log import logger
from proxy.lib.model import Address
from proxy.lib.netutil import read_and_send


class HttpListen(TCPServer):
    async def handle_stream(self, stream, address):
        local_stream = ProxyStream(stream)
        try:
            # 交换协议
            remote_stream = await self.exchange_agreement(local_stream)
            if remote_stream:
                # 交换数据
                await multi([read_and_send(local_stream, remote_stream), read_and_send(remote_stream, local_stream)])
        except tornado.iostream.StreamClosedError:
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
            logger.debug('remote connect error')
            if remote_stream:
                remote_stream.close()
            local_stream.close()
            return None

        await local_stream.write(bytes((0x05, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        return remote_stream


def listen(local_port):
    app = HttpListen()
    app.listen(local_port)
    print("socks5 proxy server is runing at %s" % local_port)


def start():
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    listen(8090)
    start()
