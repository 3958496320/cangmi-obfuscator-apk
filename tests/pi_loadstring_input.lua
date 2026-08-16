-- 模拟用户真实脚本：loadstring + game:HttpGet 加载 UI，后接功能
loadstring(game:HttpGet("https://raw.githubusercontent.com/xiaopi77/xiaopi77/main/QQ1002100032-Roblox-Pi-script.lua"))()

local Players = game:GetService("Players")
local player = Players.LocalPlayer

local function notify(msg)
    print("[PI] " .. tostring(msg))
end

notify("脚本已加载")

for _, p in ipairs(Players:GetPlayers()) do
    if p ~= player then
        notify("发现其他玩家: " .. p.Name)
    end
end

local conn
conn = game:GetService("RunService").Heartbeat:Connect(function()
    -- 简单功能循环
    if player.Character and player.Character:FindFirstChild("Humanoid") then
        local hum = player.Character.Humanoid
        if hum.Health < hum.MaxHealth then
            notify("血量不足")
        end
    end
    conn:Disconnect()
end)
