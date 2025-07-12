from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

import uuid
import smtplib
from email.utils import formataddr
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email import policy
from email.header import Header


class SendChinatelecomMailTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        # 一、首先读取插件的全局授权配置
        smtp_server = None
        smtp_port = None
        try:
            smtp_server = tool_parameters.get("smtp_server", "smtp.chinatelecom.cn").strip()
            smtp_port = int(tool_parameters.get("smtp_port", '465'))
        except KeyError:
            raise Exception("smtp_server 或 smtp_port 未配置或无效。请联系管理员，在插件授权中进行初始配置！")
        
        # 二、然后读取插件本身邮件发送相关的入参
        # 1、获取发件人相关信息
        sender_email = tool_parameters.get("sender_email", "").strip()
        password = tool_parameters.get("email_password", "").strip()
        sender_name = tool_parameters.get("sender_nickname", "").strip()
        if sender_email is None or len(sender_email) < 1:
            raise Exception('请输入发件人邮箱！形如：xxxx@chinatelecom.cn')
        elif "@chinatelecom.cn" not in sender_email: # 帮懒鬼自动拼上邮箱后缀。。。
            sender_email = sender_email + "@chinatelecom.cn"
        if password is None or len(password) < 3:
            raise Exception('请输入发件人邮箱的授权码！')
        if sender_name is None or len(sender_name) < 1:
            sender_name = sender_email.replace("@chinatelecom.cn","")
        
        # 2、获取发送对象相关信息（收件人、抄送人、密送人）
        recipients = tool_parameters.get("recipients", "").strip()
        recipients = get_mail_list_from_str(recipients)
        cc_recipients = tool_parameters.get("cc_recipients", "").strip()
        cc_recipients = get_mail_list_from_str(cc_recipients)
        bcc_recipients = tool_parameters.get("bcc_recipients", "").strip()
        bcc_recipients = get_mail_list_from_str(bcc_recipients)
        if recipients is None or len(recipients) < 1:
            raise Exception('请输入收件人邮箱！形如：xxxx@chinatelecom.cn')

        # 3、获取邮件主题和正文
        mail_subject = tool_parameters.get("mail_subject", "").strip()
        body = tool_parameters.get("mail_body", "").strip()
        if mail_subject is None or len(mail_subject) < 1 or body is None or len(body) < 1:
            raise Exception('对不起，邮件主题或邮件正文不能为空！')
        is_html = tool_parameters.get("is_html", "否")=='是'
        
        yield self.create_text_message("连接OA邮箱服务器中。。。\n")
        # 三、实际开始准备待发送的邮件对象！
        msg = None
        try:
            # 创建邮件对象时直接传入policy（兼容所有Python 3.6+）
            msg = MIMEMultipart('mixed', policy=policy.SMTP)
        except Exception as e:
            print("兼容写法报错，则尝试另一种msg创建写法！")
            msg = MIMEMultipart(_policy=policy.SMTP)

        msg["From"] = formataddr((sender_name, sender_email))
        msg["To"] = ", ".join(recipients)
        msg["Cc"] = ", ".join(cc_recipients)
        # msg["Bcc"] =... # 注意：密送（BCC）不添加到邮件头！最后再统一添加！
        msg["Subject"] = mail_subject
        # body = """
        # <h1>你好！</h1>
        # <p>这是一封来自Python的测试邮件。</p>
        # <p>支持多人、抄送、密送和附件功能。</p>
        # """
        if is_html:
            msg.attach(MIMEText(body, "html", "utf-8"))  # HTML炫酷模式！
        else:
            msg.attach(MIMEText(body, "plain", "utf-8"))  # 纯文本格式
        
        # 四、获取和设置 邮件发送附件
        send_files = tool_parameters.get("send_files", None)
        if send_files is not None and len(send_files) > 0:
            for send_file in send_files:
                content = None
                try:
                    # 至关重要的读取内容的命令！
                    # 这一行报错，则说明当前Dify平台的.env全局配置文件里，未设置FILES_URL，导致不同容器间无法共享文件流，该情况会导致灾难性后果，几乎所有文件读写类的第三方插件都会随之失效崩溃，Dify平台管理员请务必注意此项配置要无误！
                    content = send_file.blob
                    print('files.blob读取内容流 -> 成功! ')
                except Exception as e:
                    raise Exception("【严重错误】files.blob读取内容流 -> 直接失败！说明当前Dify平台根本不支持后台读取文件流！因此本插件完全无法正常运行！\n可能原因是：\n当前Dify平台的.env全局配置文件里，未设置FILES_URL，导致不同容器间无法共享文件流，该情况会导致灾难性后果，几乎所有文件读写类的第三方插件都会随之失效，并不只是影响本插件了。Dify平台管理员请务必注意此项配置要无误！\n解决办法：\n在.env全局配置文件里，设置：FILES_URL=http://dify服务器的内网IP\n")  
                file_name = '初始名字为空.png'
                try:
                    file_name = send_file.filename
                    print(f'成功解析到当前文件名：{file_name}')
                except Exception as e:
                    file_name = str(uuid.uuid4())+'_temp.bak'
                    yield self.create_text_message(f"当前待发送的附件，尝试获取文件名失败！自动生成随机名字: \n{file_name}\n")
                # 将读取到当前文件的内容流，写入邮件附件part对象里：
                part = MIMEBase("application", "octet-stream")
                part.set_payload(content)
                encoders.encode_base64(part)
                # 关键修改：统一使用Header编码文件名
                encoded_name = Header(file_name, 'utf-8').encode()
                # 规范附件头
                part.add_header("Content-Disposition","attachment",filename=encoded_name)
                # part.add_header("Content-Type", "application/octet-stream", name=encoded_name)
                msg.attach(part)
        
        # 五、实际发送
        try:
            # print("# 连接SMTP服务器并发送邮件")
            with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:  # 通常SSL端口是465
                server.login(sender_email, password)
            # with smtplib.SMTP(smtp_server, smtp_port) as server: # 不加密的通常端口是25
            #     server.login(sender_email, password)
                yield self.create_text_message("OA邮箱服务器连接成功！现在开始发送。。。\n")

                # print("# 最终开始发送邮件（关键：合并所有收件人）")
                all_recipients = recipients + cc_recipients + bcc_recipients
                server.send_message(msg, to_addrs=all_recipients)  # 使用 send_message 替代 sendmail
            print("最终，邮件发送成功！")
            yield self.create_text_message("本次邮件发送成功！\n")
        except Exception as e:
            raise Exception(f"本次邮件发送失败: \n{e}")


def get_mail_list_from_str(param):
    param = str(param)
    if param is not None and len(param) > 3 and "@" in param:
        param = param.replace("，",",").replace("；",",").replace(";",",").replace("|",",").replace("、",",").replace(" ","")
        return param.split(",")
    else:
        return []