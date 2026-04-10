/* See LICENSE file for copyright and license details.  */
#include <stdio.h>
#include <string.h>

#include "../slstatus.h"
#include "../util.h"

const char *mic_perc(const char *card) {
  char cmd[128];
  char buf[256];
  FILE *fp;
  int vol;
  char *ptr;

  (void)card; /* Suppress unused parameter warning */

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

  /* Parse volume percentage - find first '/' then skip spaces */
  ptr = strchr(buf, '/');
  if (ptr == NULL)
    return NULL;

  /* %d automatically skips leading whitespace */
  if (sscanf(ptr + 1, " %d%%", &vol) != 1)
    return NULL;

  return bprintf("%d%% Mute: no", vol);
}
