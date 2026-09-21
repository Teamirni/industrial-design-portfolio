"""
翁彥斌作品集 v2 · 轻量 QA 脚本
功能：检查所有 HTML 文件中的相对链接与图片 src 是否真实存在。
"""

import os
import re
from pathlib import Path

BASE = Path(__file__).parent.resolve()


def collect_links(html_path: Path, text: str) -> list:
    links = []
    # href="..." 与 src="..."，忽略绝对 URL、#anchor、mailto:、tel:
    for match in re.finditer(r'(?:href|src)="([^"]+)"', text):
        url = match.group(1)
        if url.startswith('http://') or url.startswith('https://'):
            continue
        if url.startswith('#') or url.startswith('mailto:') or url.startswith('tel:'):
            continue
        if url == '':
            continue
        links.append(url)
    return links


def main():
    errors = []
    html_files = sorted(BASE.rglob('*.html'))

    print(f'检查 {len(html_files)} 个 HTML 文件...')

    for html in html_files:
        text = html.read_text(encoding='utf-8')
        links = collect_links(html, text)
        for link in links:
            # 相对当前 HTML 所在目录解析
            target = (html.parent / link).resolve()
            if not target.exists():
                errors.append((html.relative_to(BASE), link, target.relative_to(BASE) if BASE in target.parents else target))

    if not errors:
        print('✅ 所有相对链接与图片均能正确解析。')
        return 0

    print(f'❌ 发现 {len(errors)} 处引用缺失：')
    for html_file, link, target in errors:
        print(f'  - {html_file} 引用 "{link}" → 未找到 {target}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
