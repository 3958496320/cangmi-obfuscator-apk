-- 压力测试：覆盖多种 Lua 语法结构，验证混淆器健壮性
-- 注意：Roblox 专用 API（game/Instance.new 等）在 lua5.3 中不存在，
--      故仅使用标准库 + 模拟对象，确保可在 lua5.3 下运行校验。

-- 1. 闭包 + 多返回值
local function make_counter(start, step)
    local count = start
    return function()
        count = count + step
        return count
    end, function()
        return count
    end
end

local next_val, get_val = make_counter(10, 5)
local c1 = next_val()  -- 15
local c2 = next_val()  -- 20

-- 2. 方法调用（模拟对象）
local Stack = {}
Stack.__index = Stack

function Stack.new()
    return setmetatable({items = {}, size = 0}, Stack)
end

function Stack:push(v)
    self.size = self.size + 1
    self.items[self.size] = v
end

function Stack:pop()
    if self.size == 0 then return nil end
    local v = self.items[self.size]
    self.items[self.size] = nil
    self.size = self.size - 1
    return v
end

function Stack:count()
    return self.size
end

local s = Stack.new()
s:push(100)
s:push(200)
s:push(300)
local popped = s:pop()  -- 300
local remaining = s:count()  -- 2

-- 3. while / repeat 循环
local function sum_until(limit)
    local i, total = 1, 0
    while i <= limit do
        total = total + i
        i = i + 1
    end
    return total
end

local function repeat_test(n)
    local x = 0
    repeat
        x = x + 2
    until x >= n
    return x
end

-- 4. 字符串操作 + table.concat
local function build_msg(parts)
    local result = ""
    for i, part in ipairs(parts) do
        if i > 1 then
            result = result .. ", "
        end
        result = result .. tostring(part)
    end
    return result
end

local msg = build_msg({1, "two", 3, "four"})

-- 5. 嵌套表 + pairs 遍历
local config = {
    name = "test",
    values = {10, 20, 30},
    nested = {
        deep = true,
        level = 2
    }
}

local pair_count = 0
for k, v in pairs(config) do
    pair_count = pair_count + 1
end

-- 6. vararg 函数
local function join_args(...)
    local n = select("#", ...)
    local out = {}
    for i = 1, n do
        local v = select(i, ...)
        out[i] = tostring(v)
    end
    return table.concat(out, "|")
end

local joined = join_args("a", 1, true, nil, "b")

-- 7. 条件表达式 + elseif
local function classify(n)
    if n < 0 then
        return "negative"
    elseif n == 0 then
        return "zero"
    elseif n < 10 then
        return "small"
    elseif n < 100 then
        return "medium"
    else
        return "large"
    end
end

-- 8. 数值 for + step
local function range_sum(lo, hi, step)
    local total = 0
    for i = lo, hi, step do
        total = total + i
    end
    return total
end

-- 输出所有结果
print("counter:", c1, c2)
print("stack:", popped, remaining)
print("sum_until:", sum_until(10))
print("repeat_test:", repeat_test(7))
print("msg:", msg)
print("pair_count:", pair_count)
print("joined:", joined)
print("classify:", classify(-5), classify(0), classify(5), classify(50), classify(500))
print("range_sum:", range_sum(1, 10, 2))
print("config_nested:", config.nested.deep, config.nested.level)
