import sys
sys.path.insert(0, "/workspace/src")
from obfuscator_core import tokenize, Parser

src = """  local t = {x = 1}
  (if true then t else t)['x'] = 99"""
toks = tokenize(src)
p = Parser(toks)
stmt1 = p.parse_statement()
print('stmt1:', stmt1.type, 'pos:', p.pos)
for j in range(p.pos, min(p.pos+15, len(p.tokens))):
    t = p.tokens[j]
    print(f'  tok[{j-p.pos}]:', t.type, repr(t.value))
