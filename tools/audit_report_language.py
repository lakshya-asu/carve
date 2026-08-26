from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from statistics import median


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILES = (
    PROJECT_ROOT / "SCENE_DESIGN_REPORT.html",
    PROJECT_ROOT / "TECHNICAL_REPORT.html",
)

STYLE_PHRASES = (
    "a credible scene before a clever pipeline",
    "timing is a distance problem",
    "best current balance",
    "it is important to note",
    "in today's landscape",
    "at its core",
    "in conclusion",
    "game changer",
    "seamlessly",
    "delve into",
    "pivotal",
    "transformative",
)


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth and data.strip():
            self.parts.append(data.strip())


class ProseParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.block_tag: str | None = None
        self.current: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "figcaption"} and self.block_tag is None:
            self.block_tag = tag
            self.current = []

    def handle_endtag(self, tag: str) -> None:
        if tag == self.block_tag:
            block = " ".join("".join(self.current).split())
            if block:
                self.blocks.append(block)
            self.block_tag = None
            self.current = []

    def handle_data(self, data: str) -> None:
        if self.block_tag:
            self.current.append(data)


def visible_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() != ".html":
        return text
    parser = VisibleTextParser()
    parser.feed(text)
    return "\n".join(parser.parts)


def prose_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() != ".html":
        return text
    parser = ProseParser()
    parser.feed(text)
    return "\n".join(parser.blocks)


def audit(path: Path) -> dict[str, object]:
    raw = path.read_text(encoding="utf-8")
    text = visible_text(path)
    normalized = re.sub(r"\s+", " ", text).strip()
    prose = prose_text(path)
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", prose)
        if sentence.strip()
    ]
    lengths = [len(re.findall(r"\b[\w./+-]+\b", sentence)) for sentence in sentences]
    found = [phrase for phrase in STYLE_PHRASES if phrase in normalized.lower()]
    return {
        "file": str(path.relative_to(PROJECT_ROOT)),
        "words": len(re.findall(r"\b[\w./+-]+\b", normalized)),
        "sentences": len(sentences),
        "median_sentence_words": median(lengths) if lengths else 0,
        "sentences_over_25_words": sum(length > 25 for length in lengths),
        "longest_sentence_words": max(lengths, default=0),
        "style_phrases": found,
        "prohibited_dash_count": raw.count("\u2013") + raw.count("\u2014"),
        "replacement_character_count": raw.count("\ufffd"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report plain-language statistics and narrow project style checks."
    )
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-style", action="store_true")
    args = parser.parse_args()
    paths = [path.resolve() for path in args.files] if args.files else list(DEFAULT_FILES)
    results = [audit(path) for path in paths]
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for result in results:
            print(
                f"{result['file']}: {result['words']} words, "
                f"median sentence {result['median_sentence_words']} words, "
                f"{result['sentences_over_25_words']} sentences over 25 words"
            )
            for phrase in result["style_phrases"]:
                print(f"  STYLE: {phrase}")
            if result["prohibited_dash_count"]:
                print(f"  STYLE: {result['prohibited_dash_count']} prohibited dash characters")
            if result["replacement_character_count"]:
                print(f"  ENCODING: {result['replacement_character_count']} replacement characters")
    if args.fail_on_style and any(
        result["style_phrases"]
        or result["prohibited_dash_count"]
        or result["replacement_character_count"]
        for result in results
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
