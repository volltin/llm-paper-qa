import os
import re
import logging
from pathlib import Path
import requests
import hashlib
from bs4 import BeautifulSoup


class PaperFailedToRender(Exception):
    pass


class PaperRenderInProgress(Exception):
    pass


class PaperNotFound(Exception):
    pass


# The directory where the cached HTML and text files are stored
CACHE_DIR = Path(".cached_html")
CACHE_DIR.mkdir(exist_ok=True)


def fetch_metainfo(arxiv_id):
    """
    Fetches the metadata for a given arXiv ID.

    Parameters:
    arxiv_id (str): The arXiv ID of the paper

    Returns:
    metadata (dict): The metadata for the paper, including the title, authors, categories, published date, updated date, and abstract.
    """

    # Construct the URL for the paper
    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"

    # Fetch the XML file for the paper
    xml = requests.get(url).text

    # Parse the XML file
    soup = BeautifulSoup(xml, "xml")

    entry = soup.find("entry")

    # Extract the metadata

    def _clean(t):
        t = t.strip()
        t = t.replace("\n", " ")
        while "  " in t:
            t = t.replace("  ", " ")
        return t

    metadata = {
        "title": entry.find("title").text,
        "authors": [author.text.strip() for author in entry.find_all("author")],
        "categories": [category["term"] for category in entry.find_all("category")],
        "published": entry.find("published").text,
        "updated": entry.find("updated").text,
        "abstract": entry.find("summary").text,
    }

    # clean
    for key in metadata:
        if isinstance(metadata[key], str):
            metadata[key] = _clean(metadata[key])
        if isinstance(metadata[key], list):
            metadata[key] = [_clean(t) for t in metadata[key]]

    return metadata


# A function that fetches and caches the HTML file for a given paper URL
def fetch_paper_html(paper_url, force_refresh=False):
    """
    Fetches and caches the HTML file for a given paper URL from arXiv Vanity.

    Parameters:
    paper_url (str): The URL of the paper on arXiv or arXiv Vanity
    force_refresh (bool): Whether to ignore the cached file and fetch a new one

    Returns:
    cache_path (Path): The path of the cached HTML file

    Raises:
    PaperFailedToRender: If the paper failed to render on arXiv Vanity
    PaperRenderInProgress: If the paper is still rendering on arXiv Vanity
    PaperNotFound: If the paper is not found on arXiv Vanity
    requests.exceptions.HTTPError: If any other HTTP error occurs
    """

    # Create a session object to reuse the same connection
    session = requests.Session()

    # Compute the hash of the paper URL
    hash = hashlib.sha256(paper_url.encode("utf-8")).hexdigest()

    # Construct the cache path for the HTML file
    cache_path = CACHE_DIR / f"{hash}.html"

    # Check if the cache file exists and is not expired
    if not force_refresh and cache_path.exists():
        logging.info(f"Using cached file {cache_path}")
    else:
        logging.info(f"Fetching HTML file from {paper_url}")

        try:
            # Make a GET request to the paper URL
            response = session.get(paper_url, allow_redirects=False)
            # Raise an exception if the status code is not 200
            response.raise_for_status()
            # Write the response text to the cache file
        except requests.exceptions.HTTPError as errh:
            # 500 failed to render
            # 503 render in progress
            # 404 not found
            if response.status_code == 500:
                raise PaperFailedToRender
            elif response.status_code == 503:
                raise PaperRenderInProgress
            elif response.status_code == 404:
                raise PaperNotFound
            else:
                raise errh

        with cache_path.open("w", encoding="utf-8") as f:
            f.write(response.text)
        logging.info(f"Saved HTML file to {cache_path}")

    # Return the cache path
    return cache_path.absolute()


# A function that parses and extracts the content of the paper from the HTML file
def parse_paper_content(
    html_path, keep_latex=False, remove_references=False, remove_appendix=False
):
    """
    Parses and extracts the content of the paper from the HTML file.

    Parameters:
    html_path (Path): The path of the HTML file

    Returns:
    paper_content (str): The text content of the paper

    Raises:
    ValueError: If the HTML file is empty or invalid
    """

    # Read the HTML file as a string
    with html_path.open("r", encoding="utf-8") as f:
        html = f.read()

    # Check if the HTML file is empty
    if not html:
        raise ValueError(f"Empty HTML file: {html_path}")

    soup = BeautifulSoup(html, "html5lib")
    if soup.title:
        title = str(soup.title.string)
    else:
        title = ""

    def remove_section_by_h2(soup, target_section_names):
        target_section_names = [x.lower() for x in target_section_names]

        for h2 in soup.find_all("h2"):
            h2_text = h2.get_text().strip()
            h2_text_comp = h2_text.lower()
            # only keep letters, e.g. "7 Appendix" -> "appendix"
            h2_text_comp = re.sub(r"[^a-z]", "", h2_text_comp)

            for target_sec_name in target_section_names:
                if target_sec_name.endswith("_"):
                    if h2_text_comp.startswith(target_sec_name[:-1]):
                        h2.parent.decompose()
                        logging.info(f"Removing: {h2_text}")
                else:
                    if h2_text_comp == target_sec_name:
                        h2.parent.decompose()
                        logging.info(f"Removing: {h2_text}")

    if remove_references:
        remove_section_by_h2(
            soup,
            [
                "References",
                "Reference",
                "Bibliography",
                "Bibliography and References",
            ],
        )

    if remove_appendix:
        remove_section_by_h2(
            soup,
            [
                "Appendix",
                "Appendices",
                "Supplementary Material",
                "Supplementary Materials",
                "Supplementary",
                "Supplementary Information",
                "Supplementary Data",
                "Supplementary Appendix",
                "Supplementary Appendices",
                "Appendix_",
            ],
        )

    # dealing with <math> tags, especially for the case of ar5iv, e.g. https://ar5iv.labs.arxiv.org/html/2303.01469
    # but not for the case of arxiv-vanity, e.g. https://arxiv-vanity.com/papers/2003.01469/

    if keep_latex:
        # for ar5iv, the <math> tag has an attribute "alttext" which contains the LaTeX source
        for elem in soup.find_all("math"):
            # replace with alttext
            elem.string = elem.get("alttext")
        # for arxiv-vanity, the <span class="mjx-math" aria-label="..."> tag contains the LaTeX source
        for elem in soup.find_all("span", class_="mjx-math"):
            # replace with aria-label
            elem.string = elem.get("aria-label")
    else:
        # for ar5iv, remove the <annotation> tag
        for elem in soup.find_all("annotation-xml"):
            elem.decompose()
        for elem in soup.find_all("annotation"):
            elem.decompose()

    try:
        content = soup.find("div", class_="ltx_page_content").get_text()
        logging.info(f"Using main content extraction method for {html_path}")
    except Exception as e:
        logging.error(f"Cannot extract main content for {html_path}")
        raise PaperFailedToRender

    # Check if the content element exists
    if not content:
        raise ValueError(f"Invalid HTML file: {html_path}")

    return content


# A function that reduces the noise and whitespace from the paper content
def reduce_paper_content(paper_content):
    """
    Reduces the noise and whitespace from the paper content.

    Parameters:
    paper_content (str): The text content of the paper

    Returns:
    reduced_content (str): The reduced text content of the paper
    """

    # Remove unnecessary whitespace and noise
    paper_content = paper_content.replace("\r", "\n")
    paper_content = paper_content.replace("\t", " ")
    paper_content = paper_content.strip()
    paper_content = re.sub(r"\n\s+", "\n", paper_content)
    paper_content = re.sub(r"\s+\n", "\n", paper_content)
    paper_content = re.sub(r"\n\n+", "\n\n", paper_content)
    paper_content = re.sub(r"\s\s+", " ", paper_content)

    # Remove arXiv Vanity specific text
    paper_content = paper_content.replace(" – arXiv Vanity", "")
    paper_content = paper_content.replace(
        "arXiv Vanity renders academic papers from", ""
    )
    paper_content = paper_content.replace("arXiv as responsive web pages so you", "")
    paper_content = paper_content.replace("don’t have to squint at a PDF", "")
    paper_content = paper_content.replace("View this paper on arXiv", "")
    paper_content = paper_content.replace("arXiv Vanity", "")
    paper_content = re.sub(
        r"Generated by LaTeXML.*?Want to hear about new.*",
        "",
        paper_content,
        flags=re.DOTALL,
    )

    # Remove some latex commands
    paper_content = paper_content.replace("start_POSTSUPERSCRIPT", "")
    paper_content = paper_content.replace("end_POSTSUPERSCRIPT", "")
    paper_content = paper_content.replace("start_POSTSUBSCRIPT", "")
    paper_content = paper_content.replace("end_POSTSUBSCRIPT", "")
    paper_content = paper_content.replace("start_FLOATSUPERSCRIPT", "")
    paper_content = paper_content.replace("end_FLOATSUPERSCRIPT", "")
    paper_content = paper_content.replace("italic_", "")
    paper_content = paper_content.replace("textbf_", "")
    paper_content = paper_content.replace("textit_", "")
    paper_content = paper_content.replace("texttt_", "")

    # Return the reduced content
    return paper_content
