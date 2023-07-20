import asyncio
import openai
import os

import dotenv

dotenv.load_dotenv()

openai.api_key = os.environ["OPENAI_API_KEY"]
openai.api_base = os.environ["OPENAI_API_BASE"]
openai.api_type = os.environ["OPENAI_API_TYPE"]
openai.api_version = os.environ["OPENAI_API_VERSION"]


async def create_stream(*, prompt=None, messages=None):
    if messages is None:
        messages = [{"role": "user", "content": prompt}]

    stream = await openai.ChatCompletion.acreate(
        model="gpt-4-32k",
        engine="gpt-4-32k",
        messages=messages,
        temperature=0,
        stream=True,
    )
    return stream


def make_chatml(messages, add_suffix=True, add_role=False):
    prompt = ""
    for msg in messages:
        prompt += f"<|im_start|>{msg['role']}\n{msg['content']}\n<|im_end|>\n"
    if add_suffix:
        if add_role:
            prompt += "<|im_start|>assistant\n"
        else:
            prompt += "<|im_start|>"
    return prompt


if __name__ == "__main__":
    prompt = "What is the title of the paper?"

    async def main():
        stream = await create_stream(prompt=prompt)
        async for c in stream:
            if not c["choices"][0]["finish_reason"]:
                if "role" in c["choices"][0]["delta"]:
                    print(c["choices"][0]["delta"]["role"])
                if "content" in c["choices"][0]["delta"]:
                    print(c["choices"][0]["delta"]["content"], end="")

    asyncio.run(main())
