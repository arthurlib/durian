import json
import os
import sys

base_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.append(os.path.join(base_path, "../../"))

from proxy.socks5agent.lib import cipher
import proxy.socks5agent.server.server_selectors as server

if __name__ == '__main__':
    config = {}
    with open(os.path.join(base_path, "config.json"), "r") as f:
        config = json.loads(f.read())

    if config['key']:
        cipher.set_cipher('caesar', config['key'])

    print("starting on port: " + str(config['server']['port']))
    server.listen(config['server']['port'])

