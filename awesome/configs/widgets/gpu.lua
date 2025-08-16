local awful = require("awful")
-- Widget and layout library
local wibox = require("wibox")

-- Create a textbox widget for GPU info
local gpu_widget = wibox.widget.textbox()

-- Function to update GPU info
local function update_gpu_info()
	awful.spawn.easy_async_with_shell(
		"nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,memory.used --format=csv,noheader,nounits",
		function(stdout)
			local lines = {}
			for line in stdout:gmatch("[^\n]+") do
				table.insert(lines, line)
			end

			if #lines > 0 then
				local gpu_data = lines[1] -- Assuming single GPU for simplicity
				local util, temp = gpu_data:match("([^,]+),([^,]+),(.+)")
				gpu_widget.text = " GPU " .. util .. "% | Temp: " .. temp .. "°C "
			else
				gpu_widget.text = " GPU N/A "
			end
		end
	)
end

-- Update GPU info initially and then every 5 seconds
awful.widget.watch("nvidia-smi", 2, update_gpu_info)
update_gpu_info()

return gpu_widget
