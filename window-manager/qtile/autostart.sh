# My screen resolution
# xrandr --rate 120

# For Virtual Machine 
# xrandr --output Virtual-1 --mode 1920x1080

# Keyboard layout
setxkbmap us

# Load picom
picom -b -f --config $HOME/.config/picom/picom.conf &
