import os
import sys
import hashlib
import logging
import asyncio
from pathlib import Path

import click
import tiktoken

from llm import create_stream, make_chatml
from arxiv_loader import (
    fetch_metainfo,
    fetch_paper_html,
    parse_paper_content,
    reduce_paper_content,
)
from arxiv_loader import PaperFailedToRender, PaperRenderInProgress, PaperNotFound

from codimd_client import get_codimd_client

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s [%(filename)s]: %(message)s"
)
logger = logging.getLogger(__name__)

TEXT_CACHE_DIR = Path(".cached_html")
TEXT_CACHE_DIR.mkdir(exist_ok=True)


def make_paper_query(paper_content):
    tpl = open("prompts/paper_query.tpl", "r").read()
    return tpl.format(paper_content=paper_content)


async def fetch_response_with_streaiming(stream):
    stream = await stream
    content = ""
    try:
        async for c in stream:
            if not c["choices"][0]["finish_reason"]:
                if "role" in c["choices"][0]["delta"]:
                    pass
                if "content" in c["choices"][0]["delta"]:
                    print(c["choices"][0]["delta"]["content"], end="")
                    content += c["choices"][0]["delta"]["content"]
    except Exception as e:
        logger.error(e)
    finally:
        print("")
        return content


@click.command()
@click.argument("arxiv_id")
@click.option(
    "--dry-run",
    is_flag=True,
    help="If True, don't actually generate a summary. The paper will still be downloaded and cached, but no calls will be made to the LLM.",
)
@click.option(
    "--keep-ref",
    is_flag=True,
    help="If True, keep the references in the paper before summarizing.",
)
@click.option(
    "--keep-app",
    is_flag=True,
    help="If True, keep the appendices in the paper before summarizing.",
)
@click.option(
    "--keep-latex",
    is_flag=True,
    help="If True, keep the LaTeX in the paper before summarizing, otherwise it will be converted to plain text.",
)
@click.option(
    "--use-ar5iv", is_flag=True, help="If True, use ar5iv instead of arxiv-vanity."
)
@click.option(
    "--force-refresh",
    is_flag=True,
    help="If True, force the paper to be refreshed, ignoring the cache.",
)
def main(
    arxiv_id,
    dry_run=False,
    keep_ref=False,
    keep_app=False,
    keep_latex=False,
    use_ar5iv=False,
    force_refresh=False,
):
    # read arxiv id from command line
    arxiv_id = arxiv_id.strip()

    enc = tiktoken.encoding_for_model("gpt-4")

    if arxiv_id != "test":
        # fetch paper html

        if use_ar5iv:
            paper_url = f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
        else:
            # default to arxiv-vanity
            paper_url = f"https://www.arxiv-vanity.com/papers/{arxiv_id}/"

        url_hash = str(hashlib.sha256(paper_url.encode("utf-8")).hexdigest())
        text_path = TEXT_CACHE_DIR / f"{url_hash}.txt"

        try:
            html_path = fetch_paper_html(paper_url, force_refresh=force_refresh)
            paper_content = parse_paper_content(
                html_path,
                keep_latex=keep_latex,
                remove_references=not keep_ref,
                remove_appendix=not keep_app,
            )
        except PaperNotFound:
            logger.error(f"Paper {arxiv_id} not found")
            exit(1)
        except PaperRenderInProgress:
            logger.error(f"Paper {arxiv_id} render in progress")
            exit(1)
        except PaperFailedToRender:
            logger.error(f"Paper {arxiv_id} failed to render")
            exit(1)

        paper_content = reduce_paper_content(paper_content)
        text_path.write_text(paper_content)
        logging.info(f"Saved text file to {text_path}")
    else:
        url_hash = "test"
        paper_content = "Hello!"

    messages = [
        {"role": "system", "content": open("prompts/paper_system.tpl", "r").read()},
        {"role": "user", "content": make_paper_query(paper_content)},
    ]

    prompt = make_chatml(messages)

    tokens = enc.encode(prompt)
    logger.info(f"Prompt length: {len(tokens)} tokens")

    if len(tokens) > 26_000:
        logger.error(f"Prompt too long: {len(tokens)}")
        exit(1)

    if not dry_run:
        stream = create_stream(messages=messages)
        content = asyncio.run(fetch_response_with_streaiming(stream))
    else:
        content = ""

    num_prompt_tokens = len(tokens)
    num_generated_tokens = len(enc.encode(content))
    logger.info(f"Generated length: {num_generated_tokens} tokens")

    arxiv_metadata = ""
    paper_title = f"Paper {arxiv_id}"
    if arxiv_id != "test":
        try:
            metadata = fetch_metainfo(arxiv_id)
            paper_title = metadata["title"]
            arxiv_metadata = f"**Authors**: {', '.join(metadata['authors'])}\n"
            arxiv_metadata += f"**Updated Dates**: {metadata['updated']}\n"
            arxiv_metadata += f"**Published Dates**: {metadata['published']}\n"
            arxiv_metadata += f"**Categories**: {', '.join(metadata['categories'])}\n"
            arxiv_metadata += f"**Abstract**: {metadata['abstract']}\n"

            arxiv_metadata = "----\n## Metadata\n" + arxiv_metadata
        except Exception as e:
            logger.error(e)

    summary_path = TEXT_CACHE_DIR / f"{url_hash}.summary.txt"
    summary_tpl = open("prompts/summary.tpl", "r").read()
    summary = summary_tpl.format(
        paper_title=paper_title,
        paper_arxiv_id=arxiv_id,
        num_prompt_tokens=num_prompt_tokens,
        num_generated_tokens=num_generated_tokens,
        arxiv_metadata=arxiv_metadata,
        content=content,
    )
    summary_path.write_text(summary)
    logger.info(f"Saved summary to {summary_path}")

    # upload to codimd
    if not dry_run:
        codimd_client = get_codimd_client()
        if codimd_client:
            url = codimd_client.create_and_publish(summary.strip())
            logger.info(f"Published summary to {url}")


if __name__ == "__main__":
    main()
