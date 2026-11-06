#!/usr/bin/python3

import html2text

html = """
<html>
<body>
<h3>heading</h3>
<ul><li>item</li></ul>
</body>
</html>
"""

text = html2text.html2text(html)

print(text)

if "### heading" not in text:
    print("Heading not converted.")
    raise SystemExit(1)

if "* item" not in text:
    print("List item not converted.")
    raise SystemExit(1)
