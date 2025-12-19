#!/usr/bin/env python3
"""
Remove AI-like styling from documentation and code.
- Remove excessive emojis from headers
- Remove overly formal punctuation
- Clean up AI-generated patterns
"""

import re
from pathlib import Path


def clean_markdown_file(file_path):
    """Clean AI-like styling from markdown file."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    original = content

    # Remove emojis from headers (keep content emojis for visual indicators)
    content = re.sub(
        r"^(#{1,6})\s*[🎯📊📧✨🚀💼📈🎯📢🔧📝✅🐛📊🔍💡🎉🤖⭐⚡🔄📋🏗️📁🗄️📈🎨📚🔗⚙️]\s*",
        r"\1 ",
        content,
        flags=re.MULTILINE,
    )

    # Remove excessive horizontal rules
    content = re.sub(r"\n---\n\n---\n", r"\n\n", content)
    content = re.sub(r"\n---\n(#{1,6})", r"\n\n\1", content)

    # Remove "**" emphasis from section headers that are already headers
    content = re.sub(r"^(#{1,6})\s*\*\*(.*?)\*\*\s*$", r"\1 \2", content, flags=re.MULTILINE)

    # Clean up excessive emphasis
    content = re.sub(r"\*\*\*\*(.*?)\*\*\*\*", r"**\1**", content)

    # Remove trailing punctuation from headers (except ? for questions)
    content = re.sub(r"^(#{1,6}\s+.*?)[.!:]+\s*$", r"\1", content, flags=re.MULTILINE)

    if content != original:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    return False


def main():
    docs_dir = Path("docs")
    cleaned = 0

    for md_file in docs_dir.glob("*.md"):
        if clean_markdown_file(md_file):
            print(f"Cleaned: {md_file.name}")
            cleaned += 1

    print(f"\nCleaned {cleaned} files")


if __name__ == "__main__":
    main()
