"""Build the display dictionaries consumed by firmware 1.2.x."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence


@dataclass(frozen=True)
class DisplayValue:
    tag: str
    label: str
    contents: list[str]
    number: Optional[float] = None
    string: Optional[str] = None
    pair: Optional[list[str]] = None
    tl_text: Optional[str] = None
    br_text: Optional[str] = None
    is_error: bool = False
    omit_line: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "label": self.label,
            "contents": self.contents,
            "tl_text": self.tl_text if self.tl_text is not None else self.label,
            "br_text": self.br_text,
            "is_error": self.is_error,
            "number": self.number,
            "string": self.string,
            "pair": self.pair,
            "omit_line": self.omit_line,
        }


def _number_text(value: float, decimals: Optional[int]) -> str:
    if decimals is not None:
        return f"{value:.{decimals}f}"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6g}"


def numeric(
    tag: str,
    label: str,
    value: float,
    *,
    pair: Optional[Sequence[str]] = None,
    symbol: Optional[str] = None,
    decimals: Optional[int] = None,
    br_text: Optional[str] = None,
) -> DisplayValue:
    text = _number_text(float(value), decimals)
    pair_value = list(pair) if pair else None
    prefix = [f"/{pair_value[0]}/{pair_value[1]}"] if pair_value else []
    available = 7 - len(prefix)
    if len(text) > available:
        text = f"{float(value):.{max(1, available - 2)}g}"
    if len(text) > available:
        text = text[-available:]
    use_symbol = symbol if symbol and len(text) < available else None
    padding = available - len(text) - (1 if use_symbol else 0)
    contents = prefix + ([" "] * max(0, padding))
    if use_symbol:
        contents.append(use_symbol)
    contents.extend(text)
    return DisplayValue(
        tag=tag,
        label=label,
        contents=contents[:7],
        number=float(value),
        pair=pair_value,
        br_text=br_text,
    )


def text(tag: str, label: str, value: str, *, br_text: Optional[str] = None) -> DisplayValue:
    visible = value[-7:].rjust(7)
    return DisplayValue(
        tag=tag,
        label=label,
        contents=list(visible),
        string=value,
        br_text=br_text,
    )


def error(tag: str, label: str, message: str) -> DisplayValue:
    return DisplayValue(
        tag=tag,
        label=label,
        contents=list("  ERROR"),
        string=message[:120],
        tl_text=label,
        br_text="offline",
        is_error=True,
    )

