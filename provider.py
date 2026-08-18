# -*- coding: utf-8 -*-
"""打码 Provider 抽象：文字点选坐标识别接口（可替换任意打码服务）。"""
import abc


class CaptchaProvider(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def solve_click(self, instruction, bg_path, proxy=None):
        """按指令顺序识别背景图中每个字的坐标框。

        :param instruction: 指令文本，如 "请依次点击：倍 拌 脖 "
        :param bg_path:      背景图路径（原生 672x480 PNG）
        :param proxy:        远程识别请求使用的原始代理；本地 Provider 可忽略
        :return: 按指令顺序的框列表 [[x0,y0,x1,y1], ...]（背景图原生坐标空间）；失败返回 [] 或 None
        """
        raise NotImplementedError