# -*- coding: utf-8 -*-
# @Time : 2024/12/23 23:23
# @Author : CodeDi
# @FileName: wall_haven.py
# 批量并发下载wallhaven图片
# https://wallhaven.cc/help/api
# 通过解析url，传参给api接口，获取壁纸详情，下载图片


import time
import random
import requests
import logging
import os
import json
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from urllib.parse import urlparse, parse_qs

# 配置日志记录
logging.basicConfig(filename='wallhaven.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

proxies = {
    'http': '127.0.0.1:18081',
    'https': '127.0.0.1:18081',
}

# 加载配置文件
with open("config.json", 'r') as f:
    config = json.load(f)
    api_key = config['sites']['wallhaven']['api_key']


# 统一日志记录和屏幕输出
def log_and_print(message, level=logging.INFO):
    logging.log(level, message)
    print(message)


# 解析URL参数
def parse_url_params(_url):
    parsed_url = urlparse(_url)
    _params = parse_qs(parsed_url.query)
    return {k: v[0] if len(v) == 1 else v for k, v in _params.items()}


# 获取壁纸ID的通用函数
def fetch_wallpaper_ids_single(base_url, _params):
    """
    处理单次请求以获取壁纸ID
    :param base_url: 基础URL
    :param _params: 查询条件
    :return: 壁纸ID列表
    """
    pic_ids = []
    _response = make_request(base_url, _params)

    if _response.status_code == 200:
        data = _response.json()
        wallpapers = data['data']

        pic_ids.extend([wallpaper['id'] for wallpaper in wallpapers])

        log_and_print("壁纸 ID 获取成功.")
    else:
        log_and_print(f"请求失败，状态码：{_response.status_code}", logging.ERROR)

    return pic_ids


def fetch_wallpaper_ids_paginated(base_url, _params, start_page, end_page):
    """
    处理分页请求以获取壁纸ID
    :param base_url: 基础URL
    :param _params: 查询条件
    :param start_page: 起始页码
    :param end_page: 结束页码
    :return: 壁纸ID列表
    """
    pic_ids = []

    for _page in range(start_page, end_page + 1):
        _params['page'] = _page  # 更新页码参数
        _response = make_request(base_url, _params)

        if _response.status_code == 200:
            data = _response.json()
            wallpapers = data['data']

            pic_ids.extend([wallpaper['id'] for wallpaper in wallpapers])

            log_and_print(f"第 {_page} 页的壁纸 ID 获取成功.")
        else:
            log_and_print(f"请求第 {_page} 页时失败，状态码：{_response.status_code}", logging.ERROR)

        # 增加请求间隔
        time.sleep(random.uniform(1.2, 1.5))

    return pic_ids


def get_wallpaper_ids(_params, **kwargs):
    """
    获取指定查询条件下的壁纸ID
    :param _params: 查询条件（例如 'id:148879' 或其它条件）
    :param kwargs: 可选参数，包括 start_page 和 end_page
    :return: 壁纸ID列表
    """
    base_url = f'https://wallhaven.cc/api/v1/search?apikey={api_key}'

    # 检查是否提供了 start_page 和 end_page
    if 'start_page' in kwargs and 'end_page' in kwargs:
        start_page = kwargs['start_page']
        end_page = kwargs['end_page']
        pic_ids = fetch_wallpaper_ids_paginated(base_url, _params, start_page, end_page)
    else:
        pic_ids = fetch_wallpaper_ids_single(base_url, _params)

    return pic_ids


# 获取壁纸详情URL
def get_wallpaper_details(pic_id):
    try:
        response = requests.get(f"https://wallhaven.cc/api/v1/w/{pic_id}")
        if response is None:
            raise ValueError("请求返回为空")
        if response.status_code == 200:
            data = response.json()
            original_image_url = data['data']['path']
            return original_image_url
        else:
            response.raise_for_status()  # 抛出HTTPError异常
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None


# 下载图片并显示进度条
def download_image(image_url, filename):
    _response = make_request(image_url, stream=True)

    if _response.status_code == 200:
        total_size = int(_response.headers.get('content-length', 0))  # 获取图片总大小
        with open(filename, 'wb') as f:
            # 使用 tqdm 显示下载进度条
            for chunk in tqdm(_response.iter_content(1024), total=total_size // 1024, unit='KB', desc=filename):
                if chunk:
                    f.write(chunk)

        # 下载完成后记录图片大小
        file_size_mb = total_size / (1024 * 1024)
        log_and_print(f"图片已保存为 {filename}，大小：{file_size_mb:.2f} MB")
    else:
        log_and_print(f"下载失败: {image_url}", logging.ERROR)


# 保存壁纸ID到文件
def save_wallpaper_ids_to_file(pic_ids, filename='wallpaper_ids.txt'):
    # 读取文件内容，检查 wallpaper_id 是否已经存在
    existing_ids = set()
    try:
        with open(filename, 'r') as f:
            existing_ids = {line.strip() for line in f}
    except FileNotFoundError:
        pass  # 文件不存在，无需处理

    with open(filename, 'a') as f:
        for wallpaper_id in pic_ids:
            if wallpaper_id not in existing_ids:
                f.write(f"{wallpaper_id}\n")
                log_and_print(f"壁纸 ID {wallpaper_id} 已保存到 {filename}")
            else:
                log_and_print(f"壁纸 ID {wallpaper_id} 已存在，未保存")


# 执行下载任务
def main(pic_id, directory):
    original_image_url = get_wallpaper_details(pic_id)

    if original_image_url:
        log_and_print(f"原图 URL: {original_image_url}")
        pic_filename = original_image_url.split('/')[-1]
        pic_filepath = os.path.join(directory, pic_filename)

        # 检查文件是否已经存在
        if os.path.exists(pic_filepath):
            log_and_print(f"图片 {pic_filename} 已存在，跳过下载。")
        else:
            download_image(original_image_url, pic_filepath)
    else:
        log_and_print("未能获取原图 URL", logging.ERROR)


# 并行下载壁纸
def download_wallpapers_concurrently(pic_ids, directory, max_workers=5):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(main, wallpaper_id, directory) for wallpaper_id in pic_ids]
        # 等待所有任务完成
        for future in futures:
            future.result()  # 捕获异常


# 通用请求函数，包含重试机制
def make_request(_url, _params=None, stream=False, retries=3, backoff_factor=0.3):
    for attempt in range(retries):
        try:
            response = requests.get(_url, params=_params, proxies=proxies, stream=stream)
            if response.status_code == 429:
                wait_time = backoff_factor * (2 ** attempt)
                log_and_print(f"收到 429 错误，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
                continue
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            log_and_print(f"请求失败: {e}", logging.ERROR)
            if attempt < retries - 1:
                wait_time = backoff_factor * (2 ** attempt)
                log_and_print(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                log_and_print(f"请求失败，已重试 {retries} 次，放弃。", logging.ERROR)
                return None


if __name__ == '__main__':
    # purity: 安全性过滤，100/010/001/etc (sfw/sketchy/nsfw)
    # sorting: 排序方式，例如 'date_added' 或 'relevance'
    # order: 排序方向，例如 'desc' 或 'asc'
    # ai_art_filter: 是否启用AI艺术过滤，1表示不显示AI生成的图片，0表示显示AI生成的图片

    # 示例 URL，可以修改为实际需求的 URL
    # 如果最后的参数是page，例如有16页，则需要修改为page=16，这样会默认下载1-16页
    url = 'https://wallhaven.cc/search?q=like%3A5gqdq1&page=3'

    # 解析 URL 参数
    params = parse_url_params(url)
    log_and_print(f"开始执行 URL: {url} 下载任务......")
    log_and_print(f"解析的 URL 参数: {params}")

    # 按照 categories 参数下载到不同的文件夹
    # categories: 分类参数，100/010/001/etc (general/anime/people)
    pic_folder = 'general'
    if 'categories' in params:
        if params['categories'] == '100':
            pic_folder = 'general'
        elif params['categories'] == '010':
            pic_folder = 'anime'
        elif params['categories'] == '001':
            pic_folder = 'people'
    # 创建本地文件夹，如果不存在则创建
    local_folder = os.path.join(r"F:\wallhaven", pic_folder)
    if not os.path.exists(local_folder):
        os.makedirs(local_folder)

    if 'page' in params:
        # 直接检查是否提供了 start_page 和 end_page
        start_page = 1
        end_page = int(params['page'])
        wallpaper_ids = get_wallpaper_ids(params, start_page=start_page, end_page=end_page)
    else:
        wallpaper_ids = get_wallpaper_ids(params)

    # 将获取到的 wallpaper_id 列表存储到文件
    log_and_print(f"共获取到 {len(wallpaper_ids)} 张壁纸")
    save_wallpaper_ids_to_file(wallpaper_ids)

    # 输出获取到的 wallpaper_id 列表
    log_and_print(f"获取到的 wallpaper_id: {wallpaper_ids}")

    # 执行并行下载任务，最大并发数为5
    download_wallpapers_concurrently(wallpaper_ids, local_folder, max_workers=5)
