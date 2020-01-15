import select
import traceback
import socket

from proxy.socks5agent.lib.model import Address
from proxy.socks5agent.lib.local import LocalSocket, SOCKS5_CONN, BUFFER_SIZE, SOCKS5_DONE, SOCKS5_CONFIRM, SOCKS5_AUTH


class Task(object):
    def __init__(self, epoll):
        # 存储 fd 连接的对应关系
        self.socket_fd_map = {}
        # fd 对应 sock
        self.fd_socket = {}
        self.poll = epoll
        # 缓存buf
        self.cache = {}

    def accept(self, fd):
        local_sock, address = self.fd_socket[fd].accept()
        local_sock.setblocking(False)
        local_sock = LocalSocket(local_sock, SOCKS5_CONN)

        # 放入队列
        self.fd_socket[local_sock.fileno()] = local_sock
        # 监听可读状态
        self.poll.register(local_sock.fileno(), select.EPOLLIN)

    def read(self, fd):
        # 能进来就是已经绑定关系完成了,且肯定存在sock
        try:
            sock = self.fd_socket.get(fd, None)
            recv = sock.recv(BUFFER_SIZE)
            buf = bytearray(recv)
            if len(buf) > 0:
                if self.cache.get(self.socket_fd_map[fd], None):
                    self.cache[self.socket_fd_map[fd]].append(buf)
                else:
                    self.cache[self.socket_fd_map[fd]] = [buf]
                # 将被绑定的sock设置为可读可写
                self.poll.modify(self.socket_fd_map[fd], select.EPOLLIN | select.EPOLLOUT)
            else:
                self.remove(fd)

        except Exception as e:
            print(e)
            traceback.print_exc()
            self.remove(fd)

    def write(self, fd):
        try:
            sock = self.fd_socket.get(fd, None)
            if len(self.cache.get(fd, '')):
                buf = self.cache[fd].pop(0)
                sock.sendall(buf)
                if not len(self.cache.get(fd, '')):
                    # 数据发送完毕，修改自身设置为可读监听
                    self.poll.modify(fd, select.EPOLLIN)
        except Exception as e:
            print(e)
            traceback.print_exc()
            self.remove(fd)

    def bind_sock(self, fd):
        # 绑定关系
        self.socket_fd_map[self.socket_fd_map[fd]] = fd
        # 监听可读状态
        self.poll.modify(fd, select.EPOLLIN)
        # 监听可读状态
        self.poll.register(self.socket_fd_map[fd], select.EPOLLIN)

    def remove(self, fd):
        fd2 = self.socket_fd_map.get(fd, None)
        sock = self.fd_socket.get(fd, None)
        sock2 = self.fd_socket.get(fd2, None)

        if sock:
            sock.close()
        if fd in self.socket_fd_map:
            del self.socket_fd_map[fd]
        if fd in self.fd_socket:
            del self.fd_socket[fd]
        try:
            self.poll.unregister(fd)
        except:
            pass
        if sock2:
            sock.close()
        if fd2 in self.socket_fd_map:
            del self.socket_fd_map[fd2]
        if fd2 in self.fd_socket:
            del self.fd_socket[fd2]
        try:
            self.poll.unregister(fd2)
        except:
            pass

        # 移除缓冲数据
        if fd in self.cache:
            del self.cache[fd]
        if fd2 in self.cache:
            del self.cache[fd2]

    def socks5_handler(self, fd):
        sock = self.fd_socket.get(fd, None)

        # 协议处理
        if sock.socks5_protocol_status == SOCKS5_CONN:
            try:
                recv = sock.recv(BUFFER_SIZE)
                buf = bytearray(recv)
                if not buf or buf[0] != 0x05:
                    sock.close()
                    del self.fd_socket[fd]
                    self.poll.unregister(fd)
                    return

                sock.sendall(bytearray((0x05, 0x00)))
                sock.socks5_protocol_status = SOCKS5_CONFIRM
            except Exception as e:
                print(e)
                traceback.print_exc()
                if sock:
                    sock.close()
                if fd in self.fd_socket:
                    del self.fd_socket[fd]
                try:
                    self.poll.unregister(fd)
                except:
                    pass

        elif sock.socks5_protocol_status == SOCKS5_AUTH:
            pass
        elif sock.socks5_protocol_status == SOCKS5_CONFIRM:
            recv = sock.recv(BUFFER_SIZE)
            buf = bytearray(recv)
            remote = None
            try:
                if len(buf) < 7:
                    sock.close()
                    del self.fd_socket[fd]
                    self.poll.unregister(fd)
                    return

                if buf[1] != 0x01:
                    sock.close()
                    del self.fd_socket[fd]
                    self.poll.unregister(fd)
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
                    del self.fd_socket[fd]
                    self.poll.unregister(fd)
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
                    del self.fd_socket[fd]
                    self.poll.unregister(fd)
                    return

                try:
                    remote.connect(dst_address)
                except BlockingIOError:
                    pass
                remote = LocalSocket(remote)
                # 放入队列
                self.fd_socket[remote.fileno()] = remote
                # 监听可写
                self.poll.register(remote.fileno(), select.EPOLLOUT)
                # 取消fd 可读注册
                self.poll.unregister(fd)
                # 绑定关系
                self.socket_fd_map[remote.fileno()] = fd

                sock.sendall(bytearray((0x05, 0x00, 0x00, 0x01, 0x00, 0x00,
                                        0x00, 0x00, 0x00, 0x00)))
                sock.socks5_protocol_status = SOCKS5_DONE
            except Exception as e:
                print(e)
                traceback.print_exc()

                sock.close()
                del self.fd_socket[fd]
                self.poll.unregister(fd)

                if remote:
                    remote.close()
                if remote and remote.fileno() in self.socket_fd_map:
                    del self.socket_fd_map[remote.fileno()]
                if remote and remote.fileno() in self.fd_socket:
                    del self.fd_socket[remote.fileno()]
                try:
                    self.poll.unregister(remote.fileno())
                except:
                    pass


def listen(port):
    poll = select.epoll()
    task = Task(poll)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client = LocalSocket(client, 0)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client.bind(('0.0.0.0', port))
    client.setblocking(False)
    client.listen(1024)

    # 放入队列
    task.fd_socket[client.fileno()] = client
    # 监听可读状态
    poll.register(client.fileno(), select.EPOLLIN)

    print("start epoll server")
    while True:
        try:

            epoll_list = poll.poll()
            print(len(epoll_list))

            for fd, events in epoll_list:
                # 检查可读
                if events & select.EPOLLIN:
                    # 如果是监听对象
                    if fd == client.fileno():
                        # 接受一个sock
                        task.accept(fd)
                    else:
                        sock = task.fd_socket.get(fd, None)  # 可能被移除，所以要检查
                        if not sock:
                            continue

                        if sock.socks5_protocol_status == 0 or sock.socks5_protocol_status == SOCKS5_DONE:
                            # 协议处理完成，读数据
                            task.read(fd)
                        else:
                            # 处理协议
                            task.socks5_handler(fd)

                if events & select.EPOLLOUT:
                    fd2 = task.socket_fd_map.get(fd, 0)
                    if fd2 and (not task.socket_fd_map.get(fd2, 0)):
                        task.bind_sock(fd)
                    else:
                        # 绑定完成的话就交换数据
                        task.write(fd)

                    continue

                if events & (select.EPOLLERR | select.EPOLLHUP):
                    task.remove(fd)
        except Exception as e:
            print(e)
            traceback.print_exc()
