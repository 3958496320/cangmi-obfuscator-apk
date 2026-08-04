-- 测试用 Luau 脚本：覆盖多种语法结构
local function greet(name, times)
    local msg = "Hi " .. name
    local sum = 0
    for i = 1, times do
        sum = sum + i
    end
    if sum > 5 then
        msg = msg .. "!"
    end
    print(msg, sum)
    return sum
end

local function vm_test(a, b)
    local x = a + b
    local y = a * b
    local z = x - y
    return z
end

local tbl = {1, 2, 3}
local total = 0
for idx, v in ipairs(tbl) do
    total = total + v
end

print(greet("Bob", 3))
print(vm_test(3, 4))
print("total:", total)
