/* 视图：终端（在 bot 所在主机执行命令）
   终端交互复用 components/term-core.js，本文件只做视图装配 */

import { terminalWsUrl } from '../api.js';
import { TERMINAL_HINT_HOST } from '../copy.js';
import { createTerminal } from '../components/term-core.js';

let term = null;

async function init(section) {
  term?.destroy();
  section.innerHTML = '<div class="term-mount"></div>';
  term = createTerminal(section.firstElementChild, {
    wsUrl: terminalWsUrl(),
    historyKey: 'atri_term_history',
    banner: (info) => [
      `ATRI 终端 · ${info.user}@${info.host} · ${info.platform || ''}`,
      TERMINAL_HINT_HOST,
    ],
  });
}

function destroy() {
  term?.destroy();
  term = null;
}

export const terminalView = { title: '终端', init, destroy };
