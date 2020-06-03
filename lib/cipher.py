from lib.ciphers.caesar_cipher import CaesarCipher


def get_cipher(cipher_name, key):
    if cipher_name == 'caesar':
        cipher = CaesarCipher(key)
    else:
        raise AttributeError('不存在的加密方式')

    return cipher
