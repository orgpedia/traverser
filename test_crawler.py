import os
import re
import shutil
from pathlib import Path

import pytest

from crawler import Crawler, Link

test_page_url = 'file://' + str(Path('sample2.html').resolve())
output_dir = Path('test_output')

@pytest.fixture(scope="module")
def crawler():
    c = Crawler()
    c.start(test_page_url, output_dir)
    yield c
    #c.browser.close()
    if output_dir.exists():
        shutil.rmtree(output_dir)

def test_start(crawler):
    assert crawler.page.url.strip('/') == test_page_url
    assert crawler.output_dir == output_dir


def test_click(crawler):
    crawler.start(test_page_url, output_dir)    
    crawler.click(title='file1')
    assert re.search(r'example\.com/file1\.pdf$', crawler.get_current_url())
    crawler.page.goto(test_page_url)


def test_get_drop_downs(crawler):
    drop_downs = crawler.get_drop_downs(id='test-dropdown')
    print(drop_downs)
    assert drop_downs == [('option1', 'Option 1'), ('option2', 'Option 2')]
    

def test_save_screenshot(crawler):
    crawler.save_screenshot('test_screenshot')
    assert (output_dir / 'test_screenshot.png').exists()

def test_get_text(crawler):
    text = crawler.get_text(id='paragraph')
    assert text == 'This is a sample paragraph.'
    

def test_save_html(crawler):
    crawler.save_html('test_html')
    assert (output_dir / 'test_html.html').exists()

def test_get_links(crawler):
    links = crawler.get_links(url_regex=r'file\d\.pdf')
    assert len(links) == 3

def test_output_go_down(crawler):
    crawler.output_go_down('subdir')
    assert (output_dir / 'subdir').exists()
    crawler.output_go_up()    

def test_output_go_up(crawler):
    crawler.output_go_down('subdir')
    crawler.output_go_up()
    assert crawler.output_dir == output_dir

@pytest.mark.skip("Need to download pdf from a page")
def test_save_links(crawler):
    links = [Link('https://example.com/file1.pdf', 'Download file 1')]
    crawler.save_links(links)
    assert (output_dir / 'file1.pdf').exists()

def test_write_links(crawler):
    links = [Link('https://example.com/file1.pdf', 'Download file 1')]
    crawler.write_links(links)
    assert (output_dir / 'urls.yml').exists()

def test_set_form_element(crawler):
    crawler.set_form_element(id='test-dropdown', value='option2')
    selected_value = crawler.page.eval_on_selector("#test-dropdown", "el => el.value")
    assert selected_value == 'option2'

def test_get_current_url(crawler):
    url = crawler.get_current_url()
    assert url == test_page_url

def test_has_element(crawler):
    assert crawler.has_element(element_type='p', id_regex='paragraph')
    assert not crawler.has_element(element_type='a', id_regex=r'nonexistent')

def test_wait(crawler):
    import time
    start_time = time.time()
    crawler.wait(2)
    elapsed_time = time.time() - start_time
    assert elapsed_time >= 2


def test_get_table_links(crawler):
    table_links = crawler.get_table_links(id_regex=r'test-table')
    assert len(table_links) == 1
    assert table_links[0].url == 'https://example.com/file3.pdf'



"""
HTML forms are an essential part of web applications and are used to collect user input. A variety of form elements are available to accommodate different types of input. Here's a list of the most common form elements:

    <form>: The container for all form elements. It defines a form that can be submitted to a server for processing.

    <input>: The most versatile form element, with different types depending on the desired user input. Common input types include:
        text: A single-line text field for user input.
        password: Similar to text, but the characters are obscured for security.
        submit: A button that submits the form data to the server.
        reset: A button that resets all form fields to their default values.
        radio: A circular button that allows users to choose a single option from a list.
        checkbox: A square button that allows users to select multiple options from a list.
        button: A general-purpose button that can be used for various purposes, such as client-side scripting.
        file: A file picker that lets users upload files.
        hidden: A hidden field that stores data that is not visible to the user but is submitted with the form.
        image: An image that functions as a submit button.
        date, time, datetime-local, month, week: Various date and time input types.

    <textarea>: A multi-line text field for user input, often used for comments or messages.

    <select>: A drop-down list that lets users choose one or more options from a predefined list. It contains <option> elements to define the available choices.

    <option>: Represents a single choice within a <select> element.

    <optgroup>: A container for grouping related <option> elements within a <select> element. It can be used to create categories or sections within a drop-down list.

    <label>: A text label associated with a form control, such as an <input> or <select>. It improves accessibility and allows users to click the label to focus on the associated form control.

    <fieldset>: A container for grouping related form elements and creating a visual boundary around them. It can be used in conjunction with the <legend> element to provide a caption or title for the group.

    <legend>: Represents a caption or title for a <fieldset> element.

    <datalist>: Provides an auto-complete feature for <input> elements. It contains a list of <option> elements that represent suggested input values.

    <meter>: Represents a scalar measurement within a known range, such as disk usage or a progress indicator.

    <progress>: Represents the completion progress of a task, such as a file download or a form submission.

These form elements, when combined, can create powerful and interactive forms that collect various types of user input, enhance user experience, and facilitate communication between the client and server.

"""                  
