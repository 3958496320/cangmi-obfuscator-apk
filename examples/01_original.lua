-- ============================================================================
-- 示例 1：原始 Luau 脚本（混淆前）
-- 功能：简单的游戏辅助逻辑 —— 循环检测玩家血量并提示
-- ============================================================================

local Players = game:GetService("Players")
local player = Players.LocalPlayer

local function checkHealth(p)
    local char = p.Character
    if not char then return end
    local humanoid = char:FindFirstChild("Humanoid")
    if not humanoid then return end
    local hp = humanoid.Health
    if hp < 30 then
        print("警告：" .. p.Name .. " 血量过低: " .. tostring(hp))
    elseif hp > 100 then
        print("提示：" .. p.Name .. " 血量异常: " .. tostring(hp))
    end
end

for _, p in ipairs(Players:GetPlayers()) do
    checkHealth(p)
end

-- 注入器调用入口
print("[脚本] 已加载")
