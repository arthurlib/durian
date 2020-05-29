# -*- coding: utf-8 -*-

import logging
import sys


def get_logger():
    # 获取logger实例，如果参数为空则返回root logger
    logger = logging.getLogger("Proxy")

    # 指定日志的最低输出级别，默认为WARN级别
    logger.setLevel(logging.ERROR)

    # 指定logger输出格式
    # formatter = logging.Formatter('%(name)s %(asctime)s %(pathname)s; file_name: %(filename)s; %(module)s; %(funcName)s; line:%(lineno)d; %(levelname)-8s: %(message)s')
    formatter = logging.Formatter('%(asctime)s %(filename)s;%(funcName)s;line:%(lineno)d; %(levelname)-8s: %(message)s')

    # 控制台日志
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.formatter = formatter  # 也可以直接给formatter赋值
    # 为logger添加的日志处理器
    logger.addHandler(console_handler)

    # 文件日志
    # file_handler = logging.FileHandler("test.log")
    # file_handler.setFormatter(formatter)  # 可以通过setFormatter指定输出格式
    # logger.addHandler(file_handler)

    # 移除一些日志处理器
    # logger.removeHandler(file_handler)
    return logger


logger = get_logger()


def test():
    # 输出不同级别的log
    logger.debug('this is debug info')
    logger.info('this is information')
    logger.warning('this is warning message')
    logger.error('this is error message')
    logger.fatal('this is fatal message, it is same as logger.critical')
    logger.critical('this is critical message')
    # 等同于error级别，但是会额外记录当前抛出的异常堆栈信息
    logger.exception('this is an exception message')


if __name__ == '__main__':
    test()
