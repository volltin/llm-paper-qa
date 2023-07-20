# count tokens from stdin
import tiktoken
import click
import sys

@click.command()
@click.option("--model", default="gpt-4", help="Model name")
def main(model):
    enc = tiktoken.encoding_for_model(model)
    print(len(enc.encode(sys.stdin.read())))

if __name__ == "__main__":
    main()
