from logging import Logger

from atribot.core.service_container import container
from atribot.LLMchat.skills.skills_manager import SkillsManager

tool_json = {
    "name": "load_skill_prompt",
    "description": "根据技能名称加载对应<available_skills>里面的skill提示词,或读取该技能目录下相对路径文本文件的内容。可以获取对应方面的补充技能说明、附加文档或脚本文本",
    "properties": {
        "skill_name": {
            "type": "string",
            "description": "要加载的skill里面的name"
        },
        "relative_path": {
            "type": "string",
            "description": "可选。要读取的技能目录下相对文件路径,例如`docs/readme.md`或`scripts/example.py`不填时默认读取该技能的skill.md提示词"
        }
    }
}

skills_manager: SkillsManager = container.get("SkillsManager")
log: Logger = container.get_by_type(Logger).getChild("SkillPrompt")


async def main(skill_name: str, relative_path: str = None) -> str:
    try:
        if relative_path:
            content = skills_manager.get_skill_relative_file_content(
                skill_name=skill_name,
                relative_path=relative_path,
                max_length=10000,#给1万字应该就好了吧
            )
        else:
            content = skills_manager.get_skill_md_prompt(skill_name)
    except ValueError as exc:
        log.warning(
            f"加载技能内容失败: skill_name={skill_name}, relative_path={relative_path}, error: {exc}"
        )
        return f"加载技能内容失败: {exc}"

    if relative_path:
        return f"已加载技能`{skill_name}`下文件`{relative_path}`的文本内容:\n\n{content}"

    return f"已加载技能`{skill_name}`的提示词:\n\n{content}"