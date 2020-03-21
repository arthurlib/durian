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
    "port": 7002
  }
}
```
* key: 与服务端key一致
* client.server_host: 服务端ip
* client.server_port: 服务端监听端口
* client.port: 本地socks5代理监听端口

http监听(http转socks5)

> 放在http2socks5目录下，http配置设置后会同时启动socks5和http监听,  
不设置则不启动http监听.

```json
{
  "http": {
    "socks5_host": "127.0.0.1",
    "socks5_port": 7002,
    "port": 7003
  }
}
```
* http.socks5_host: socks5代理的ip
* http.socks5_port: socks5代理监听端口
* http.port: 本地http代理监听端口

http2socks5目录下两个文件：
* http2socks5_selectors： 默认代码中使用的，使用selectors完成
* http2socks5_tornado： 使用tornado编写，单独启动使用。（配置信息修改代码）

