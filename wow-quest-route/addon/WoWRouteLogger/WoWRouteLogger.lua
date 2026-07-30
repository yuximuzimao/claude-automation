local ADDON_NAME = ...
local frame = CreateFrame("Frame")

local SAMPLE_INTERVAL = 5
local MIN_MOVE = 0.0025
local FORCE_SAMPLE_AFTER = 60
local session
local elapsed = 0
local lastPoint
local questState = {}
local recentTurnIn = {}
local RETENTION_SECONDS = 30 * 24 * 60 * 60
local MAX_SESSIONS = 100

local function now()
    return time()
end

local function ensureDB()
    if type(WoWRouteLoggerDB) ~= "table" then
        WoWRouteLoggerDB = {}
    end
    WoWRouteLoggerDB.schema_version = 1
    WoWRouteLoggerDB.addon_version = "0.1.0"
    WoWRouteLoggerDB.sessions = WoWRouteLoggerDB.sessions or {}
    local cutoff = now() - RETENTION_SECONDS
    local kept = {}
    for _, oldSession in ipairs(WoWRouteLoggerDB.sessions) do
        local startedAt = tonumber(oldSession.started_at) or 0
        if startedAt >= cutoff then
            table.insert(kept, oldSession)
        end
    end
    while #kept > MAX_SESSIONS do
        table.remove(kept, 1)
    end
    WoWRouteLoggerDB.sessions = kept
end

local function getPosition()
    if not C_Map or not C_Map.GetBestMapForUnit or not C_Map.GetPlayerMapPosition then
        return nil
    end
    local mapID = C_Map.GetBestMapForUnit("player")
    if not mapID then
        return nil
    end
    local position = C_Map.GetPlayerMapPosition(mapID, "player")
    if not position then
        return { map_id = mapID }
    end
    local x, y = position:GetXY()
    if not x or not y or (x == 0 and y == 0) then
        return { map_id = mapID }
    end
    return {
        map_id = mapID,
        x = math.floor(x * 10000 + 0.5) / 100,
        y = math.floor(y * 10000 + 0.5) / 100,
    }
end

local function classToken()
    local _, token = UnitClass("player")
    return token
end

local function raceToken()
    local _, token = UnitRace("player")
    return token
end

local function baseRecord(kind)
    local position = getPosition() or {}
    return {
        t = now(),
        kind = kind,
        level = UnitLevel("player"),
        map_id = position.map_id,
        x = position.x,
        y = position.y,
    }
end

local function appendEvent(kind, extra)
    if not session then return end
    local entry = baseRecord(kind)
    if type(extra) == "table" then
        for key, value in pairs(extra) do
            entry[key] = value
        end
    end
    table.insert(session.events, entry)
end

local function samplePosition(force, reason)
    if not session then return end
    local position = getPosition()
    if not position or not position.x or not position.y then return end
    local current = {
        t = now(),
        map_id = position.map_id,
        x = position.x,
        y = position.y,
        level = UnitLevel("player"),
        reason = reason,
    }
    local shouldStore = force or not lastPoint
    if lastPoint and not shouldStore then
        if current.map_id ~= lastPoint.map_id then
            shouldStore = true
        else
            local dx = (current.x - lastPoint.x) / 100
            local dy = (current.y - lastPoint.y) / 100
            local distance = math.sqrt(dx * dx + dy * dy)
            shouldStore = distance >= MIN_MOVE or current.t - lastPoint.t >= FORCE_SAMPLE_AFTER
        end
    end
    if shouldStore then
        table.insert(session.path, current)
        lastPoint = current
    end
end

local function questTitle(questID)
    if C_QuestLog and C_QuestLog.GetTitleForQuestID then
        return C_QuestLog.GetTitleForQuestID(questID)
    end
    return nil
end

local function readQuestState()
    local state = {}
    if not C_QuestLog or not C_QuestLog.GetNumQuestLogEntries or not C_QuestLog.GetInfo then
        return state
    end
    local count = C_QuestLog.GetNumQuestLogEntries()
    for index = 1, count do
        local info = C_QuestLog.GetInfo(index)
        if info and not info.isHeader and info.questID then
            state[info.questID] = {
                complete = info.isComplete and true or false,
                title = info.title,
            }
        end
    end
    return state
end

local function refreshQuestState()
    local newState = readQuestState()
    for questID, info in pairs(newState) do
        local previous = questState[questID]
        if previous and not previous.complete and info.complete then
            appendEvent("objective_complete", {
                quest_id = questID,
                quest_title = info.title or questTitle(questID),
            })
            samplePosition(true, "objective_complete")
        end
    end
    for questID, previous in pairs(questState) do
        if not newState[questID] and not recentTurnIn[questID] then
            appendEvent("quest_removed", {
                quest_id = questID,
                quest_title = previous.title or questTitle(questID),
            })
        end
    end
    questState = newState
end

local function startSession()
    ensureDB()
    local entry = {
        started_at = now(),
        ended_at = nil,
        client = "classic_titan",
        class = classToken(),
        race = raceToken(),
        faction = UnitFactionGroup("player"),
        initial_level = UnitLevel("player"),
        events = {},
        path = {},
    }
    table.insert(WoWRouteLoggerDB.sessions, entry)
    session = entry
    lastPoint = nil
    questState = readQuestState()
    appendEvent("session_start")
    samplePosition(true, "session_start")
end

local function endSession()
    if not session then return end
    samplePosition(true, "session_end")
    appendEvent("session_end")
    session.ended_at = now()
end

frame:RegisterEvent("ADDON_LOADED")
frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("PLAYER_LOGOUT")
frame:RegisterEvent("PLAYER_ENTERING_WORLD")
frame:RegisterEvent("ZONE_CHANGED_NEW_AREA")
frame:RegisterEvent("QUEST_ACCEPTED")
frame:RegisterEvent("QUEST_TURNED_IN")
frame:RegisterEvent("QUEST_LOG_UPDATE")
frame:RegisterEvent("PLAYER_LEVEL_UP")

frame:SetScript("OnEvent", function(_, event, ...)
    if event == "ADDON_LOADED" then
        local loadedName = ...
        if loadedName == ADDON_NAME then
            ensureDB()
        end
        return
    end
    if event == "PLAYER_LOGIN" then
        startSession()
        return
    end
    if event == "PLAYER_LOGOUT" then
        endSession()
        return
    end
    if not session then return end

    if event == "PLAYER_ENTERING_WORLD" or event == "ZONE_CHANGED_NEW_AREA" then
        appendEvent("zone", { zone = GetRealZoneText and GetRealZoneText() or nil })
        samplePosition(true, "zone")
    elseif event == "QUEST_ACCEPTED" then
        local _, questID = ...
        if questID then
            appendEvent("quest_accept", {
                quest_id = questID,
                quest_title = questTitle(questID),
            })
            samplePosition(true, "quest_accept")
        end
    elseif event == "QUEST_TURNED_IN" then
        local questID, xpReward, moneyReward = ...
        if questID then
            recentTurnIn[questID] = true
            appendEvent("quest_turnin", {
                quest_id = questID,
                quest_title = questTitle(questID),
                xp_reward = xpReward,
                money_reward = moneyReward,
            })
            samplePosition(true, "quest_turnin")
            C_Timer.After(2, function()
                recentTurnIn[questID] = nil
            end)
        end
    elseif event == "QUEST_LOG_UPDATE" then
        refreshQuestState()
    elseif event == "PLAYER_LEVEL_UP" then
        local level = ...
        appendEvent("level_up", { new_level = level })
        samplePosition(true, "level_up")
    end
end)

frame:SetScript("OnUpdate", function(_, delta)
    elapsed = elapsed + delta
    if elapsed >= SAMPLE_INTERVAL then
        elapsed = 0
        samplePosition(false, "movement")
    end
end)

SLASH_WOWROUTELOGGER1 = "/wrl"
SlashCmdList.WOWROUTELOGGER = function(message)
    message = message or ""
    local command, rest = message:match("^(%S*)%s*(.-)$")
    command = string.lower(command or "")
    if command == "note" and rest ~= "" then
        appendEvent("note", { text = rest })
        samplePosition(true, "note")
        print("WoW Route Logger: 已记录备注。")
    elseif command == "checkpoint" then
        appendEvent("checkpoint")
        samplePosition(true, "checkpoint")
        print("WoW Route Logger: 已记录当前位置。")
    elseif command == "status" then
        local sessions = WoWRouteLoggerDB and WoWRouteLoggerDB.sessions or {}
        local events = session and #session.events or 0
        local points = session and #session.path or 0
        print("WoW Route Logger: 会话 " .. #sessions .. "，当前事件 " .. events .. "，轨迹点 " .. points .. "。")
    else
        print("WoW Route Logger: /wrl note 备注 | /wrl checkpoint | /wrl status")
    end
end
