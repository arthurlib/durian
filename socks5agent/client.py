import os
import sys

base_path = os.path.dirname(os.path.realpath(sys.argv[0]))
sys.path.append(os.path.join(base_path, "../../"))

from proxy.socks5agent.lib import cipher
import proxy.socks5agent.client.client_selectors as client

if __name__ == '__main__':
    key = 'EkJSKinK3QzQe_MIMmRbGoI4IrJNg-uUhqLEiOGt-LN1wOJalcO8WGt0VG0On6_7f3kFnCysM0fx7pGbh12hsBm1JD9m3G_mq2GEd_X0zvkQADRZeAftScag71fyx9iqAtbSjxNLFjf3uGipbj4bUdOLpS5EriUdo2cR1b3MciEmt9HP9mp9Xgq5BMIxPew6Rl9WOTV-Y3BgU-kfjsg2J52ZcTAtHJi7pkp2FfqN3w2FGOggQXyxwSOWOxQDkMsJnjzJTrTlxWn_gJq2QyukqFxV49fbL0-Mc4G_KAGXHup6YuDkTGXN5wtQRbqS1L5sihfaQP4P2Ynwk95I_Qan_A=='
    cipher.set_cipher('caesar', key)

    client.listen(7001, '127.0.0.1', 7000)
