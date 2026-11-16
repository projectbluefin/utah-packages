#!/usr/bin/python3


FILE_TEMPLATE='''summary: Fonts related tests
discover:
  how: fmf
  url: https://src.fedoraproject.org/tests/fonts
prepare:
  name: tmt
  how: install
  package: {packagename}
execute:
  how: tmt
environment:
  PACKAGE: {packagename}
  FONT_ALIAS: {fontalias}
  FONT_FAMILY: {fontfamily}
  FONT_LANG: {fontlang}
'''


# file name, package name, font alias, font family, font lang
FILE_CONTENTS = [
    ("google-noto-serif-cjk-vf-fonts-jp.fmf", "google-noto-serif-cjk-vf-fonts", "serif", "Noto Serif CJK JP", "ja"),
    ("google-noto-serif-cjk-vf-fonts-kr.fmf", "google-noto-serif-cjk-vf-fonts", "serif", "Noto Serif CJK KR", "ko"),
    ("google-noto-serif-cjk-vf-fonts-sc.fmf", "google-noto-serif-cjk-vf-fonts", "serif", "Noto Serif CJK SC", "zh-cn,zh-sg"),
    ("google-noto-serif-cjk-vf-fonts-tc.fmf", "google-noto-serif-cjk-vf-fonts", "serif", "Noto Serif CJK TC", "zh-tw"),
    ("google-noto-serif-cjk-vf-fonts-hk.fmf", "google-noto-serif-cjk-vf-fonts", "serif", "Noto Serif CJK HK", "zh-hk,zh-mo"),
]

def gen_plan_files():
    for item in FILE_CONTENTS:
        file_name = item[0]
        font_alias = item[2]
        plan_content = FILE_TEMPLATE.format(packagename=item[1], fontalias=font_alias, fontfamily=item[3], fontlang=item[4])
        with open(file_name, "w") as f:
            f.write(plan_content)
            if font_alias == "sans-serif":
                f.write("  DEFAULT_SANS: 1\n")
            if font_alias == "monospace":
                f.write("  DEFAULT_MONO: 1\n")
            if font_alias == "serif":
                f.write("  DEFAULT_SERIF: 1\n")


if __name__ == "__main__":
    gen_plan_files()
