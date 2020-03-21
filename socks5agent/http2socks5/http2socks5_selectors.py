import selectors
import struct
import traceback
import socket

from proxy.socks5agent.lib.model import Address
from proxy.socks5agent.lib.local import LocalSocket, SOCKS5_CONN, BUFFER_SIZE, SOCKS5_DONE, SOCKS5_CONFIRM, SOCKS5_AUTH, \
    SOCKS5_CONFIRM_REPL


class Task(object):
    def __init__(self, poll, host='', port=0):
        self.poll = poll
        # 存储 sock 连接的对应关系
        self.socket_map = {}
        # sock 集合
        self.sockets = set()
        # 缓存buf
        self.cache = {}
        self.dst_address = Address(host, port)

    def cache_set(self, sock, data):
        if self.cache.get(self.socket_map[sock], None):
            self.cache[self.socket_map[sock]] = self.cache[self.socket_map[sock]] + data
        else:
            self.cache[self.socket_map[sock]] = bytes(data)

    def cache_get(self, sock):
        buf = self.cache[sock][:BUFFER_SIZE]
        self.cache[sock] = self.cache[sock][BUFFER_SIZE:]
        return buf

    def cache_exist(self, sock):
        return len(self.cache.get(sock, b''))

    def accept(self, sock):
        try:
            local_sock, address = sock.accept()
            local_sock.setblocking(False)
            local_sock = LocalSocket(local_sock, 0)

            # 放入队列
            self.sockets.add(local_sock)
            # 监听可读状态
            self.poll.register(local_sock, selectors.EVENT_READ)

            self.conn_remote(local_sock)
        except Exception as e:
            print(e)
            traceback.print_exc()
            self.remove(sock)

    def conn_remote(self, sock):
        remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote.setblocking(False)
        try:
            remote.connect(self.dst_address)
        except BlockingIOError:
            pass
        remote = LocalSocket(remote, SOCKS5_CONN)
        # 放入队列
        self.sockets.add(remote)
        # 监听可写
        self.poll.register(remote, selectors.EVENT_WRITE)
        # 绑定关系
        self.socket_map[remote] = sock
        self.socket_map[sock] = remote

    def read(self, sock):
        # 能进来就是已经绑定关系完成了,且肯定存在sock
        try:
            buf = sock.recv(BUFFER_SIZE)

            if len(buf) > 0:
                # 放入缓存
                self.cache_set(sock, buf)
                # 将被绑定的sock设置为可读可写
                self.poll.modify(self.socket_map[sock], selectors.EVENT_READ | selectors.EVENT_WRITE)
            else:
                self.remove(sock)
        except TimeoutError:
            pass
        except Exception as e:
            print(e)
            traceback.print_exc()
            self.remove(sock)

    def write(self, sock):
        try:
            # 存在缓存数据
            if self.cache_exist(sock):
                # 从缓存获取数据
                buf = self.cache_get(sock)
                sock.sendall(buf)
                if not self.cache_exist(sock):
                    # 数据发送完毕，修改自身设置为可读监听
                    self.poll.modify(sock, selectors.EVENT_READ)
        except Exception as e:
            print(e)
            traceback.print_exc()
            self.remove(sock)

    def socks5_read_handler(self, sock):
        if sock.socks5_protocol_status == SOCKS5_AUTH:
            try:
                buf = sock.recv(BUFFER_SIZE)
                # print("recv " + str(buf))
                if buf is None:
                    return
                # 验证版本
                if not buf or buf[0] != 0x05:
                    sock.close()
                    self.sockets.remove(sock)
                    self.poll.unregister(sock)
                    return

                if buf[1] == 0x00:
                    sock.socks5_protocol_status = SOCKS5_CONFIRM
                    # 数据发送完毕，修改自身设置为可写监听
                    self.poll.modify(sock, selectors.EVENT_WRITE)

            except Exception as e:
                print(e)
                traceback.print_exc()
                self.remove(sock)

        elif sock.socks5_protocol_status == SOCKS5_CONFIRM_REPL:
            try:
                buf = sock.recv(BUFFER_SIZE)
                # print("recv " + str(buf))
                if buf is None:
                    return
                # 验证版本
                if not buf or buf[0] != 0x05:
                    sock.close()
                    self.sockets.remove(sock)
                    self.poll.unregister(sock)
                    return

                if buf[1] == 0x00:
                    sock.socks5_protocol_status = SOCKS5_DONE

                    conn_content = self.cache_get(sock)
                    if not conn_content.startswith(b"CONNECT"):
                        self.cache_set(self.socket_map[sock], conn_content)  # !!!
                        self.poll.modify(sock, selectors.EVENT_WRITE | selectors.EVENT_READ)
                        self.poll.modify(self.socket_map[sock], selectors.EVENT_READ)
                    else:
                        self.cache_set(sock, b"HTTP/1.1 200 Connection Established\r\n\r\n")
                        self.poll.modify(sock, selectors.EVENT_READ)
                        self.poll.modify(self.socket_map[sock], selectors.EVENT_WRITE | selectors.EVENT_READ)
                else:
                    self.remove(sock)

            except Exception as e:
                print(e)
                traceback.print_exc()
                self.remove(sock)

    def socks5_write_handler(self, sock):
        if sock.socks5_protocol_status == SOCKS5_CONN:
            try:
                data = bytes((0x05, 0x01, 0x00))
                sock.sendall(data)
                # print("send " + str(data))
                sock.socks5_protocol_status = SOCKS5_AUTH
                # 数据发送完毕，修改自身设置为可读监听
                self.poll.modify(sock, selectors.EVENT_READ)
            except Exception as e:
                print(e)
                traceback.print_exc()
                self.remove(sock)

        elif sock.socks5_protocol_status == SOCKS5_CONFIRM:
            try:
                conn_content = self.cache_get(sock)
                self.cache_set(self.socket_map[sock], conn_content)
                conn_content = conn_content.decode()
                # print(conn_content)  # !!!

                host = ""
                port = 0
                for line in conn_content.split('\r\n'):
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
                port = struct.pack('>H', port)

                data = bytes((0x05, 0x01, 0x00, 0x03)) + host_len + host + port
                sock.sendall(data)
                # print("send " + str(data))

                sock.socks5_protocol_status = SOCKS5_CONFIRM_REPL
                # 数据发送完毕，修改自身设置为可读监听
                self.poll.modify(sock, selectors.EVENT_READ)
            except Exception as e:
                print(e)
                traceback.print_exc()
                self.remove(sock)

    def remove(self, sock):
        sock2 = self.socket_map.get(sock, None)

        # 关闭sock
        if sock:
            sock.close()
        # 删除
        if sock in self.socket_map:
            del self.socket_map[sock]
        # 删除绑定的sock
        if sock in self.sockets:
            self.sockets.remove(sock)
        # 移除缓冲数据
        if sock in self.cache:
            del self.cache[sock]
        try:
            # 取消监听
            self.poll.unregister(sock)
        except:
            pass

        if sock2:
            sock.close()
        if sock2 in self.socket_map:
            del self.socket_map[sock2]
        if sock2 in self.sockets:
            self.sockets.remove(sock2)
        if sock2 in self.cache:
            del self.cache[sock2]
        try:
            self.poll.unregister(sock2)
        except:
            pass


def listen(listen_port, remote_host, remote_port):
    # 根据系统自动选择多路复用框架
    poll = selectors.DefaultSelector()
    task = Task(poll, remote_host, remote_port)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client = LocalSocket(client, 0)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client.bind(('0.0.0.0', listen_port))
    client.setblocking(False)
    client.listen(1024)

    # 放入队列
    task.sockets.add(client)
    # 监听可读状态
    poll.register(client, selectors.EVENT_READ)

    print(poll)
    print('start http client poll')
    while True:
        try:
            events = poll.select()
            # print(len(events))
            for key, mask in events:
                sock = key.fileobj

                if mask & selectors.EVENT_READ:
                    # 如果是监听对象
                    if sock == client:
                        # 接受一个sock
                        task.accept(sock)
                    else:

                        if sock not in task.sockets:
                            # 可能发生error被移除，所以要检查
                            continue

                        if not sock.socks5_protocol_status or sock.socks5_protocol_status == SOCKS5_DONE:
                            # 协议处理完成，读数据
                            task.read(sock)
                        else:
                            # 处理协议
                            task.socks5_read_handler(sock)

                if mask & selectors.EVENT_WRITE:
                    if not sock.socks5_protocol_status or sock.socks5_protocol_status == SOCKS5_DONE:
                        task.write(sock)
                    else:
                        task.socks5_write_handler(sock)

        except Exception as e:
            print(e)
            traceback.print_exc()


if __name__ == "__main__":
    listen(7003, "127.0.0.1", 7002)
