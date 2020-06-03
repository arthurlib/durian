# durian

依赖
- python3.7(3.6)
- tornado
- msgpack

> python3.8 存在问题，tornado暂未兼容py3.8的 asyncio库的一些修改

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

> 配置文件命名为 config.json ,放在proxy目录下,按需配置
```json

{
  "Socks5Client": {
    "key": "EkJSKinK3QzQe_MIMmRbGoI4IrJNg-uUhqLEiOGt-LN1wOJalcO8WGt0VG0On6_7f3kFnCysM0fx7pGbh12hsBm1JD9m3G_mq2GEd_X0zvkQADRZeAftScag71fyx9iqAtbSjxNLFjf3uGipbj4bUdOLpS5EriUdo2cR1b3MciEmt9HP9mp9Xgq5BMIxPew6Rl9WOTV-Y3BgU-kfjsg2J52ZcTAtHJi7pkp2FfqN3w2FGOggQXyxwSOWOxQDkMsJnjzJTrTlxWn_gJq2QyukqFxV49fbL0-Mc4G_KAGXHup6YuDkTGXN5wtQRbqS1L5sihfaQP4P2Ynwk95I_Qan_A==",
    "local_host": "0.0.0.0",
    "local_port": 20001,
    "remote_host": "127.0.0.1",
    "remote_port": 20000
  },
  "TunnelClient": {
    "key": "test",
    "remote_host": "127.0.0.1",
    "remote_port": 18091
  },
  "Socks5Agent": [
    {
      "host": "0.0.0.0",
      "port": 10000
    }
  ],
  "TCPForwardServer": [
    {
      "local_host": "0.0.0.0",
      "local_port": 10001,
      "remote_host": "127.0.0.1",
      "remote_port": 10000
    }
  ],
  "Http2Socks5Server": [
    {
      "local_host": "0.0.0.0",
      "local_port": 10002,
      "remote_host": "127.0.0.1",
      "remote_port": 10000
    }
  ],
  "TunnerlServer": [
    {
      "host": "0.0.0.0",
      "port": 18091,
      "configs": {
        "test": {
          "1": {
            "ty": "TCP_FORWARD_AGENT",
            "host": "0.0.0.0",
            "port": 18000,
            "remote_host": "127.0.0.1",
            "remote_port": 18888
          },
          "2": {
            "ty": "TCP_REVERSE_PROXY",
            "host": "0.0.0.0",
            "port": 18001,
            "remote_host": "127.0.0.1",
            "remote_port": 18888
          }
        }
      }
    }
  ],
  "Socks5Server": [
    {
      "key": "EkJSKinK3QzQe_MIMmRbGoI4IrJNg-uUhqLEiOGt-LN1wOJalcO8WGt0VG0On6_7f3kFnCysM0fx7pGbh12hsBm1JD9m3G_mq2GEd_X0zvkQADRZeAftScag71fyx9iqAtbSjxNLFjf3uGipbj4bUdOLpS5EriUdo2cR1b3MciEmt9HP9mp9Xgq5BMIxPew6Rl9WOTV-Y3BgU-kfjsg2J52ZcTAtHJi7pkp2FfqN3w2FGOggQXyxwSOWOxQDkMsJnjzJTrTlxWn_gJq2QyukqFxV49fbL0-Mc4G_KAGXHup6YuDkTGXN5wtQRbqS1L5sihfaQP4P2Ynwk95I_Qan_A==",
      "host": "0.0.0.0",
      "port": 20000
    }
  ]
}
```
