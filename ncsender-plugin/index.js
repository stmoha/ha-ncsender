/**
 * HA Switches - ncSender plugin entry for the Node-based platforms (v1 / pro-v1).
 *
 * On pro-v2 the manifest's clientOnly Tool Menu item opens config.html directly
 * and this file is not used. Everything happens in config.html, which runs in
 * the ncSender page and posts comment commands to /api/send-command.
 */
import { readFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

export async function onLoad(ctx) {
  ctx.registerToolMenu('HA Switches', async () => {
    const html = readFileSync(join(__dirname, 'config.html'), 'utf-8')
      .split('__TOOL_MENU_LABEL__').join('HA Switches');
    ctx.showDialog('HA Switches', html, { closable: true });
  });
}

export function onUnload() {}
