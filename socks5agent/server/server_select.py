import select
import traceback
import socket

from proxy.socks5agent.lib.model import Address
from proxy.socks5agent.lib.local import LocalSocket, SOCKS5_CONN, BUFFER_SIZE, SOCKS5_DONE, SOCKS5_CONFIRM, SOCKS5_AUTH


class Task(object):
    def __init__(self):
        # socket 队列
        self.socket_read_list = []
        # socket 等待队列（等待remote连接的sock的队列）
        self.socket_write_list = []
        # 存储 连接的对应关系
        self.socket_map = {}
        # 缓存buf
        self.cache = {}

    def accept(self, sock):
        local_sock, address = sock.accept()
        local_sock.setblocking(False)
        self.socket_read_list.append(LocalSocket(local_sock, SOCKS5_CONN))  # 监听可读

    def read(self, sock):
        # 能进来就是已经绑定关系完成了,且肯定存在sock
        try:
            recv = sock.recv(BUFFER_SIZE)
            buf = bytearray(recv)
            if len(buf) > 0:
                if self.cache.get(self.socket_map[sock], None):
                    self.cache[self.socket_map[sock]].append(buf)
                else:
                    self.cache[self.socket_map[sock]] = [buf]
                # 将被绑定的sock设置为可读可写
                if self.socket_map[sock] not in self.socket_write_list:
                    self.socket_write_list.append(self.socket_map[sock])  # 同时监听可写
            else:
                self.remove(sock)
        except Exception as e:
            print(e)
            traceback.print_exc()
            self.remove(sock)

    def write(self, sock):
        try:
            if len(self.cache.get(sock, '')):
                buf = self.cache[sock].pop(0)
                sock.sendall(buf)
                if not len(self.cache.get(sock, '')):
                    # 数据发送完毕，修改自身设置为可读监听
                    self.socket_write_list.remove(sock)
        except Exception as e:
            print(e)
            traceback.print_exc()
            self.remove(sock)

    def bind_sock(self, sock):
        self.socket_write_list.remove(sock)  # 取消监听可写
        self.socket_read_list.append(sock)  # 监听可读

        self.socket_map[self.socket_map[sock]] = sock  # 绑定关系
        self.socket_read_list.append(self.socket_map[sock])  # 监听可读

    def remove(self, sock):
        sock2 = self.socket_map.get(sock, None)

        if sock:
            sock.close()
        if sock in self.socket_map:
            del self.socket_map[sock]
        if sock in self.socket_read_list:
            self.socket_read_list.remove(sock)
        if sock in self.socket_write_list:
            self.socket_write_list.remove(sock)

        if sock2:
            sock.close()
        if sock2 in self.socket_map:
            del self.socket_map[sock2]
        if sock2 in self.socket_read_list:
            self.socket_read_list.remove(sock2)
        if sock2 in self.socket_write_list:
            self.socket_write_list.remove(sock2)

        # 移除缓冲数据
        if sock in self.cache:
            del self.cache[sock]
        if sock2 in self.cache:
            del self.cache[sock2]

    def socks5_handler(self, sock):

        if sock.socks5_protocol_status == SOCKS5_CONN:
            try:
                recv = sock.recv(BUFFER_SIZE)
                buf = bytearray(recv)
                if not buf or buf[0] != 0x05:
                    sock.close()
                    self.socket_read_list.remove(sock)
                    return

                sock.sendall(bytearray((0x05, 0x00)))
                sock.socks5_protocol_status = SOCKS5_CONFIRM
            except Exception as e:
                print(e)
                traceback.print_exc()
                if sock:
                    sock.close()
                self.socket_read_list.remove(sock)

        elif sock.socks5_protocol_status == SOCKS5_AUTH:
            pass
        elif sock.socks5_protocol_status == SOCKS5_CONFIRM:
            recv = sock.recv(BUFFER_SIZE)
            buf = bytearray(recv)
            remote = None
            try:
                if len(buf) < 7:
                    sock.close()
                    self.socket_read_list.remove(sock)
                    return

                if buf[1] != 0x01:
                    sock.close()
                    self.socket_read_list.remove(sock)
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
                    self.socket_read_list.remove(sock)
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
                            remote = socket.socket(dst_family, socket.SOCK_STREAM, proto)
                            remote.setblocking(False)
                            break
                        except OSError:
                            if remote is not None:
                                remote.close()
                                remote = None

                if dst_family is None:
                    sock.close()
                    self.socket_read_list.remove(sock)
                    return

                try:
                    remote.connect(dst_address)
                except BlockingIOError:
                    pass
                remote = LocalSocket(remote, 0)
                self.socket_write_list.append(remote)  # 监听可写
                self.socket_map[remote] = sock  # 绑定关系
                self.socket_read_list.remove(sock)  # 取消监听可读

                sock.sendall(bytearray((0x05, 0x00, 0x00, 0x01, 0x00, 0x00,
                                        0x00, 0x00, 0x00, 0x00)))
                sock.socks5_protocol_status = SOCKS5_DONE
            except Exception as e:
                print(e)
                traceback.print_exc()

                sock.close()
                self.socket_read_list.remove(sock)

                if remote:
                    remote.close()
                if remote in self.socket_map.keys():
                    del self.socket_map[remote]
                if remote in self.socket_write_list:
                    self.socket_write_list.remove(remote)


def listen(port):
    task = Task()

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client.bind(('0.0.0.0', port))
    client.setblocking(False)
    client.listen(1024)

    client = LocalSocket(client, 0)
    task.socket_read_list.append(client)
    print("start select server")
    while True:
        try:
            r_list, w_list, x_list = select.select(task.socket_read_list,
                                                   task.socket_write_list,
                                                   task.socket_read_list + task.socket_write_list)
            print(len(r_list + w_list + x_list))
            for r in r_list:
                if r == client:
                    # 接受新连接
                    task.accept(r)
                else:
                    if r not in task.socket_read_list:
                        continue

                    if r.socks5_protocol_status == 0 or r.socks5_protocol_status == SOCKS5_DONE:
                        task.read(r)
                    else:
                        # 处理协议
                        task.socks5_handler(r)

            for w in w_list:
                w2 = task.socket_map.get(w, None)
                if w2 and (not task.socket_map.get(w2, None)):
                    # 建立关联
                    task.bind_sock(w)
                else:
                    task.write(w)

                continue

            for x in x_list:
                # 出错关闭
                task.remove(x)
        except Exception as e:
            print(e)
            traceback.print_exc()
