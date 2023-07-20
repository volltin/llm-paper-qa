# LLM Paper QA
The LLM Paper QA is a tool designed to read, parse, and generate summaries from scientific papers hosted on the arXiv repository. This tool uses OpenAI's GPT-4 (gpt-4-32k) to generate the summaries and can be useful for quickly understanding the key points of a paper without having to read the entire document.

## Quick Start
Before running the script, you need to install the required packages using pip:

```bash
pip install -r requirements.txt
```

Once the required packages are installed, you can run the script with the following command:

```bash
python src/read_paper.py [arxiv_id]
```

Replace [arxiv_id] with the ID of the paper from arXiv that you wish to summarize.

## Options
The script supports several command-line options:

`--dry-run``: If True, don't actually generate a summary. The paper will still be downloaded and cached, but no calls will be made to the LLM.

`--keep-ref``: If True, keep the references in the paper before summarizing.

`--keep-app``: If True, keep the appendices in the paper before summarizing.

`--keep-latex``: If True, keep the LaTeX in the paper before summarizing, otherwise it will be converted to plain text.

`--use-ar5iv``: If True, use ar5iv instead of arxiv-vanity.

`--force-refresh``: If True, force the paper to be refreshed, ignoring the cache.

## Output
The script outputs a text file containing the generated summary of the paper. This summary includes the paper's metadata, number of tokens in the input prompt, number of tokens in the generated content, and the content itself.

If the CodiMD client is enabled and not in dry-run mode, the summary is also published to a CodiMD document and its URL is printed to the console.

## Known Issues
If a paper is not found, is still being rendered, or has failed to render, the script will print an error message and exit.

Please report any issues you encounter here.

## Contributing
Contributions to LLM Paper QA are welcomed.

## License
This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
