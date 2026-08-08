#!/usr/bin/env python3
"""Run obfuscated Lua code with lupa to detect runtime errors."""
import sys
import traceback
from lupa import LuaRuntime

def run_obf_code(code_path):
    with open(code_path, 'r', encoding='utf-8') as f:
        code = f.read()

    # Roblox environment shims for plain Lua
    prelude = """
        -- Mock Roblox globals
        game = setmetatable({}, {__index = function(t, k)
            if k == 'GetService' then
                return function(self, svc)
                    return setmetatable({}, {__index = function(t,k)
                        if k == 'GetPlayers' then
                            return function() return {} end
                        end
                        return nil
                    end})
                end
            end
            return nil
        end})
        workspace = {}
        _print = print
        _warn = warn
        print = function(...) _print('[lua]', ...) end
        warn = function(...) _print('[warn]', ...) end
        loadstring = loadstring or load
        -- bit32 for older Lua
    """

    # Postlude to catch errors
    postlude = """
        print('[ok] obfuscated code finished')
    """

    lua = LuaRuntime(unpack_returned_tuples=True)
    try:
        # Combine and run
        full = prelude + "\n" + code + "\n" + postlude
        result = lua.execute(full)
        print(f"[result] {result}")
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python run_lua_test.py <obf.lua>")
        sys.exit(1)
    ok = run_obf_code(sys.argv[1])
    sys.exit(0 if ok else 1)
