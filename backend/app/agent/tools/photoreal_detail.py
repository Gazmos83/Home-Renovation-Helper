"""Re-export: implementation lives in `plugins.photoreal_detail.tool`."""

from plugins.photoreal_detail.tool import (
    detail_screenshot,
    render_detail,
    run_detail_script,
    start_detail_pass,
)

__all__ = ["detail_screenshot", "render_detail", "run_detail_script", "start_detail_pass"]
