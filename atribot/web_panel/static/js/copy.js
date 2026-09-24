/* 公共文案常量：跨文件复用的界面说明统一在此维护
   仅存放纯常量，不 import 其他模块（避免循环依赖） */

/* ---------- tool_search / deferred 双列表机制 ---------- */

/* 摘要：配置页「工具预设」区块与聊天页工具弹窗的说明首行 */
export const TOOL_SEARCH_BRIEF =
  '默认组中的工具直接可用；待发现组不占上下文，由模型调用 tool_search 搜索后当轮临时启用。';

/* 完整规则：默认折叠的详情内容（保留全部约束） */
export const TOOL_SEARCH_RULES = `
  <ul>
    <li>待发现组（deferred）中的工具不出现在模型的工具列表里；模型须先调用默认组里的 <code>tool_search</code> 搜索到它，才会在当轮临时启用（仅当轮有效）。</li>
    <li>保存时校验两条硬性规则：默认组必须保留 <code>tool_search</code>，否则待发现列表无效；配置了 <code>tool_search</code> 就必须在待发现组中至少放一个工具。</li>
    <li>删除默认组中的 <code>tool_search</code> 且待发现组为空时，会自动切回单列表白名单模式。</li>
  </ul>`;

/* 折叠入口文案 */
export const TOOL_SEARCH_HELP_LABEL = '查看完整规则';

/* 「限制工具」开关的短说明 */
export const TOOL_RESTRICT_NOTE =
  '开启 = 白名单，只能用下方列出的工具；关闭 = 不限制，向模型暴露全部工具（保存为 <code>null</code>，不推荐）。';

/* ---------- 终端横幅 ---------- */

export const TERMINAL_HINT_HOST = '命令在 bot 所在主机执行 · Tab 补全 · ↑↓ 历史 · Ctrl+C 终止 · Ctrl+L 清屏';
export const TERMINAL_HINT_SANDBOX = '命令在沙盒环境内执行 · ↑↓ 历史 · Ctrl+C 终止 · Ctrl+L 清屏';

/* ---------- 停止服务确认框（顶栏菜单与仪表盘共用） ---------- */

export const STOP_SERVICE_CONFIRM = {
  title: '停止服务',
  message: '停止后 bot 完全下线，<b>需手动重新启动</b>。确定继续吗？',
};
