"""紙面HTMLをA5のPDFにする（iPad などで手書きする用）。

使い方: python -m ronbun_news.pdf [--out docs] [--date YYYY-MM-DD]
Playwright の Chromium が必要（GitHub Actions のワークフローで入れる）。
"""

import argparse
import datetime
import sys
from pathlib import Path

JST = datetime.timezone(datetime.timedelta(hours=9))


def html_to_pdf(html_path, pdf_path, executable_path=None):
    from playwright.sync_api import sync_playwright

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=executable_path)
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        page.evaluate("document.fonts.ready")  # Webフォントの読み込みを待ってから描画する
        page.pdf(path=str(pdf_path), prefer_css_page_size=True, print_background=True)
        browser.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs")
    parser.add_argument("--date", default=datetime.datetime.now(JST).date().isoformat())
    parser.add_argument("--chromium", help="Chromium の実行ファイル（省略時は Playwright の既定）")
    args = parser.parse_args(argv)
    out = Path(args.out)
    html = out / "days" / f"{args.date}.html"
    if not html.exists():
        print(f"[error] {html} がありません", file=sys.stderr)
        return 1
    html_to_pdf(html, out / "pdf" / f"{args.date}.pdf", args.chromium)
    print(f"PDF: {out / 'pdf' / f'{args.date}.pdf'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
