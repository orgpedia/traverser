from pathlib import Path
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import requests
import os

from typing import List, Tuple, Optional


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
            parsed = urlparse(self.__href)
            return os.path.dirname(parsed_url.path).lstrip('/')
        else:
            parsed = urlparse(self.url)
            return os.path.dirname(parsed_url.path).lstrip('/')

    def clone(self, url):
        c = Link(url, self.text)
        return c

    @classmethod
    def build_links(cls, anchors, base_url):
        links = []
        for anchor in anchors:
            href, text = anchor.get('href', ''), anchor.contents[0] if anchor.contents else ''
            if href and text:
                links.append(Link(href, text, base_url))
        return links

    @classmethod
    def build_link(cls, href, text):
        return Link(href, text, href)


def get_links(base_url, retries=1):
    if isinstance(base_url, str) and base_url[:4] == 'http':
        response = requests.get(base_url)
        if response.status_code != 200:
            print("Failed to get the webpage")
            return
        html_text = response.text
    else:
        html_text = Path(base_url).read_text()

    soup = BeautifulSoup(html_text, 'html.parser')
    return Link.build_links(soup.find_all('a'), base_url)


def get_tables(base_url, class_regex: Optional[str] = None, table_idx=None):
    if isinstance(base_url, str) and base_url[:4] == 'http':
        response = requests.get(base_url)
        if response.status_code != 200:
            print("Failed to get the webpage")
            return
        html_text = response.text
    else:
        html_text = Path(base_url).read_text()

    soup = BeautifulSoup(html_text, 'html.parser')
    if class_regex:
        tables = soup.findAll("table", {"class": class_regex})
    else:
        tables = soup.findAll("table")

    if table_idx:
        return [tables[table_idx]]
    else:
        return tables


def get_table_links(base_url, class_regex: Optional[str] = None, table_idx=None):
    tables = get_tables(base_url, class_regex, table_idx)
    if len(tables) > 1:
        raise ValueError(f'Multiple tables found: {len(tables)} found.')
    elif len(tables) == 0:
        return []

    anchors = []
    for row in tables[0].tbody.find_all('tr'):
        anchors.extend([td.a for td in row.find_all('td') if td.a])

    return Link.build_links(anchors, base_url)


def download_link(link, download_dir='.', make_directory=False, make_symlink=False):
    download_dir = Path(download_dir)
    save_dir = download_dir / link.get_directory_structure() if make_directory else download_dir

    try:
        r = requests.get(link.url)
        if r.status_code == 200:  # and 'application/pdf' in r.headers['Content-Type']:
            # Parse the filename from the URL path
            path = urlparse(link.url).path
            filename = os.path.basename(path)

            # Create directory if it doesn't exist
            if not save_dir.exists():
                os.makedirs(save_dir, exist_ok=False, parents=True)

            full_filename = save_dir / filename

            with open(full_filename, 'wb') as f:
                f.write(r.content)

            print(f"Downloaded: {filename}")
            if make_symlink:
                os.symlink(full_filename, link.name)
        else:
            print(f"Failed to download: {link.url} status: {r.status_code}")
    except Exception as e:
        print(f"An error occurred while downloading {link.url}: {e}")
        return None

    return full_filename
