import html
from logging import Logger
from pathlib import Path
from typing import Optional

from atribot.core.atri_config import atriConfig
from atribot.core.service_container import ServiceBase, container

from .models import SkillProperties
from .parser import find_skill_md
from .validator import load_validated_properties


class SkillsManager(ServiceBase):
    """用于管理和加载 Agent 技能"""
    
    prompt: str
    """Skills提示词缓存"""
    skills_dict: dict[str, SkillProperties]
    """skills的缓存字典, key: skill_name, value: SkillProperties对象"""
    
    
    def __init__(self, skill_dir=Path(__file__).parent / "agent_skills"):
        self.log: Logger = container.get_by_type(Logger).getChild("Skills")
        self.log.info("正在初始化SkillsManager!")
        self.skills_dict = {}
        self.prompt = ""
        self.initialize_skills(skill_dir)

    @classmethod
    def factory(cls, config: atriConfig) -> "SkillsManager":
        return cls(skill_dir=config.file_path.agent_skills)

    def initialize_skills(self, skill_dir: str):
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
            if item.is_dir():
                try:
                    props = load_validated_properties(item)
                
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
            #因为不是命令行的ai给出路径也没有意义，里面要是有脚本什么的也运行不了要额外适配什么的

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
        获取指定技能文档的完整路径
        
        根据技能名称从技能字典中查找对应的技能对象，并将技能的根路径
        与提供的相对路径拼接，返回完整的文件路径
        
        Args:
            skill_name (str): 技能名称，用于在 skills_dict 中查找对应的技能对象
            relative_path (str): 相对于技能根目录的文件路径（如 "docs/readme.md")
            
        Returns:
            Path: 拼接后的完整文件路径(pathlib.Path 对象）
            
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
            raise ValueError(f"尝试获取了不存在的skill_key:{skill_name}")
        
        skill_root = skill.path.resolve()
        path = (skill.path / relative_path).resolve()

        if skill_root not in path.parents and path != skill_root:
            raise ValueError(f"技能'{skill_name}'的相对路径非法:{relative_path}")

        if path.exists():
            return path
        
        raise ValueError(f"技能'{skill_name}'中不存在文件路径:{relative_path}")

    def get_skill_relative_file_content(
        self,
        skill_name: str,
        relative_path: str,
        max_length: Optional[int] = None,
    ) -> str:
        """按文本格式读取技能目录下某个相对路径文件的内容。

        Args:
            skill_name (str): 技能名称。
            relative_path (str): 相对于技能根目录的文件路径。
            max_length (Optional[int], optional): 返回字符串最大长度，None 表示不截断。

        Returns:
            str: 读取到的文本内容。

        Raises:
            ValueError: 当技能不存在、路径非法、目标不是文件或读取失败时抛出。
        """
        path = self.get_skill_document_path(skill_name, relative_path)

        if not path.is_file():
            raise ValueError(f"技能'{skill_name}'中的路径不是文件:{relative_path}")

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise ValueError(f"技能'{skill_name}'中的文件不是有效的 UTF-8 文本: {relative_path}")
        except Exception as exc:
            raise ValueError(f"读取技能'{skill_name}'的文件失败:{relative_path},error: {exc}")

        if max_length is not None and len(content) > max_length:
            return content[:max_length]

        return content
            