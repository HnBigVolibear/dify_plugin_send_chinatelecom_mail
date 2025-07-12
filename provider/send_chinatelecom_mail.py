from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class SendChinatelecomMailProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            smtp_server = credentials['smtp_server']
            smtp_port = credentials['smtp_port']
            print(f'成功读取到配置：{smtp_server} {smtp_port}')
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
