import socket
import struct

import tornado.ioloop
import tornado.web
import tornado.iostream
from tornado.tcpserver import TCPServer

from tornado.gen import multi

from proxy.socks5agent.lib.model import Address

socks5_agent_remote_addr = Address("127.0.0.1", 7002)


class HttpListen(TCPServer):
    async def handle_stream(self, stream, address):
        conn_content = await stream.read_bytes(1024, True)
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
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn_stream = tornado.iostream.IOStream(s)
        await conn_stream.connect(socks5_agent_remote_addr)
        # handle socks5
        await conn_stream.write(bytes((0x05, 0x01, 0x00)))
        buf = await conn_stream.read_bytes(1024, True)
        if buf is None:
            return
        # 验证版本
        if not buf or buf[0] != 0x05:
            conn_stream.close()
            return

        if not buf[1] == 0x00:
            return

        data = bytes((0x05, 0x01, 0x00, 0x03)) + host_len + host + struct.pack('>H', port)
        await conn_stream.write(data)
        buf = await conn_stream.read_bytes(1024, True)
        if buf is None:
            return
        # 验证版本
        if not buf or buf[0] != 0x05:
            conn_stream.close()
            return

        if buf[1] == 0x00 and port == 443:
            await stream.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        else:
            await conn_stream.write(conn_content)

        async def local2remote(local, remote):
            try:
                while True:
                    buf = await local.read_bytes(1024, True)
                    if buf != b"":
                        await remote.write(buf)
                    else:
                        local.close()
                        remote.close()
            except:
                local.close()
                remote.close()

        async def remote2local(remote, local):
            try:
                while True:
                    buf = await remote.read_bytes(1024, True)
                    if buf != b"":
                        await local.write(buf)
                    else:
                        local.close()
                        remote.close()
            except:
                local.close()
                remote.close()

        await multi([local2remote(stream, conn_stream), remote2local(conn_stream, stream)])


# def listen(listen_port, remote_host, remote_port):
#     global http_agent_remote_addr
#     http_agent_remote_addr = Address(remote_host, remote_port)
#
#     HttpListen().listen(listen_port)
#     tornado.ioloop.IOLoop.current().start()


def make_app():
    return HttpListen()


if __name__ == "__main__":
    app = make_app()
    app.listen(7003)
    print("server is runing at 7003...")
    tornado.ioloop.IOLoop.current().start()
