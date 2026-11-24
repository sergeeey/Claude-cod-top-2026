import re, pathlib
p = pathlib.Path('fixed/money.py'); s = p.read_text(encoding='utf-8')
s = s.replace('    text = f"{q:f}"\n', '    sign = "-" if q < 0 else ""\n    text = f"{abs(q):f}"\n')
s = s.replace('return " ".join(groups) + "," + frac', 'return sign + " ".join(groups) + "," + frac')
p.write_text(s, encoding='utf-8')
t = pathlib.Path('test_money_hidden.py').read_text(encoding='utf-8')
fx = pathlib.Path('fixed').resolve().as_posix()
t = re.sub(r'sys\.path\.insert\(0, r"[^"]+"\)', lambda _m: f'sys.path.insert(0, r"{fx}")', t)
pathlib.Path('test_fixed.py').write_text(t, encoding='utf-8')
