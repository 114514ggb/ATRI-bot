from atribot.core.service_container import container
from logging import Logger
from pathlib import Path
import html

from .parser import read_properties, find_skill_md
from .models import SkillProperties
from .validator import validate




class SkillsManager:
    """用于管理和加载 Agent 技能"""
    
    prompt: str
    """提示词缓存"""
    skills_dict: dict[str, SkillProperties]
    """skills的缓存字典, key: skill_name, value: SkillProperties对象"""
    
    def __init__(self, skill_dir=Path(__file__).parent / "agent_skills"):
        self.log:Logger = container.get("log")
        self.log.info("正在初始化SkillsManager!")
        self.skills_dict = {}
        self.prompt = ""
        self.initialize(skill_dir)

    def initialize(self, skill_dir: str):
        """加载一个目录下的skills
        
        流程:
        1. 遍历目录下的一级文件夹
        2. 调用 validate 验证
        3. 验证通过则调用 read_properties 读取
        4. 存入 skills_dict
        5. 生成 prompt
        """
        base_path = Path(skill_dir)
        self.skills_dict = {}

        if not base_path.exists() or not base_path.is_dir():
            return

        for item in base_path.iterdir():
            if item.is_dir() and not validate(item):
                try:
                    props = read_properties(item)
                
                    self.skills_dict[props.name] = props
                except Exception as e:
                    self.log.error(f"有agent_skills导入失败,{item}:{e}")
                    continue

        self.prompt = self.get_prompt()
        
        
    def get_prompt(self) -> str:
        """生成用于包含在代理提示词中的 <available_skills> XML 块。

        Returns:
            包含 <available_skills> 块的 XML 字符串，其中包含每个技能的
            名称、描述和位置。

        Example output:
            <available_skills>
            <skill>
            <name>pdf-reader</name>
            <description>读取并提取 PDF 文件的文本</description>
            </skill>
            </available_skills>
        """
        if not self.skills_dict:
            return "<available_skills>\n</available_skills>"

        lines = ["<available_skills>"]

        for props in self.skills_dict.values():

            lines.append("<skill>")
            lines.append("<name>")
            lines.append(html.escape(props.name))
            lines.append("</name>")
            lines.append("<description>")
            lines.append(html.escape(props.description))
            lines.append("</description>")

            # lines.append("<location>")
            # lines.append(str(props.path.resolve()))
            # lines.append("</location>")

            lines.append("</skill>")

        lines.append("</available_skills>")

        return "\n".join(lines)
    
    def get_skill_md_prompt(self, skill_name:str)->str:
        """获取一个skill内的完整提示词

        Args:
            skill_name (str): 名称

        Returns:
            str: 内容
        """
        skill = self.skills_dict.get(skill_name)
        
        if skill is None:
            raise ValueError(f"尝试获取了不存在的skill_key:{skill_name}")
        
        if skill_path := find_skill_md(skill_dir=skill.path):
            try:
                return skill_path.read_text(encoding='utf-8').split("---", 2)[2].strip()
            except Exception:
                raise ValueError(f"读取{skill_name}的skill.md时候文件内容不符合格式要求")
        else:
            raise ValueError(f"在获取{skill_name}的skill.md时候文件不存在")
    
    def get_skill_document_path(self, skill_name:str, relative_path:str)->Path:
        """
        获取指定技能文档的完整路径。
        
        根据技能名称从技能字典中查找对应的技能对象，并将技能的根路径
        与提供的相对路径拼接，返回完整的文件路径。
        
        Args:
            skill_name (str): 技能名称，用于在 skills_dict 中查找对应的技能对象
            relative_path (str): 相对于技能根目录的文件路径（如 "docs/readme.md"）
            
        Returns:
            Path: 拼接后的完整文件路径（pathlib.Path 对象）
            
        Raises:
            ValueError: 当指定的 skill_name 不存在于 skills_dict 中，
                    或当拼接后的文件路径不存在时抛出
                    
        Example:
            >>> path = get_skill_document_path("translation", "config.yaml")
            >>> print(path)
            PosixPath('/path/to/skills/translation/config.yaml')
        """
        skill = self.skills_dict.get(skill_name)
        
        if skill is None:
            raise ValueError(f"尝试获取了不存在的 skill_key: {skill_name}")
        
        path = skill.path / relative_path
        if path.exists():
            return path
        
        raise ValueError(f"技能 '{skill_name}' 中不存在文件路径: {relative_path}")
            