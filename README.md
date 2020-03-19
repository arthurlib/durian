# socks5 proxy

目前
* 只支持凯撒加密

使用

1. 获取密钥

在 socks5agent 目录下

获取key

```python
python3 lib/ciphers/caesar_cipher.py
``` 


2. 配置文件

> 配置文件命名为 config.json ,放在socks5agent目录下

服务端
```json
{
  "key": "EkJSKinK3QzQe_MIMmRbGoI4IrJNg-uUhqLEiOGt-LN1wOJalcO8WGt0VG0On6_7f3kFnCysM0fx7pGbh12hsBm1JD9m3G_mq2GEd_X0zvkQADRZeAftScag71fyx9iqAtbSjxNLFjf3uGipbj4bUdOLpS5EriUdo2cR1b3MciEmt9HP9mp9Xgq5BMIxPew6Rl9WOTV-Y3BgU-kfjsg2J52ZcTAtHJi7pkp2FfqN3w2FGOggQXyxwSOWOxQDkMsJnjzJTrTlxWn_gJq2QyukqFxV49fbL0-Mc4G_KAGXHup6YuDkTGXN5wtQRbqS1L5sihfaQP4P2Ynwk95I_Qan_A==",
  "server": {
    "port": 8090
  }
}
```
* key: 第一步获取的key
* server.port: 服务端监听的端口

客户端
```json
{
  "key": "EkJSKinK3QzQe_MIMmRbGoI4IrJNg-uUhqLEiOGt-LN1wOJalcO8WGt0VG0On6_7f3kFnCysM0fx7pGbh12hsBm1JD9m3G_mq2GEd_X0zvkQADRZeAftScag71fyx9iqAtbSjxNLFjf3uGipbj4bUdOLpS5EriUdo2cR1b3MciEmt9HP9mp9Xgq5BMIxPew6Rl9WOTV-Y3BgU-kfjsg2J52ZcTAtHJi7pkp2FfqN3w2FGOggQXyxwSOWOxQDkMsJnjzJTrTlxWn_gJq2QyukqFxV49fbL0-Mc4G_KAGXHup6YuDkTGXN5wtQRbqS1L5sihfaQP4P2Ynwk95I_Qan_A==",
  "client": {
    "server_host": "111.111.111.111",
    "server_port": 8090,
    "local_socks5_port": 7002,
    "local_http_port": 7003
  }
}
```
* key: 与服务端key一致
* client.server_host: 服务端ip
* client.server_port: 服务端监听端口
* client.local_socks5_port: 本地socks5代理监听端口
* client.local_http_port: 本地http代理监听端口,若为空或不存在，则不启动


另： http2socks5.py 该文件可以单独运行
