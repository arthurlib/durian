import json
import os
import sys

import tornado

base_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.append(os.path.join(base_path, "../"))

from proxy.lib import cipher
import proxy.service.socks5client as socks5_client
import proxy.service.http2socks5 as http_client

if __name__ == '__main__':

    config = {}
    with open(os.path.join(base_path, "config.json"), "r") as f:
        content = f.read()
        config = json.loads(content)

    if config.get('key'):
        cipher.set_cipher('caesar', config['key'])
    socks5_client.listen(
        config['client']['port'],
        config['client']['server_host'],
        config['client']['server_port']
    )
    http = config.get('http')
    if http:
        http_client.listen(
            http['port'],
            http['socks5_host'],
            http['socks5_port']
        )
    socks5_client.start()
