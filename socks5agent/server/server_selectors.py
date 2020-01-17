import selectors
import traceback
import socket

from proxy.socks5agent.lib.model import Address
from proxy.socks5agent.lib.local import LocalSocket, SOCKS5_CONN, BUFFER_SIZE, SOCKS5_DONE, SOCKS5_CONFIRM, SOCKS5_AUTH


class Task(object):
    def __init__(self, poll, username='', password=''):
        self.poll = poll
        # 存储 sock 连接的对应关系
        self.socket_map = {}
        # sock 集合
        self.sockets = set()
        # 缓存buf
        self.cache = {}

        # 用户认证
        self.username = username
        self.password = password
        # self.username = bytearray((0x02, 0x02))
        # self.password = bytearray((0x02, 0x02))

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
        local_sock, address = sock.accept()
        local_sock.setblocking(False)
        local_sock = LocalSocket(local_sock, SOCKS5_CONN)

        # 放入队列
        self.sockets.add(local_sock)
        # 监听可读状态
        self.poll.register(local_sock, selectors.EVENT_READ)

    def read(self, sock):
        # 能进来就是已经绑定关系完成了,且肯定存在sock
        try:
            if not sock.socks5_protocol_status:
                buf = sock.recv(BUFFER_SIZE)
            else:
                buf = sock.recv_with_head()
                if buf is None:
                    return

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
            if self.cache_exist(sock):
                # 从缓存获取数据
                buf = self.cache_get(sock)
                if not sock.socks5_protocol_status:
                    sock.sendall(buf)
                else:
                    sock.sendall_with_head(buf)
                if not self.cache_exist(sock):
                    # 数据发送完毕，修改自身设置为可读监听
                    self.poll.modify(sock, selectors.EVENT_READ)
        except Exception as e:
            print(e)
            traceback.print_exc()
            self.remove(sock)

    def bind_sock(self, sock):
        # 绑定关系
        self.socket_map[self.socket_map[sock]] = sock
        # 监听可读状态
        self.poll.modify(sock, selectors.EVENT_READ)
        # 监听可读状态
        self.poll.register(self.socket_map[sock], selectors.EVENT_READ)

    def socks5_handler(self, sock):
        # 协议处理
        if sock.socks5_protocol_status == SOCKS5_CONN:
            try:
                buf = sock.recv_with_head()
                if buf is None:
                    return
                if not buf or buf[0] != 0x05:
                    sock.close()
                    self.sockets.remove(sock)
                    self.poll.unregister(sock)
                    return
                # 判断是否要加密
                if self.password:
                    # 要认证
                    sock.sendall_with_head(bytearray((0x05, 0x02)))
                    sock.socks5_protocol_status = SOCKS5_AUTH
                else:
                    sock.sendall_with_head(bytearray((0x05, 0x00)))
                    sock.socks5_protocol_status = SOCKS5_CONFIRM
            except Exception as e:
                print(e)
                traceback.print_exc()
                self.remove(sock)

        elif sock.socks5_protocol_status == SOCKS5_AUTH:
            try:
                buf = sock.recv_with_head()
                if buf is None:
                    return
                # 验证版本
                if not buf or buf[0] != 0x05:
                    sock.close()
                    self.sockets.remove(sock)
                    self.poll.unregister(sock)
                    return
                # 获取用户名
                u_end = 2 + buf[1]
                username = buf[2:u_end]
                # 获取密码
                passwd = buf[u_end + 1: u_end + 1 + buf[u_end]]
                if self.username == username and self.password == passwd:
                    # 登录成功
                    sock.sendall_with_head(bytearray((0x05, 0x00)))
                    sock.socks5_protocol_status = SOCKS5_CONFIRM
                else:
                    # 登录失败
                    sock.sendall_with_head(bytearray((0x05, 0x01)))

                    sock.close()
                    self.sockets.remove(sock)
                    self.poll.unregister(sock)

            except Exception as e:
                print(e)
                traceback.print_exc()
                self.remove(sock)

        elif sock.socks5_protocol_status == SOCKS5_CONFIRM:
            buf = sock.recv_with_head()
            if buf is None:
                return
            try:
                if len(buf) < 7:
                    sock.close()
                    self.sockets.remove(sock)
                    self.poll.unregister(sock)
                    return

                if buf[1] != 0x01:
                    sock.close()
                    self.sockets.remove(sock)
                    self.poll.unregister(sock)
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
                elif buf[3] == 0x04:
                    # ipv6
                    dst_ip = socket.inet_ntop(socket.AF_INET6, buf[4:4 + 16])
                    dst_address = (dst_ip, dst_port, 0, 0)
                    dst_family = socket.AF_INET6
                else:
                    sock.close()
                    self.sockets.remove(sock)
                    self.poll.unregister(sock)
                    return

                remote = None
                if dst_family:
                    try:
                        remote = socket.socket(
                            family=dst_family, type=socket.SOCK_STREAM)
                        remote.setblocking(False)
                    except OSError:
                        if remote is not None:
                            remote.close()
                            remote = None
                else:
                    host, port = dst_address
                    for res in socket.getaddrinfo(host, port):
                        dst_family, sock_type, proto, _, dst_address = res
                        try:
                            # socket.SOCK_STREAM: TCP, 目前不支持 UDP
                            # remote = socket.socket(dst_family, sock_type, proto)
                            # remote = socket.socket(dst_family, socket.SOCK_STREAM, proto)
                            remote = socket.socket(dst_family, socket.SOCK_STREAM)
                            remote.setblocking(False)
                            break
                        except OSError:
                            if remote is not None:
                                remote.close()
                                remote = None

                if dst_family is None:
                    sock.close()
                    self.sockets.remove(sock)
                    self.poll.unregister(sock)
                    return

                try:
                    remote.connect(dst_address)
                except BlockingIOError:
                    pass
                remote = LocalSocket(remote)
                # 放入队列
                self.sockets.add(remote)
                # 监听可写
                self.poll.register(remote, selectors.EVENT_WRITE)
                # 取消可读注册
                self.poll.unregister(sock)
                # 绑定关系
                self.socket_map[remote] = sock

                sock.sendall_with_head(bytearray((0x05, 0x00, 0x00, 0x01, 0x00, 0x00,
                                                  0x00, 0x00, 0x00, 0x00)))
                sock.socks5_protocol_status = SOCKS5_DONE
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


def listen(port):
    # 根据系统自动选择多路复用框架
    poll = selectors.DefaultSelector()
    task = Task(poll)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client = LocalSocket(client)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client.bind(('0.0.0.0', port))
    client.setblocking(False)
    client.listen(1024)

    # 放入队列
    task.sockets.add(client)
    # 监听可读状态
    poll.register(client, selectors.EVENT_READ)

    print(poll)
    print('start server poll')
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
                            task.socks5_handler(sock)

                if mask & selectors.EVENT_WRITE:
                    sock2 = task.socket_map.get(sock, None)
                    if sock2 and (not task.socket_map.get(sock2, None)):
                        # 建立关联
                        task.bind_sock(sock)
                    else:
                        task.write(sock)

        except Exception as e:
            print(e)
            traceback.print_exc()
