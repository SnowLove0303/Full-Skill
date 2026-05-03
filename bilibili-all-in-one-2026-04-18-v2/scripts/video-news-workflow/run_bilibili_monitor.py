#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站UP主定时监控脚本 (Cron版)
每2小时运行一次，检查三位UP主的最新视频并生成AI早报

UP主列表:
- 橘郡Juya: UID 285286947
- 初芽Sprout: UID 1638385490
- 程序员晓刘: UID 615697341
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

# 在import前设置UP_LIST，确保覆盖默认配置
import os
os.environ['VIDEO_NEWS_UP_LIST'] = '橘郡Juya:285286947,初芽Sprout:1638385490,程序员晓刘:615697341'

# 切换到脚本目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

# 导入并覆盖UP_LIST
sys.path.insert(0, SCRIPT_DIR)
import run

# 修改UP_LIST为三位UP主
run.UP_LIST = [
    {"name": "橘郡Juya", "uid": "285286947"},
    {"name": "初芽Sprout", "uid": "1638385490"},
    {"name": "程序员晓刘", "uid": "615697341"},
]

if __name__ == '__main__':
    run.main()
