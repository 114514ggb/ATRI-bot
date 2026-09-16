/* 零依赖 JSON 源码编辑器：textarea 叠加高亮层 + 行号 + 实时校验 */

import { escapeHtml } from '../ui.js';

function highlightJson(src) {
  const escaped = escapeHtml(src);
  return escaped.replace(
    /("(?:\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*"(?:\s*:)?|\b(?:true|false)\b|\bnull\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      let cls = 'jn';
      if (match.startsWith('"')) {
        cls = /:\s*$/.test(match) ? 'jk' : 'js';
      } else if (match === 'true' || match === 'false') {
        cls = 'jb';
      } else if (match === 'null') {
        cls = 'jx';
      }
      return `<span class="${cls}">${match}</span>`;
    }
  );
}

/**
 * 创建 JSON 编辑器
 * @returns {{getContent, isValid}}
 */
export function createJsonEditor(root, { content = '', onChange = null } = {}) {
  root.classList.add('json-editor');
  root.innerHTML = `
    <div class="json-editor-inner">
      <div class="json-gutter"></div>
      <div class="json-code-area">
        <pre class="json-highlight" aria-hidden="true"></pre>
        <textarea class="json-input" spellcheck="false" autocomplete="off"
          autocapitalize="off" wrap="off"></textarea>
      </div>
    </div>
    <div class="json-status"></div>`;

  const gutter = root.querySelector('.json-gutter');
  const highlight = root.querySelector('.json-highlight');
  const input = root.querySelector('.json-input');
  const status = root.querySelector('.json-status');

  let valid = true;

  function render() {
    const src = input.value;
    highlight.innerHTML = highlightJson(src) + '\n';

    const lines = src.split('\n').length;
    gutter.innerHTML = Array.from({ length: lines }, (_, i) => i + 1).join('<br>');

    try {
      JSON.parse(src);
      valid = true;
      status.className = 'json-status ok';
      status.textContent = `✓ 合法的 JSON · ${lines} 行`;
    } catch (e) {
      valid = false;
      const lineMatch = /position (\d+)/.exec(e.message);
      let extra = '';
      if (lineMatch) {
        const pos = Number(lineMatch[1]);
        extra = `（第 ${src.slice(0, pos).split('\n').length} 行附近）`;
      }
      status.className = 'json-status err';
      status.textContent = `✗ ${e.message} ${extra}`;
    }
    syncScroll();
  }

  function syncScroll() {
    highlight.scrollTop = input.scrollTop;
    highlight.scrollLeft = input.scrollLeft;
    gutter.scrollTop = input.scrollTop;
  }

  input.addEventListener('input', () => {
    render();
    if (onChange) onChange(input.value, valid);
  });

  input.addEventListener('scroll', syncScroll);

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const { selectionStart: s, selectionEnd: en } = input;
      input.value = input.value.slice(0, s) + '  ' + input.value.slice(en);
      input.selectionStart = input.selectionEnd = s + 2;
      render();
      if (onChange) onChange(input.value, valid);
    }
  });

  input.value = content;
  render();

  function setContent(src) {
    input.value = src;
    render();
    if (onChange) onChange(input.value, valid);
  }

  return {
    getContent: () => input.value,
    isValid: () => valid,
    setContent,
  };
}
