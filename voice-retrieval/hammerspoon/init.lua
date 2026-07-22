-- phone-voice-paste
-- Copy this file to ~/.hammerspoon/init.lua, then edit the three values below.

local WORKER_URL = "https://phone-voice-paste.1366094310.workers.dev"
local PROJECT_DIR = os.getenv("HOME") .. "/claude/voice-retrieval"
local TOKEN_FILE = PROJECT_DIR .. "/.runtime/phone-voice-paste-token"

-- Keep the voice retrieval button available after logging back into macOS.
hs.autoLaunch(true)

-- Prefer keyCode after running detect-key.lua. Leave nil to use PASTE_KEY_NAME.
local PASTE_KEY_CODE = nil
local PASTE_KEY_NAME = "f13"

-- Some keyboard special keys, such as calculator/media keys, are macOS system-defined keys.
-- If detect-key.lua reports eventType: systemDefined, set this to systemKeyCode.
local PASTE_SYSTEM_KEY_CODE = nil

-- Small always-on-top copy button for remote control sessions.
local FLOATING_BUTTON_ENABLED = true
local FLOATING_BUTTON_WIDTH = 108
local FLOATING_BUTTON_HEIGHT = 46
local FLOATING_BUTTON_MARGIN = 8
local FLOATING_BUTTON_LABEL = "语音取回"
local FLOATING_BUTTON_POSITION_FILE = PROJECT_DIR .. "/.runtime/phone-voice-paste-button-position.json"

local function workerBaseUrl()
  return WORKER_URL:gsub("/+$", "")
end

local function show(message)
  hs.alert.show(message, 1.2)
end

local function readToken()
  local file = io.open(TOKEN_FILE, "r")
  if not file then
    return ""
  end

  local token = file:read("*a") or ""
  file:close()
  return token:gsub("%s+$", "")
end

local function pasteText(text)
  hs.pasteboard.setContents(text)
  hs.timer.doAfter(0.05, function()
    hs.eventtap.keyStroke({ "cmd" }, "v", 0)
  end)
end

local function copyText(text)
  hs.pasteboard.setContents(text)
  show("已复制")
end

local function handleResponse(status, body, mode)
  if status == 401 then
    show("Token 错误")
    return
  end

  if status < 200 or status >= 300 then
    show("网络错误")
    return
  end

  local ok, data = pcall(hs.json.decode, body or "")
  if not ok or type(data) ~= "table" then
    show("响应异常")
    return
  end

  if data.ok == false and data.error == "unauthorized" then
    show("Token 错误")
    return
  end

  if data.ok ~= true then
    show("响应异常")
    return
  end

  if data.text == nil then
    show("无文本")
    return
  end

  if type(data.text) ~= "string" or data.text == "" then
    show("响应异常")
    return
  end

  if mode == "copy" then
    copyText(data.text)
  else
    pasteText(data.text)
  end
end

local function fetchLatest(mode)
  local token = readToken()

  if WORKER_URL == "" or token == "" then
    show("请先配置")
    return
  end

  hs.http.asyncPost(
    workerBaseUrl() .. "/latest",
    "{}",
    {
      ["Content-Type"] = "application/json",
      ["Authorization"] = "Bearer " .. token,
    },
    function(status, body)
      if status == nil or status <= 0 then
        show("网络错误")
        return
      end

      handleResponse(status, body, mode)
    end
  )
end

local function fetchLatestAndPaste()
  fetchLatest("paste")
end

local function fetchLatestAndCopy()
  fetchLatest("copy")
end

local floatingCopyButton = nil
local floatingButtonDrag = nil
local floatingButtonDragTap = nil

local function stopFloatingButtonDragTap()
  if floatingButtonDragTap then
    floatingButtonDragTap:stop()
    floatingButtonDragTap = nil
  end
end

local function clampFloatingButtonFrame(buttonFrame)
  local screenFrame = hs.screen.mainScreen():frame()
  local minX = screenFrame.x
  local minY = screenFrame.y
  local maxX = screenFrame.x + screenFrame.w - buttonFrame.w
  local maxY = screenFrame.y + screenFrame.h - buttonFrame.h

  return {
    x = math.min(math.max(buttonFrame.x, minX), maxX),
    y = math.min(math.max(buttonFrame.y, minY), maxY),
    w = buttonFrame.w,
    h = buttonFrame.h,
  }
end

local function readSavedFloatingButtonFrame()
  local file = io.open(FLOATING_BUTTON_POSITION_FILE, "r")
  if not file then
    return nil
  end

  local body = file:read("*a") or ""
  file:close()

  local ok, data = pcall(hs.json.decode, body)
  if not ok or type(data) ~= "table" or type(data.x) ~= "number" or type(data.y) ~= "number" then
    return nil
  end

  return clampFloatingButtonFrame({
    x = data.x,
    y = data.y,
    w = FLOATING_BUTTON_WIDTH,
    h = FLOATING_BUTTON_HEIGHT,
  })
end

local function saveFloatingButtonFrame(buttonFrame)
  local file = io.open(FLOATING_BUTTON_POSITION_FILE, "w")
  if not file then
    return
  end

  file:write(hs.json.encode({
    x = math.floor(buttonFrame.x + 0.5),
    y = math.floor(buttonFrame.y + 0.5),
  }))
  file:close()
end

local function moveFloatingButtonFromMouse()
  if not floatingCopyButton or not floatingButtonDrag then
    return
  end

  local mouse = hs.mouse.absolutePosition()
  local dx = mouse.x - floatingButtonDrag.mouse.x
  local dy = mouse.y - floatingButtonDrag.mouse.y

  if math.abs(dx) > 3 or math.abs(dy) > 3 then
    floatingButtonDrag.moved = true
  end

  floatingCopyButton:frame(clampFloatingButtonFrame({
    x = floatingButtonDrag.frame.x + dx,
    y = floatingButtonDrag.frame.y + dy,
    w = FLOATING_BUTTON_WIDTH,
    h = FLOATING_BUTTON_HEIGHT,
  }))
end

local function finishFloatingButtonDrag()
  local moved = floatingButtonDrag and floatingButtonDrag.moved

  if moved and floatingCopyButton then
    saveFloatingButtonFrame(floatingCopyButton:frame())
  end

  floatingButtonDrag = nil
  stopFloatingButtonDragTap()

  if not moved then
    fetchLatestAndCopy()
  end
end

local function startFloatingButtonDrag()
  stopFloatingButtonDragTap()

  floatingButtonDrag = {
    mouse = hs.mouse.absolutePosition(),
    frame = floatingCopyButton:frame(),
    moved = false,
  }

  floatingButtonDragTap = hs.eventtap.new({
    hs.eventtap.event.types.leftMouseDragged,
    hs.eventtap.event.types.leftMouseUp,
  }, function(event)
    local eventType = event:getType()

    if eventType == hs.eventtap.event.types.leftMouseDragged then
      moveFloatingButtonFromMouse()
      return false
    end

    if eventType == hs.eventtap.event.types.leftMouseUp then
      finishFloatingButtonDrag()
      return false
    end

    return false
  end)

  floatingButtonDragTap:start()
end

local function floatingButtonFrame()
  local screen = hs.screen.mainScreen()
  local frame = screen:frame()

  local savedFrame = readSavedFloatingButtonFrame()
  if savedFrame then
    return savedFrame
  end

  return clampFloatingButtonFrame({
    x = frame.x + FLOATING_BUTTON_MARGIN,
    y = frame.y + frame.h - FLOATING_BUTTON_HEIGHT - FLOATING_BUTTON_MARGIN,
    w = FLOATING_BUTTON_WIDTH,
    h = FLOATING_BUTTON_HEIGHT,
  })
end

local function createFloatingCopyButton()
  if not FLOATING_BUTTON_ENABLED then
    return
  end

  if floatingCopyButton then
    floatingCopyButton:delete()
    floatingCopyButton = nil
  end

  floatingCopyButton = hs.canvas.new(floatingButtonFrame())
  floatingCopyButton:appendElements(
    {
      type = "rectangle",
      action = "strokeAndFill",
      frame = { x = 0, y = 0, w = "100%", h = "100%" },
      roundedRectRadii = { xRadius = 10, yRadius = 10 },
      fillColor = { white = 0.08, alpha = 0.82 },
      strokeColor = { white = 1, alpha = 0.18 },
      strokeWidth = 1,
      trackMouseDown = true,
    },
    {
      type = "text",
      action = "fill",
      text = FLOATING_BUTTON_LABEL,
      textAlignment = "center",
      textSize = 15,
      textColor = { white = 1, alpha = 0.95 },
      frame = { x = 0, y = 11, w = "100%", h = 24 },
      trackMouseDown = true,
    }
  )
  floatingCopyButton:level(hs.canvas.windowLevels.floating)
  floatingCopyButton:behavior({ "canJoinAllSpaces", "stationary" })
  floatingCopyButton:mouseCallback(function(_, eventName)
    if eventName == "mouseDown" then
      startFloatingButtonDrag()
    end
  end)
  floatingCopyButton:show()
end

createFloatingCopyButton()

local keyCodeTap = nil
local systemKeyTap = nil

local function bindByKeyCode(keyCode)
  keyCodeTap = hs.eventtap.new({ hs.eventtap.event.types.keyDown }, function(event)
    if event:getKeyCode() ~= keyCode then
      return false
    end

    local isRepeat = event:getProperty(hs.eventtap.event.properties.keyboardEventAutorepeat) == 1
    if isRepeat then
      return true
    end

    fetchLatestAndPaste()
    return true
  end)

  keyCodeTap:start()
  show("语音粘贴已绑定 keyCode " .. tostring(keyCode))
end

local function bindByKeyName(keyName)
  hs.hotkey.bind({}, keyName, fetchLatestAndPaste)
  show("语音粘贴已绑定 " .. keyName)
end

local function bindBySystemKeyCode(systemKeyCode)
  systemKeyTap = hs.eventtap.new({ hs.eventtap.event.types.systemDefined }, function(event)
    local systemKey = event:systemKey()
    if not systemKey or systemKey.keyCode ~= systemKeyCode then
      return false
    end

    if systemKey["repeat"] or not systemKey.down then
      return true
    end

    fetchLatestAndPaste()
    return true
  end)

  systemKeyTap:start()
  show("语音粘贴已绑定 systemKeyCode " .. tostring(systemKeyCode))
end

if type(PASTE_SYSTEM_KEY_CODE) == "number" then
  bindBySystemKeyCode(PASTE_SYSTEM_KEY_CODE)
elseif type(PASTE_KEY_CODE) == "number" then
  bindByKeyCode(PASTE_KEY_CODE)
else
  bindByKeyName(PASTE_KEY_NAME)
end
