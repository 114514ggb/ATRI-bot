/* config.json 表单 schema：驱动配置编辑器的结构化表单
   字段说明整理自 assets/如何配置配置文件.md */

import { TOOL_SEARCH_BRIEF, TOOL_SEARCH_RULES } from './copy.js';

export const SCHEMA = [
  {
    id: 'platforms',
    label: '平台连接',
    icon: 'plug',
    type: 'platforms',
    path: 'platforms',
    desc: 'QQ 平台连接配置（napcat / OneBot 协议），可同时配置多个实例。',
    itemFields: [
      { key: 'adapter', label: '适配器类型', type: 'select', options: ['onebot'], desc: '目前只有 onebot' },
      { key: 'connection_type', label: '连接方式', type: 'select', options: ['WebSocket_client', 'WebSocket_server', 'http'], desc: 'client=主动连接 napcat；server=等 napcat 来连；http=HTTP 回调' },
      { key: 'access_token', label: '访问令牌', type: 'text', desc: '需与 napcat 侧配置一致' },
      { key: 'enabled', label: '启用该平台', type: 'toggle', desc: '关闭后该平台实例不会启动' },
      { key: 'source_name', label: '来源标识', type: 'text', optional: true, desc: '留空则取平台条目的 key' },
      { key: 'url', label: '连接地址', type: 'text', desc: 'WebSocket_client：napcat 的 WS 服务地址（如 127.0.0.1:8888）；http 模式为回调地址', conn: ['WebSocket_client', 'http'] },
      { key: 'host', label: '监听地址', type: 'text', desc: 'WebSocket_server / http 模式的监听地址', conn: ['WebSocket_server', 'http'] },
      { key: 'port', label: '监听端口', type: 'number', desc: 'WebSocket_server / http 模式的监听端口', conn: ['WebSocket_server', 'http'] },
    ],
  },
  {
    id: 'account',
    label: '账号信息',
    icon: 'bot',
    fields: [
      { path: 'root_user_id', label: 'Root QQ 号', type: 'number', desc: '最高权限用户，无视名单配置强制接收消息' },
      { path: 'account.id', label: 'Bot QQ 号', type: 'number', desc: '机器人自己的账号' },
      { path: 'account.name', label: 'Bot 名称', type: 'text', desc: '机器人账号名称' },
    ],
  },
  {
    id: 'model',
    label: '主聊天模型',
    icon: 'cloud',
    desc: '核心聊天模型的供应商与参数设置。',
    fields: [
      { path: 'model.connect.supplier', label: '供应商', type: 'supplier-select', desc: '对应供应商配置（supplier_config.json）中的 name' },
      { path: 'model.connect.model_name', label: '模型名称', type: 'model-select', depends: 'model.connect.supplier', desc: '对应供应商配置中 models 的 key' },
      { path: 'model.connect.user_global_context', label: '独立上下文', type: 'toggle', span: true, desc: '开启后群聊内每人使用独立上下文，关闭则全群共享' },
      { path: 'model.tavily_search_API_key', label: 'Tavily 搜索 Key', type: 'password', span: true, optional: true, desc: '联网搜索 API 密钥（免费）：docs.tavily.com' },
    ],
  },
  {
    id: 'chat-params',
    label: '聊天请求参数',
    icon: 'gauge',
    type: 'chat-params',
    path: 'model.chat_parameter',
    desc: '聊天请求携带的参数，键值对原样并入请求体；stream=true 走流式接口。',
  },
  {
    id: 'aux-models',
    label: '辅助模型',
    icon: 'layers',
    desc: '视觉/音频/视频描述、群聊摘要等辅助模型，未配置留空。',
    fields: [
      { path: 'model.detection_image.supplier', label: '视觉辅助 · 供应商', type: 'supplier-select', optional: true },
      { path: 'model.detection_image.model_name', label: '视觉辅助 · 模型', type: 'model-select', depends: 'model.detection_image.supplier', optional: true },
      { path: 'model.detection_audio.supplier', label: '音频辅助 · 供应商', type: 'supplier-select', optional: true },
      { path: 'model.detection_audio.model_name', label: '音频辅助 · 模型', type: 'model-select', depends: 'model.detection_audio.supplier', optional: true },
      { path: 'model.detection_video.supplier', label: '视频辅助 · 供应商', type: 'supplier-select', optional: true },
      { path: 'model.detection_video.model_name', label: '视频辅助 · 模型', type: 'model-select', depends: 'model.detection_video.supplier', optional: true },
      { path: 'model.memory.summarize_model.supplier', label: '群聊摘要 · 供应商', type: 'supplier-select', optional: true },
      { path: 'model.memory.summarize_model.model_name', label: '群聊摘要 · 模型', type: 'model-select', depends: 'model.memory.summarize_model.supplier', optional: true, desc: '总结群聊内容并存为模型记忆' },
      { path: 'model.agency_Agent.supplier', label: '子代理 · 供应商', type: 'supplier-select', optional: true },
      { path: 'model.agency_Agent.model_name', label: '子代理 · 模型', type: 'model-select', depends: 'model.agency_Agent.supplier', optional: true },
    ],
  },
  {
    id: 'standby',
    label: '备用模型链',
    icon: 'refresh',
    type: 'standby-list',
    path: 'model.standby_model',
    desc: '主模型失败后按顺序切换，备用模型使用内置通用参数。',
  },
  {
    id: 'rag',
    label: '记忆检索 RAG',
    icon: 'search',
    desc: '为模型提供记忆搜索支持的嵌入模型。',
    fields: [
      { path: 'model.RAG.enable', label: '启用 RAG', type: 'toggle' },
      { path: 'model.RAG.dimensions', label: '向量维度', type: 'number', desc: '嵌入模型的向量维度（如 1024）' },
      { path: 'model.RAG.use_embedding_model.supplier', label: '嵌入模型 · 供应商', type: 'supplier-select', optional: true },
      { path: 'model.RAG.use_embedding_model.model_name', label: '嵌入模型 · 模型', type: 'model-select', depends: 'model.RAG.use_embedding_model.supplier', optional: true, desc: '一般配置这一个就够了' },
      { path: 'model.RAG.use_reranker_model.supplier', label: '重排序 · 供应商', type: 'supplier-select', optional: true },
      { path: 'model.RAG.use_reranker_model.model_name', label: '重排序 · 模型', type: 'model-select', depends: 'model.RAG.use_reranker_model.supplier', optional: true, desc: '目前未启用' },
    ],
  },
  {
    id: 'ai_chat',
    label: '聊天行为',
    icon: 'message',
    desc: '人设与上下文窗口设置。',
    fields: [
      { path: 'ai_chat.playRole', label: '默认人设', type: 'persona-select', desc: '对应 character_setting 目录下的人设文件' },
      { path: 'ai_chat.ai_max_record', label: '上下文轮数', type: 'number', desc: '上下文保留的对话轮数（1 轮 = 用户 1 条 + AI 回复）' },
      { path: 'ai_chat.group_max_record', label: '群消息缓存', type: 'number', desc: '群消息缓存条数（作为 AI 上下文）' },
      { path: 'ai_chat.private_max_record', label: '私聊上下文轮数', type: 'number' },
    ],
  },
  {
    id: 'sandbox',
    label: '沙盒',
    icon: 'terminal',
    desc: 'LLM 执行代码/命令的沙盒；工具描述可追加定制，修改后点「刷新工具」立即生效。',
    fields: [
      { path: 'sand_box.type', label: '后端类型', type: 'select', options: ['docker', 'none', 'e2b'], desc: 'docker=容器隔离；none=本机直执行（无隔离，注意安全）；e2b=云端沙盒' },
      { path: 'sand_box.image', label: 'Docker 镜像', type: 'text', desc: '如 atri-sandbox:latest（仅 docker 后端使用）' },
      { path: 'sand_box.work_dir', label: '工作区目录', type: 'text', span: true, optional: true, desc: '本机直执行的工作目录，默认 document/work' },
      { path: 'sand_box.shell', label: 'Shell 程序', type: 'text', optional: true, desc: '本机直执行使用的 shell，留空自动探测' },
    ],
  },
  {
    id: 'tools',
    label: '工具预设',
    icon: 'sliders',
    type: 'tool-presets',
    desc: TOOL_SEARCH_BRIEF,
    help: TOOL_SEARCH_RULES,
  },
  {
    id: 'whitelist',
    label: '白名单',
    icon: 'check',
    desc: '消息处理的核心开关。输入 QQ 号/群号后回车添加。',
    fields: [
      { path: 'group_white_list', label: '群白名单', type: 'chips-int', span: true, desc: '只有名单内的群会接收并处理消息' },
      { path: 'group_initiative_chat_white_list', label: '主动聊天名单', type: 'chips-int', span: true, desc: '启用主动聊天的群，必须同时也在群白名单内' },
      { path: 'group_information_extraction', label: '群消息提取', type: 'chips-int', span: true, desc: '启用群消息提取入库（由群聊摘要模型处理）' },
      { path: 'private_chat_white_list', label: '私聊白名单', type: 'chips-int', span: true, desc: '允许触发 LLM 私聊的用户 QQ 号；root 可绕过' },
    ],
  },
  {
    id: 'database',
    label: '数据库',
    icon: 'memory',
    desc: 'PostgreSQL 连接信息。',
    fields: [
      { path: 'database.host', label: '地址', type: 'text' },
      { path: 'database.port', label: '端口', type: 'number' },
      { path: 'database.user', label: '用户名', type: 'text' },
      { path: 'database.password', label: '密码', type: 'password' },
      { path: 'database.database', label: '库名', type: 'text' },
    ],
  },
  {
    id: 'web_panel',
    label: '管理面板',
    icon: 'settings',
    desc: 'Web 管理面板的访问设置。',
    fields: [
      { path: 'web_panel.enable', label: '启用管理面板', type: 'toggle', desc: '关闭后重启 bot 将不再启动面板' },
      { path: 'web_panel.port', label: '面板端口', type: 'number', optional: true, desc: '默认 5125，修改后需重启 bot' },
      { path: 'web_panel.access_token', label: '面板访问令牌', type: 'password', span: true, optional: true, desc: '主令牌/登录口令：登录页用它换取会话令牌；未配置时接口全部返回 503，修改后全部会话失效' },
      { path: 'web_panel.session_ttl_hours', label: '会话有效期（小时）', type: 'number', optional: true, desc: '登录会话的固定有效期，默认 4（范围 1-24）；到期后 WebUI 自动退出登录' },
    ],
  },
];

/* 供应商配置（supplier_config.json）的模型能力字段 */
export const MODEL_SENSES = [
  { key: 'visual_sense', label: '视觉' },
  { key: 'audio_sense', label: '音频' },
  { key: 'video_sense', label: '视频' },
  { key: 'document_sense', label: '文档' },
];

/* 聊天请求参数（model.chat_parameter）中常见键的渲染定义。
   键值对本身是自由透传的，这里只负责给已知键更好的控件与说明；
   不在表中的键按「文本/数字/开关/JSON」通用行编辑。 */
export const CHAT_PARAM_DEFS = {
  temperature: { label: '采样温度', type: 'num', min: 0, max: 2, step: 0.05, desc: '值越低输出越稳定' },
  top_p: { label: 'Top P', type: 'num', min: 0, max: 1, step: 0.05 },
  max_tokens: { label: '最大 Token', type: 'num', min: 1, step: 256 },
  stream: { label: '流式输出', type: 'bool', desc: 'true 时走流式接口' },
  tool_choice: { label: '工具选择', type: 'select', options: ['auto', 'none', 'required'], optional: true },
  thinking_level: { label: '思考等级', type: 'select', options: ['minimal', 'low', 'medium', 'high'], optional: true },
  reasoning_effort: { label: '推理力度', type: 'select', options: ['minimal', 'low', 'medium', 'high'], optional: true },
  frequency_penalty: { label: '频率惩罚', type: 'num', min: -2, max: 2, step: 0.1 },
  presence_penalty: { label: '存在惩罚', type: 'num', min: -2, max: 2, step: 0.1 },
  response_format: { label: '响应格式', type: 'json', optional: true, desc: '如 {"type": "json_object"}' },
  stop: { label: '停止序列', type: 'json', optional: true, desc: '如 ["\n\n用户："]' },
};

/* 未知参数行的值类型选项 */
export const CHAT_PARAM_VALUE_TYPES = [
  { key: 'str', label: '文本' },
  { key: 'num', label: '数字' },
  { key: 'bool', label: '开关' },
  { key: 'json', label: 'JSON' },
];
