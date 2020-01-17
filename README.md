# socks5 proxy

目前
* 只支持凯撒加密

使用

1. 获取密钥

在 socks5agent 目录下

```python
python3 lib/ciphers/caesar_cipher.py
``` 

2. 将上面的打印的字符串替换到 server.py、client.py 中的 key 变量
3. 修改 server.py 中的监听端口， 修改 client.py 中的监听端口和远程hsot及port
