-- Temporary Hammerspoon key detector.
-- Copy this file to ~/.hammerspoon/init.lua, reload Hammerspoon, then press the target key once.
-- It detects both normal keys and macOS system-defined media/function keys.

local function keyNameFromCode(code)
  for name, mappedCode in pairs(hs.keycodes.map) do
    if mappedCode == code then
      return name
    end
  end

  return "unknown"
end

local tap

local function showAndStop(message)
  print(message)
  hs.alert.show(message, 6)
  tap:stop()
end

tap = hs.eventtap.new({
  hs.eventtap.event.types.keyDown,
  hs.eventtap.event.types.systemDefined,
}, function(event)
  if event:getType() == hs.eventtap.event.types.systemDefined then
    local systemKey = event:systemKey()
    if systemKey and systemKey.down then
      showAndStop(
        "eventType: systemDefined\n"
          .. "systemKeyCode: " .. tostring(systemKey.keyCode) .. "\n"
          .. "systemKeyName: " .. tostring(systemKey.key) .. "\n"
          .. "repeat: " .. tostring(systemKey["repeat"])
      )
      return true
    end

    return false
  end

  local code = event:getKeyCode()
  local name = keyNameFromCode(code)
  showAndStop(
    "eventType: keyDown\n"
      .. "keyCode: " .. tostring(code) .. "\n"
      .. "keyName: " .. tostring(name)
  )

  return true
end)

tap:start()
hs.alert.show("请按一下目标键", 2)
