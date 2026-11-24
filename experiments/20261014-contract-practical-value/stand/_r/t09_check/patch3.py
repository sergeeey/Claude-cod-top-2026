import pathlib, re
p = pathlib.Path('fixed/money.py'); s = p.read_text(encoding='utf-8')
s = re.sub(r'\.replace\("[^"]*00a0", ""\)\.replace\("[^"]*202f", ""\)', lambda m: '.replace(chr(0xA0), "").replace(chr(0x202F), "")', s)
p.write_text(s, encoding='utf-8')
