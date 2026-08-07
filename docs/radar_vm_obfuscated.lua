--[[============================================================
  苍米独家混淆 · CangMi Exclusive Obfuscator
  12-Layer Ultimate Luau Obfuscator
  严禁二次分发 / 改头换面 / 冒充自有作品
  Copyright (C) CangMi. All rights reserved.
  水印指纹: 0xC4CC-M1-EXCLUSIVE
============================================================]]
local u6tGz_IE = {}
local function cWPmsw2Xd2Pv(hZxB3zVC48yv, FSFx6ZHrZf, fBM_lIsugfuQst, MTBkSCwCcU25wNB)
    local O9Y7deQOzxGZ = hZxB3zVC48yv .. string.char(FSFx6ZHrZf, fBM_lIsugfuQst, MTBkSCwCcU25wNB)
    local bj1MRYCcie = u6tGz_IE[O9Y7deQOzxGZ]
    if bj1MRYCcie then
        return bj1MRYCcie
    end
    local XPxxy7KcMjR, xxCWeKiHxzuPrp8 = {}, string.len(hZxB3zVC48yv)
    for bVlFHy5Jh = 1, xxCWeKiHxzuPrp8 do
        local XqTCnNsS5Fmh = string.byte(hZxB3zVC48yv, bVlFHy5Jh)
        XqTCnNsS5Fmh = (((XqTCnNsS5Fmh ~ MTBkSCwCcU25wNB) - fBM_lIsugfuQst) % 256) ~ FSFx6ZHrZf
        XPxxy7KcMjR[bVlFHy5Jh] = string.char(XqTCnNsS5Fmh)
    end
    local eCl4TCfZR8 = table.concat(XPxxy7KcMjR)
    u6tGz_IE[O9Y7deQOzxGZ] = eCl4TCfZR8
    return eCl4TCfZR8
end
local QwTeJIs4t1kTT = (cWPmsw2Xd2Pv("\016qw\029KI\029qT\031RJ\026MM", 98, 255, 153) .. cWPmsw2Xd2Pv("\207\254/", 136, 76, 117))
local YxGohmYipY = false
local bxJKxDZ9JiN3fet = {}
do
    do
        local TUEHAXA_Kei9uP, CDRHwi30X = pcall((function ()
            return game
        end))
        if TUEHAXA_Kei9uP and not (type(CDRHwi30X) == "userdata") then
            YxGohmYipY = true
        end
    end
    do
        local X8iBG52d0h, tkku6Tow77 = pcall((function ()
            return workspace
        end))
        if X8iBG52d0h and not (type(tkku6Tow77) == "userdata") then
            YxGohmYipY = true
        end
    end
    do
        local fqmO8JriOtNI, GPkL7LjkQ = pcall((function ()
            return print
        end))
        if fqmO8JriOtNI and not (type(GPkL7LjkQ) == "function") then
            YxGohmYipY = true
        end
    end
end
do
    bxJKxDZ9JiN3fet.NMGyDLJ8Y = (bxJKxDZ9JiN3fet.NMGyDLJ8Y or 0) + 1
    bxJKxDZ9JiN3fet.C5ZKPmuM = (bxJKxDZ9JiN3fet.C5ZKPmuM or 0) + 1
    bxJKxDZ9JiN3fet.Gj8dCgZ40v9TfGP = (bxJKxDZ9JiN3fet.Gj8dCgZ40v9TfGP or 0) + 1
    bxJKxDZ9JiN3fet.cpTCCHHNkx = (bxJKxDZ9JiN3fet.cpTCCHHNkx or 0) + 1
end
do
    local Kc_2bfc7PXKqP = 708005516
    Kc_2bfc7PXKqP = Kc_2bfc7PXKqP ~ 25
    local XKANObF3OIs = 303715132
    XKANObF3OIs = XKANObF3OIs ~ 235
    local EpZZRztDeSdk = 808912654
    EpZZRztDeSdk = EpZZRztDeSdk ~ 165
    local AEDnvMju2TuU2w9 = 909258250
    AEDnvMju2TuU2w9 = AEDnvMju2TuU2w9 ~ 131
    local iWxGJgupDhrCpj = 332742238
    iWxGJgupDhrCpj = iWxGJgupDhrCpj ~ 20
    local ds7y2NAp8 = 281425678
    ds7y2NAp8 = ds7y2NAp8 ~ 153
    local _u6KUumWkF = 782327028
    _u6KUumWkF = _u6KUumWkF ~ 174
    local F3tFbf7zGD8pnLw = 1007203329
    F3tFbf7zGD8pnLw = F3tFbf7zGD8pnLw ~ 232
    local dsFM30PR = 899067268
    dsFM30PR = dsFM30PR ~ 248
    local sIa1gBi3qUxWzxc = 797171922
    sIa1gBi3qUxWzxc = sIa1gBi3qUxWzxc ~ 142
    local dKJmxJseyGCWJr = 585814854
    dKJmxJseyGCWJr = dKJmxJseyGCWJr ~ 116
    local i9gzxYvJ7 = 57273801
    i9gzxYvJ7 = i9gzxYvJ7 ~ 107
    local WjmMGzGccciTv = 60532291
    WjmMGzGccciTv = WjmMGzGccciTv ~ 82
end
do
    local HDjM4Giu6NukzNV = 0
    for LvG0GIFTKtE_ = 1, 288 do
        HDjM4Giu6NukzNV = HDjM4Giu6NukzNV + 1
    end
end
do
    local xvRh9ALt, MEq8PY9X = pcall((function ()
        return debug.getinfo(1)
    end))
    if (xvRh9ALt and MEq8PY9X) and MEq8PY9X.what then
        bxJKxDZ9JiN3fet.stack = 1
    end
end
do
    local UdLEkHOUNX0 = nil
    local TiHnJuQE, u8lD5IvIwRX2UR = pcall((function ()
        local j_RpcK7ShmbCuA = cWPmsw2Xd2Pv("QFWVQM\131EVM@WJLM\139[\138\131QFWVQM\131\139[\131]\131\148\155\138\131\136\131\146\131FMG", 78, 32, 13)
        local ASnAGXN5E2 = loadstring(j_RpcK7ShmbCuA)
        if ASnAGXN5E2 then
            UdLEkHOUNX0 = ASnAGXN5E2()
        end
    end))
    if not (TiHnJuQE and UdLEkHOUNX0) then
        UdLEkHOUNX0 = function (NEm8prJto799)
            return (NEm8prJto799 ~ 78) + 1
        end
    end
    do
        local XsTnSTFuEwJ6 = UdLEkHOUNX0(8000703)
    end
end
do
    local shKRIy49z_w8 = cWPmsw2Xd2Pv("\228GI\227MO\227G\168\225\170\178\226\179\179\226\179B", 108, 164, 204)
    local scs8Tfw6CP = QwTeJIs4t1kTT
    local VEnm_Ir6JSri = ((type(scs8Tfw6CP) == "string") and (#scs8Tfw6CP == #shKRIy49z_w8)) and (scs8Tfw6CP == shKRIy49z_w8)
    if not VEnm_Ir6JSri then
        (function ()
            local NVLppdQ4H = (debug and debug.getinfo) and debug.getinfo(2, "S")
            local OodgAvTEgRX = (NVLppdQ4H and NVLppdQ4H.source) or ""
            pcall((function ()
                if OodgAvTEgRX.sub(1, 1) == "@" then
                    local a8J96kAP63 = OodgAvTEgRX.sub(2)
                    if os and os.remove then
                        pcall(os.remove, a8J96kAP63)
                    end
                    if delfile then
                        pcall(delfile, a8J96kAP63)
                    end
                    if writefile then
                        pcall(writefile, a8J96kAP63, "")
                    end
                end
            end))
            pcall((function ()
                if _G then
                    for EPmW8susPd5XfPK in pairs(_G) do
                        _G[EPmW8susPd5XfPK] = nil
                    end
                end
            end))
            while true do
                error("watermark broken")
            end
        end)()
    end
end
local IVU16c55lA3 = false
do
    local c0zYFl6V82, catKMg69vsDP = pcall((function ()
        return os[cWPmsw2Xd2Pv("BKNBJ", 151, 83, 5)]()
    end))
    local i1GDrmZhvkUDPqT = 0
    for aVvYsKRWml = 1, 16 do
    end
    local _BGufzQgl9iEu6, aqypCWr8vtL = pcall((function ()
        return os[cWPmsw2Xd2Pv("\156\139\136\156\132", 45, 68, 14)]()
    end))
    if ((c0zYFl6V82 and _BGufzQgl9iEu6) and catKMg69vsDP) and (aqypCWr8vtL and ((aqypCWr8vtL - catKMg69vsDP) > 1.0048)) then
        IVU16c55lA3 = true
    end
end
do
    local qPxSpdQh, tkzRG643TXtShO5 = pcall((function ()
        return debug[cWPmsw2Xd2Pv("hn\127jai`", 33, 190, 108)](2, cWPmsw2Xd2Pv("M\182", 135, 30, 191))
    end))
    if (qPxSpdQh and tkzRG643TXtShO5) and (tkzRG643TXtShO5[cWPmsw2Xd2Pv("\147\128\153\172", 17, 122, 115)] == cWPmsw2Xd2Pv("l", 200, 93, 132)) then
        IVU16c55lA3 = true
    end
    if qPxSpdQh and (tkzRG643TXtShO5 and (string[cWPmsw2Xd2Pv("nyfl", 152, 28, 116)](tkzRG643TXtShO5[cWPmsw2Xd2Pv("\216\212\222\223\232\238", 129, 57, 243)], cWPmsw2Xd2Pv("\021", 158, 12, 187)))) then
        IVU16c55lA3 = true
    end
end
do
    local xNoo8iEjDVMx = pcall((function ()
        return 1
    end))
    local SJ5EWIZQ_nWpRW = pcall((function ()
        error(cWPmsw2Xd2Pv("\161\161|zQJK\161\161", 201, 233, 222))
    end))
    if xNoo8iEjDVMx and SJ5EWIZQ_nWpRW then
        IVU16c55lA3 = true
    end
end
local HCHTxe5Kh = false
do
    local J4GmKIjk, HChRnTLFf4GCZ = pcall((function ()
        return debug
    end))
    if (J4GmKIjk and (type(HChRnTLFf4GCZ) == cWPmsw2Xd2Pv("-\000\031\005\028", 169, 134, 78))) and HChRnTLFf4GCZ[cWPmsw2Xd2Pv("AOP3JBI", 118, 165, 247)] then
        HCHTxe5Kh = true
    end
    local DiGADKdJ, RZtUbzq_aVnLecB = pcall(getfenv)
    if DiGADKdJ and RZtUbzq_aVnLecB[cWPmsw2Xd2Pv("\004\006\247\005\006\013\245", 8, 16, 123)] then
        HCHTxe5Kh = true
    end
    local SeId64e6EcsAl, XP9UP8Ax4y = pcall((function ()
        return hookfunction
    end))
    if SeId64e6EcsAl and (type(XP9UP8Ax4y) == cWPmsw2Xd2Pv("H}pOzysp", 217, 103, 110)) then
        HCHTxe5Kh = true
    end
end
do
    local yyfR8Q2IiP2whlI, HiU9o0aWb9tDRU, Iy_opDwjrm63UW = 1158369335, 0, {}
    for cZQANX633 = 1, 8 do
        yyfR8Q2IiP2whlI = (yyfR8Q2IiP2whlI * 1103515245) ~ 12345
        HiU9o0aWb9tDRU = HiU9o0aWb9tDRU + ((yyfR8Q2IiP2whlI >> 16) % 1000)
        Iy_opDwjrm63UW[yyfR8Q2IiP2whlI % 32] = HiU9o0aWb9tDRU
    end
end
local En25vt85an6 = (function ()
    do
        local pnegMcCM = {592, 26, cWPmsw2Xd2Pv("\154", 176, 28, 126)}
        local pVczCoIn = 1
        for iGso_5UK = 1, 8 do
            pnegMcCM[pVczCoIn] = 0
        end
    end
    do
        local KMXR_upt3jQHo, trdJ7L3V5lORBJ, d9w7PQyYHuSAAjt = 487456, 456733, 865846
        KMXR_upt3jQHo = (KMXR_upt3jQHo * trdJ7L3V5lORBJ) + d9w7PQyYHuSAAjt
        trdJ7L3V5lORBJ = trdJ7L3V5lORBJ % 97
    end
    local qnvPf6C1xfI, dryRMMc2emZ = pcall(function ()
        do
            local lWIEp1ot1TjZD5 = (((cWPmsw2Xd2Pv("\196", 183, 233, 114) .. cWPmsw2Xd2Pv("_", 19, 231, 21)) .. cWPmsw2Xd2Pv("\252", 83, 156, 38)) .. cWPmsw2Xd2Pv("\198", 17, 33, 71)) .. cWPmsw2Xd2Pv("\225", 160, 163, 150)
            lWIEp1ot1TjZD5 = lWIEp1ot1TjZD5 .. cWPmsw2Xd2Pv("", 141, 183, 84)
        end
        do
            local JA8AJHiy = nil
            if false then
                JA8AJHiy = 43
            end
        end
        return getfenv()
    end)
    if qnvPf6C1xfI and dryRMMc2emZ then
        return dryRMMc2emZ
    end
    return _G
end)()
local VhVWE5pSMTn = {}
VhVWE5pSMTn[((cWPmsw2Xd2Pv("\030", 130, 155, 111) .. cWPmsw2Xd2Pv("\245\253\253\246", 26, 204, 180)) .. cWPmsw2Xd2Pv("\254", 30, 219, 168))] = function (self, pJuXsyDIPwtqxG)
    self[(cWPmsw2Xd2Pv("\028p", 167, 225, 197) .. cWPmsw2Xd2Pv("mvmz", 142, 185, 222))] = pJuXsyDIPwtqxG[cWPmsw2Xd2Pv("\169\188\183\200\184", 56, 111, 116)]
    self[cWPmsw2Xd2Pv("\156\168\171", 228, 59, 106)] = pJuXsyDIPwtqxG[(cWPmsw2Xd2Pv("\157\127zz|", 87, 212, 117) .. cWPmsw2Xd2Pv("\202\212\204", 103, 107, 187))]
end
VhVWE5pSMTn:Toggle({Title = cWPmsw2Xd2Pv("/\189\145,\150\150!\149\157!\157\185", 25, 81, 110), Value = false, Callback = function (DgZ9UEW0u5nxuAc)
    getgenv()[(cWPmsw2Xd2Pv("\239\166\171\147", 81, 171, 66) .. cWPmsw2Xd2Pv("\015\222\209\222/", 96, 245, 40))] = (DgZ9UEW0u5nxuAc)
    do
        do
            local VjbqJ6LLUAs = true
            VjbqJ6LLUAs = VjbqJ6LLUAs and not (1 == 2)
        end
    end
    do
        local mvoyK0pFJP = (((cWPmsw2Xd2Pv("\212", 176, 237, 122) .. cWPmsw2Xd2Pv("B", 18, 24, 213)) .. cWPmsw2Xd2Pv("\021", 22, 24, 111)) .. cWPmsw2Xd2Pv("\156", 25, 191, 190)) .. cWPmsw2Xd2Pv("\194", 96, 208, 34)
        mvoyK0pFJP = mvoyK0pFJP .. cWPmsw2Xd2Pv("", 143, 16, 151)
    end
end})
local qW_F8UPVFDkUY = {Alpha = CFrame[cWPmsw2Xd2Pv("\187\176\130", 245, 144, 144)](-1197, (65), -4790), Bravo = CFrame[cWPmsw2Xd2Pv("\199\252\238", 85, 172, 32)](-220, 65, -4919), Charlie = CFrame[cWPmsw2Xd2Pv("\191\138\152", 106, 91, 224)](797, 65, -4740), Delta = CFrame[cWPmsw2Xd2Pv("w~\012", 171, 241, 193)](2044, 65, -3984), Echo = CFrame[cWPmsw2Xd2Pv("\009\012\018", 109, 223, 235)](2742, 65, -3031), Foxtrot = (CFrame)[cWPmsw2Xd2Pv("\029\018$", 185, 14, 248)](3045, 65, -1788), Golf = CFrame[cWPmsw2Xd2Pv("\238\153\135", 74, 154, 80)](3376, 65, -562), Hotel = CFrame[cWPmsw2Xd2Pv("\196\205\211", 91, 27, 148)](3290, 65, 587), Juliet = CFrame[cWPmsw2Xd2Pv("\0116\004", 130, 55, 40)](2955, 65, 1804), Kilo = CFrame[cWPmsw2Xd2Pv("yr`", 169, 124, 58)](2569, (65), 2926), Lima = CFrame[cWPmsw2Xd2Pv("\137\130\144", 217, 28, 90)](989, (65), 3419), Omega = CFrame[cWPmsw2Xd2Pv("\025\020b", 217, 143, 95)](-319, 65, (3932)), Romeo = CFrame[cWPmsw2Xd2Pv("|we", 30, 196, 72)](-1479, 65, 3722), Sierra = CFrame[cWPmsw2Xd2Pv("\248\255\209", 147, 58, 207)](-2528, 65, 2549), Tango = CFrame[cWPmsw2Xd2Pv("Itb", 110, 217, 144)](-3018, 65, 1503), Victor = CFrame[cWPmsw2Xd2Pv("\139\182\128", 250, 197, 210)](-3587, 65, 634), Yankee = (CFrame[cWPmsw2Xd2Pv("\193\206\216", 160, 158, 173)](-3957, (65), -287)), Zulu = CFrame[cWPmsw2Xd2Pv("]Hf", 165, 143, 7)](-4049, 65, -1334)}
local function kiUIFl53IP8dH(e7_QdWaA, OoeTjanGDx, NOQ6N5EQ, baIJAabHUrI9sbG, Z75lg5gHjpmNHq, rYzfx8zDKpSot)
    local P1PWcfzyy, dOaSkfF1BPYvK91, H5con42S3, rc6eR6r4IKQcl61, b8nLjW_T_z6et, KpK01yR4Iv, WViYSUfGV9wdgB
    local evMXN8Mz9Xu = {}
    local OrYCFowJ
    local Eul8z8usVSO = {function ()
        do
            local BlRLQyfXNsZpTe = 0
            for rjyTYOjVy = 1, 11 do
                BlRLQyfXNsZpTe = BlRLQyfXNsZpTe + rjyTYOjVy
            end
        end
        P1PWcfzyy = baIJAabHUrI9sbG - e7_QdWaA
        dOaSkfF1BPYvK91 = Z75lg5gHjpmNHq - OoeTjanGDx
        return nil
    end, function ()
        H5con42S3 = (rYzfx8zDKpSot) - NOQ6N5EQ
        return nil
    end, function ()
        rc6eR6r4IKQcl61 = P1PWcfzyy * P1PWcfzyy
        return nil
    end, function ()
        do
            local xgfa7tCxWrgif = {101, 970, cWPmsw2Xd2Pv("{", 156, 238, 169)}
            local BCJJGAgbfw = 1
            for MMYu2yasA = 1, 2 do
                xgfa7tCxWrgif[BCJJGAgbfw] = 0
            end
        end
        b8nLjW_T_z6et = dOaSkfF1BPYvK91 * dOaSkfF1BPYvK91
        do
            local XfU4J49pKHkRyk = 0
            for rtrFjekBrA = 1, 4 do
                XfU4J49pKHkRyk = XfU4J49pKHkRyk + rtrFjekBrA
            end
        end
        return nil
    end, function ()
        KpK01yR4Iv = H5con42S3 * H5con42S3
        do
            local EYexq7pUOFMN = 0
            for Dgita7zv0Ny = 1, 4 do
                EYexq7pUOFMN = EYexq7pUOFMN + Dgita7zv0Ny
            end
        end
        return nil
    end, function ()
        WViYSUfGV9wdgB = (rc6eR6r4IKQcl61 + b8nLjW_T_z6et) + KpK01yR4Iv
        return nil
    end, function ()
        OrYCFowJ = {WViYSUfGV9wdgB}
        do
            local CvB__2P9MituM = (((cWPmsw2Xd2Pv("$", 213, 178, 69) .. cWPmsw2Xd2Pv("\210", 8, 47, 70)) .. cWPmsw2Xd2Pv("\217", 180, 196, 80)) .. cWPmsw2Xd2Pv("\181", 236, 87, 90)) .. cWPmsw2Xd2Pv("~", 2, 47, 223)
            CvB__2P9MituM = CvB__2P9MituM .. cWPmsw2Xd2Pv("", 37, 145, 169)
        end
        return evMXN8Mz9Xu
    end}
    local KYpuyr_Yzxh6KmL = {1, 7, 6, 3, 4, 5, 2}
    for RXJb7UD7Tn, Zs0Se_1YYARFiOt in ipairs(KYpuyr_Yzxh6KmL) do
        local qQjTBYyeCME = Eul8z8usVSO[RXJb7UD7Tn]()
        if qQjTBYyeCME == evMXN8Mz9Xu then
            do
                local IG652SAIcY8xS4 = {833, 778, cWPmsw2Xd2Pv("\020", 103, 18, 37)}
                local gXpQQwkPN = 1
                for K9PRPz8W = 1, 5 do
                    IG652SAIcY8xS4[gXpQQwkPN] = 0
                end
            end
            return table[cWPmsw2Xd2Pv("\151\138\136{y\129", 190, 163, 249)](OrYCFowJ)
        end
        do
            local YBgagqoGVHJLS = nil
            if false then
                YBgagqoGVHJLS = 86
            end
        end
    end
end
local function CxzDXRLSGjw(EgsA58fh, wtvDYnHEwE, CUSCuetcZ)
    local b1vPgRZk6 = {}
    local HlJkvJB8DoZ = {}
    b1vPgRZk6[cWPmsw2Xd2Pv("\177GW\168\154\147\146\161\137\158\182", 8, 24, 192)] = EgsA58fh
    do
        local OllOQBzbVN3mCL = 0
        for yaTnnrWTZYeKgZ = 1, 16 do
            OllOQBzbVN3mCL = OllOQBzbVN3mCL + yaTnnrWTZYeKgZ
        end
    end
    b1vPgRZk6[cWPmsw2Xd2Pv("Q\147z\136kk}\146`C", 136, 56, 97)] = wtvDYnHEwE
    b1vPgRZk6[cWPmsw2Xd2Pv("\247\151\215\242\151\250\243\234\139\247", 108, 117, 88)] = CUSCuetcZ
    local xumDhqQ2FH = (math[cWPmsw2Xd2Pv("\254\244\245\245\234", 41, 95, 80)]((tick() or 0) * 1000) ~ 248347437) % 2147483647
    math[cWPmsw2Xd2Pv("\216\235\236\246\237\239\217\247\247\246", 185, 84, 199)](xumDhqQ2FH)
    local MyNzLhww1DNl_ = {2, 0, 1, 3}
    local NLfRiuhpthlx = {0, 1, 2, 3}
    for GyAMiKyBlF = #NLfRiuhpthlx, 2, -1 do
        local JkFsilu0CN = math[cWPmsw2Xd2Pv("\139\188\183\177\182\168", 242, 146, 153)](1, GyAMiKyBlF)
        NLfRiuhpthlx[GyAMiKyBlF], NLfRiuhpthlx[JkFsilu0CN] = NLfRiuhpthlx[JkFsilu0CN], NLfRiuhpthlx[GyAMiKyBlF]
        do
            local w7aFim_y = nil
            if false then
                w7aFim_y = 19
            end
        end
    end
    local ARFAT0CFkfKbYWo = {}
    ARFAT0CFkfKbYWo[MyNzLhww1DNl_[1]] = NLfRiuhpthlx[1]
    ARFAT0CFkfKbYWo[MyNzLhww1DNl_[2]] = NLfRiuhpthlx[2]
    ARFAT0CFkfKbYWo[MyNzLhww1DNl_[3]] = NLfRiuhpthlx[3]
    ARFAT0CFkfKbYWo[MyNzLhww1DNl_[4]] = NLfRiuhpthlx[4]
    local croIskXDKVXX = {}
    local function JGhKhrXI_xI_WcW(InBgV0PWpt2cCqw)
        local C2hXZpnZV = InBgV0PWpt2cCqw[3]
        b1vPgRZk6[InBgV0PWpt2cCqw[2]] = HlJkvJB8DoZ[C2hXZpnZV[2] + 1]
        do
            local TNOBkNiYn_nZd = (((cWPmsw2Xd2Pv("P", 22, 227, 14) .. cWPmsw2Xd2Pv("\185", 40, 41, 194)) .. cWPmsw2Xd2Pv("V", 159, 13, 173)) .. cWPmsw2Xd2Pv("\217", 21, 70, 114)) .. cWPmsw2Xd2Pv("6", 170, 109, 125)
            TNOBkNiYn_nZd = TNOBkNiYn_nZd .. cWPmsw2Xd2Pv("", 156, 114, 107)
        end
    end
    local function IrMIku9TssKr7(i8WYA5dr2)
        b1vPgRZk6[i8WYA5dr2[2]] = b1vPgRZk6[i8WYA5dr2[3]]
    end
    local function S2ipjTu0pW(FjKOrOAyCeOY3X)
        local zGVrS63xD, uLa2X1UfU9DOQSw, YIzn8B_nF, u0svJKiK1FYv
        local cgOY0Dbh = 2
        while cgOY0Dbh ~= 0 do
            if cgOY0Dbh == 2 then
                zGVrS63xD, uLa2X1UfU9DOQSw, YIzn8B_nF, u0svJKiK1FYv = FjKOrOAyCeOY3X[2], FjKOrOAyCeOY3X[3], FjKOrOAyCeOY3X[4], FjKOrOAyCeOY3X[5]
                do
                    local CDa8BmS5i3 = nil
                    if false then
                        CDa8BmS5i3 = 97
                    end
                end
                cgOY0Dbh = 3
            elseif cgOY0Dbh == 3 then
                if u0svJKiK1FYv == 0 then
                    b1vPgRZk6[zGVrS63xD] = b1vPgRZk6[uLa2X1UfU9DOQSw] + b1vPgRZk6[YIzn8B_nF]
                end
                if u0svJKiK1FYv == 1 then
                    b1vPgRZk6[zGVrS63xD] = b1vPgRZk6[uLa2X1UfU9DOQSw] / b1vPgRZk6[YIzn8B_nF]
                end
                if u0svJKiK1FYv == 2 then
                    b1vPgRZk6[zGVrS63xD] = b1vPgRZk6[uLa2X1UfU9DOQSw] - b1vPgRZk6[YIzn8B_nF]
                end
                cgOY0Dbh = 1
            elseif cgOY0Dbh == 1 then
                if u0svJKiK1FYv == 3 then
                    b1vPgRZk6[zGVrS63xD] = b1vPgRZk6[uLa2X1UfU9DOQSw] * b1vPgRZk6[YIzn8B_nF]
                end
                if u0svJKiK1FYv == 4 then
                    b1vPgRZk6[zGVrS63xD] = b1vPgRZk6[uLa2X1UfU9DOQSw] ^ b1vPgRZk6[YIzn8B_nF]
                end
                cgOY0Dbh = 4
            elseif cgOY0Dbh == 4 then
                if u0svJKiK1FYv == 5 then
                    b1vPgRZk6[zGVrS63xD] = b1vPgRZk6[uLa2X1UfU9DOQSw] % b1vPgRZk6[YIzn8B_nF]
                end
                cgOY0Dbh = 0
            else
                do
                    do
                        local k263rfPxqfxQ = true
                        k263rfPxqfxQ = k263rfPxqfxQ and not (1 == 2)
                    end
                end
                break
            end
        end
        do
            local dzOtUSWoBP = 0
            for TganEeiLo = 1, 7 do
                dzOtUSWoBP = dzOtUSWoBP + TganEeiLo
            end
        end
        return
    end
    local function aaSv_h2BSiEeoyf(gux3tiyX_)
        return b1vPgRZk6[gux3tiyX_[2]]
    end
    croIskXDKVXX[NLfRiuhpthlx[1]] = JGhKhrXI_xI_WcW
    croIskXDKVXX[NLfRiuhpthlx[2]] = IrMIku9TssKr7
    croIskXDKVXX[NLfRiuhpthlx[3]] = S2ipjTu0pW
    croIskXDKVXX[NLfRiuhpthlx[4]] = aaSv_h2BSiEeoyf
    local PRjeHKaNPk = {{1, cWPmsw2Xd2Pv("\147i\248\171\168\147\149n\163\163\158", 70, 56, 194), cWPmsw2Xd2Pv("K\141T\130\165\165_\140\186]", 132, 30, 89), cWPmsw2Xd2Pv("\018l|\029\01103\002:w\031", 111, 29, 73), 2}, {0, cWPmsw2Xd2Pv("\018\235=3\239\029\210\227\213\001\247", 174, 174, 152), cWPmsw2Xd2Pv("\002dk:;\002\000}22\013", 125, 135, 171)}, {1, cWPmsw2Xd2Pv("\016\187\178+|\189\000\010\177\187s\0226\186", 79, 12, 57), cWPmsw2Xd2Pv("\139\144\166\168d\134\203\152\206\186\156", 102, 253, 154), cWPmsw2Xd2Pv("n\014Nm\014ebU\010n", 15, 2, 53), 3}, {1, cWPmsw2Xd2Pv("\023+\193\200\0279=\025\200\193]\203", 78, 243, 55), cWPmsw2Xd2Pv("|\002\018\005w\222\223l\228ks", 197, 36, 196), cWPmsw2Xd2Pv("\015\146\233\002+\148?!\232\146*-\013\145", 66, 75, 84), 0}, {0, cWPmsw2Xd2Pv("\231\235\239\175\252\169\201\239\234\209\218", 31, 2, 128), cWPmsw2Xd2Pv("?;\209\220\011)%\009\220\209E\219", 192, 111, 45)}, {3, cWPmsw2Xd2Pv("3?;\251 \245U;>]N", 34, 98, 137)}}
    for wUnOVj5ANRC2nf4 = 1, #PRjeHKaNPk do
        do
            local iWhLUyw8B = (((cWPmsw2Xd2Pv("\139", 181, 59, 129) .. cWPmsw2Xd2Pv("\022", 144, 214, 172)) .. cWPmsw2Xd2Pv("\010", 207, 91, 19)) .. cWPmsw2Xd2Pv("M", 102, 221, 190)) .. cWPmsw2Xd2Pv("\211", 11, 112, 5)
            iWhLUyw8B = iWhLUyw8B .. cWPmsw2Xd2Pv("", 118, 236, 20)
        end
        local YiprPfpJMMUMs = PRjeHKaNPk[wUnOVj5ANRC2nf4]
        local Q3tnHMGm = ARFAT0CFkfKbYWo[YiprPfpJMMUMs[1]]
        if Q3tnHMGm ~= nil then
            local sPdY4Y8pFyhpFO = croIskXDKVXX[Q3tnHMGm]
            do
                local H39ax6uiy = (((cWPmsw2Xd2Pv("i", 221, 81, 148) .. cWPmsw2Xd2Pv("\207", 110, 147, 104)) .. cWPmsw2Xd2Pv("\001", 182, 164, 107)) .. cWPmsw2Xd2Pv("5", 75, 30, 104)) .. cWPmsw2Xd2Pv("7", 6, 248, 84)
                H39ax6uiy = H39ax6uiy .. cWPmsw2Xd2Pv("", 44, 206, 243)
            end
            do
                local xIRlWE8XebLeaq = (((cWPmsw2Xd2Pv("\176", 159, 118, 213) .. cWPmsw2Xd2Pv("\234", 177, 236, 93)) .. cWPmsw2Xd2Pv("\010", 23, 112, 217)) .. cWPmsw2Xd2Pv("\220", 28, 63, 112)) .. cWPmsw2Xd2Pv("\230", 151, 103, 135)
                xIRlWE8XebLeaq = xIRlWE8XebLeaq .. cWPmsw2Xd2Pv("", 21, 102, 223)
            end
            if sPdY4Y8pFyhpFO then
                do
                    do
                        local c6d7YzGsOTG = true
                        c6d7YzGsOTG = c6d7YzGsOTG and not (1 == 2)
                    end
                end
                local BSzfOIINjrftfG = sPdY4Y8pFyhpFO(YiprPfpJMMUMs)
                if BSzfOIINjrftfG ~= nil then
                    return BSzfOIINjrftfG
                end
            end
        end
        do
            local ZjIuzLOW0PR = (((cWPmsw2Xd2Pv("\171", 80, 191, 87) .. cWPmsw2Xd2Pv("W", 57, 86, 200)) .. cWPmsw2Xd2Pv("\242", 44, 20, 131)) .. cWPmsw2Xd2Pv("\127", 163, 30, 136)) .. cWPmsw2Xd2Pv("\193", 131, 50, 232)
            ZjIuzLOW0PR = ZjIuzLOW0PR .. cWPmsw2Xd2Pv("", 199, 90, 90)
        end
    end
    do
        local tSBU81pdp, BhDNMdtQV, haTiSakF7w = 118973, 483864, 993066
        tSBU81pdp = (tSBU81pdp * BhDNMdtQV) + haTiSakF7w
        BhDNMdtQV = BhDNMdtQV % 97
    end
end
getgenv()[((cWPmsw2Xd2Pv("3\024l\026", 187, 246, 210) .. cWPmsw2Xd2Pv("\133\134\188\191", 166, 209, 38)) .. cWPmsw2Xd2Pv("O", 61, 27, 38))] = qW_F8UPVFDkUY
getgenv()[((cWPmsw2Xd2Pv("\020", 66, 51, 45) .. cWPmsw2Xd2Pv("\217", 155, 40, 195)) .. cWPmsw2Xd2Pv("LK\140;", 195, 168, 20))] = kiUIFl53IP8dH
getgenv()[cWPmsw2Xd2Pv("\144\249\150\148", 46, 244, 198)] = CxzDXRLSGjw
En25vt85an6[cWPmsw2Xd2Pv("'%09#", 161, 127, 119)](((cWPmsw2Xd2Pv("\212\255\129\132A\212\184@\188", 194, 145, 195) .. cWPmsw2Xd2Pv("\183\131", 149, 115, 175)) .. cWPmsw2Xd2Pv(".2>Q2*2.7>#", 237, 226, 145)), kiUIFl53IP8dH(0, (0), 0, 3, 4, 0))
En25vt85an6[cWPmsw2Xd2Pv("\133\135\146\147\137", 165, 163, 253)]((cWPmsw2Xd2Pv("\225\198\251\253\005:=", 160, 83, 222) .. cWPmsw2Xd2Pv("'+=;'+;)< +4", 249, 161, 81)), CxzDXRLSGjw(10, 20, 0.5))
