from collections.abc import Iterable
from typing import Any

import marimo as mo


class mtqdm:
    def __init__(
        self, 
        iterable: Iterable[Any] | None = None, 
        desc: str | None = None, 
        total: int | None = None,
        **kwargs
    ):
        self.iterable = iterable
        self.desc = desc
        self.total = total
        
        # Auto-infer total from len() if possible
        if self.total is None and self.iterable is not None:
            try:
                self.total = len(self.iterable) # type: ignore
            except (TypeError, AttributeError):
                self.total = None

        # marimo uses 'title' for what tqdm calls 'desc'
        self._manager = mo.status.progress_bar(
            iterable,
            title=self.desc,
            total=self.total,
            **kwargs
        )
        self._pbar = None

    def __enter__(self):
        self._pbar = self._manager.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._manager.__exit__(exc_type, exc_val, exc_tb)

    def __iter__(self):
        # Support 'for item in mtqdm(range(10))'
        with self._manager as pbar:
            for item in self.iterable:
                yield item
                pbar.update()

    def update(self, n: int = 1):
        """Update progress by increment n."""
        if self._pbar:
            self._pbar.update(increment=n)

    def set_description(self, desc: str):
        """Update the progress bar title."""
        self.desc = desc
        if self._pbar:
            self._pbar.update(title=desc)

    def set_postfix(self, ordered_dict: dict[str, Any] | None = None, **kwargs):
        """Update the progress bar subtitle using key-value pairs."""
        # tqdm logic: merge dict and kwargs
        postfix_parts = []
        if ordered_dict:
            postfix_parts.extend([f"{k}={v}" for k, v in ordered_dict.items()])
        if kwargs:
            postfix_parts.extend([f"{k}={v}" for k, v in kwargs.items()])
        
        subtitle = ", ".join(postfix_parts)
        if self._pbar:
            self._pbar.update(subtitle=subtitle)

    def close(self):
        """Explicitly close the bar if not using context manager."""
        if self._pbar:
            self._manager.__exit__(None, None, None)
