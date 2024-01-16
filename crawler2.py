from datetime import datetime
import os
from typing import Union
import urllib.request
import socket
from urllib.error import *

import re
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Tuple, Optional
from playwright.sync_api import sync_playwright
import yaml
import time
import shutil


class Link:
    def __init__(self, url: str, text: str):
        self.__url = url
        self.__text = text

    def set_url(self, new_url):
        self.__url = new_url

    @property
    def url(self):
        return self.__url

    @property
    def text(self):
        return self.__text

    @property
    def extension(self):
        return Path(urlparse(self.__url).path).suffix

    @property
    def name(self):
        return Path(urlparse(self.__url).path).name

    def is_pdf(self):
        return Path(urlparse(self.__url).path).suffix.lower() == '.pdf'


DefaultTimeout = 10  # seconds


class Crawler:
    def __init__(self, headless=False):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.page = self.browser.new_page()
        self.output_dir = None
        self.log_file = None
        self.urls_file = None
        self.timeout_count = 0
        self.timeout_urls = []

    def __del__(self):
        self.browser.close()
        self.playwright.stop()

    def _write_log(self, message: str):
        with open(self.log_file, "a") as log:
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

    def load_crawled(self):
        dirs = [d for d in output_dir.glob('*') if d.is_dir()]
        dir_dates = [get_date_from_date_str(d.name) for d in dirs]
        dir_dates = sorted(dir_dates, reverse=True)

        urls = set()
        for dir_date in dir_dates:
            urls_file = dir_date / 'urls.yml'
            if urls_file.exists():
                url_infos = yaml.load(urls_file.read_text(), Loader=yaml.FullLoader)
                urls.add(u['url'] for u in urls)
        return urls

    def start(self, url: str, output_dir: Path, crawl_dir: str):
        self.page.goto(url)
        self.base_output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.crawled_urls = self.load_crawled()

        self.output_dir = output_dir / crawl_dir

        self.log_file = self.output_dir / "log.txt"
        self.urls_file = self.output_dir / "urls.yml"
        self._write_log(f"Started crawling at {url}")

    def click(
        self, title: Optional[str] = None, text: Optional[str] = None, link_id: Optional[str] = None
    ):
        if title:
            link = self.page.query_selector(f'a[title="{title}"]')
        elif text:
            link = self.page.query_selector(f'a >> text="{text}"')
        elif link_id:
            link = self.page.query_selector(f'#{link_id}')
        else:
            raise ValueError("Either title or text must be provided")

        if link:
            link.click()
            self._write_log(f"Clicked on link with title='{title}' and text='{text}'")
        else:
            raise Exception("Link not found")

    def click_link(self, link, wait=0):
        self.page.click(f'a[href="{link.url}"]')
        self.wait(wait)

    def go_back(self):
        self.page.go_back(wait_until='networkidle')

    def set_form_element(self, form_id: str, value: str):
        element = self.page.query_selector(f'#{form_id}')
        print(f'Setting form element: {form_id}')

        if not element:
            raise ValueError(f'Incorrect id: {form_id} no element found')

        tag_name = element.evaluate('(element) => element.tagName').lower()

        if tag_name in ('text', 'password', 'textarea', 'input'):
            element.fill(str(value))
        elif tag_name == 'select':
            element.select_option(str(value))
        elif tag_name == 'radio':
            element.click()
        elif tag_name == 'checkbox':
            if value:
                element.check()
            else:
                element.uncheck()
        else:
            raise ValueError(f'Found the element but not an editable form element. Tag: {tag_name}')

    def get_drop_downs(
        self, id: Optional[str] = None, name: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        if id:
            options = self.page.query_selector_all(f'#{id} > option')
        elif name:
            options = self.page.query_selector_all(f'select[name="{name}"] option')
        else:
            options = self.page.query_selector_all('select option')

        return [(option.get_attribute('value'), option.inner_text()) for option in options]

    def get_text(self, id: Optional[str] = None, class_: Optional[str] = None) -> str:
        if id:
            element = self.page.query_selector(f'#{id}')
        elif class_:
            element = self.page.query_selector(f'.{class_}')
        else:
            raise ValueError("Either id or class must be provided")

        if element:
            return element.inner_text()
        else:
            return None

    def get_links(
        self,
        text_regex: Optional[str] = None,
        url_regex: Optional[str] = None,
        class_regex: Optional[str] = None,
    ) -> List[Link]:
        links = self.page.query_selector_all('a')

        if text_regex:
            text_pattern = re.compile(text_regex)
            links = [link for link in links if text_pattern.match(link.inner_text())]

        if url_regex:
            url_pattern = re.compile(url_regex)
            print(len(links), url_pattern)
            print([link.get_attribute('href') for link in links])
            links = [link for link in links if url_pattern.search(link.get_attribute('href'))]

        if class_regex:
            class_pattern = re.compile(class_regex)
            links = [
                link
                for link in links
                if any(
                    class_pattern.match(class_name)
                    for class_name in link.get_attribute('class').split()
                )
            ]

        return [Link(link.get_attribute('href'), link.inner_text()) for link in links]

    def get_table_links(
        self,
        id_regex: Optional[str] = None,
        class_regex: Optional[str] = None,
        caption_regex: Optional[str] = None,
    ) -> List[Link]:
        if id_regex:
            id_pattern = re.compile(id_regex)
            tables = self.page.query_selector_all('table')
            tables = [table for table in tables if id_pattern.match(table.get_attribute('id'))]
        elif class_regex:
            class_pattern = re.compile(class_regex)
            tables = self.page.query_selector_all('table')
            tables = [
                table
                for table in tables
                if any(
                    class_pattern.match(class_name)
                    for class_name in table.get_attribute('class').split()
                )
            ]
        elif caption_regex:
            caption_pattern = re.compile(caption_regex)
            tables = self.page.query_selector_all('table caption')
            tables = [
                table.evaluate_handle('el => el.parentElement')
                for table in tables
                if caption_pattern.match(table.inner_text())
            ]
        else:
            tables = self.page.query_selector_all('table')

        if len(tables) > 1:
            raise ValueError('Multiple tables found: {len(tables)} found.')
        elif len(tables) == 0:
            return []

        anchors = tables[0].query_selector_all('a')
        return [Link(a.get_attribute('href'), a.inner_text()) for a in anchors]

    def get_current_url(self) -> str:
        return self.page.url

    def crawled_before(self, links):
        return [l for l in links if l.url in self.crawled_urls]

    def save_links(self, links: List[Link], wait_seconds=0):
        def download_file(link):
            file_path = self.output_dir / link.name
            if file_path.exists():
                print('Already donwnloaded')
                return 501, file_path

            try:
                response = urllib.request.urlopen(link.url, timeout=DefaultTimeout)
            except (socket.timeout, urllib.error.URLError):
                print('Request Timedout')
                self.timeout_count += 1
                self.timeout_urls.append(link.url)
                return 408, None

            if response.getcode() == 200:
                with open(file_path, 'wb') as f:
                    f.write(response.read())
                print('File downloaded successfully')
                return response.getcode(), file_path
            else:
                return response.getcode(), None

        if self.timeout_count > 5:
            urls_str = "\n".join(self.timeout_urls)
            raise RuntimeError('Too many timeouts {urls_str}')

        if not os.path.exists(self.urls_file):
            with open(self.urls_file, 'w') as urls:
                yaml.dump('', urls)

        saved_links = []
        for link in links:
            response_code, file_path = download_file(link)
            if response_code == 200:
                saved_link_info = {
                    'url': link.url,
                    'text': link.text.replace('\n', ' '),
                    'download_time': datetime.now().isoformat(),
                    'file_path': str(file_path),
                    'crawl_dir': self.output_dir.name,
                }
                saved_links.append(saved_link_info)
            elif not file_path:
                print(f'Download Failed: {link.text} {response_code}')
            self.wait(wait_seconds)

        with open(self.urls_file, 'a') as urls:
            yaml.dump(saved_links, urls)

    def save_screenshot(self, name: str):
        file_path = self.output_dir / f"{name}.png"
        self.page.screenshot(path=file_path)
        self._write_log(f"Saved screenshot as {file_path}")

    def save_html(self, name: str):
        file_path = self.output_dir / f"{name}"
        html_content = self.page.content()
        with open(file_path, 'w') as file:
            file.write(html_content)
        self._write_log(f"Saved HTML as {file_path}")

    def write_links(self, links: List[Link]):
        link_info_list = [
            {'url': link.url, 'text': link.text, 'crawl_dir': self.output_dir.name}
            for link in links
        ]

        with open(self.urls_file, 'a') as urls:
            yaml.dump(link_info_list, urls)

    def output_go_down(self, sub_directory: str):
        self.output_dir = self.output_dir / sub_directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._write_log(f"Changed output directory to {self.output_dir}")

    def output_go_up(self, write_done=False):
        if write_done:
            (self.output_dir / '.done').touch()

        self.output_dir = self.output_dir.parent
        self._write_log(f"Changed output directory to {self.output_dir}")

    def has_done_file(self):
        return (self.output_dir / '.done').exists()

    def has_element(
        self,
        element_type: str,
        id_regex: Optional[str] = None,
        class_regex: Optional[str] = None,
        text_regex: Optional[str] = None,
    ) -> bool:
        if id_regex:
            id_pattern = re.compile(id_regex)
            elements = self.page.query_selector_all(f'{element_type}#{id_pattern.pattern}')
        elif class_regex:
            class_pattern = re.compile(class_regex)
            elements = self.page.query_selector_all(f'{element_type}.{class_pattern.pattern}')
        elif text_regex:
            text_pattern = re.compile(text_regex)
            elements = self.page.query_selector_all(
                f'{element_type} >> text={text_pattern.pattern}'
            )
        else:
            elements = self.page.query_selector_all(element_type)

        return len(elements) > 0

    def wait(self, seconds: int):
        self.page.wait_for_timeout(seconds * 1000)
