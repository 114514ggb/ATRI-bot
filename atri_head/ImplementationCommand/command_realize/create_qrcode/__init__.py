from atri_head.Basics import Basics,Command_information
from qrcode.image.styledpil import StyledPilImage
import qrcode



basics = Basics()

# content = "https://www.bilibili.com/"
file_path = "document/img/ATRI_qrcode/qrcode.png"
acquiesce_img = "document/img/ATRI_qrcode/qrcode_inset.png"



async def create_qrcode(argument,group_ID,data):
    
    content = ' '.join(argument[1])
    
    if len(content) > 400:
        raise Exception("输入内容过长")
    
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)

    img = qr.make_image(
        fill_color="black", 
        back_color="white", 
        image_factory=StyledPilImage,
        embeded_image_path=acquiesce_img
        )

    img.save(file_path)
    
    await basics.QQ_send_message.send_group_pictures(group_ID, "ATRI_qrcode/qrcode.png", default = True)


command_main = Command_information(
    name="qrcode",
    aliases=["二维码", "生成二维码","qrcode"],
    handler=create_qrcode,
    description="生成指定文本的二维码",
    parameter=[[0, 0], [1, 999]],
    authority_level=1, 
)