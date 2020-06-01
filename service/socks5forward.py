import tornado.ioloop
from tornado.iostream import IOStream
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
            remote_stream = None
            try:
                # 连接远程
                tcp_client = TCPClient()
                remote_stream = await tcp_client.connect(self.remote_addr[0], self.remote_addr[1])
            except Exception as e:
                logger.debug('remote connect error')
                stream.close()
                if remote_stream:
                    remote_stream.close()
                return None

            # 开始交换数据
            await multi([read_and_send(stream, remote_stream), read_and_send(remote_stream, stream)])
        except tornado.iostream.StreamClosedError:
            pass
        except Exception as e:
            logger.exception('error')


def listen(local_port, remote_host, remote_port):
    app = Listener(address=Address(remote_host, remote_port))
    app.listen(local_port)
    print('socks5 forward server is runing at %s, remote at %s:%s' % (local_port, remote_host, remote_port))


def start():
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    listen(8000, "127.0.0.1", 8888)
    start()
