import base64
from zhipuai import ZhipuAI  

img_path = "E:\程序文件\python\ATRI\document\img\模型理解下载\图片.jpeg"
with open(img_path, 'rb') as img_file:
    img_base = base64.b64encode(img_file.read()).decode('utf-8')

client = ZhipuAI(api_key="fc57c8c15fe94a83a56aaa1f9401be6b.kALSJcRdCTn87TdO")  
response = client.chat.completions.create(  
    model="GLM-4V-Flash",  
    messages=[  
        {
            "role": "user",
            "content": [
                {"type": "image_url","image_url": {"url": img_base}},
                {"type": "text","text": "这上面有什么？"}
            ]  
        }
    ],  
)  
print(response.model_dump())  



# import requests

# def download_image_sync(url, img_path):
#     response = requests.get(url, stream=True)
#     if response.status_code == 200:
#         with open(img_path, 'wb') as img_file:
#             for chunk in response.iter_content(chunk_size=8192):
#                 img_file.write(chunk)
#         print(f"图片已保存到 {img_path}")
#     else:
#         print(f"无法下载图片，状态码: {response.status_code}")


# if __name__ == '__main__':
#     image_url = 'https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhQPbjlEL_PaZZ7G2L6X6M3jDOFofRiK7fQBIP8KKPbHhrKU34oDMgRwcm9kUIC9owFaEEJfZjwx2gnRHPhMtjQ-vrI&rkey=CAMSKLgthq-6lGU_B9Nnz7OIkewKak1tXoaEB4j2KcreJXz5KqW3COf7dSk'  
#     image_path = 'E:\程序文件\python\ATRI\document\img\模型理解下载\图片.jpeg"'          
#     download_image_sync(image_url, image_path)

