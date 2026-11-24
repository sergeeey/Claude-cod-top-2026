import re, pathlib
p = pathlib.Path('fixed/money.py'); s = p.read_text(encoding='utf-8')
s = s.replace('.replace("00a0", "").replace("202f", "")', '.replace("\u00a0", "").replace("\u202f", "")')
p.write_text(s, encoding='utf-8')
t = pathlib.Path('test_money_hidden.py').read_text(encoding='utf-8')
fx = pathlib.Path('fixed').resolve().as_posix()
t, n = re.subn(r'sys\.path\.insert\(\s*0,\s*r"[^"]+",?\s*\)', lambda _m: f'sys.path.insert(0, r"{fx}")', t)
print("subs", n)
pathlib.Path('test_fixed.py').write_text(t, encoding='utf-8')
