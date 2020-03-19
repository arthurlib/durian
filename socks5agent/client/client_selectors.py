import selectors
import traceback
import socket

from proxy.socks5agent.lib.model import Address
from proxy.socks5agent.lib.local import LocalSocket, SOCKS5_CONN, BUFFER_SIZE, SOCKS5_DONE, SOCKS5_CONFIRM, SOCKS5_AUTH, \
    SOCKS5_CONFIRM_REPL, SOCKS5_AUTH_REPL


class Task(object):
    def __init__(self, poll, host='', port=0, username='', password='', ):
        self.poll = poll
        # 存储 sock 连接的对应关系
        self.socket_map = {}
        # sock 集合
        self.sockets = set()
        # 缓存buf
        self.cache = {}

        # self.host = '127.0.0.1'
        # self.port = 7000
        # self.host = host
        # self.port = port
        self.dst_address = Address(host, port)
        # 用户认证
        self.username = username
        self.password = password

    def cache_set(self, sock, data):
        if self.cache.get(self.socket_map[sock], None):
            self.cache[self.socket_map[sock]] += data
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
            # self.poll.register(local_sock, selectors.EVENT_READ)

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
        # 取消可读注册
        # self.poll.unregister(sock)
        # 绑定关系
        self.socket_map[remote] = sock

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
            # 存在缓存数据
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

    def socks5_read_handler(self, sock):
        # 协议处理
        # if sock.socks5_protocol_status == SOCKS5_CONN:
        #     pass

        if sock.socks5_protocol_status == SOCKS5_AUTH:
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

                if buf[1] == 0x00:
                    # 不验证
                    self.cache_set(sock, buf)
                    # if self.cache.get(self.socket_map[sock], None):
                    #     self.cache[self.socket_map[sock]] = b''.join([self.cache[self.socket_map[sock]], buf])
                    # else:
                    #     self.cache[self.socket_map[sock]] = bytes(buf)

                    # 将被绑定的sock设置为可读可写
                    self.poll.modify(self.socket_map[sock], selectors.EVENT_READ | selectors.EVENT_WRITE)
                    sock.socks5_protocol_status = SOCKS5_CONFIRM
                elif buf[1] == 0x02:
                    # 要验证
                    data = bytes((0x05, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02))
                    if self.cache.get(sock, None):
                        self.cache[sock] += data
                    else:
                        self.cache[sock] = data
                    # 将当前的sock设置为监听可写
                    self.poll.modify(sock, selectors.EVENT_WRITE)
                    sock.socks5_protocol_status = SOCKS5_AUTH

            except Exception as e:
                print(e)
                traceback.print_exc()
                self.remove(sock)

        elif sock.socks5_protocol_status == SOCKS5_AUTH_REPL:
            try:
                buf = sock.recv_with_head()
                if buf is None:
                    return
                check_login = buf[1]
                if not check_login:
                    # print("login success")
                    # 本地验证结束，返回不验证
                    buf = bytes((0x05, 0x00))
                    self.cache_set(sock, buf)
                    # if self.cache.get(self.socket_map[sock], None):
                    #     self.cache[self.socket_map[sock]].append(buf)
                    # else:
                    #     self.cache[self.socket_map[sock]] = buf
                    # 将被绑定的sock设置为可读可写
                    self.poll.modify(self.socket_map[sock], selectors.EVENT_READ | selectors.EVENT_WRITE)
                    sock.socks5_protocol_status = SOCKS5_CONFIRM
                else:
                    # print("login fail!")
                    self.remove(sock)
            except Exception as e:
                print(e)
                traceback.print_exc()
                self.remove(sock)

        # elif sock.socks5_protocol_status == SOCKS5_CONFIRM:
        #     pass

        elif sock.socks5_protocol_status == SOCKS5_CONFIRM_REPL:
            self.read(sock)
            sock.socks5_protocol_status = SOCKS5_DONE

    def socks5_write_handler(self, sock):
        if sock.socks5_protocol_status == SOCKS5_CONN:
            self.write(sock)
            sock.socks5_protocol_status = SOCKS5_AUTH

        elif sock.socks5_protocol_status == SOCKS5_AUTH:
            self.write(sock)
            sock.socks5_protocol_status = SOCKS5_AUTH_REPL
        elif sock.socks5_protocol_status == SOCKS5_CONFIRM:
            self.write(sock)
            sock.socks5_protocol_status = SOCKS5_CONFIRM_REPL
        # elif sock.socks5_protocol_status == SOCKS5_CONFIRM_REPL:
        #     pass

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
    print('start client poll')
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
                    sock2 = task.socket_map.get(sock, None)
                    if sock2 and (not task.socket_map.get(sock2, None)):
                        # 建立关联
                        task.bind_sock(sock)
                    else:
                        if not sock.socks5_protocol_status or sock.socks5_protocol_status == SOCKS5_DONE:
                            task.write(sock)
                        else:
                            task.socks5_write_handler(sock)

        except Exception as e:
            print(e)
            traceback.print_exc()
