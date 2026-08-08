-- [AI-DETECT] 付费级字节码 VM 保护
local function YCBRAbF5()
    local UqfwehwSbwwla = {{3153705735,"FLOv1mpbU",3153705734},{3153705736,"z0vtAggJ5EEv",3153705734},{3153705740,"CFQPS59YwfuN","FLOv1mpbU",3153705736,"z0vtAggJ5EEv"},{3153705753}}
    local _xeM4jnanQR = 3153705730
    local VasxSb6Mo = {}
    local H3LTzCgVqws2WR = {}
    local IWzrO9bhr3Q = {["CFQPS59YwfuN"]=42,["FLOv1mpbU"]=1,["z0vtAggJ5EEv"]=263}  -- P2-2 寄存器虚拟化映射表
    local yzLDiJQtw = {[3]=true,[4]=true,[36]=true,[90]=true,[72]=true,[10]=true,[11]=true,[42]=true,[43]=true,[15]=true,[81]=true,[82]=true,[52]=true,[53]=true,[54]=true,[24]=true,[58]=true,[30]=true}  -- P2-3 secure opcode 查找表
    local lDhEwT8qib = {[1]={data="\232\096\155\215\117",k1=70,k2=30,perm="\065\131\116\088\199\227\153\156\229\245\171\163\215\127\054\185\167\028\045\107\019\026\042\214\193\076\058\069\129\168\103\082\198\080\134\149\239\197\190\220\221\075\254\036\142\124\222\141\210\013\255\068\083\102\219\055\007\022\138\240\176\166\101\246\032\175\110\074\002\093\050\060\148\223\035\038\187\192\105\012\078\250\133\118\027\230\132\097\086\125\001\016\092\189\081\070\024\121\237\059\244\177\063\126\170\191\196\226\062\067\115\236\144\140\008\160\021\206\235\084\098\211\072\195\194\184\004\137\096\114\057\161\234\150\216\000\151\106\157\159\033\253\073\090\123\061\034\071\205\241\251\020\117\164\143\039\169\099\182\079\130\180\104\181\003\044\113\188\225\064\135\087\041\040\207\014\052\172\243\252\145\120\091\201\051\224\179\202\152\010\119\128\249\046\111\089\077\165\233\242\017\066\247\158\108\139\217\173\248\204\186\053\122\231\183\047\049\005\228\009\029\213\094\023\100\030\147\212\155\048\238\031\006\018\174\154\136\232\162\146\209\011\056\178\218\037\200\025\015\208\109\085\043\203\095\112",dec=nil},[2]={data="\211\034\009\009\041\213\173\116",k1=216,k2=205,perm="\093\005\047\146\017\158\067\220\089\013\078\028\121\071\155\099\060\227\070\253\140\111\113\027\161\034\218\014\181\224\131\046\112\079\069\116\166\043\171\048\102\185\136\104\254\024\012\234\167\035\044\226\083\040\202\207\088\106\001\118\150\080\090\006\058\246\059\204\184\045\019\239\062\018\249\107\004\223\178\036\195\141\154\020\232\194\168\052\135\177\063\169\205\032\072\064\143\023\210\000\174\157\217\147\247\203\123\061\105\245\119\068\151\244\199\196\054\130\153\137\128\208\170\190\086\011\073\008\148\129\095\180\176\041\084\219\003\076\222\033\057\145\186\221\211\200\120\075\097\242\189\172\197\248\165\081\087\225\209\156\138\193\162\187\229\082\126\133\212\241\103\238\183\124\152\215\038\139\092\237\117\230\026\037\159\213\010\164\053\065\101\250\030\051\214\192\115\134\007\251\233\252\091\049\110\240\198\216\066\243\094\231\108\055\173\182\149\201\125\114\074\132\142\100\025\002\098\015\056\191\050\021\236\016\022\163\206\096\144\160\042\235\039\228\255\188\085\077\009\109\127\179\029\122\031\175",dec=nil}}
        local function _dec_str(s)
            if s.dec then return s.dec end
            local inv = {}
            for i = 0, 255 do inv[(string.byte(string.sub(s.perm, i+1, i+1)))] = i end
            local out = {}
            for i = 1, #s.data do
                local b = string.byte(string.sub(s.data, i, i))
                b = b ~ s.k1
                b = (b - s.k2) % 256
                b = inv[b]
                out[i] = string.char(b)
            end
            s.dec = table.concat(out)
            return s.dec
        end
    local jWKsmgBDTvy = false  -- 反 trace 触发标志：true 时静默 corrupt 内部状态
    local Of2lxdVORlo=nil local function lCwY9yBZFyU(_bc,_lo,_hi) if not Of2lxdVORlo then Of2lxdVORlo={} for _i=0,255 do local _c=_i for _=1,8 do if _c%2==1 then _c=(_c//2)~0xEDB88320 else _c=_c//2 end end Of2lxdVORlo[_i]=_c end end local _crc=0xFFFFFFFF for _pc=_lo,_hi do local _ins=_bc[_pc] if _ins then for _i=1,#_ins do local _e=_ins[_i] if type(_e)=="number" then local _v=_e local _b0=_v%256 local _b1=(_v//256)%256 local _b2=(_v//65536)%256 local _b3=(_v//16777216)%256 _crc=(_crc//256)~Of2lxdVORlo[(_crc~_b0)%256] _crc=(_crc//256)~Of2lxdVORlo[(_crc~_b1)%256] _crc=(_crc//256)~Of2lxdVORlo[(_crc~_b2)%256] _crc=(_crc//256)~Of2lxdVORlo[(_crc~_b3)%256] end end end end return _crc~0xFFFFFFFF end
    local AP4RBjC6TjHui = {{1,1,1840431651},{2,2,3029520527},{3,3,3490163014},{4,4,1553196552}}
    -- P2-1 自擦除：safe_erase_set（已排除 jump_targets/CLOSURE 入口，回跳安全）
        local NfT2GWsX33wA = {1,2,3,4}
        local TEnvrccdkwas = {}
        for _i = 1, #NfT2GWsX33wA do TEnvrccdkwas[NfT2GWsX33wA[_i]] = true end
        local ieYBRo9M = false  -- 擦除一旦发生，CRC 校验不再运行（bc 已不全）
        local function xvE8ss638JO(lLfgILtky4j7i_start, IMjBTWEfRFW8, ...)
        if IMjBTWEfRFW8 == nil then IMjBTWEfRFW8 = {} end
        local yAaA8U4u = {...}
        local lLfgILtky4j7i = lLfgILtky4j7i_start
        local uGppWlsxAQc = {}
        local nxs7Ef7lYgrhJMS = {}
        local YSC6zlXABl = 0
        local sa0SCNDanth = #UqfwehwSbwwla
        local R7V6Qzaxc = os.clock()
        local YmC7nLTd4yc = 0
        local dOSHQ8P8J6V6BLD = 0  -- P2-1 自擦除水位线（已擦除到的最高 PC）
        while lLfgILtky4j7i <= sa0SCNDanth do
            local Dv6HjwDOOfE = UqfwehwSbwwla[lLfgILtky4j7i]
            if not Dv6HjwDOOfE then break end
            local MbzeSeiAtJ = {}
            for _i = 1, #Dv6HjwDOOfE do
                local _e = Dv6HjwDOOfE[_i]
                if type(_e) == "number" then
                    local _v = _e ~ ((_xeM4jnanQR + lLfgILtky4j7i + _i) & 0xFFFFFFFF)
                    if _v >= 2147483648 then _v = _v - 4294967296 end
                    MbzeSeiAtJ[_i] = _v
                else
                    MbzeSeiAtJ[_i] = _e
                end
            end
            -- 自修改 dispatcher：opcode 二次解密
            -- shift_key = (pc // shift_period) & 0xFFFF，每 shift_period 条指令变化
            -- 编译时 opcode 已按此规律加密，运行时反向异或还原
            local VAnEFSGuFP8dCtj = (lLfgILtky4j7i // 17) & 0xFFFF
            local V6jLBtOwfpCOxO = MbzeSeiAtJ[1] ~ VAnEFSGuFP8dCtj
            YSC6zlXABl = YSC6zlXABl + 1
            if YSC6zlXABl % 145 == 0 then
                -- 反 trace 1: _G 表大小监测（注入器环境注入大量全局）
                local _gc = 0
                for _ in pairs(_G) do _gc = _gc + 1 end
                if _gc > 2000 then return nil end
                -- 反 trace 2: 高频时间检测
                -- 正常执行 ad_period 条指令耗时 << time_limit
                -- 单步/trace 会让耗时暴涨 100-1000 倍
                local bwEz3a1H9eR = os.clock()
                if bwEz3a1H9eR - R7V6Qzaxc > 0.05 then
                    jWKsmgBDTvy = true
                end
                -- last_time_var 在本块末尾重置（见 P1-3 后），避免 CRC 计算耗时被计入下一窗口
                -- 反 trace 3: debug hook 检测
                -- debug.sethook 被设置说明有人在 trace（line/call/return 断点）
                local Nar2OSsU4 = debug and debug.gethook and debug.gethook()
                if Nar2OSsU4 then
                    jWKsmgBDTvy = true
                end
                -- 反 trace 4: 调用栈深度检测
                -- VM 正常调用栈深度有限，过深说明被包装/trace
                if debug and debug.getinfo then
                    local _di = debug.getinfo(3, "f")
                    -- _di 为 nil 说明栈很浅（正常），非 nil 说明有外层包装
                    -- 但 VM 自身也有包装，这里只检测极深栈（>20 层）
                    local _depth = 0
                    local _frame = debug.getinfo(1, "f")
                    while _frame and _depth < 30 do
                        _depth = _depth + 1
                        _frame = debug.getinfo(_depth + 1, "f")
                    end
                    if _depth >= 25 then jWKsmgBDTvy = true end
                end
                -- P1-3 字节码防篡改校验：CRC32 分段轮询
                -- 每个 ad_period 周期校验一段，轮询覆盖全部段。
                -- 任一字节被篡改 → 校验和失配 → 静默 corrupt。
                -- P2-1 自擦除发生后跳过 CRC（bc 已不全，必然失配）。
                if not ieYBRo9M then
                    local _ns = #AP4RBjC6TjHui
                    if _ns > 0 then
                        local _si = (YmC7nLTd4yc % _ns) + 1
                        local _seg = AP4RBjC6TjHui[_si]
                        local _rc = lCwY9yBZFyU(UqfwehwSbwwla, _seg[1], _seg[2])
                        if _rc ~= _seg[3] then jWKsmgBDTvy = true end
                        YmC7nLTd4yc = YmC7nLTd4yc + 1
                    end
                end
                -- 重置时间窗口基准：把本块全部工作（含 CRC 计算）排除出下一窗口
                R7V6Qzaxc = os.clock()
                -- P2-1 运行期字节码自擦除：防 dump
                -- 在 CRC 校验之后执行（CRC 先看到完整 bc 表，再擦除历史指令）。
                -- 擦除 (pc - lag) 且在 safe_set 中、且超过 watermark 的 PC。
                -- safe_set 仅含第一个跳转目标之前的线性序言，永不被回跳重访。
                -- 擦除后置 erase_done=true，后续 CRC 跳过（bc 已不全）。
                local _ep = lLfgILtky4j7i - 12
                if _ep > dOSHQ8P8J6V6BLD and TEnvrccdkwas[_ep] then
                    UqfwehwSbwwla[_ep] = nil
                    dOSHQ8P8J6V6BLD = _ep
                    ieYBRo9M = true
                end
            end
            -- corrupt 触发：静默破坏内部状态（不报错，让结果错乱，比直接崩更难排查）
            if jWKsmgBDTvy then
                uGppWlsxAQc[1] = nil
                uGppWlsxAQc[2] = "corrupted"
                lLfgILtky4j7i = lLfgILtky4j7i + YSC6zlXABl % 7 + 1
            end
            -- jump_flag：跳转指令设置后，跳过 pc+1（因为已设绝对目标）
            local _jmp = false
            -- P2-3 分片嵌套：secure opcode 走独立 dispatcher 链
            if yzLDiJQtw[V6jLBtOwfpCOxO] then
                if V6jLBtOwfpCOxO==3 or V6jLBtOwfpCOxO==42 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=_G[_dec_str(lDhEwT8qib[MbzeSeiAtJ[3]+1])]
elseif V6jLBtOwfpCOxO==4 or V6jLBtOwfpCOxO==43 then
_G[_dec_str(lDhEwT8qib[MbzeSeiAtJ[2]+1])]=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]]
elseif V6jLBtOwfpCOxO==10 or V6jLBtOwfpCOxO==52 or V6jLBtOwfpCOxO==53 then
local _fn=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]] local _args={} for _ai=1,MbzeSeiAtJ[4] do _args[_ai]=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[4+_ai]]] end nxs7Ef7lYgrhJMS=table.pack(_fn(table.unpack(_args))) uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=nxs7Ef7lYgrhJMS[1]
elseif V6jLBtOwfpCOxO==11 or V6jLBtOwfpCOxO==54 then
local _uvc={} for _k,_v in pairs(IMjBTWEfRFW8) do _uvc[_k]=_v end for _k,_v in pairs(uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[4]]]) do _uvc[_k]=_v end uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=function(...) return xvE8ss638JO(MbzeSeiAtJ[3],_uvc,...) end
elseif V6jLBtOwfpCOxO==15 or V6jLBtOwfpCOxO==58 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=IMjBTWEfRFW8[_dec_str(lDhEwT8qib[MbzeSeiAtJ[3]+1])]
elseif V6jLBtOwfpCOxO==24 or V6jLBtOwfpCOxO==72 then
local _obj=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]] local _m=_dec_str(lDhEwT8qib[MbzeSeiAtJ[4]+1]) local _args={} for _ai=1,MbzeSeiAtJ[5] do _args[_ai]=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[5+_ai]]] end local _fn=_obj[_m] nxs7Ef7lYgrhJMS=table.pack(_fn(_obj,table.unpack(_args))) uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=nxs7Ef7lYgrhJMS[1]
elseif V6jLBtOwfpCOxO==30 or V6jLBtOwfpCOxO==81 or V6jLBtOwfpCOxO==82 then
if MbzeSeiAtJ[3] and MbzeSeiAtJ[3]>0 then local _rv={} for _ri=1,MbzeSeiAtJ[3] do _rv[_ri]=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3+_ri]]] end return table.unpack(_rv) end return
elseif V6jLBtOwfpCOxO==36 or V6jLBtOwfpCOxO==90 then
IMjBTWEfRFW8[_dec_str(lDhEwT8qib[MbzeSeiAtJ[2]+1])]=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]]
end
            else
                if V6jLBtOwfpCOxO==0 or V6jLBtOwfpCOxO==37 or V6jLBtOwfpCOxO==38 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=VasxSb6Mo[MbzeSeiAtJ[3]+1]
elseif V6jLBtOwfpCOxO==1 or V6jLBtOwfpCOxO==39 or V6jLBtOwfpCOxO==40 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]][_dec_str(lDhEwT8qib[MbzeSeiAtJ[4]+1])]
elseif V6jLBtOwfpCOxO==2 or V6jLBtOwfpCOxO==41 then
for _pi=1,MbzeSeiAtJ[2] do uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2+_pi]]]=yAaA8U4u[_pi] end
elseif V6jLBtOwfpCOxO==5 or V6jLBtOwfpCOxO==44 or V6jLBtOwfpCOxO==45 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]][uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[4]]]]
elseif V6jLBtOwfpCOxO==6 or V6jLBtOwfpCOxO==46 then
local _j=_G[MbzeSeiAtJ[2]]
elseif V6jLBtOwfpCOxO==7 or V6jLBtOwfpCOxO==47 or V6jLBtOwfpCOxO==48 then
local _j=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]][MbzeSeiAtJ[3]]
elseif V6jLBtOwfpCOxO==8 or V6jLBtOwfpCOxO==49 or V6jLBtOwfpCOxO==50 then
lLfgILtky4j7i=H3LTzCgVqws2WR[MbzeSeiAtJ[2]] _jmp=true
elseif V6jLBtOwfpCOxO==9 or V6jLBtOwfpCOxO==51 then
local d,a,b,c=MbzeSeiAtJ[2],MbzeSeiAtJ[3],MbzeSeiAtJ[4],MbzeSeiAtJ[5] if c==0 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]<uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==1 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]] or uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==2 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]/uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==3 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]<=uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==4 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]%uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==5 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]^uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==6 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]==uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==7 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]..uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==8 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]<<uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==9 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]//uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==10 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]+uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==11 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]] and uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==12 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]~uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==13 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]>=uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==14 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]>uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==15 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]|uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==16 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]*uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==17 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]&uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==18 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]~=uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==19 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]>>uGppWlsxAQc[IWzrO9bhr3Q[b]] end if c==20 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=uGppWlsxAQc[IWzrO9bhr3Q[a]]-uGppWlsxAQc[IWzrO9bhr3Q[b]] end
elseif V6jLBtOwfpCOxO==12 or V6jLBtOwfpCOxO==55 then
local _j=function() end
elseif V6jLBtOwfpCOxO==13 or V6jLBtOwfpCOxO==56 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=_dec_str(lDhEwT8qib[MbzeSeiAtJ[3]+1])
elseif V6jLBtOwfpCOxO==14 or V6jLBtOwfpCOxO==57 then
lLfgILtky4j7i=H3LTzCgVqws2WR[MbzeSeiAtJ[2]]
elseif V6jLBtOwfpCOxO==16 or V6jLBtOwfpCOxO==59 or V6jLBtOwfpCOxO==60 then
if uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]] then lLfgILtky4j7i=H3LTzCgVqws2WR[MbzeSeiAtJ[3]] _jmp=true end
elseif V6jLBtOwfpCOxO==17 or V6jLBtOwfpCOxO==61 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=nil
elseif V6jLBtOwfpCOxO==18 or V6jLBtOwfpCOxO==62 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]][_dec_str(lDhEwT8qib[MbzeSeiAtJ[3]+1])]=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[4]]]
elseif V6jLBtOwfpCOxO==19 or V6jLBtOwfpCOxO==63 or V6jLBtOwfpCOxO==64 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]+uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[4]]] if (uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[4]]]>0 and uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]<=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]] ) or (uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[4]]]<0 and uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]>=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]] ) then lLfgILtky4j7i=H3LTzCgVqws2WR[MbzeSeiAtJ[5]] _jmp=true end
elseif V6jLBtOwfpCOxO==20 or V6jLBtOwfpCOxO==65 or V6jLBtOwfpCOxO==66 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]]
elseif V6jLBtOwfpCOxO==21 or V6jLBtOwfpCOxO==67 then
local _j=#{} for _k=1,3 do _j=_j+1 end
elseif V6jLBtOwfpCOxO==22 or V6jLBtOwfpCOxO==68 or V6jLBtOwfpCOxO==69 then
local d,a,c=MbzeSeiAtJ[2],MbzeSeiAtJ[3],MbzeSeiAtJ[4] if c==0 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=#uGppWlsxAQc[IWzrO9bhr3Q[a]] end if c==1 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=not uGppWlsxAQc[IWzrO9bhr3Q[a]] end if c==2 then uGppWlsxAQc[IWzrO9bhr3Q[d]]=-uGppWlsxAQc[IWzrO9bhr3Q[a]] end
elseif V6jLBtOwfpCOxO==23 or V6jLBtOwfpCOxO==70 or V6jLBtOwfpCOxO==71 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]][uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]]=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[4]]]
elseif V6jLBtOwfpCOxO==25 or V6jLBtOwfpCOxO==73 or V6jLBtOwfpCOxO==74 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=nxs7Ef7lYgrhJMS[MbzeSeiAtJ[3]]
elseif V6jLBtOwfpCOxO==26 or V6jLBtOwfpCOxO==75 then
if not uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]] then lLfgILtky4j7i=H3LTzCgVqws2WR[MbzeSeiAtJ[3]] _jmp=true end
elseif V6jLBtOwfpCOxO==27 or V6jLBtOwfpCOxO==76 or V6jLBtOwfpCOxO==77 then
local _j=math.floor(uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]])
elseif V6jLBtOwfpCOxO==28 or V6jLBtOwfpCOxO==78 or V6jLBtOwfpCOxO==79 then
-- unknown COPYUV
elseif V6jLBtOwfpCOxO==29 or V6jLBtOwfpCOxO==80 then
local _j=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]+uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]]
elseif V6jLBtOwfpCOxO==31 or V6jLBtOwfpCOxO==83 or V6jLBtOwfpCOxO==84 then
if uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]] then local _j=1 end
elseif V6jLBtOwfpCOxO==32 or V6jLBtOwfpCOxO==85 then
local _j=tostring(uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]])..tostring(uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]])
elseif V6jLBtOwfpCOxO==33 or V6jLBtOwfpCOxO==86 or V6jLBtOwfpCOxO==87 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]={}
elseif V6jLBtOwfpCOxO==34 or V6jLBtOwfpCOxO==88 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=(MbzeSeiAtJ[3]~=0)
elseif V6jLBtOwfpCOxO==35 or V6jLBtOwfpCOxO==89 then
uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[2]]]=uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]] if (uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[5]]]>0 and uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]]>uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[4]]] ) or (uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[5]]]<0 and uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[3]]]<uGppWlsxAQc[IWzrO9bhr3Q[MbzeSeiAtJ[4]]] ) then lLfgILtky4j7i=H3LTzCgVqws2WR[MbzeSeiAtJ[6]] _jmp=true end
end
            end
            if not _jmp then lLfgILtky4j7i = lLfgILtky4j7i + 1 end
        end
    end
    return xvE8ss638JO(1, {})
end
return YCBRAbF5()
