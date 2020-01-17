from proxy.socks5agent.lib.ciphers.caesar_cipher import CaesarCipher

# global obj
cipher = None


def set_cipher(cipher_name, key):
    global cipher
    if cipher_name == 'caesar':
        cipher = CaesarCipher(key)
    else:
        raise AttributeError('不存在的加密方式')
