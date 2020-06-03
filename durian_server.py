import json
import os
import sys

import tornado

from lib.cipher import get_cipher
from lib.config import server_config_handler
from service.server import Socks5Agent, TCPForwardServer, TunnerlServer, Socks5Server, Http2Socks5Server

base_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.append(os.path.join(base_path, "./"))


def main():
    cfgs = {}
    with open(os.path.join(base_path, "config.json"), "r") as f:
        content = f.read()
        cfgs = json.loads(content)
    cfgs = server_config_handler(cfgs)

    for cfg in cfgs.get('Socks5Agent', []):
        socks5_agent = Socks5Agent()  # 单独的socks5代理服务器
        socks5_agent.listen(cfg['port'], cfg['host'] if cfg.get('host') else '')

    for cfg in cfgs.get('TCPForwardServer', []):
        tcp_forward_server = TCPForwardServer()  # 转发tcp包到指定端口
        tcp_forward_server.set_remote_address(cfg['remote_host'], cfg['remote_port'])
        tcp_forward_server.listen(cfg['local_port'], cfg['local_host'] if cfg.get('local_host') else '')

    for cfg in cfgs.get('Http2Socks5Server', []):
        http2socks5_server = Http2Socks5Server()
        http2socks5_server.set_remote_address(cfg['remote_host'], cfg['remote_port'])
        http2socks5_server.listen(cfg['local_port'], cfg['local_host'] if cfg.get('local_host') else '')

    for cfg in cfgs.get('TunnerlServer', []):
        tunner_server = TunnerlServer()
        tunner_server.set_config(cfg['configs'])
        tunner_server.listen(cfg['port'], cfg['host'] if cfg.get('host') else '')

    for cfg in cfgs.get('Socks5Server', []):
        socks5_server = Socks5Server()
        if cfg.get('key'):
            socks5_server.set_cipher(get_cipher('caesar', cfg['key']))
        socks5_server.listen(cfg['port'], cfg['host'] if cfg.get('host') else '')

    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
