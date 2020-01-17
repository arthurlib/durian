"""
凯撒加密
"""
import base64
import random

PASSWORD_LENGTH = 256
IDENTITY_PASSWORD = bytearray(range(256))


class Password(object):

    def random_password(self) -> bytearray:
        password = IDENTITY_PASSWORD.copy()
        random.shuffle(password)
        return password

    def dumps_password(self, password: bytearray) -> str:
        return base64.urlsafe_b64encode(password).decode('utf8', errors='strict')

    def loads_password(self, password_str: str) -> bytearray:
        return bytearray(base64.urlsafe_b64decode(password_str.encode('utf8', errors='strict')))


class CaesarCipher(object):
    def __init__(self, password: str):
        self.__encrypted_pw = Password().loads_password(password)
        self.__decrypt_pw = self.__encrypted_pw.copy()
        for i, v in enumerate(self.__encrypted_pw):
            self.__decrypt_pw[v] = i

    def encrypt(self, bs: bytearray):
        bs = bytearray(bs)
        for i, v in enumerate(bs):
            bs[i] = self.__encrypted_pw[v]
        return bytes(bs)

    def decrypt(self, bs: bytearray):
        bs = bytearray(bs)
        for i, v in enumerate(bs):
            bs[i] = self.__decrypt_pw[v]
        return bytes(bs)


if __name__ == '__main__':
    # 生成密码
    p = Password()
    key = p.dumps_password(p.random_password())
    print(key)
