//Modify this file to change what commands output to your statusbar, and recompile using the make command.
static const Block blocks[] = {
	/*Icon*/	/*Command*/		/*Update Interval*/	/*Update Signal*/
	{"  ", "/home/pedro/dotfiles/scripts/mem",	          5,		0},
  // {" 󰍛 ", "/home/pedro/dotfiles/scripts/cpu",	          5,		0},
	{"  ", "/home/pedro/dotfiles/scripts/clock",				 60,		0},
};

//sets delimiter between status commands. NULL character ('\0') means no delimiter.
static char delim[] = " | ";
static unsigned int delimLen = 5;
