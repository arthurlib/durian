import json
import os
import sys
import threading

base_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.append(os.path.join(base_path, "../../"))

from proxy.socks5agent.lib import cipher
import proxy.socks5agent.client.client_selectors as socks5_client
import proxy.socks5agent.http2socks5 as http_client

if __name__ == '__main__':

    config = {}
    with open(os.path.join(base_path, "config.json"), "r") as f:
        content = f.read()
        config = json.loads(content)

    if config['key']:
        cipher.set_cipher('caesar', config['key'])

    thread_list = []
    thread_list.append(
        threading.Thread(target=socks5_client.listen,
                         name='socks5_agent',
                         args=(
                             config['client']['local_socks5_port'],
                             config['client']['server_host'],
                             config['client']['server_port']
                         )))
    print("starting socks5 proxy on port: " + str(config['client']['local_socks5_port']) +
          "  connect to " + "%s:%d" % (config['client']['server_host'], config['client']['server_port']))

    if config['client'].get('local_http_port'):
        thread_list.append(
            threading.Thread(target=http_client.listen,
                             name='http_agent',
                             args=(
                                 config['client']['local_http_port'],
                                 "127.0.0.1",
                                 config['client']['local_socks5_port']
                             )))
        print("starting http proxy on port: " + str(config['client']['local_http_port']) +
              "  connect to 127.0.0.1:" + str(config['client']['local_socks5_port']))

    for t in thread_list:
        t.start()
    for t in thread_list:
        t.join()
