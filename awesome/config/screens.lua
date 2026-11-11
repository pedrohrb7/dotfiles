-- Screen hotplug: lays out the monitors with autorandr whenever one is plugged
-- or unplugged, and when a monitor goes away, its windows land together on the
-- first empty tag of the primary screen instead of being dumped on tag 1.
--
-- Hotplug is driven from awesome, not from autorandr's udev rule: the NVIDIA
-- driver behind HDMI-1-0 sends no DRM uevent, so the rule never fires and the
-- unplugged output stays configured (X keeps a "disconnected" output at
-- 1920x1080+1920+0, awesome keeps its screen and nothing moves). awesome does
-- get the RandR output change as the global "screen::change" signal.
--
-- awesome 4.3 deletes the tags of a removed screen and moves every client left on
-- them to the first tag of another screen, mixed with whatever is already there.
-- "removal-pending" is the hook it offers right before that fallback: it fires once
-- per tag of the departing screen, while the tag still has its clients.
local awful = require("awful")
local gears = require("gears")
local naughty = require("naughty")

local M = {}

-- Destination tag per departing screen, so all of its tags share one target.
local targets = setmetatable({}, { __mode = "k" })
-- Clients moved per departing screen, for the single notification at the end.
local moved = setmetatable({}, { __mode = "k" })

local function is_empty(t)
	return #t:clients() == 0
end

-- First tag of `s` with no clients; the last tag when every one is in use.
function M.free_tag(s)
	for _, t in ipairs(s.tags) do
		if is_empty(t) then
			return t
		end
	end
	return s.tags[#s.tags]
end

-- The screen that receives the windows: the primary one, or any other screen
-- that still has tags when the primary itself is the one leaving.
local function destination_screen(leaving)
	if screen.primary and screen.primary ~= leaving and #screen.primary.tags > 0 then
		return screen.primary
	end
	for s in screen do
		if s ~= leaving and #s.tags > 0 then
			return s
		end
	end
end

local function notify(leaving)
	local count = moved[leaving]
	local target = targets[leaving]
	if not count or count == 0 or not target then
		return
	end
	naughty.notify({
		preset = naughty.config.presets.low,
		title = "Monitor desconectado",
		text = string.format(
			"%d janela%s movida%s para a tag %d",
			count,
			count == 1 and "" or "s",
			count == 1 and "" or "s",
			target.index
		),
	})
end

local function on_removal_pending(t)
	local leaving = t.screen
	if not leaving then
		return
	end

	local clients = t:clients()
	if #clients == 0 then
		return
	end

	if not targets[leaving] then
		local dest = destination_screen(leaving)
		if not dest then
			return
		end
		targets[leaving] = M.free_tag(dest)
		moved[leaving] = 0
		-- Every tag of the leaving screen emits "removal-pending" synchronously
		-- inside the same "removed" handler, so one deferred call reports them all.
		gears.timer.delayed_call(notify, leaving)
	end

	local target = targets[leaving]
	for _, c in ipairs(clients) do
		c:move_to_tag(target)
		-- Floating windows keep coordinates from the old monitor.
		if c.floating then
			awful.placement.no_offscreen(c)
		end
		moved[leaving] = moved[leaving] + 1
	end
end

-- The autorandr profile matching the connected monitors (~/.config/autorandr),
-- or all of them side by side when none matches. X falls back to the monitor's
-- preferred mode (1024x768 on DP-1) otherwise.
function M.apply_layout()
	awful.spawn.with_shell("command -v autorandr > /dev/null && autorandr --change --default default")
end

-- One plug or unplug emits several output changes in a row; lay out once after
-- they stop.
local relayout = gears.timer({
	timeout = 0.5,
	single_shot = true,
	callback = M.apply_layout,
})

function M.init()
	tag.connect_signal("removal-pending", on_removal_pending)
	awesome.connect_signal("screen::change", function()
		relayout:again()
	end)
end

return M
