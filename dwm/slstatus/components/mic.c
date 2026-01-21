/* See LICENSE file for copyright and license details.  */
#include <stdio.h>
#include <string.h>

#include "../slstatus.h"
#include "../util.h"

const char *mic_perc(const char *card) {
  char cmd[128];
  char buf[64];
  FILE *fp;
  int vol;
  char muted[4];

  /* Get mute status */
  snprintf(cmd, sizeof(cmd), "pactl get-source-mute @DEFAULT_SOURCE@");
  fp = popen(cmd, "r");
  if (fp == NULL)
    return NULL;

  if (fgets(buf, sizeof(buf), fp) == NULL) {
    pclose(fp);
    return NULL;
  }
  pclose(fp);

  /* Check if muted */
  if (strstr(buf, "yes") != NULL) {
    return bprintf("Mute: yes");
  }

  /* Get volume percentage */
  snprintf(cmd, sizeof(cmd), "pactl get-source-volume @DEFAULT_SOURCE@");
  fp = popen(cmd, "r");
  if (fp == NULL)
    return NULL;

  if (fgets(buf, sizeof(buf), fp) == NULL) {
    pclose(fp);
    return NULL;
  }
  pclose(fp);

  /* Parse volume percentage */
  if (sscanf(buf, "%*s %*d / %d%%", &vol) != 1)
    return NULL;

  return bprintf("%d%% Mute: no", vol);
}
