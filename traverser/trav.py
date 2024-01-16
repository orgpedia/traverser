import os
import time
import json

import re
from pathlib import Path
from urllib.parse import urlparse, urljoin
from typing import List, Tuple, Optional

from more_itertools import flatten
from playwright.sync_api import sync_playwright


def start(self, url, log_file):
    pass


class Table:
    def __init__(self, headers, rows_texts, rows_links):
        self.header = headers[0]
        self.rows_texts = rows_texts
        self.rows_links = rows_links

    def get_col(self, idx):
        return [row[idx] for row in self.rows_texts]

    def get_col_links(self, idx):
        return flatten(row[idx] for row in self.rows_links)

    def get_cols(self, col_names):
        if col_names:
            col_idxs = [idx for idx in len(self.header) if self.header[idx] in col_names]
        else:
            col_idxs = range(len(self.header))

        return [self.get_col(idx) for idx in col_idxs]

    def get_cols_links(self, col_names):
        if col_names:
            col_idxs = [idx for idx in len(self.header) if self.header[idx] in col_names]
        else:
            col_idxs = range(len(self.header))
        return [self.get_col_links(idx) for idx in col_idxs]


class Link:
    def __init__(self, href: str, text: str, base_url: str):
        self.__href = href
        self.__text = text
        if isinstance(base_url, str) and base_url[:4] == 'http':
            self.__base_url = base_url
        else:
            self.__base_url = None

        self.__url = None

    def set_url(self, new_url):
        self.__url = new_url

    @property
    def url(self):
        print(self.__base_url, self.__href)
        if not self.__base_url:
            return self.__href

        self.__url = urljoin(self.__base_url, self.__href) if self.__url is None else self.__url
        return self.__url

    @property
    def text(self):
        return self.__text

    @property
    def extension(self):
        return Path(urlparse(self.__href).path).suffix

    @property
    def name(self):
        return Path(urlparse(self.__href).path).name

    def is_pdf(self):
        return Path(urlparse(self.__href).path).suffix.lower() == '.pdf'

    def is_relative(self):
        parsed = urlparse(self.__href)
        return not parsed.scheme and not parsed.netloc

    def get_directory_structure(self, relative_only=False):
        if relative_only:
            parsed_url = urlparse(self.__href)
            return os.path.dirname(parsed_url.path).lstrip('/')
        else:
            parsed_url = urlparse(self.url)
            return os.path.dirname(parsed_url.path).lstrip('/')

    def clone(self, url):
        c = Link(url, self.text)
        return c


class Traverser:
    def __init__(self, url, log_file, headless=False, download_pdf=False):
        self.playwright = sync_playwright.start()

        # Overwrite to always open pdf externally.
        if download_pdf:
            chromium_dir = Path('./chrome/userdir/Default')
            chromium_dir.mkdir(parents=True, exist_ok=True)

            prefs_file = chromium_dir / 'Preferences'
            prefs_file.write_text(
                json.dumps(
                    {
                        'plugins': {'always_open_pdf_externally': True},
                    }
                )
            )
            print('Setting preferences')
            import pdb

            pdb.set_trace()
            prefs_file_str = str(prefs_file.absolute())
            self.browser = self.playwright.chromium.launch(
                args=[f'--initial-preferences-file={prefs_file_str}'], headless=headless
            )
        else:
            self.browser = self.playwright.chromium.launch(headless=headless)

        self.page.set_extra_http_headers(
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            }
        )
        self.log_file = Path(log_file) if log_file else log_file
        self.timeout_urls = []
        self.page = self.browser.new_page()
        self.page.goto(url)
        self._write_log(f'Starting with {url}')

    def __del__(self):
        self.browser.close()
        self.playwright.stop()

    def _write_log(self, message: str):
        self.log_file.write_text(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

    def _build_link(self, anchor):
        return Link(anchor.get_attribute('href'), anchor.inner_text(), self.get_current_url())

    def _build_table(self, table):
        headers, rows_texts, rows_links = [], [], []

        for row, idx in enumerate(table.query_selector_all("tr")):
            header_elems = row.query_selector_all('th')
            if header_elems:
                header = [e.text_content() for e in header_elems]
                headers.append(header)
            else:
                row_texts, row_links = [], []
                for cell in row.query_selector_all('td'):
                    row_texts.append(cell.text_content())
                    row_links.append([self._build_link(a) for a in cell.query_selector_all('a')])

                rows_texts.append(row_texts)
                rows_links.append(row_links)
        return Table(headers, rows_texts, rows_links)

    def click(self, title=None, text=None, id_=None, ignore_error=False):
        if title:
            anchor = self.page.query_selector(f'a[title="{title}"]')
        elif text:
            anchor = self.page.query_selector(f'a >> text="{text}"')
            if not anchor:
                anchor = self.page.query_selector(f'text="{text}"')
        elif id_:
            anchor = self.page.query_selector(f'#{id_}')
        else:
            raise ValueError("Either title or text must be provided")

        if anchor:
            self.clicked_link = self._build_link(anchor)
            anchor.click()
            self._write_log(f"Clicked on link {self.clicked_link}")
            return True

        elif not ignore_error:
            self._write_log(f"Clicked on link {[title, text, id_]} - Not Found")
            raise Exception("Link not found")
        else:
            self._write_log(f"Clicked on link {[title, text, id_]} - Not Found")
            return False

    def click_link(self, link) -> bool:
        self.click_link = link
        self.page.click(f'a[href="{link.url}"]')
        self._write_log(f"Clicked on link {self.clicked_link}")
        return True

    def set_form_element(self, form_id, value):
        element = self.page.locator(f'#{form_id}')
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

    def get_text(self, id_=None, class_=None) -> str:
        """Get the text for the element associated with id or class_name"""
        if id_:
            element = self.page.query_selector(f'#{id_}')
        elif class_:
            element = self.page.query_selector(f'.{class_}')
        else:
            raise ValueError("Either id or class must be provided")

        if element:
            return element.inner_text()
        else:
            return None

    def get_drop_downs(self, id_=None, class_=None) -> List[Tuple[str, str]]:
        if id_:
            options = self.page.query_selector_all(f'#{id_} > option')
        elif class_:
            options = self.page.query_selector_all(f'select[name="{class_}"] option')
        else:
            options = self.page.query_selector_all('select option')

        return [(option.get_attribute('value'), option.inner_text()) for option in options]

    def get_links(self, text_regex=None, url_regex=None, class_regex=None) -> List[Link]:
        anchors = self.page.query_selector_all('a')

        if text_regex:
            text_pattern = re.compile(text_regex)
            anchors = [a for a in anchors if text_pattern.match(a.inner_text())]

        if url_regex:
            url_pattern = re.compile(url_regex)
            print(len(anchors), url_pattern)
            print([a.get_attribute('href') for a in anchors])

            anchors = [a for a in anchors if url_pattern.search(a.get_attribute('href'))]

        if class_regex:
            r = re.compile(class_regex)
            anchors = [
                a for a in anchors if any(r.match(c) for c in a.get_attribute('class').split())
            ]

        return [self._build_link(a) for a in anchors]

    def get_tables(self, id_regex=None, class_regex=None, caption_regex=None) -> List[Table]:
        def elim_none(v):
            return v if v is not None else ''

        if id_regex:
            id_pattern = re.compile(id_regex)
            tables = self.page.query_selector_all('table')
            tables = [
                table for table in tables if id_pattern.match(elim_none(table.get_attribute('id')))
            ]
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

        tables = [self._build_table(t) for t in tables]

        return tables

    def get_table_links(self, table, col_name=None):
        links = []
        if col_name:
            return table.get_cols([col_name])
        else:
            for col in table.get_cols():
                if any(isinstance(c, Link) for c in col):
                    links.extend(col)
            return links

    def get_current_url(self) -> str:
        return self.page.url

    def get_clicked_link(self) -> Link:
        return self.clicked_link

    def save_screenshot(self, file_path):
        self.page.screenshot(path=file_path, full_page=True)
        self._write_log(f"Saved screenshot at {file_path}")

    def save_html(self, file_path):
        Path(file_path).write_text(self.page.content())
        self._write_log(f"Saved html at {file_path}")

    def has_element(
        self,
        element_type: str,
        id_regex: Optional[str] = None,
        class_regex: Optional[str] = None,
        text_regex: Optional[str] = None,
    ) -> bool:
        if id_regex:
            id_pattern = re.compile(id_regex)
            elems = self.page.query_selector_all(f'{element_type}#{id_pattern.pattern}')
        elif class_regex:
            class_pattern = re.compile(class_regex)
            elems = self.page.query_selector_all(f'{element_type}.{class_pattern.pattern}')
        elif text_regex:
            text_pattern = re.compile(text_regex)
            elems = self.page.query_selector_all(f'{element_type} >> text={text_pattern.pattern}')
        else:
            elems = self.page.query_selector_all(element_type)

        return len(elems) > 0

    def wait(self, seconds):
        time.sleep(3)
        self.page.wait_for_timeout(seconds * 1000)
