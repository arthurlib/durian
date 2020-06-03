from lib.base import TCP_FORWARD_AGENT, TCP_REVERSE_PROXY


def client_config__handler(configs):
    cfgs = {}
    if configs.get('Socks5Client'):
        cfgs['Socks5Client'] = configs.get('Socks5Client')

    if configs.get('TunnelClient'):
        cfgs['TunnelClient'] = configs.get('TunnelClient')
    return cfgs


def server_config_handler(configs):
    cfgs = {}
    if configs.get('Socks5Agent'):
        cfgs['Socks5Agent'] = configs.get('Socks5Agent')

    if configs.get('TCPForwardServer'):
        cfgs['TCPForwardServer'] = configs.get('TCPForwardServer')

    if configs.get('Http2Socks5Server'):
        cfgs['Http2Socks5Server'] = configs.get('Http2Socks5Server')

    if configs.get('Socks5Server'):
        cfgs['Socks5Server'] = configs.get('Socks5Server')

    if configs.get('TunnerlServer'):
        cfg_list = configs.get('TunnerlServer')
        for cfg in cfg_list:
            for key, key_cfg in cfg.get('configs', {}).items():
                for cfg_id, tmp_cfg in key_cfg.items():
                    if tmp_cfg['ty'] == 'TCP_FORWARD_AGENT':
                        tmp_cfg['ty'] = TCP_FORWARD_AGENT
                    elif tmp_cfg['ty'] == 'TCP_REVERSE_PROXY':
                        tmp_cfg['ty'] = TCP_REVERSE_PROXY
        cfgs['TunnerlServer'] = cfg_list

    return cfgs
