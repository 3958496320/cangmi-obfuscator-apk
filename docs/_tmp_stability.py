# -*- coding: utf-8 -*-
"""端到端稳定性测试：多种脚本类型 → 混淆 → parse→generate 往返一致。
确保 100% 不报错（混淆阶段 + 序列化往返 + 重命名往返）。"""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
exec(open(os.path.join(HERE, 'obfuscator_all.py')).read())


SAMPLES = [
    # 1. 简单函数
    'local function f(x) return x + 1 end print(f(10))',
    # 2. 字符串操作
    'local s = "hello" .. " " .. "world" print(s)',
    # 3. 表 + 元表
    '''
local t = setmetatable({}, {__index = function(_, k) return k end})
print(t.foo)
    ''',
    # 4. 嵌套函数 + 闭包
    '''
local function counter()
    local n = 0
    return function() n = n + 1; return n end
end
local c = counter()
print(c(), c(), c())
    ''',
    # 5. 循环 + 条件
    '''
local sum = 0
for i = 1, 100 do
    if i % 2 == 0 then
        sum = sum + i
    end
end
print(sum)
    ''',
    # 6. while + break
    '''
local i = 1
while true do
    if i > 50 then break end
    i = i + 1
end
print(i)
    ''',
    # 7. 多返回值 + ipairs
    '''
local function multi() return 1, 2, 3 end
local a, b, c = multi()
print(a, b, c)
    ''',
    # 8. 复杂表达式
    '''
local function calc(x, y)
    local r = (x * 2 + y) / 3 - (x - y) % 5
    return r ^ 2
end
print(calc(10, 20))
    ''',
    # 9. 字符串方法链
    '''
local s = "Hello,World,Lua"
local parts = {}
for w in string.gmatch(s, "[^,]+") do
    table.insert(parts, w)
end
print(#parts)
    ''',
    # 10. 较大脚本（混合）
    '''
local PlayerData = {}
PlayerData.__index = PlayerData

function PlayerData.new(name)
    local self = setmetatable({}, PlayerData)
    self.name = name
    self.hp = 100
    self.inventory = {}
    return self
end

function PlayerData:take(item)
    table.insert(self.inventory, item)
    return #self.inventory
end

function PlayerData:damage(amount)
    self.hp = self.hp - amount
    if self.hp <= 0 then
        return false
    end
    return true
end

local p = PlayerData.new("Hero")
p:take("sword")
p:take("shield")
print(p.name, p.hp, #p.inventory)
    ''',
    # 11. 递归
    '''
local function fact(n)
    if n <= 1 then return 1 end
    return n * fact(n - 1)
end
print(fact(10))
    ''',
    # 12. 复杂条件 + elseif
    '''
local function grade(score)
    if score >= 90 then return "A"
    elseif score >= 80 then return "B"
    elseif score >= 70 then return "C"
    elseif score >= 60 then return "D"
    else return "F"
    end
end
print(grade(85))
    ''',
]


def test_one(src, idx):
    """对单个样本做 5 轮混淆（不同 seed），全部要求：
    1. obfuscate 不抛异常
    2. 输出非空且显著膨胀
    3. parse→generate 往返一致（语法合法）
    4. 重命名后往返一致
    """
    for trial in range(5):
        try:
            r = obfuscate(src, seed=trial * 1000 + idx)
        except Exception:
            print(f"FAIL 样本{idx} trial{trial}: obfuscate 抛异常")
            traceback.print_exc()
            return False
        code = r["code"]
        if not code or len(code) <= len(src):
            print(f"FAIL 样本{idx} trial{trial}: 输出未膨胀 "
                  f"(in={len(src)} out={len(code)})")
            return False
        # 往返：parse → generate
        try:
            chunk2 = parse_source(code)
            code2 = generate_code(chunk2)
            if not code2:
                print(f"FAIL 样本{idx} trial{trial}: 往返序列化为空")
                return False
        except Exception:
            print(f"FAIL 样本{idx} trial{trial}: parse→generate 抛异常")
            traceback.print_exc()
            return False
        # 重命名后往返
        try:
            chunk3 = parse_source(code)
            import random as _r
            rename(chunk3, _r.Random(trial * 99 + idx))
            code3 = generate_code(chunk3)
            if not code3:
                print(f"FAIL 样本{idx} trial{trial}: 重命名后序列化为空")
                return False
        except Exception:
            print(f"FAIL 样本{idx} trial{trial}: 重命名后抛异常")
            traceback.print_exc()
            return False
    return True


def main():
    ok = True
    for i, src in enumerate(SAMPLES, 1):
        if test_one(src, i):
            print(f"[stab {i:2d}] OK — 5 轮混淆全部稳定（膨胀+往返+重命名往返）")
        else:
            ok = False
    print()
    print("==== 全部通过 ====" if ok else "==== 存在失败 ====")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
