"""Build the display dictionaries consumed by firmware 1.2.x."""

from __future__ import annotations

import html
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

    def as_html(self) -> str:
        """Admin-UI preview HTML (get_html), matching Coinkite be-preview shape."""
        title = self.label if not self.is_error else f"{self.tag} (failed render)"
        tl = self.tl_text if self.tl_text is not None else self.label
        tl_html = html.escape(tl) if tl else "&nbsp"
        br = self.br_text
        br_html = html.escape(br) if br else "&nbsp;"
        cells = list(self.contents[:7])
        while len(cells) < 7:
            cells.append(" ")
        parts = [
            f'<table class="be-preview" title="{html.escape(title)}"><tbody><tr>\n',
            f'<td class="be-tl-text" colspan=7>{tl_html}</td><tr>\n',
        ]
        for cell in cells:
            parts.append("<td class=\"be-dig\">\n")
            parts.append(_preview_cell_html(cell))
            parts.append("</td>\n")
        parts.append(f'<tr><td class="be-br-text" colspan=7>{br_html}</td>\n')
        parts.append("</table></center>")
        return "".join(parts)


def _preview_cell_html(cell: str) -> str:
    if cell.startswith("/") and cell.count("/") >= 2:
        pieces = [part for part in cell.split("/") if part]
        if len(pieces) >= 2:
            over = html.escape(pieces[0])
            under = html.escape(pieces[1])
            return (
                f'<div class="be-ou"><span class="be-over">{over}</span>\n'
                f'<hr><span class="be-under">{under}</span>\n'
            )
    return f'<span class="be-single-char">{html.escape(cell)}</span>\n'


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

