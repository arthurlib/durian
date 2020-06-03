from lib.base import BUFFER_SIZE


async def read_and_send(sock_from, sock_to):
    try:
        while True:
            buf = await sock_from.read_bytes(BUFFER_SIZE, True)
            if buf is None:  # 完整数据未到
                continue
            if buf != b"":
                await sock_to.write(buf)
            else:
                sock_from.close()
                sock_to.close()
    except Exception as e:
        sock_from.close()
        sock_to.close()
